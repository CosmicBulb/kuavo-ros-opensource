#!/usr/bin/env python3
"""
启动KUAVO Studio后端（模拟器模式）- 使用端口8001
"""
import os
import sys
import subprocess

# 设置环境变量启用模拟器
os.environ["USE_ROBOT_SIMULATOR"] = "true"

# 禁用标定监控器，避免启动延迟
os.environ["DISABLE_CALIBRATION_MONITOR"] = "true"

# 设置使用8001端口
os.environ["KUAVO_PORT"] = "8001"

print("启动KUAVO Studio后端...")
print("- 模拟器模式: 已启用")
print("- 标定监控器: 已禁用（避免启动延迟）")
print("- 端口: 8001")
print("\n访问 http://localhost:8001")
print("API文档: http://localhost:8001/docs\n")

# 运行主程序
subprocess.run([sys.executable, "main.py"])