from fastapi import APIRouter
from .robots import router as robots_router
from .calibration import router as calibration_router
from .robots_fast import router as robots_fast_router

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(robots_router, prefix="/robots", tags=["robots"])
api_router.include_router(calibration_router, prefix="/robots", tags=["calibration"])
api_router.include_router(robots_fast_router, prefix="/robots", tags=["robots"])