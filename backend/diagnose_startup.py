#!/usr/bin/env python3
"""
诊断后端启动问题
"""
import sys
import os

print("=" * 60)
print("KUAVO Studio 后端启动诊断")
print("=" * 60)

# 1. 检查Python版本
print("\n1. Python版本:")
print(f"   {sys.version}")

# 2. 检查当前目录
print("\n2. 当前目录:")
print(f"   {os.getcwd()}")

# 3. 检查必要的包
print("\n3. 检查依赖包:")
required_packages = ['fastapi', 'uvicorn', 'sqlalchemy', 'paramiko']
for package in required_packages:
    try:
        __import__(package)
        print(f"   ✅ {package} 已安装")
    except ImportError:
        print(f"   ❌ {package} 未安装")

# 4. 尝试导入主要模块
print("\n4. 测试模块导入:")

# 设置环境变量
os.environ["USE_ROBOT_SIMULATOR"] = "true"
os.environ["DISABLE_CALIBRATION_MONITOR"] = "true"

try:
    print("   导入 app.core.config...")
    from app.core.config import settings
    print("   ✅ config 导入成功")
except Exception as e:
    print(f"   ❌ config 导入失败: {e}")

try:
    print("   导入 app.core.database...")
    from app.core.database import init_db
    print("   ✅ database 导入成功")
except Exception as e:
    print(f"   ❌ database 导入失败: {e}")

try:
    print("   导入 app.api.v1...")
    from app.api.v1 import api_router
    print("   ✅ api_router 导入成功")
except Exception as e:
    print(f"   ❌ api_router 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 检查端口
print("\n5. 检查8000端口:")
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('localhost', 8000))
sock.close()
if result == 0:
    print("   ⚠️  端口8000已被占用")
else:
    print("   ✅ 端口8000可用")

# 6. 尝试启动最小化的FastAPI
print("\n6. 测试最小化FastAPI:")
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="测试")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    def root():
        return {"status": "ok"}
    
    print("   ✅ FastAPI基础功能正常")
except Exception as e:
    print(f"   ❌ FastAPI基础功能异常: {e}")

print("\n" + "=" * 60)
print("诊断完成！")
print("\n如果有❌标记，请先解决这些问题。")
print("通常需要运行: pip install -r requirements.txt")
print("=" * 60)