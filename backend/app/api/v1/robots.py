from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import asyncio
import logging
import os

from app.core.database import get_db
from app.models.robot import Robot
from app.schemas.robot import RobotCreate, RobotResponse, RobotUpdate, RobotConnectionStatus
from app.services.ssh_service import ssh_service
from app.api.websocket import connection_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/test")
async def test_endpoint():
    """简单的测试端点"""
    return {"status": "ok", "message": "API is working"}


@router.post("/{robot_id}/reset-status")
async def reset_robot_status(robot_id: str, db: Session = Depends(get_db)):
    """重置设备连接状态"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 重置为断开状态
    robot.connection_status = "disconnected"
    db.commit()
    
    # 通知WebSocket客户端
    await connection_manager.broadcast_robot_status(
        RobotConnectionStatus(
            robot_id=robot_id,
            status="disconnected"
        )
    )
    
    return {"message": "状态已重置", "status": "disconnected"}


@router.post("/test-connection")
async def test_connection(robot: RobotCreate):
    """测试设备连接并获取设备信息，不保存到数据库"""
    logger.info(f"开始测试连接: {robot.ip_address}:{robot.port}")
    
    try:
        # 创建临时ID用于SSH服务
        temp_id = f"test_{robot.ip_address}_{robot.port}"
        
        # 首先验证网络环境
        network_valid, network_message = await ssh_service.validate_network_environment(robot.ip_address)
        if not network_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"设备不在同一网络下，无法连接: {network_message}"
            )
        
        # 尝试连接
        success, error = await ssh_service.connect(
            temp_id,
            robot.ip_address,
            robot.port,
            robot.ssh_user,
            robot.ssh_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"连接失败: {error}"
            )
        
        # 获取机器人信息
        robot_info = await ssh_service.get_robot_info(temp_id)
        if not robot_info:
            # 断开连接
            await ssh_service.disconnect(temp_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取设备信息"
            )
        
        # 断开连接
        await ssh_service.disconnect(temp_id)
        
        # 返回设备信息
        return {
            "success": True,
            "device_info": {
                "name": robot.name,
                "ip_address": robot.ip_address,
                "hardware_model": robot_info.get("hardware_model", "未知"),
                "software_version": robot_info.get("software_version", "未知"),
                "sn_number": robot_info.get("sn_number", "未知"),
                "end_effector_type": robot_info.get("end_effector_type", "未知")
            },
            "network_info": {
                "network_validation": network_message
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"连接测试失败: {str(e)}"
        )


@router.post("/", response_model=RobotResponse)
async def create_robot(robot: RobotCreate, db: Session = Depends(get_db)):
    """添加新设备（已经过连接测试）"""
    # 检查设备名是否已存在
    existing = db.query(Robot).filter(Robot.name == robot.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设备名称已存在"
        )
    
    # 创建新机器人记录
    db_robot = Robot(
        name=robot.name,
        ip_address=robot.ip_address,
        port=robot.port,
        ssh_user=robot.ssh_user,
        ssh_password_stored=robot.ssh_password,  # 生产环境应该加密
        connection_status="disconnected",
        # 这些信息应该从前端传过来（从test-connection的结果）
        hardware_model=getattr(robot, 'hardware_model', None),
        software_version=getattr(robot, 'software_version', None),
        sn_number=getattr(robot, 'sn_number', None),
        end_effector_type=getattr(robot, 'end_effector_type', None)
    )
    db.add(db_robot)
    db.commit()
    db.refresh(db_robot)
    
    # 通知所有WebSocket客户端
    await connection_manager.broadcast_robot_status(
        RobotConnectionStatus(
            robot_id=db_robot.id,
            status=db_robot.connection_status
        )
    )
    
    return db_robot


@router.get("/", response_model=List[RobotResponse])
def get_robots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取所有设备列表"""
    robots = db.query(Robot).offset(skip).limit(limit).all()
    return robots


@router.get("/{robot_id}", response_model=RobotResponse)
def get_robot(robot_id: str, db: Session = Depends(get_db)):
    """获取单个设备详情"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    return robot


@router.delete("/{robot_id}")
async def delete_robot(robot_id: str, db: Session = Depends(get_db)):
    """删除设备"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 如果已连接，先断开
    if robot.connection_status == "connected":
        await ssh_service.disconnect(robot_id)
    
    db.delete(robot)
    db.commit()
    
    # 通知WebSocket客户端
    await connection_manager.broadcast_robot_status(
        RobotConnectionStatus(
            robot_id=robot_id,
            status="deleted"
        )
    )
    
    return {"message": "设备删除成功"}


@router.post("/{robot_id}/connect")
async def connect_robot(robot_id: str, db: Session = Depends(get_db)):
    """连接机器人"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    if robot.connection_status == "connected":
        return {"message": "设备已连接"}
    
    # 在模拟器模式下，直接连接
    if os.getenv("USE_ROBOT_SIMULATOR", "false").lower() == "true":
        # 模拟器模式下立即连接
        success, error = await ssh_service.connect(
            robot_id,
            robot.ip_address,
            robot.port,
            robot.ssh_user,
            robot.ssh_password_stored
        )
        
        if success:
            robot.connection_status = "connected"
            db.commit()
            
            # 通知WebSocket客户端
            await connection_manager.broadcast_robot_status(
                RobotConnectionStatus(
                    robot_id=robot_id,
                    status="connected"
                )
            )
            return {"message": "连接成功", "status": "connected"}
        else:
            robot.connection_status = "disconnected"
            db.commit()
            return {"message": f"连接失败: {error}", "status": "disconnected"}
    else:
        # 真实模式下使用异步连接
        robot.connection_status = "connecting"
        db.commit()
        
        # 通知WebSocket客户端
        await connection_manager.broadcast_robot_status(
            RobotConnectionStatus(
                robot_id=robot_id,
                status="connecting"
            )
        )
        
        # 异步执行连接
        asyncio.create_task(_async_connect(robot_id, db))
        
        return {"message": "正在连接设备"}


@router.post("/{robot_id}/disconnect")
async def disconnect_robot(robot_id: str, db: Session = Depends(get_db)):
    """断开机器人连接"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    if robot.connection_status == "disconnected":
        return {"message": "设备已断开"}
    
    # 检查并停止正在进行的标定
    from app.services.calibration_service import calibration_service
    active_sessions = calibration_service.get_robot_active_sessions(robot_id)
    for session in active_sessions:
        await calibration_service.stop_calibration(session.session_id)
        logger.info(f"断开连接时停止了标定会话: {session.session_id}")
    
    # 更新状态
    robot.connection_status = "disconnecting"
    db.commit()
    
    # 通知WebSocket客户端
    await connection_manager.broadcast_robot_status(
        RobotConnectionStatus(
            robot_id=robot_id,
            status="disconnecting"
        )
    )
    
    # 执行断开
    success = await ssh_service.disconnect(robot_id)
    
    # 更新最终状态
    robot.connection_status = "disconnected"
    db.commit()
    
    # 通知WebSocket客户端
    await connection_manager.broadcast_robot_status(
        RobotConnectionStatus(
            robot_id=robot_id,
            status="disconnected"
        )
    )
    
    return {"message": "设备已断开"}


async def _async_connect(robot_id: str, db: Session):
    """异步连接任务"""
    try:
        # 获取机器人信息
        robot = db.query(Robot).filter(Robot.id == robot_id).first()
        if not robot:
            return
        
        # 执行连接
        success, error = await ssh_service.connect(
            robot_id,
            robot.ip_address,
            robot.port,
            robot.ssh_user,
            robot.ssh_password_stored
        )
        
        if success:
            robot.connection_status = "connected"
            message = "连接成功"
        else:
            robot.connection_status = "disconnected"
            message = f"连接失败: {error}"
        
        db.commit()
        
        # 通知WebSocket客户端
        await connection_manager.broadcast_robot_status(
            RobotConnectionStatus(
                robot_id=robot_id,
                status=robot.connection_status,
                message=message
            )
        )
        
    except Exception as e:
        logger.error(f"连接任务异常: {str(e)}")
        try:
            robot = db.query(Robot).filter(Robot.id == robot_id).first()
            if robot:
                robot.connection_status = "disconnected"
                db.commit()
            
            await connection_manager.broadcast_robot_status(
                RobotConnectionStatus(
                    robot_id=robot_id,
                    status="disconnected",
                    message=f"连接异常: {str(e)}"
                )
            )
        except:
            pass