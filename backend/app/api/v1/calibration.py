from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.robot import Robot
from app.services.calibration_service import calibration_service
from app.schemas.calibration import (
    CalibrationStartRequest,
    CalibrationResponse,
    CalibrationUserResponse
)

router = APIRouter()


@router.post("/{robot_id}/calibrations")
async def start_calibration(
    robot_id: str,
    request: CalibrationStartRequest,
    db: Session = Depends(get_db)
):
    """开始标定流程"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"开始标定: robot_id={robot_id}, type={request.calibration_type}")
    
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        # 尝试用sn_number查找
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    # 检查机器人是否已连接
    if robot.connection_status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设备未连接"
        )
    
    try:
        # 开始标定
        session = await calibration_service.start_calibration(
            robot_id,
            request.calibration_type
        )
        
        return {
            "session_id": session.session_id,
            "message": "标定流程已启动"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/calibrations/response")
async def send_calibration_response(
    robot_id: str,
    response: CalibrationUserResponse,
    db: Session = Depends(get_db)
):
    """发送用户响应"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 获取当前会话
    session = calibration_service.get_robot_session(robot_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有正在进行的标定任务"
        )
    
    try:
        await calibration_service.send_user_response(
            session.session_id,
            response.response
        )
        
        return {"message": "响应已发送"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{robot_id}/calibrations/current")
async def stop_calibration(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """停止当前标定"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 获取当前会话
    session = calibration_service.get_robot_session(robot_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有正在进行的标定任务"
        )
    
    try:
        await calibration_service.stop_calibration(session.session_id)
        return {"message": "标定已停止"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{robot_id}/calibrations/current")
async def get_current_calibration(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """获取当前标定状态"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在"
        )
    
    # 获取当前会话
    session = calibration_service.get_robot_session(robot_id)
    if not session:
        return None
    
    return {
        "session_id": session.session_id,
        "calibration_type": session.calibration_type,
        "status": session.status,
        "current_step": session.current_step,
        "user_prompt": session.user_prompt,
        "logs": session.logs[-100:]  # 返回最近100条日志
    }