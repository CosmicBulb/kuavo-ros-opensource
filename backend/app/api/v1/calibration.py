from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.robot import Robot
from app.services.calibration_service import calibration_service
from app.services.ssh_service import ssh_service
from app.services.calibration_file_service import calibration_file_service
from app.services.zero_point_calibration_service import zero_point_calibration_service, ZeroPointStep
from app.schemas.calibration import (
    CalibrationStartRequest,
    CalibrationResponse,
    CalibrationUserResponse,
    # 新增的schemas
    ZeroPointCalibrationStartRequest,
    ZeroPointToolConfirmRequest,
    ZeroPointConfigConfirmRequest,
    ZeroPointSessionResponse,
    CalibrationFileInfoResponse,
    JointDataUpdateRequest,
    CalibrationFileReadResponse,
    HeadHandCalibrationStartRequest,
    CalibrationConfigCheckResponse,
    CalibrationModeRequest,
    JointDataSchema,
    CalibrationExecuteRequest,
    JointDebugRequest,
    JointDebugResponse
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
    
    # 检查机器人是否已连接（模拟器模式下跳过此检查）
    from app.services.ssh_service import ssh_service  
    if not (hasattr(ssh_service, 'use_simulator') and ssh_service.use_simulator):
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


@router.delete("/{robot_id}/calibrations/sessions")
async def cleanup_calibration_sessions(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """清理所有标定会话"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        cleaned_sessions = 0
        
        # 清理零点标定会话
        zero_point_session = await zero_point_calibration_service.get_robot_session(robot_id)
        if zero_point_session:
            await zero_point_calibration_service.cancel_calibration(zero_point_session.session_id)
            cleaned_sessions += 1
        
        # 清理普通标定会话
        regular_session = calibration_service.get_robot_session(robot_id)
        if regular_session:
            await calibration_service.stop_calibration(regular_session.session_id)
            cleaned_sessions += 1
        
        # 强制清理已完成的会话
        zero_point_calibration_service._cleanup_finished_sessions()
        
        return {
            "message": f"已清理 {cleaned_sessions} 个标定会话",
            "cleaned_sessions": cleaned_sessions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理会话时发生错误: {str(e)}"
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


@router.post("/{robot_id}/upper-computer/connect")
async def connect_upper_computer(
    robot_id: str,
    upper_host: Optional[str] = "192.168.26.1",
    upper_port: Optional[int] = 22,
    upper_username: Optional[str] = "kuavo",
    upper_password: Optional[str] = "leju_kuavo",
    db: Session = Depends(get_db)
):
    """连接上位机"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        success, error = await ssh_service.connect_to_upper_computer(
            robot_id=robot_id,
            upper_host=upper_host,
            upper_port=upper_port,
            upper_username=upper_username,
            upper_password=upper_password
        )
        
        if success:
            return {
                "message": "上位机连接成功",
                "upper_host": upper_host,
                "status": "connected"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"上位机连接失败: {error}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"连接上位机时发生错误: {str(e)}"
        )


@router.delete("/{robot_id}/upper-computer/connect")
async def disconnect_upper_computer(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """断开上位机连接"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        success = await ssh_service.disconnect_upper_computer(robot_id)
        
        if success:
            return {
                "message": "上位机连接已断开",
                "status": "disconnected"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="断开上位机连接失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"断开上位机连接时发生错误: {str(e)}"
        )


@router.get("/{robot_id}/upper-computer/status")
async def get_upper_computer_status(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """获取上位机连接状态"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        is_connected = ssh_service.is_upper_connected(robot_id)
        
        return {
            "robot_id": robot_id,
            "upper_computer_connected": is_connected,
            "status": "connected" if is_connected else "disconnected"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取上位机状态时发生错误: {str(e)}"
        )


@router.post("/{robot_id}/upper-computer/command")
async def execute_upper_computer_command(
    robot_id: str,
    command: str,
    db: Session = Depends(get_db)
):
    """在上位机执行命令"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    # 检查上位机是否已连接
    if not ssh_service.is_upper_connected(robot_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上位机未连接"
        )
    
    try:
        success, stdout, stderr = await ssh_service.execute_upper_command(
            robot_id, command
        )
        
        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "command": command
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行上位机命令时发生错误: {str(e)}"
        )


# ==================== 零点标定分步流程 API ====================

@router.post("/{robot_id}/zero-point-calibration")
async def start_zero_point_calibration(
    robot_id: str,
    request: ZeroPointCalibrationStartRequest,
    db: Session = Depends(get_db)
):
    """开始零点标定分步流程"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        session = await zero_point_calibration_service.start_zero_point_calibration(
            robot_id=robot_id,
            calibration_type=request.calibration_type
        )
        
        return {
            "session_id": session.session_id,
            "message": "零点标定流程已启动",
            "current_step": session.current_step.value,
            "status": session.status.value
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/confirm-tool")
async def confirm_zero_point_tool(
    robot_id: str,
    session_id: str,
    request: ZeroPointToolConfirmRequest,
    db: Session = Depends(get_db)
):
    """确认零点标定工具安装"""
    try:
        success = await zero_point_calibration_service.confirm_tool(
            session_id=session_id,
            tool_index=request.tool_index
        )
        
        if success:
            return {"message": "工具确认成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="工具确认失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/confirm-config")
async def confirm_config_and_proceed(
    robot_id: str,
    session_id: str,
    request: ZeroPointConfigConfirmRequest,
    db: Session = Depends(get_db)
):
    """确认配置并进入标定步骤"""
    try:
        success = await zero_point_calibration_service.confirm_config_and_proceed(
            session_id=session_id,
            modified_joints=request.modified_joints if hasattr(request, 'modified_joints') else None
        )
        
        if success:
            return {"message": "配置确认成功，开始标定"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配置确认失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/start-calibration-script")
async def start_calibration_script(
    robot_id: str,
    session_id: str,
    request: ZeroPointCalibrationStartRequest,
    db: Session = Depends(get_db)
):
    """启动标定脚本（在步骤3执行）"""
    try:
        success = await zero_point_calibration_service.start_calibration_script(
            session_id=session_id,
            calibration_type=request.calibration_type
        )
        
        if success:
            return {"message": "标定脚本已启动"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="启动标定脚本失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/start-execution")
async def start_zero_point_calibration_execution(
    robot_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """开始执行零点标定（进入步骤4）"""
    try:
        success = await zero_point_calibration_service.start_calibration_execution(session_id)
        
        if success:
            return {"message": "标定开始执行"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始执行标定失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/user-response")
async def send_zero_point_user_response(
    robot_id: str,
    session_id: str,
    response_data: dict,
    db: Session = Depends(get_db)
):
    """发送零点标定用户响应"""
    try:
        # 获取session
        session = await zero_point_calibration_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="会话不存在"
            )
        
        # 发送用户响应
        success = await zero_point_calibration_service.send_user_response(
            session_id=session_id,
            response=response_data.get("response", "y")
        )
        
        if success:
            return {"message": "响应已发送"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="发送响应失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{robot_id}/zero-point-calibration/{session_id}")
async def cancel_zero_point_calibration(
    robot_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """取消零点标定会话"""
    try:
        success = await zero_point_calibration_service.cancel_calibration(session_id)
        
        if success:
            return {"message": "标定已取消"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="取消标定失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{robot_id}/zero-point-calibration/current")
async def get_current_zero_point_calibration(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """获取当前零点标定状态"""
    try:
        session = await zero_point_calibration_service.get_robot_session(robot_id)
        
        if session:
            # 转换为JointDataSchema格式
            joint_data_schemas = [
                JointDataSchema(
                    id=joint.id,
                    name=joint.name,
                    current_position=joint.current_position,
                    zero_position=joint.zero_position,
                    offset=joint.offset,
                    status=joint.status
                )
                for joint in session.current_joint_data
            ]
            
            return ZeroPointSessionResponse(
                session_id=session.session_id,
                robot_id=session.robot_id,
                calibration_type=session.calibration_type,
                current_step=session.current_step.value,
                status=session.status.value,
                start_time=session.start_time,
                step_progress=session.step_progress,
                warnings=session.warnings,
                error_message=session.error_message,
                joint_data=joint_data_schemas
            )
        else:
            return None
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取零点标定状态时发生错误: {str(e)}"
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/execute-calibration")
async def execute_calibration(
    robot_id: str,
    session_id: str,
    request: CalibrationExecuteRequest,
    db: Session = Depends(get_db)
):
    """执行标定命令（一键标零或特定关节标定）"""
    try:
        # 获取当前会话
        session = await zero_point_calibration_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="标定会话不存在"
            )
        
        # 执行标定命令
        success = await zero_point_calibration_service.execute_calibration_command(
            session_id=session_id,
            calibration_mode=request.calibration_mode,
            command=request.command
        )
        
        if success:
            return {"message": f"{request.calibration_mode}标定已启动"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="执行标定命令失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/save-zero-point")
async def save_zero_point_data(
    robot_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """保存零点数据到配置文件"""
    try:
        success = await zero_point_calibration_service.save_zero_point_data(session_id)
        
        if success:
            return {"message": "零点数据已保存到配置文件"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="保存零点数据失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/validate")
async def validate_zero_point_calibration(
    robot_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """执行零点标定验证（运行roslaunch让机器人缩腿）"""
    try:
        # 获取当前会话
        session = await zero_point_calibration_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="标定会话不存在"
            )
        
        # 执行验证命令
        success = await zero_point_calibration_service.validate_calibration(
            session_id=session_id
        )
        
        if success:
            return {"message": "零点标定验证已启动"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="执行验证失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/go-to-step")
async def go_to_calibration_step(
    robot_id: str,
    session_id: str,
    request: dict,
    db: Session = Depends(get_db)
):
    """跳转到指定步骤"""
    try:
        step_name = request.get('step', '')
        step_map = {
            'confirm_tools': ZeroPointStep.CONFIRM_TOOLS,
            'read_config': ZeroPointStep.READ_CONFIG,
            'initialize_zero': ZeroPointStep.INITIALIZE_ZERO,
            'remove_tools': ZeroPointStep.REMOVE_TOOLS
        }
        
        if step_name not in step_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的步骤: {step_name}"
            )
        
        target_step = step_map[step_name]
        success = await zero_point_calibration_service.go_to_step(session_id, target_step)
        
        if success:
            return {"message": f"已跳转到步骤 {step_name}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="步骤跳转失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== 标定文件管理 API ====================

@router.get("/{robot_id}/calibration-files/{file_type}/data")
async def read_calibration_file_data(
    robot_id: str,
    file_type: str,  # arms_zero 或 legs_offset
    db: Session = Depends(get_db)
):
    """读取标定文件数据"""
    if file_type not in ["arms_zero", "legs_offset"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型"
        )
    
    try:
        if file_type == "arms_zero":
            joint_data = await calibration_file_service.read_arms_zero_data(robot_id)
        else:
            joint_data = await calibration_file_service.read_legs_offset_data(robot_id)
        
        # 获取当前关节位置
        current_positions = await calibration_file_service.get_current_joint_positions(robot_id)
        
        # 更新当前位置
        for joint in joint_data:
            joint.current_position = current_positions.get(joint.id, 0.0)
        
        # 数据验证
        warnings = await calibration_file_service.validate_joint_data(joint_data)
        
        # 转换为Schema格式
        joint_data_schemas = [
            JointDataSchema(
                id=joint.id,
                name=joint.name,
                current_position=joint.current_position,
                zero_position=joint.zero_position,
                offset=joint.offset,
                status=joint.status
            )
            for joint in joint_data
        ]
        
        return CalibrationFileReadResponse(
            file_type=file_type,
            joint_data=joint_data_schemas,
            warnings=warnings
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取文件数据时发生错误: {str(e)}"
        )


@router.put("/{robot_id}/calibration-files/{file_type}/data")
async def update_calibration_file_data(
    robot_id: str,
    file_type: str,  # arms_zero 或 legs_offset
    request: JointDataUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新标定文件数据"""
    if file_type not in ["arms_zero", "legs_offset"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型"
        )
    
    try:
        # 手动验证参数范围（补充Pydantic验证）
        warnings = []
        errors = []
        
        for joint in request.joint_data:
            if abs(joint.offset) > 0.05:
                if abs(joint.offset) > 0.1:
                    errors.append(
                        f"关节 {joint.name} 的偏移值 {joint.offset:.4f} "
                        f"超过安全范围(±0.1)，可能导致机器人损坏"
                    )
                else:
                    warnings.append(
                        f"关节 {joint.name} 的偏移值 {joint.offset:.4f} "
                        f"超过建议范围(±0.05)，请谨慎操作"
                    )
        
        # 如果有严重错误，直接拒绝
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"参数验证失败: {'; '.join(errors)}"
            )
        
        # 转换Schema为JointData
        from app.services.calibration_file_service import JointData
        joint_data = [
            JointData(
                id=joint.id,
                name=joint.name,
                current_position=joint.current_position,
                zero_position=joint.zero_position,
                offset=joint.offset,
                status=joint.status
            )
            for joint in request.joint_data
        ]
        
        # 保存数据
        if file_type == "arms_zero":
            success = await calibration_file_service.write_arms_zero_data(robot_id, joint_data)
        else:
            success = await calibration_file_service.write_legs_offset_data(robot_id, joint_data)
        
        if success:
            response = {"message": "标定数据保存成功"}
            if warnings:
                response["warnings"] = warnings
            return response
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存数据失败"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新文件数据时发生错误: {str(e)}"
        )


# ==================== 头手标定 API ====================

@router.get("/{robot_id}/calibration-config-check")
async def check_calibration_config(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """检查标定配置"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        # 检查标定环境配置 - 对应截图中的7项要求
        config_checks = {
            "virtual_env_ready": False,
            "apriltag_ready": False,
            "rosbag_files_ready": False,
            "camera_ready": False,
            "network_ready": False,
            "upper_computer_connected": False
        }
        
        # 1. 检查sudo权限和roscore启动能力
        try:
            sudo_check = await ssh_service.execute_command(
                robot_id, 
                "sudo -n true 2>/dev/null && echo 'ok' || echo 'failed'"
            )
            sudo_ok = "ok" in sudo_check.get("stdout", "")
            roscore_check = await ssh_service.execute_command(
                robot_id,
                "which roscore >/dev/null 2>&1 && echo 'ok' || echo 'failed'"
            )
            roscore_ok = "ok" in roscore_check.get("stdout", "")
            config_checks["network_ready"] = sudo_ok and roscore_ok
        except Exception:
            config_checks["network_ready"] = False
        
        # 2. 检查虚拟环境 (create_venv.sh)
        try:
            venv_check = await ssh_service.execute_command(
                robot_id, 
                "test -d /home/lab/kuavo_venv/joint_cali && echo 'exists' || echo 'missing'"
            )
            config_checks["virtual_env_ready"] = "exists" in venv_check.get("stdout", "")
        except Exception:
            config_checks["virtual_env_ready"] = False
        
        # 3. 检查标定工具和AprilTag（通过查看相机是否能检测到AprilTag）
        try:
            # 检查相机设备
            camera_check = await ssh_service.execute_command(
                robot_id,
                "ls /dev/video* 2>/dev/null | wc -l"
            )
            camera_count = int(camera_check.get("stdout", "0").strip())
            config_checks["camera_ready"] = camera_count > 0
            
            # 检查AprilTag配置文件
            apriltag_config_check = await ssh_service.execute_command(
                robot_id,
                "test -f /home/kuavo_ws/kuavo_ros_application/src/ros_vision/detection_apriltag/apriltag_ros/config/tags.yaml && echo 'exists' || echo 'missing'"
            )
            config_checks["apriltag_ready"] = "exists" in apriltag_config_check.get("stdout", "")
        except Exception:
            config_checks["camera_ready"] = False
            config_checks["apriltag_ready"] = False
        
        # 4. 检查rosbag文件
        try:
            rosbag_check = await ssh_service.execute_command(
                robot_id,
                "ls /root/kuavo_ws/src/kuavo-ros-opensource/scripts/joint_cali/bags/hand_move_demo_*.bag 2>/dev/null | wc -l"
            )
            bag_count = int(rosbag_check.get("stdout", "0").strip())
            config_checks["rosbag_files_ready"] = bag_count >= 2  # left和right两个bag文件
        except Exception:
            config_checks["rosbag_files_ready"] = False
        
        # 5. 检查上位机连接和密码配置
        config_checks["upper_computer_connected"] = ssh_service.is_upper_connected(robot_id)
        
        return CalibrationConfigCheckResponse(**config_checks)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查标定配置时发生错误: {str(e)}"
        )


@router.post("/{robot_id}/head-hand-calibration")
async def start_head_hand_calibration(
    robot_id: str,
    request: HeadHandCalibrationStartRequest,
    db: Session = Depends(get_db)
):
    """启动头手标定"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    # 检查机器人是否已连接（模拟器模式下跳过此检查）
    from app.services.ssh_service import ssh_service  
    if not (hasattr(ssh_service, 'use_simulator') and ssh_service.use_simulator):
        if robot.connection_status != "connected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设备未连接"
            )
    
    try:
        # 启动头手标定任务
        session = await calibration_service.start_calibration(
            robot_id=robot_id,
            calibration_type="head_hand"
        )
        
        return {
            "session_id": session.session_id,
            "message": "头手标定已启动",
            "script_path": request.script_path
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"启动头手标定失败: {str(e)}"
        )


@router.post("/{robot_id}/head-hand-calibration/save")
async def save_head_hand_calibration(
    robot_id: str,
    db: Session = Depends(get_db)
):
    """保存头手标定结果"""
    from app.services.ssh_service import ssh_service
    
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    try:
        # 确保模拟器模式下有连接
        if hasattr(ssh_service, 'use_simulator') and ssh_service.use_simulator:
            if robot_id not in ssh_service.connections:
                ssh_service.connections[robot_id] = "simulator"
        
        # 检查备份文件是否存在（说明标定已完成）
        success, backup_stdout, backup_stderr = await ssh_service.execute_command(
            robot_id,
            "ls /home/lab/.config/lejuconfig/arms_zero.yaml*.bak 2>/dev/null | head -1"
        )
        
        backup_file = backup_stdout.strip() if success else ""
        if not backup_file:
            # 模拟器模式下默认返回成功
            if hasattr(ssh_service, 'use_simulator') and ssh_service.use_simulator:
                backup_file = "/home/lab/.config/lejuconfig/arms_zero.yaml.head_cali.bak"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="未找到头手标定备份文件，请先完成标定"
                )
        
        # 确认标定结果已保存
        save_status = {
            "head_calibration_saved": True,
            "backup_file": backup_file,
            "save_time": "2024-01-30 15:30:45"
        }
        
        return {
            "message": "头手标定结果已确认保存",
            "status": save_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Exception in save_head_hand_calibration: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存头手标定结果时发生错误: {str(e)}"
        )


# ==================== 头手标定辅助函数 ====================

async def _execute_head_hand_script(robot_id: str, session_id: str):
    """执行头手标定脚本的后台任务，处理用户交互"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 提前导入connection_manager，避免在异常处理时出现导入错误
    from app.api.websocket import connection_manager
    
    try:
        script_path = "/root/kuavo_ws/src/kuavo-ros-opensource/scripts/joint_cali/One_button_start.sh"
        
        # 创建自动化交互脚本
        automated_script = f"""#!/bin/bash
cd /root/kuavo_ws/src/kuavo-ros-opensource

# 确保脚本可执行
chmod +x {script_path}

# 使用expect来自动化交互
expect << 'EOF'
set timeout 1800
spawn sudo bash {script_path}

# 处理"是否启动机器人控制系统？(y/N)"
expect "是否启动机器人控制系统" {{
    send "y\\r"
}}

# 处理机器人状态确认
expect "机器人是否已完成缩腿动作" {{
    send "y\\r"
}}

# 处理"是否继续头部标定？(y/N)"
expect "是否继续头部标定" {{
    send "y\\r"
}}

# 处理头部标定完成后的确认
expect "按下回车键继续保存文件" {{
    send "\\r"
}}

# 处理手臂标定相关确认
expect "标定已完成，是否应用新的零点位置" {{
    send "y\\r"
}}

# 等待脚本完成
expect eof
EOF
"""
        
        # 创建交互式会话
        def output_callback(data: str):
            # 通过WebSocket发送实时日志
            message = {
                "type": "calibration_log",
                "session_id": session_id,
                "robot_id": robot_id,
                "data": data,
                "timestamp": None
            }
            import asyncio
            asyncio.create_task(connection_manager.broadcast(message))
        
        # 先安装expect工具
        await ssh_service.execute_command(robot_id, "which expect >/dev/null || sudo apt-get update && sudo apt-get install -y expect")
        
        # 执行自动化脚本 - 模拟器模式下直接运行模拟脚本
        if hasattr(ssh_service, 'use_simulator') and ssh_service.use_simulator:
            # 模拟器模式：使用模拟器的头手标定脚本
            script_id = ssh_service.simulator.start_calibration_script("head_hand")
            
            # 监控脚本输出
            import asyncio
            while ssh_service.simulator.is_script_running(script_id):
                output = ssh_service.simulator.get_script_output(script_id)
                if output:
                    output_callback(output)
                await asyncio.sleep(0.5)
            
            # 获取脚本的实际执行结果
            success = ssh_service.simulator.get_script_result(script_id)
            if success:
                stdout = "Head-hand calibration simulation completed successfully"
                stderr = ""
            else:
                stdout = "Head-hand calibration simulation failed"
                stderr = "AprilTag detection failed or calibration precision not met"
        else:
            # 真实模式：执行实际脚本
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id=robot_id,
                command=automated_script
            )
            # 发送完整输出
            output_callback(stdout)
        
        # 发送完成状态
        completion_message = {
            "type": "head_hand_calibration_complete",
            "session_id": session_id,
            "robot_id": robot_id,
            "success": success,
            "error": stderr if not success else None
        }
        await connection_manager.broadcast(completion_message)
        
        # 清理标定会话
        try:
            await calibration_service.stop_calibration(session_id)
            logger.info(f"头手标定会话已清理: {session_id}")
        except Exception as cleanup_error:
            logger.warning(f"清理头手标定会话失败: {cleanup_error}")
        
        logger.info(f"头手标定脚本执行完成: robot_id={robot_id}, success={success}")
        
    except Exception as e:
        logger.error(f"执行头手标定脚本失败: robot_id={robot_id}, error={str(e)}")
        
        # 发送错误状态
        error_message = {
            "type": "head_hand_calibration_error",
            "session_id": session_id,
            "robot_id": robot_id,
            "error": str(e)
        }
        await connection_manager.broadcast(error_message)
        
        # 清理标定会话
        try:
            await calibration_service.stop_calibration(session_id)
            logger.info(f"头手标定会话已清理（异常情况）: {session_id}")
        except Exception as cleanup_error:
            logger.warning(f"清理头手标定会话失败（异常情况）: {cleanup_error}")


@router.get("/{robot_id}/zero-point-calibration/{session_id}/summary")
async def get_calibration_summary(
    robot_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """获取标定结果汇总，包括解析的Slave位置数据"""
    try:
        # 获取标定汇总
        summary = await zero_point_calibration_service.get_calibration_summary(session_id)
        
        if summary:
            return summary
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="标定会话不存在"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标定汇总时发生错误: {str(e)}"
        )


@router.post("/{robot_id}/zero-point-calibration/{session_id}/joint-debug")
async def debug_joints(
    robot_id: str,
    session_id: str,
    request: JointDebugRequest,
    db: Session = Depends(get_db)
) -> JointDebugResponse:
    """执行关节调试命令"""
    # 检查机器人是否存在
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        robot = db.query(Robot).filter(Robot.sn_number == robot_id).first()
        if not robot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设备不存在: {robot_id}"
            )
    
    # 检查标定会话是否存在
    session = await zero_point_calibration_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="标定会话不存在"
        )
    
    try:
        # 构建关节名称和位置列表
        joint_names = []
        positions = []
        
        for joint in request.joints:
            joint_id = joint['id'] if isinstance(joint, dict) else joint.id
            joint_name = joint.get("name", f"joint{joint_id}") if isinstance(joint, dict) else getattr(joint, 'name', f"joint{joint_id}")
            joint_position = joint["position"] if isinstance(joint, dict) else joint.position
            
            joint_names.append(joint_name)
            positions.append(float(joint_position))
        
        # 构建ROS命令
        # 格式化名称列表和位置列表
        names_str = ", ".join([f"'{name}'" for name in joint_names])
        positions_str = ", ".join([str(pos) for pos in positions])
        
        # 构建完整的rostopic pub命令
        command = f"""rostopic pub -1 /kuavo_arm_traj sensor_msgs/JointState "header: {{seq: 0, stamp: {{secs: 0, nsecs: 0}}, frame_id: ''}}
name: [{names_str}]
position: [{positions_str}]
velocity: []
effort: []" """
        
        # 执行命令
        success, stdout, stderr = await ssh_service.execute_command(robot_id, command)
        
        if success:
            # 广播日志消息
            log_message = f"✅ 关节调试命令已执行：调整了 {len(request.joints)} 个关节"
            await zero_point_calibration_service._broadcast_log(session, log_message)
            
            # 记录每个关节的调整
            for joint in request.joints:
                joint_id = joint['id'] if isinstance(joint, dict) else joint.id
                joint_name = joint.get("name", f"joint{joint_id}") if isinstance(joint, dict) else getattr(joint, 'name', f"joint{joint_id}")
                joint_position = joint["position"] if isinstance(joint, dict) else joint.position
                detail_log = f"  - {joint_name} -> {joint_position} rad"
                await zero_point_calibration_service._broadcast_log(session, detail_log)
            
            return JointDebugResponse(
                success=True,
                message=f"成功调整 {len(request.joints)} 个关节",
                command_executed=command
            )
        else:
            error_msg = stderr if stderr else "命令执行失败"
            await zero_point_calibration_service._broadcast_log(session, f"❌ 关节调试失败: {error_msg}")
            
            return JointDebugResponse(
                success=False,
                message="关节调试命令执行失败",
                error=error_msg,
                command_executed=command
            )
            
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        
        # 安全地尝试发送日志
        try:
            if 'session' in locals() and session and hasattr(session, 'session_id'):
                await zero_point_calibration_service._broadcast_log(session, f"❌ 关节调试异常: {str(e)}")
        except:
            pass  # 忽略日志发送失败
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行关节调试时发生错误: {str(e)}"
        )