#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ServerDock Launcher
轻量级启动器，用于打包成 exe
"""
import sys
import os
from pathlib import Path

# 添加当前目录到 Python 路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 导入并运行主程序
if __name__ == "__main__":
    import main
