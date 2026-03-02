# ServerDock 🚢

[English](#english) | [中文](#中文)

---

## 中文

一个轻量级的本地开发服务器管理面板。可视化查看哪些服务器正在运行，一键启动和停止，实时流式日志，再也不会丢失端口追踪。

专为同时处理多个服务（前端 + 后端、微服务、副项目）的开发者打造，提供可视化概览，无需 Docker Compose 或 PM2 的开销。

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## ✨ 功能特性

### 核心功能
- **项目注册表** — 存储项目配置（名称、目录、启动命令、端口），支持完整的 CRUD 操作
- **三态状态检测** — Running（我们启动的）、External（端口被外部占用）、Stopped（已停止）
- **一键启动/停止/重启** — 从浏览器启动和终止进程
- **日志流式传输** — 实时查看每个项目的最后 100 行日志，每 2 秒更新
- **进程持久化** — 管理的进程在管理器重启后仍然存活；面板会重新连接到它们
- **强制终止** — 终止占用所需端口的外部进程，支持多方法回退
- **端口检查** — 查看哪个进程正在使用任何端口（PID、名称、子进程数量）

### 🎨 界面增强
- **7 种主题** — 深色驼色（默认）、浅色、护眼、高对比度、深蓝、深紫、深青
- **主题切换器** — 一键切换主题，偏好自动保存到 localStorage
- **平滑过渡** — 主题切换时的流畅动画效果
- **响应式设计** — 完美适配桌面、平板和移动设备

### 🔍 搜索与过滤
- **实时搜索** — 按项目名称、目录或端口快速搜索
- **状态过滤** — 按运行状态筛选项目（全部/运行中/已停止/外部占用）
- **智能排序** — 支持按名称、端口、状态排序，排序偏好持久化
- **结果计数** — 实时显示筛选结果数量

### ⚡ 批量操作
- **多选模式** — Ctrl+B 快速进入批量操作模式
- **批量启动/停止** — 一次性操作多个项目
- **批量删除** — 快速清理不需要的项目
- **全选/取消全选** — 便捷的批量选择功能

### ⌨️ 键盘快捷键
- **Ctrl+K** — 聚焦搜索框
- **Ctrl+N** — 添加新项目
- **Ctrl+T** — 切换主题下拉菜单
- **Ctrl+B** — 切换批量操作模式
- **Esc** — 关闭弹窗/下拉菜单
- **?** — 显示快捷键帮助面板

### 📦 导入/导出
- **导出配置** — 将所有项目配置导出为 JSON 文件
- **导入配置** — 从 JSON 文件批量导入项目
- **冲突检测** — 自动检测端口冲突，智能选择可导入项目
- **预览导入** — 导入前预览所有项目，选择性导入

### 🔔 通知系统
- **Toast 通知** — 优雅的通知提示，替代传统 alert
- **操作反馈** — 启动、停止、删除等操作的即时反馈
- **批量操作结果** — 清晰显示批量操作的成功/失败数量
- **自动消失** — 通知 5 秒后自动消失，可手动关闭

### 🛠️ 技术特性
- **虚拟环境支持** — 相对路径如 `venv/Scripts/python` 会自动解析
- **fnm 集成** — 检测 Fast Node Manager 安装，使 `npm` 命令开箱即用
- **零依赖前端** — 单个 HTML 文件，内嵌 CSS/JS，无需构建步骤
- **文件日志** — 每个项目的日志保存到独立文件，支持持久化查看

## 快速开始

### 前置要求

- Python 3.10+
- Windows（进程管理使用 Windows 特定 API）
- [fnm](https://github.com/Schniz/fnm)（可选，用于 Node.js/npm 项目）

### 安装

```bash
git clone https://github.com/yg2224/ServerDock.git
cd ServerDock
pip install -r requirements.txt
```

### 运行

**方法 1：双击 start.bat（推荐）** ⭐

最简单的方式！直接双击 `start.bat` 文件即可启动。

**方法 2：命令行启动**

```bash
python main.py
```

**方法 3：创建桌面快捷方式**

```powershell
# 运行此脚本创建桌面快捷方式
.\create_shortcut.ps1
```

启动后，在浏览器中打开 [http://localhost:9001](http://localhost:9001)。

> 💡 **提示**：查看 [USAGE.md](USAGE.md) 了解更多启动方式和使用技巧。

### 打包为 EXE（可选）

如果你想要一个独立的 exe 文件，无需安装 Python 即可运行：

**快速打包（推荐）**

```bash
# 双击运行，5-10 分钟完成
build_exe.bat
```

**轻量打包（更小更快）**

```bash
# 双击运行，10-20 分钟完成
build_exe_nuitka.bat
```

构建完成后，`dist\ServerDock.exe` 即可独立运行，无需 Python 环境。

**对比**：
- **PyInstaller**: 15-20 MB，构建快（5-10 分钟）
- **Nuitka**: 8-12 MB，构建慢（10-20 分钟），运行更快
- **start.bat**: ~1 MB，无需构建，推荐日常使用

> 📖 **详细说明**：查看 [USAGE.md](USAGE.md) 了解完整的打包指南和对比。

### 添加项目

1. 点击面板中的 **+ Add Project** 按钮
2. 填写项目名称、目录路径、启动命令和端口
3. 点击保存
4. 点击 **Start** 启动服务器

或者复制 `config/projects.example.json` 到 `config/projects.json` 并手动编辑。

## 架构

```
浏览器 (localhost:9000)
    │
    ▼  REST API (每 3 秒轮询)
┌─────────────────────────────────────────────┐
│          FastAPI 后端 (main.py)              │
│                                             │
│  项目 CRUD  ·  进程管理  ·  端口检查         │
│  (JSON 存储)   (subprocess/psutil)          │
└─────────────────────────────────────────────┘
    │                    │                │
    ▼                    ▼                ▼
projects.json    基于文件的日志    psutil/socket
```

- **后端**: FastAPI 提供 REST API + 面板 HTML
- **前端**: 单文件 SPA，原生 JS，深色模式 UI，无框架
- **进程管理**: `subprocess.Popen` 配合 Windows 创建标志实现干净的进程组
- **状态检测**: 结合跟踪的 PID 查找和端口扫描实现三态感知

### API 端点

| 方法 | 端点 | 描述 |
|--------|----------|-------------|
| `GET` | `/api/projects` | 列出所有项目及状态 |
| `POST` | `/api/projects` | 添加新项目 |
| `PUT` | `/api/projects/{id}` | 更新项目配置 |
| `DELETE` | `/api/projects/{id}` | 删除项目（如果运行中则停止） |
| `POST` | `/api/projects/{id}/start` | 启动服务器进程 |
| `POST` | `/api/projects/{id}/stop` | 停止服务器进程 |
| `POST` | `/api/projects/{id}/restart` | 重启服务器进程 |
| `GET` | `/api/projects/{id}/logs` | 获取最近的日志行 |
| `POST` | `/api/ports/{port}/kill` | 终止占用端口的进程 |
| `GET` | `/api/ports/{port}/info` | 获取端口的进程信息 |

## 配置

项目存储在 `config/projects.json` 中（首次使用时自动创建）。参考 `config/projects.example.json` 的格式：

```json
{
  "projects": [
    {
      "id": "my-api",
      "name": "My API Server",
      "directory": "C:/dev/my-project/backend",
      "start_command": "python -m uvicorn main:app --reload --port 8000",
      "port": 8000,
      "url": "http://localhost:8000"
    }
  ]
}
```

`url` 字段是可选的 — 当存在时，会在面板中添加一个 "Open" 按钮。

## 主题

项目内置 7 种精心设计的主题：

1. **Dark Camel**（默认）— 温暖的深色主题，驼色强调
2. **Light** — 明亮的浅色主题，适合白天使用
3. **Eye Care** — 柔和的绿色/米色调，减少眼睛疲劳
4. **High Contrast** — 强对比度配色，提高可读性
5. **Dark Blue** — 深蓝色主题，专业感
6. **Dark Purple** — 深紫色主题，优雅感
7. **Dark Cyan** — 深青色主题，清新感

主题偏好自动保存到浏览器 localStorage，下次访问时自动应用。

## 限制

- **仅限 Windows** — 进程管理使用 Windows 特定的 subprocess 标志（`CREATE_NEW_PROCESS_GROUP`、`CREATE_NO_WINDOW`）、netstat 解析和 PowerShell 回退。Linux/macOS 支持需要平台抽象层。
- **仅限本地** — 绑定到 `127.0.0.1:9000`，无身份验证。不适合远程访问。
- **无进程接管** — 无法附加到在管理器外部启动的进程（但会检测为 "external"）。
- **无健康检查** — 状态基于端口可用性，而非 HTTP 响应验证。

## 安全性

此工具在本地运行，专为单用户开发工作流设计：

- 仅绑定到 `localhost`（非 `0.0.0.0`）
- 无身份验证（本地信任模型）
- 启动命令存储在配置中并通过 `shell=True` 执行 — 只有机器所有者应编辑配置
- 不传输或存储敏感数据

## 许可证

MIT
