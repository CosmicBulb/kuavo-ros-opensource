from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import asyncio
import logging
import os

from app.core.database import get_db
from app.models.robot import Robot
from app.schemas.robot import (
    RobotCreate, RobotResponse, RobotUpdate, RobotConnectionStatus,
    RobotListResponse, PaginationInfo, RobotTestConnection
)
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
async def test_connection(robot: RobotTestConnection):
    """测试设备连接并获取设备信息，不保存到数据库"""
    logger.info(f"开始测试连接: {robot.ip_address}:{robot.port}")
    
    try:
        # 创建临时ID用于SSH服务
        temp_id = f"test_{robot.ip_address}_{robot.port}"
        
        # 发送进度更新 - 开始验证网络
        if robot.client_id:
            await connection_manager.send_message(robot.client_id, message={
                "type": "connection_progress",
                "step": "network_validation",
                "progress": 20,
                "message": "正在验证网络环境..."
            })
        
        # 首先验证网络环境
        network_valid, network_message = await ssh_service.validate_network_environment(robot.ip_address)
        if not network_valid:
            if robot.client_id:
                await connection_manager.send_message(robot.client_id, message={
                    "type": "connection_progress",
                    "step": "network_validation",
                    "progress": 0,
                    "message": f"网络验证失败: {network_message}",
                    "error": True
                })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"设备不在同一网络下，无法连接: {network_message}"
            )
        
        # 发送进度更新 - 开始连接
        if robot.client_id:
            await connection_manager.send_message(robot.client_id, message={
                "type": "connection_progress",
                "step": "ssh_connection",
                "progress": 40,
                "message": "正在建立SSH连接..."
            })
        
        # 尝试连接
        success, error = await ssh_service.connect(
            temp_id,
            robot.ip_address,
            robot.port,
            robot.ssh_user,
            robot.ssh_password
        )
        
        if not success:
            if robot.client_id:
                await connection_manager.send_message(robot.client_id, message={
                    "type": "connection_progress",
                    "step": "ssh_connection",
                    "progress": 0,
                    "message": f"SSH连接失败: {error}",
                    "error": True
                })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"连接失败: {error}"
            )
        
        # 发送进度更新 - 获取设备信息
        if robot.client_id:
            await connection_manager.send_message(robot.client_id, message={
                "type": "connection_progress",
                "step": "device_info",
                "progress": 70,
                "message": "正在读取设备信息..."
            })
        
        # 获取机器人信息
        robot_info = await ssh_service.get_robot_info(temp_id)
        if not robot_info:
            # 断开连接
            await ssh_service.disconnect(temp_id)
            if robot.client_id:
                await connection_manager.send_message(robot.client_id, message={
                    "type": "connection_progress",
                    "step": "device_info",
                    "progress": 0,
                    "message": "无法获取设备信息",
                    "error": True
                })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取设备信息"
            )
        
        # 发送进度更新 - 完成
        if robot.client_id:
            await connection_manager.send_message(robot.client_id, message={
                "type": "connection_progress",
                "step": "completed",
                "progress": 100,
                "message": "设备信息读取完成"
            })
        
        # 断开连接
        await ssh_service.disconnect(temp_id)
        
        # 返回设备信息（匹配界面需要的字段）
        return {
            "success": True,
            "device_info": {
                "name": robot.name,
                "ip_address": robot.ip_address,
                # 基本信息
                "robot_model": robot_info.get("robot_model", "未知"),
                "robot_version": robot_info.get("robot_version", "未知"),
                "robot_sn": robot_info.get("robot_sn", "未知"),
                "robot_software_version": robot_info.get("robot_software_version", "未知"),
                "end_effector_model": robot_info.get("end_effector_model", "未知"),
                # 兼容旧字段
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


@router.post("", response_model=RobotResponse)
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
        device_type=robot.device_type,  # 设备类型
        # 这些信息应该从前端传过来（从test-connection的结果）
        robot_model=getattr(robot, 'robot_model', None),
        robot_version=getattr(robot, 'robot_version', None),
        robot_sn=getattr(robot, 'robot_sn', None),
        robot_software_version=getattr(robot, 'robot_software_version', None),
        end_effector_model=getattr(robot, 'end_effector_model', None),
        # 兼容旧字段
        hardware_model=getattr(robot, 'hardware_model', None) or getattr(robot, 'robot_model', None),
        software_version=getattr(robot, 'software_version', None) or getattr(robot, 'robot_software_version', None),
        sn_number=getattr(robot, 'sn_number', None) or getattr(robot, 'robot_sn', None),
        end_effector_type=getattr(robot, 'end_effector_type', None) or getattr(robot, 'end_effector_model', None)
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


@router.get("/online", response_model=RobotListResponse)
@router.get("/online/", response_model=RobotListResponse)
def get_online_robots(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
):
    """获取所有在线设备（支持分页）"""
    # 确保参数有效
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    
    # 获取在线设备总数
    total = db.query(Robot).filter(Robot.connection_status == "connected").count()
    
    # 获取在线设备分页数据
    robots = db.query(Robot).filter(
        Robot.connection_status == "connected"
    ).offset(offset).limit(page_size).all()
    
    # 计算分页信息
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    
    pagination_info = PaginationInfo(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )
    
    return RobotListResponse(
        items=robots,
        pagination=pagination_info
    )


@router.get("", response_model=RobotListResponse)
@router.get("/", response_model=RobotListResponse)
def get_robots(
    page: int = 1,
    page_size: int = 10,
    skip: int = None,
    limit: int = None,
    db: Session = Depends(get_db)
):
    """
    获取设备列表（支持分页）
    
    - **page**: 页码，从1开始（默认1）
    - **page_size**: 每页大小（默认10，最大100）
    - **skip**: 跳过记录数（已废弃，建议使用page）
    - **limit**: 限制记录数（已废弃，建议使用page_size）
    """
    # 向后兼容：如果提供了skip和limit，使用它们
    if skip is not None or limit is not None:
        offset = skip if skip is not None else 0
        size = limit if limit is not None else 100
    else:
        # 使用新的分页参数
        page = max(1, page)  # 确保页码至少为1
        page_size = min(max(1, page_size), 100)  # 确保页大小在1-100之间
        offset = (page - 1) * page_size
        size = page_size
    
    # 获取总数
    total = db.query(Robot).count()
    
    # 获取分页数据
    robots = db.query(Robot).offset(offset).limit(size).all()
    
    # 计算分页信息
    if skip is not None or limit is not None:
        # 使用skip/limit时的分页信息
        current_page = (offset // size) + 1 if size > 0 else 1
        total_pages = (total + size - 1) // size if size > 0 else 1
    else:
        # 使用page/page_size时的分页信息
        current_page = page
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    
    pagination_info = PaginationInfo(
        page=current_page,
        page_size=size,
        total=total,
        total_pages=total_pages,
        has_next=current_page < total_pages,
        has_prev=current_page > 1
    )
    
    return RobotListResponse(
        items=robots,
        pagination=pagination_info
    )


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


@router.get("/{robot_id}/status")
async def get_robot_status(robot_id: str, db: Session = Depends(get_db)):
    """获取机器人实时状态信息（电量、服务状态等）"""
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 如果未连接，返回默认状态
    if robot.connection_status != "connected":
        return {
            "robot_id": robot_id,
            "connection_status": robot.connection_status,
            "service_status": "断开",
            "battery_level": "断开",
            "error_code": ""
        }
    
    # 获取实时状态信息
    robot_status = await ssh_service.get_robot_status(robot_id)
    if robot_status:
        # 更新数据库中的状态信息
        robot.service_status = robot_status.get("service_status")
        robot.battery_level = robot_status.get("battery_level")
        robot.error_code = robot_status.get("error_code")
        db.commit()
    
    return {
        "robot_id": robot_id,
        "connection_status": robot.connection_status,
        "service_status": robot.service_status,
        "battery_level": robot.battery_level,
        "error_code": robot.error_code
    }


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
            
            # 获取机器人信息并更新
            robot_info = await ssh_service.get_robot_info(robot_id)
            if robot_info:
                robot.robot_model = robot_info.get("robot_model")
                robot.robot_version = robot_info.get("robot_version")
                robot.robot_sn = robot_info.get("robot_sn")
                robot.robot_software_version = robot_info.get("robot_software_version")
                robot.end_effector_model = robot_info.get("end_effector_model")
                # 兼容旧字段
                robot.hardware_model = robot_info.get("hardware_model")
                robot.software_version = robot_info.get("software_version")
                robot.sn_number = robot_info.get("sn_number")
                robot.end_effector_type = robot_info.get("end_effector_type")
            
            # 获取机器人状态信息
            robot_status = await ssh_service.get_robot_status(robot_id)
            if robot_status:
                robot.service_status = robot_status.get("service_status")
                robot.battery_level = robot_status.get("battery_level")
                robot.error_code = robot_status.get("error_code")
        else:
            robot.connection_status = "disconnected"
            message = f"连接失败: {error}"
            # 重置状态信息
            robot.service_status = "断开"
            robot.battery_level = "断开"
            robot.error_code = ""
        
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