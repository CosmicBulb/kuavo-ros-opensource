from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import os
import logging

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.api.websocket import websocket_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    
    # 启动后台任务
    monitor_task = None
    if os.getenv("DISABLE_CALIBRATION_MONITOR", "false").lower() != "true":
        try:
            from app.services.calibration_monitor import start_calibration_monitor
            monitor_task = asyncio.create_task(start_calibration_monitor())
            logger.info("标定监控器已启动")
        except Exception as e:
            logger.error(f"无法启动标定监控器: {e}")
    else:
        logger.info("标定监控器已禁用")
    
    yield
    
    # 清理资源
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="KUAVO Studio API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该配置具体的前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router)


@app.get("/")
async def root():
    return {"message": "KUAVO Studio Backend API", "version": "1.0.0"}


if __name__ == "__main__":
    # 从环境变量获取端口，默认8001
    port = int(os.getenv("KUAVO_PORT", "8001"))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )