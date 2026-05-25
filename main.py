# -*- coding: utf-8 -*-
"""
ServerDock — FastAPI Backend

A lightweight local dashboard for managing multiple development servers.
Provides REST API for project CRUD, process start/stop, and log retrieval.
"""

import collections
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# =============================================================================
# Logging Configuration
# =============================================================================

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "server_manager.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("serverdock")

# =============================================================================
# Configuration
# =============================================================================

CONFIG_DIR = Path(__file__).parent / "config"
PROJECTS_FILE = CONFIG_DIR / "projects.json"
RUNNING_FILE = CONFIG_DIR / "running.json"  # Persisted runtime state
MANAGER_PORT = 9001
LOG_BUFFER_SIZE = 100
IS_WINDOWS = sys.platform.startswith("win")

# fnm (Fast Node Manager) — detect Node.js installation dynamically
def _detect_fnm_node_path() -> Optional[Path]:
    """Find the latest fnm-managed Node.js installation."""
    candidate_dirs = []
    if IS_WINDOWS:
        candidate_dirs.append(Path.home() / "AppData/Roaming/fnm/node-versions")
    else:
        candidate_dirs.extend([
            Path.home() / "Library/Application Support/fnm/node-versions",
            Path.home() / ".local/share/fnm/node-versions",
        ])

    node_executable = "node.exe" if IS_WINDOWS else "bin/node"
    for fnm_versions_dir in candidate_dirs:
        if not fnm_versions_dir.exists():
            continue
        # Sort version directories descending so we pick the latest
        for version_dir in sorted(fnm_versions_dir.iterdir(), reverse=True):
            installation = version_dir / "installation"
            if installation.exists() and (installation / node_executable).exists():
                return installation if IS_WINDOWS else installation / "bin"
    return None

FNM_NODE_PATH = _detect_fnm_node_path()

# =============================================================================
# Data Models
# =============================================================================

class ProjectCreate(BaseModel):
    """Request model for creating a new project."""
    name: str
    directory: str
    start_command: Optional[str] = None
    start_commands: Optional[list[str]] = None
    port: int
    url: Optional[str] = None  # Optional URL for "Open in Browser"

class ProjectUpdate(BaseModel):
    """Request model for updating a project."""
    name: Optional[str] = None
    directory: Optional[str] = None
    start_command: Optional[str] = None
    start_commands: Optional[list[str]] = None
    port: Optional[int] = None
    url: Optional[str] = None

class Project(BaseModel):
    """Full project model with all fields."""
    id: str
    name: str
    directory: str
    start_command: Optional[str] = None
    start_commands: Optional[list[str]] = None
    port: int
    created_at: str
    url: Optional[str] = None

# =============================================================================
# Runtime State
# =============================================================================

# Tracks running processes started by this manager
# Key: project_id, Value: dict with process, pid, started_at, logs, log_thread
# Note: 'process' and 'log_thread' are runtime-only, not persisted
running_processes: dict = {}

# Lock for thread-safe access to running_processes
# This prevents race conditions when multiple requests access/modify the dict
running_processes_lock = threading.Lock()

# =============================================================================
# Persistence Layer
# =============================================================================

def load_projects() -> list[dict]:
    """Load projects from JSON file."""
    if not PROJECTS_FILE.exists():
        return []
    with open(PROJECTS_FILE, "r") as f:
        data = json.load(f)
    return data.get("projects", [])

def save_projects(projects: list[dict]) -> None:
    """Save projects to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROJECTS_FILE, "w") as f:
        json.dump({"projects": projects}, f, indent=2)

def load_running_state() -> dict:
    """Load persisted running state (PIDs) from disk."""
    if not RUNNING_FILE.exists():
        return {}
    try:
        with open(RUNNING_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_running_state() -> None:
    """Persist running state (PIDs, log file paths) to disk. Thread-safe."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Only save the serializable parts (pid, started_at, log_file_path)
    # Take a snapshot while holding the lock to avoid iteration issues
    with running_processes_lock:
        state = {
            project_id: {
                "pid": info.get("pid"),
                "pids": info.get("pids") or [info.get("pid")],
                "started_at": info["started_at"],
                "log_file_path": info.get("log_file_path", ""),
                "log_file_paths": info.get("log_file_paths") or [info.get("log_file_path", "")],
            }
            for project_id, info in running_processes.items()
        }
    try:
        with open(RUNNING_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save running state: {e}")

def restore_running_state() -> None:
    """
    On startup, restore running_processes from persisted state.
    Only restores entries where the PID is still alive.
    Also restores log streaming from log files.
    """
    saved_state = load_running_state()
    restored_count = 0
    processes_to_restore = []

    # First pass: identify which processes are still alive
    for project_id, info in saved_state.items():
        pids = info.get("pids") or [info.get("pid")]
        live_pids = [pid for pid in pids if pid and is_process_running(pid)]
        if live_pids:
            info["pids"] = live_pids
            info["pid"] = live_pids[0]
            processes_to_restore.append((project_id, info))
            logger.info(f"Restored running process for project {project_id} (PIDs: {live_pids})")
        else:
            logger.info(f"Discarded stale process entry for project {project_id} (PIDs: {pids})")

    # Second pass: restore processes and start log streaming threads
    for project_id, info in processes_to_restore:
        log_buffer = collections.deque(maxlen=LOG_BUFFER_SIZE)
        log_file_paths = [path for path in (info.get("log_file_paths") or [info.get("log_file_path", "")]) if path]
        log_file_path = log_file_paths[0] if log_file_paths else ""

        # Start log streaming thread if log file exists
        log_threads = []
        for path in log_file_paths:
            if path and Path(path).exists():
                log_thread = threading.Thread(
                    target=stream_logs_from_file,
                    args=(Path(path), log_buffer, project_id, True),  # start_from_end=True
                    daemon=True,
                    name=f"log-stream-{project_id}"
                )
                log_thread.start()
                log_threads.append(log_thread)

        with running_processes_lock:
            running_processes[project_id] = {
                "process": None,  # We don't have the Popen object
                "processes": [],
                "pid": info.get("pid"),
                "pids": info.get("pids") or [info.get("pid")],
                "started_at": info.get("started_at", ""),
                "logs": log_buffer,
                "log_thread": log_threads[0] if log_threads else None,
                "log_threads": log_threads,
                "log_file": None,  # File was opened by the previous run
                "log_files": [],
                "log_file_path": log_file_path,
                "log_file_paths": log_file_paths,
            }
        restored_count += 1

    logger.info(f"Restored {restored_count} running process(es) from saved state")
    # Clean up the persisted file to match actual state
    save_running_state()

def get_project_by_id(project_id: str) -> Optional[dict]:
    """Find a project by its ID."""
    projects = load_projects()
    for project in projects:
        if project["id"] == project_id:
            return project
    return None


def normalize_start_commands(project: dict) -> list[str]:
    """Return the non-empty commands configured for a project."""
    commands = project.get("start_commands")
    if isinstance(commands, list):
        cleaned = [str(command).strip() for command in commands if str(command).strip()]
        if cleaned:
            return cleaned

    command = (project.get("start_command") or "").strip()
    if not command:
        return []
    return [line.strip() for line in command.splitlines() if line.strip()]


def command_text(commands: list[str]) -> str:
    """Convert command list to the legacy text representation."""
    return "\n".join(commands)


def normalize_project_payload(project_data: dict) -> dict:
    """Keep start_command and start_commands in sync for older configs/frontends."""
    commands = normalize_start_commands(project_data)
    if not commands:
        raise HTTPException(status_code=400, detail="At least one start command is required")
    project_data["start_commands"] = commands
    project_data["start_command"] = command_text(commands)
    return project_data


def model_to_dict(model: BaseModel) -> dict:
    """Convert Pydantic v1/v2 models without deprecation warnings."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def model_set_fields(model: BaseModel) -> set[str]:
    """Return fields explicitly provided by the client for Pydantic v1/v2."""
    if hasattr(model, "model_fields_set"):
        return model.model_fields_set
    return getattr(model, "__fields_set__", set())


def prepare_shell_command(command: str, project_dir: Path) -> str:
    """Expand relative executable paths while preserving normal shell commands."""
    first_word = command.split()[0] if command else ""
    if not first_word:
        return command

    has_path_separator = "/" in first_word or "\\" in first_word
    is_windows_absolute = len(first_word) > 1 and first_word[1] == ":"
    is_absolute = Path(first_word).is_absolute() or is_windows_absolute
    if has_path_separator and not is_absolute:
        absolute_path = project_dir / first_word
        command = str(absolute_path) + command[len(first_word):]
        logger.debug(f"Expanded relative path: {first_word} -> {absolute_path}")

    return command

# =============================================================================
# Port & Process Utilities
# =============================================================================

def is_port_in_use(port: int) -> bool:
    """Check if a port is currently in use. Handles socket errors gracefully."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)  # 100ms timeout - closed ports respond quickly
            return s.connect_ex(("127.0.0.1", port)) == 0
    except (OSError, socket.error) as e:
        # Socket creation or operation failed - assume port is not in use
        # but log the error for debugging
        logger.warning(f"Socket error checking port {port}: {e}")
        return False


def get_process_using_port(port: int) -> Optional[psutil.Process]:
    """Find the process that is listening on a given port."""
    logger.info(f"[PORT LOOKUP] Searching for process on port {port}")

    # First try psutil (faster, but may not have PID on Windows without admin)
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                logger.info(f"[PORT LOOKUP] psutil found port {port}, pid={conn.pid}")
                if conn.pid is not None:
                    try:
                        return psutil.Process(conn.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.warning(f"[PORT LOOKUP] psutil process lookup failed for PID {conn.pid}: {e}")
    except psutil.AccessDenied:
        logger.warning(f"[PORT LOOKUP] psutil.net_connections access denied for port {port}")

    # Fallback: use OS-native tools when psutil cannot expose the PID.
    pid = get_pid_on_port(port)
    if pid:
        try:
            return psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"[PORT LOOKUP] Failed to get process {pid}: {e}")

    logger.warning(f"[PORT LOOKUP] Could not find process for port {port}")
    return None


def kill_process_tree(pid: int) -> dict:
    """
    Kill a process and all its children (tree kill).

    Returns:
        Dict with 'killed' (list of PIDs) and 'failed' (list of PIDs)
    """
    killed = []
    failed = []

    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        if not IS_WINDOWS:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                failed.append(pid)
                logger.error(f"Access denied terminating process group {pid}")
            except Exception as e:
                logger.debug(f"Process group terminate failed for {pid}: {e}")

        # Terminate children first, then parent
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass

        # Wait briefly for graceful shutdown
        all_procs = [parent] + children
        gone, alive = psutil.wait_procs(all_procs, timeout=3)

        for p in gone:
            killed.append(p.pid)

        # Force kill any survivors
        for p in alive:
            try:
                if not IS_WINDOWS and p.pid == pid:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except Exception:
                        pass
                p.kill()
                killed.append(p.pid)
                logger.warning(f"Force killed process {p.pid}")
            except psutil.NoSuchProcess:
                killed.append(p.pid)  # Already dead
            except psutil.AccessDenied:
                failed.append(p.pid)
                logger.error(f"Access denied killing process {p.pid}")

    except psutil.NoSuchProcess:
        logger.info(f"Process {pid} already terminated")
    except psutil.AccessDenied:
        failed.append(pid)
        logger.error(f"Access denied terminating process {pid}")

    return {"killed": killed, "failed": failed}

def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

def get_project_status(project: dict) -> str:
    """
    Determine the display status of a project. Thread-safe.

    Returns:
        "running" - We started it and it's running
        "external" - Port is in use by something we didn't start
        "stopped" - Not running
    """
    project_id = project["id"]
    port = project["port"]

    # Check if we have a tracked process for this project
    with running_processes_lock:
        if project_id in running_processes:
            process_info = running_processes[project_id]
            pids = process_info.get("pids") or [process_info.get("pid")]
            live_pids = [pid for pid in pids if pid and is_process_running(pid)]
            if live_pids:
                return "running"
            else:
                # Process died, clean up our tracking
                del running_processes[project_id]
                logger.info(f"Cleaned up dead processes for project {project_id} (PIDs: {pids})")

    # Check if port is in use by something external
    if is_port_in_use(port):
        return "external"

    return "stopped"

# =============================================================================
# Log Streaming
# =============================================================================

def stream_logs_from_file(
    log_file_path: Path,
    log_buffer: collections.deque,
    project_id: str,
    start_from_end: bool = False
) -> None:
    """
    Background thread function to tail a log file and buffer lines.
    Runs until the project is stopped (checks if project is still in running_processes).

    Args:
        log_file_path: Path to the log file to tail
        log_buffer: Deque to append log lines to
        project_id: Project ID for logging purposes
        start_from_end: If True, seek to end of file first (for restored processes)
    """
    import time

    try:
        # Wait for log file to exist
        wait_count = 0
        while not log_file_path.exists() and wait_count < 50:  # 5 second timeout
            time.sleep(0.1)
            wait_count += 1

        if not log_file_path.exists():
            logger.warning(f"Log file not created for project {project_id}")
            return

        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
            if start_from_end:
                # For restored processes, read the last N lines first then tail
                # Read entire file to get last LOG_BUFFER_SIZE lines
                f.seek(0)
                all_lines = f.readlines()
                recent_lines = all_lines[-LOG_BUFFER_SIZE:] if len(all_lines) > LOG_BUFFER_SIZE else all_lines
                for line in recent_lines:
                    log_buffer.append(line.rstrip())
                # Now positioned at end of file for tailing

            while True:
                # Check if project is still running
                with running_processes_lock:
                    if project_id not in running_processes:
                        logger.debug(f"Log streaming stopped - project {project_id} no longer running")
                        break

                # Read any new lines
                line = f.readline()
                if line:
                    log_buffer.append(line.rstrip())
                else:
                    # No new data, wait a bit before checking again
                    time.sleep(0.1)

        logger.debug(f"Log streaming ended for project {project_id}")

    except Exception as e:
        logger.error(f"Error streaming logs for project {project_id}: {type(e).__name__}: {e}")

# =============================================================================
# Process Management
# =============================================================================

def start_project_process(project: dict) -> dict:
    """
    Start the server process for a project. Thread-safe.

    Returns:
        Dict with pid and started_at on success

    Raises:
        HTTPException on failure
    """
    project_id = project["id"]
    project_name = project.get("name", project_id)
    commands = normalize_start_commands(project)
    if not commands:
        raise HTTPException(status_code=400, detail="At least one start command is required")

    # Check if already running (thread-safe)
    with running_processes_lock:
        if project_id in running_processes:
            process_info = running_processes[project_id]
            pids = process_info.get("pids") or [process_info.get("pid")]
            if any(pid and is_process_running(pid) for pid in pids):
                raise HTTPException(status_code=400, detail="Project is already running")
            else:
                # Clean up stale entry
                del running_processes[project_id]
                logger.info(f"Cleaned up stale entry for project {project_name}")

    # Check if port is already in use
    if is_port_in_use(project["port"]):
        raise HTTPException(
            status_code=400,
            detail=f"Port {project['port']} is already in use"
        )

    # Validate directory exists
    project_dir = Path(project["directory"])
    if not project_dir.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist: {project['directory']}"
        )

    try:
        # shell=True handles commands like npm scripts and user-defined shell snippets.
        # Each command gets a platform process group/session so stop can clean the tree.

        # Build environment with fnm node path for npm commands
        env = os.environ.copy()
        if FNM_NODE_PATH and FNM_NODE_PATH.exists():
            env["PATH"] = str(FNM_NODE_PATH) + os.pathsep + env.get("PATH", "")

        logger.info(f"Starting project {project_name}: {len(commands)} command(s)")

        creation_flags = 0
        popen_kwargs = {}
        if IS_WINDOWS:
            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP |
                subprocess.CREATE_BREAKAWAY_FROM_JOB |
                subprocess.CREATE_NO_WINDOW
            )
            popen_kwargs["creationflags"] = creation_flags
        else:
            # New session gives every command its own process group for clean tree stops.
            popen_kwargs["start_new_session"] = True

        project_log_dir = LOG_DIR / "projects"
        project_log_dir.mkdir(parents=True, exist_ok=True)
        project_dir = Path(project["directory"])
        log_buffer = collections.deque(maxlen=LOG_BUFFER_SIZE)
        processes = []
        log_files = []
        log_file_paths = []
        log_threads = []

        try:
            for index, command in enumerate(commands, start=1):
                start_command = prepare_shell_command(command, project_dir)
                log_file_path = project_log_dir / f"{project_id}-{index}.log"
                log_file = open(log_file_path, "w", encoding="utf-8")
                log_files.append(log_file)
                log_file_paths.append(str(log_file_path))
                log_file.write(f"$ {command}\n")
                log_file.flush()

                process = subprocess.Popen(
                    start_command,
                    shell=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(project_dir),
                    env=env,
                    **popen_kwargs,
                )
                processes.append(process)
                logger.info(f"Started command {index}/{len(commands)} for {project_name} with PID {process.pid}")

                log_thread = threading.Thread(
                    target=stream_logs_from_file,
                    args=(log_file_path, log_buffer, project_id),
                    daemon=True,
                    name=f"log-stream-{project_id}-{index}"
                )
                log_thread.start()
                log_threads.append(log_thread)
        except Exception:
            for process in processes:
                try:
                    kill_process_tree(process.pid)
                except Exception:
                    logger.exception(f"Failed to clean up partially started PID {process.pid}")
            for log_file in log_files:
                try:
                    log_file.close()
                except Exception:
                    pass
            raise

        started_at = datetime.utcnow().isoformat() + "Z"
        pids = [process.pid for process in processes]

        # Track the running process (thread-safe)
        with running_processes_lock:
            running_processes[project_id] = {
                "process": processes[0],
                "processes": processes,
                "pid": pids[0],
                "pids": pids,
                "started_at": started_at,
                "logs": log_buffer,
                "log_thread": log_threads[0] if log_threads else None,
                "log_threads": log_threads,
                "log_file": log_files[0] if log_files else None,
                "log_files": log_files,
                "log_file_path": log_file_paths[0] if log_file_paths else "",
                "log_file_paths": log_file_paths,
                "commands": commands,
            }

        # Persist running state to survive manager restarts
        save_running_state()

        logger.info(f"Started project {project_name} with PIDs {pids}")
        return {"pid": pids[0], "pids": pids, "started_at": started_at}

    except Exception as e:
        logger.error(f"Failed to start project {project_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start process: {str(e)}")

def stop_project_process(project_id: str) -> None:
    """
    Stop the server process for a project. Thread-safe.

    Terminates the process and all its children, then cleans up resources.

    Raises:
        HTTPException if project is not running
    """
    # Get process info while holding lock
    with running_processes_lock:
        if project_id not in running_processes:
            raise HTTPException(status_code=400, detail="Project is not running")
        process_info = running_processes[project_id]
        pids = process_info.get("pids") or [process_info.get("pid")]
        processes = process_info.get("processes") or [process_info.get("process")]
        log_files = process_info.get("log_files") or [process_info.get("log_file")]

    logger.info(f"Stopping project {project_id} (PIDs: {pids})")

    for pid in pids:
        if not pid:
            continue
        kill_process_tree(pid)

    # Clean up the Popen object to release resources
    for process_obj in [process for process in processes if process is not None]:
        try:
            process_obj.wait(timeout=1)  # Reap the zombie process
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            logger.warning(f"Error waiting for process cleanup: {e}")

    # Close the log file handles
    for log_file in [handle for handle in log_files if handle is not None]:
        try:
            log_file.close()
        except Exception as e:
            logger.warning(f"Error closing log file for project {project_id}: {e}")

    # Clean up tracking (thread-safe)
    with running_processes_lock:
        if project_id in running_processes:
            del running_processes[project_id]

    # Persist updated running state
    save_running_state()
    logger.info(f"Stopped project {project_id}")

# =============================================================================
# FastAPI Application
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Restore running state on startup."""
    logger.info("ServerDock starting up...")
    restore_running_state()
    logger.info(f"ServerDock ready on port {MANAGER_PORT}")
    yield


app = FastAPI(title="ServerDock", version="1.0.0", lifespan=lifespan)

# -----------------------------------------------------------------------------
# Static Files
# -----------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1><p>index.html is missing</p>")
    return FileResponse(html_path, media_type="text/html")

# -----------------------------------------------------------------------------
# Project CRUD
# -----------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects():
    """
    List all projects with their current status. Thread-safe.

    Returns list of projects, each with an added 'status' field.
    """
    projects = load_projects()
    result = []
    for project in projects:
        project_with_status = project.copy()
        project_with_status["status"] = get_project_status(project)

        # Include started_at if running (thread-safe access)
        with running_processes_lock:
            if project["id"] in running_processes:
                project_with_status["started_at"] = running_processes[project["id"]]["started_at"]

        result.append(project_with_status)
    return result

@app.post("/api/projects")
async def create_project(project: ProjectCreate):
    """Create a new project configuration."""
    projects = load_projects()
    project_data = normalize_project_payload(model_to_dict(project))

    # Generate unique ID
    new_id = uuid.uuid4().hex[:8]

    new_project = {
        "id": new_id,
        "name": project_data["name"],
        "directory": project_data["directory"],
        "start_command": project_data["start_command"],
        "start_commands": project_data["start_commands"],
        "port": project_data["port"],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    if project_data.get("url"):
        new_project["url"] = project_data["url"]

    projects.append(new_project)
    save_projects(projects)

    return new_project

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, update: ProjectUpdate):
    """Update an existing project configuration."""
    projects = load_projects()

    for i, project in enumerate(projects):
        if project["id"] == project_id:
            # Apply updates
            set_fields = model_set_fields(update)
            update_data = {key: value for key, value in model_to_dict(update).items() if key in set_fields}
            if update.name is not None:
                project["name"] = update.name
            if update.directory is not None:
                project["directory"] = update.directory
            if "start_command" in update_data or "start_commands" in update_data:
                command_data = normalize_project_payload({**project, **update_data})
                project["start_command"] = command_data["start_command"]
                project["start_commands"] = command_data["start_commands"]
            if update.port is not None:
                project["port"] = update.port
            if update.url is not None:
                project["url"] = update.url

            projects[i] = project
            save_projects(projects)
            return project

    raise HTTPException(status_code=404, detail="Project not found")

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project configuration. Thread-safe."""
    projects = load_projects()

    # Stop the project if running (thread-safe check)
    with running_processes_lock:
        is_running = project_id in running_processes

    if is_running:
        stop_project_process(project_id)
        logger.info(f"Stopped running project {project_id} before deletion")

    # Remove from list
    new_projects = [p for p in projects if p["id"] != project_id]

    if len(new_projects) == len(projects):
        raise HTTPException(status_code=404, detail="Project not found")

    save_projects(new_projects)
    logger.info(f"Deleted project {project_id}")
    return {"status": "deleted"}

# -----------------------------------------------------------------------------
# Process Control
# -----------------------------------------------------------------------------

@app.post("/api/projects/{project_id}/start")
async def start_project(project_id: str):
    """Start the server for a project."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = start_project_process(project)
    return {"status": "started", **result}

@app.post("/api/projects/{project_id}/stop")
async def stop_project(project_id: str):
    """Stop the server for a project."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stop_project_process(project_id)
    return {"status": "stopped"}

@app.post("/api/projects/{project_id}/restart")
async def restart_project(project_id: str):
    """Restart the server for a project (stop then start)."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Stop if running (ignore error if not running)
    with running_processes_lock:
        is_running = project_id in running_processes

    if is_running:
        stop_project_process(project_id)

    # Start fresh
    result = start_project_process(project)
    logger.info(f"Restarted project {project.get('name', project_id)}")
    return {"status": "restarted", **result}

# -----------------------------------------------------------------------------
# Port Management
# -----------------------------------------------------------------------------

def get_pid_on_port(port: int) -> Optional[int]:
    """
    Get the PID listening on a port using the best available platform command.
    Returns just the PID, not a psutil.Process (which may fail for zombie PIDs).
    """
    if not IS_WINDOWS:
        try:
            result = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line)
        except FileNotFoundError:
            logger.warning("lsof is not available for port lookup")
        except Exception as e:
            logger.warning(f"lsof port lookup failed for {port}: {e}")
        return None

    try:
        result = subprocess.run(
            "netstat -ano",
            capture_output=True,
            text=True,
            timeout=5,
            shell=True,
        )
        for line in result.stdout.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    if local_addr.endswith(f":{port}"):
                        return int(parts[-1])
    except Exception as e:
        logger.warning(f"get_pid_on_port failed for {port}: {e}")
    return None


def force_kill_pid(pid: int) -> dict:
    """
    Force kill a PID using multiple methods.
    Returns dict with 'success' and 'method' used.
    """
    # Method 1: psutil (preferred - handles process tree)
    try:
        result = kill_process_tree(pid)
        if result["killed"] and not result["failed"]:
            return {"success": True, "method": "psutil", "details": result}
    except Exception as e:
        logger.warning(f"psutil kill failed for PID {pid}: {e}")

    if not IS_WINDOWS:
        try:
            os.kill(pid, signal.SIGKILL)
            return {"success": True, "method": "kill", "details": f"Sent SIGKILL to {pid}"}
        except ProcessLookupError:
            return {"success": True, "method": "kill", "details": f"PID {pid} already exited"}
        except Exception as e:
            logger.warning(f"kill fallback failed for PID {pid}: {e}")
            return {"success": False, "method": None, "details": "All kill methods failed"}

    # Method 2: taskkill via cmd (handles some cases psutil can't)
    try:
        result = subprocess.run(
            f'taskkill /PID {pid} /F /T',
            capture_output=True,
            text=True,
            timeout=10,
            shell=True,
        )
        if result.returncode == 0:
            return {"success": True, "method": "taskkill", "details": result.stdout}
        else:
            logger.warning(f"taskkill failed for PID {pid}: {result.stderr}")
    except Exception as e:
        logger.warning(f"taskkill exception for PID {pid}: {e}")

    # Method 3: PowerShell Stop-Process (another fallback)
    try:
        result = subprocess.run(
            f'powershell -Command "Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"',
            capture_output=True,
            text=True,
            timeout=10,
            shell=True,
        )
        # PowerShell might succeed even with non-zero return
        if "Cannot find a process" not in result.stderr:
            return {"success": True, "method": "powershell", "details": result.stdout}
    except Exception as e:
        logger.warning(f"PowerShell kill failed for PID {pid}: {e}")

    return {"success": False, "method": None, "details": "All kill methods failed"}


@app.post("/api/ports/{port}/kill")
async def kill_port(port: int):
    """
    Kill whatever process is using a port (tree kill).

    This is useful for cleaning up orphaned processes that weren't started
    by this manager, or processes whose parent was killed but children survived.

    Returns:
        Dict with status, killed PIDs, and any failures
    """
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port number")

    # First check if this port is managed by us
    projects = load_projects()
    for project in projects:
        if project["port"] == port:
            with running_processes_lock:
                if project["id"] in running_processes:
                    # Use our normal stop which has better cleanup
                    pids = running_processes[project["id"]].get("pids") or [running_processes[project["id"]].get("pid")]
                    stop_project_process(project["id"])
                    logger.info(f"Stopped managed project on port {port}")
                    return {
                        "status": "stopped",
                        "message": f"Stopped managed project: {project['name']}",
                        "killed": pids,
                        "failed": []
                    }

    # Try to find and kill the process using this port
    process = get_process_using_port(port)
    if process:
        pid = process.pid
        try:
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"

        logger.info(f"Killing process tree on port {port}: PID {pid} ({process_name})")
        result = kill_process_tree(pid)

        if result["failed"]:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to kill some processes: {result['failed']}. May need elevated permissions."
            )

        return {
            "status": "killed",
            "message": f"Killed process {pid} ({process_name}) and {len(result['killed']) - 1} children",
            "killed": result["killed"],
            "failed": result["failed"]
        }

    # psutil couldn't find the process - try direct PID lookup and kill
    pid = get_pid_on_port(port)
    if pid:
        logger.info(f"Attempting force kill of PID {pid} on port {port} (psutil couldn't access it)")
        kill_result = force_kill_pid(pid)

        if kill_result["success"]:
            # Verify the port is now free
            import time
            time.sleep(0.5)  # Brief wait for OS to release port
            if not is_port_in_use(port):
                return {
                    "status": "killed",
                    "message": f"Killed PID {pid} via {kill_result['method']}",
                    "killed": [pid],
                    "failed": []
                }
            else:
                # Port still in use - likely a zombie socket
                raise HTTPException(
                    status_code=500,
                    detail=f"Killed PID {pid} but port {port} is still in use. This is a zombie socket - it will clear on its own or after a system restart."
                )
        else:
            # All kill methods failed - this is a zombie/phantom process
            raise HTTPException(
                status_code=500,
                detail=f"Port {port} is held by PID {pid} which cannot be killed (zombie process). The port will clear on its own or after a system restart."
            )

    # No PID found at all
    if is_port_in_use(port):
        raise HTTPException(
            status_code=500,
            detail=f"Port {port} is in use but no process could be identified. May need elevated permissions or system restart."
        )

    return {"status": "not_in_use", "message": f"Port {port} is not in use", "killed": [], "failed": []}


@app.get("/api/ports/{port}/info")
async def get_port_info(port: int):
    """
    Get information about what's using a port.

    Returns process details if port is in use.
    """
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port number")

    if not is_port_in_use(port):
        return {"in_use": False, "port": port}

    process = get_process_using_port(port)
    if not process:
        return {
            "in_use": True,
            "port": port,
            "process": None,
            "message": "Port in use but could not identify process"
        }

    try:
        children = process.children(recursive=True)
        return {
            "in_use": True,
            "port": port,
            "process": {
                "pid": process.pid,
                "name": process.name(),
                "cmdline": " ".join(process.cmdline()[:5]),  # First 5 args
                "children_count": len(children)
            }
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return {
            "in_use": True,
            "port": port,
            "process": {"pid": process.pid},
            "error": str(e)
        }

# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------

@app.get("/api/projects/{project_id}/logs")
async def get_project_logs(project_id: str, lines: int = 100):
    """
    Get recent log lines for a running project. Thread-safe.

    Args:
        project_id: The project ID
        lines: Maximum number of lines to return (default 100)

    Returns:
        List of log lines (most recent last)
    """
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Thread-safe access to running_processes
    with running_processes_lock:
        if project_id not in running_processes:
            return {"logs": [], "status": "not_running"}
        # Take a snapshot of the log buffer while holding the lock
        log_buffer = running_processes[project_id]["logs"]
        log_lines = list(log_buffer)[-lines:]

    return {"logs": log_lines, "status": "running"}

# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    print(f"Starting ServerDock on http://localhost:{MANAGER_PORT}")
    uvicorn.run(app, host="127.0.0.1", port=MANAGER_PORT)
