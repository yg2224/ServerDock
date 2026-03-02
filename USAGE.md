# ServerDock 使用指南

## 🚀 三种启动方式

### 1. 双击 start.bat（最简单，推荐）⭐

**适合**：日常开发使用

**步骤**：
1. 双击 `start.bat` 文件
2. 等待服务器启动（会自动打开命令行窗口）
3. 在浏览器中访问 http://localhost:9001

**优点**：
- ✅ 最简单，一键启动
- ✅ 可以看到实时日志
- ✅ 关闭窗口即停止服务器

---

### 2. 打包成 EXE（分发给他人）

**适合**：分享给没有 Python 环境的用户

#### 方案 A：PyInstaller（推荐，快速）

**特点**：
- 构建时间：5-10 分钟
- 文件大小：15-20 MB
- 兼容性：好

**步骤**：
```bash
# 双击运行
build_exe.bat

# 或命令行运行
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --name=ServerDock --onefile --windowed ServerDock.py
```

#### 方案 B：Nuitka（更小更快）

**特点**：
- 构建时间：10-20 分钟
- 文件大小：8-12 MB
- 运行速度：更快

**步骤**：
```bash
# 双击运行
build_exe_nuitka.bat

# 或命令行运行
py -3 -m pip install nuitka
py -3 -m nuitka --standalone --onefile ServerDock.py
```

**构建完成后**：
- EXE 文件位置：`dist\ServerDock.exe`
- 可以复制到任意位置使用
- 无需 Python 环境即可运行

---

### 3. 命令行启动（开发调试）

**适合**：开发者调试

```bash
# 方法 1
python main.py

# 方法 2
py -3 main.py

# 方法 3（后台运行）
start /B python main.py
```

---

## 📦 EXE 打包对比

| 方案 | 构建时间 | 文件大小 | 运行速度 | 推荐度 |
|------|---------|---------|---------|--------|
| **start.bat** | 0 秒 | ~1 MB | 快 | ⭐⭐⭐⭐⭐ 日常使用 |
| **PyInstaller** | 5-10 分钟 | 15-20 MB | 快 | ⭐⭐⭐⭐ 快速分发 |
| **Nuitka** | 10-20 分钟 | 8-12 MB | 更快 | ⭐⭐⭐ 追求极致 |

---

## 🎯 使用建议

### 日常开发
```bash
# 直接双击 start.bat 即可
start.bat
```

### 分享给朋友
```bash
# 1. 运行打包脚本
build_exe.bat

# 2. 将 dist\ServerDock.exe 发给朋友
# 3. 朋友双击即可使用，无需安装 Python
```

### 部署到服务器
```bash
# 使用 Python 直接运行
python main.py

# 或使用进程管理器（如 PM2）
pm2 start main.py --name serverdock
```

---

## ⚠️ 常见问题

### Q: 为什么推荐 start.bat 而不是 exe？
**A**:
- start.bat 启动最快（0 秒）
- 可以看到实时日志，方便调试
- 文件最小（~1 MB）
- exe 主要用于分发给没有 Python 的用户

### Q: 打包 exe 失败怎么办？
**A**:
```bash
# 1. 确保安装了所有依赖
pip install -r requirements.txt

# 2. 更新打包工具
pip install --upgrade pyinstaller

# 3. 查看详细错误信息
py -3 -m PyInstaller --log-level=DEBUG ServerDock.py
```

### Q: exe 文件太大怎么办？
**A**:
- 使用 Nuitka 打包（更小）
- 或者使用 UPX 压缩：
```bash
pip install pyinstaller[encryption]
pyinstaller --onefile --upx-dir=upx ServerDock.py
```

### Q: 如何创建桌面快捷方式？
**A**:
```powershell
# 运行此脚本
.\create_shortcut.ps1
```

---

## 🔧 高级配置

### 修改默认端口
编辑 `main.py`：
```python
MANAGER_PORT = 9001  # 改为你想要的端口
```

### 自定义主题
编辑 `index.html` 中的 CSS 变量即可添加新主题。

### 添加开机自启动
1. 按 `Win + R`
2. 输入 `shell:startup`
3. 将 `start.bat` 的快捷方式复制到打开的文件夹

---

## 📝 总结

**推荐使用方式**：
1. 🥇 **日常使用**：双击 `start.bat`
2. 🥈 **分发他人**：使用 `build_exe.bat` 打包
3. 🥉 **追求极致**：使用 `build_exe_nuitka.bat`

**记住**：start.bat 是最简单最快的方式！
