from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


# === 原有的标定Schemas ===
class CalibrationStartRequest(BaseModel):
    calibration_type: str = Field(..., description="标定类型: zero_point 或 head_hand")


class CalibrationUserResponse(BaseModel):
    response: str = Field(..., description="用户响应内容")


class CalibrationResponse(BaseModel):
    session_id: str
    robot_id: str
    calibration_type: str
    status: str
    current_step: int
    user_prompt: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = []


class CalibrationLogMessage(BaseModel):
    session_id: str
    robot_id: str
    log: str
    timestamp: datetime = Field(default_factory=datetime.now)


# === 新增的零点标定Schemas ===
class JointDataSchema(BaseModel):
    """关节数据Schema"""
    id: int
    name: str
    current_position: float
    zero_position: float
    offset: float
    status: str = "normal"  # normal, warning, error
    
    @validator('offset')
    def validate_offset_range(cls, v):
        """验证偏移值范围，建议不超过0.05"""
        if abs(v) > 0.05:
            # 这里不直接抛出错误，而是在后续的更新请求中进行验证
            pass
        return v


class ToolConfirmationSchema(BaseModel):
    """工具确认Schema"""
    tool_name: str
    description: str
    image_path: str
    confirmed: bool = False


class ZeroPointCalibrationStartRequest(BaseModel):
    """零点标定开始请求"""
    calibration_type: str = Field(
        default="full_body", 
        description="标定类型: full_body, arms_only, legs_only"
    )


class ZeroPointToolConfirmRequest(BaseModel):
    """工具确认请求"""
    tool_index: int = Field(..., description="工具索引")


class ZeroPointConfigConfirmRequest(BaseModel):
    """配置确认请求"""
    modified_joints: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="修改的关节数据"
    )


class ZeroPointSessionResponse(BaseModel):
    """零点标定会话响应"""
    session_id: str
    robot_id: str
    calibration_type: str
    current_step: str
    status: str
    start_time: datetime
    step_progress: Dict[str, Any]
    warnings: List[str] = []
    error_message: Optional[str] = None
    joint_data: List[JointDataSchema] = []


# === 标定文件管理Schemas ===
class CalibrationFileInfoResponse(BaseModel):
    """标定文件信息响应"""
    file_path: str
    file_type: str
    exists: bool
    last_modified: Optional[datetime]
    backup_count: int
    file_size: int


class JointDataUpdateRequest(BaseModel):
    """关节数据更新请求"""
    joint_data: List[JointDataSchema]
    
    @validator('joint_data')
    def validate_joint_data_changes(cls, joint_data_list):
        """验证关节数据修改范围"""
        warnings = []
        errors = []
        
        for joint_data in joint_data_list:
            # 检查偏移值是否超过建议范围
            if abs(joint_data.offset) > 0.05:
                if abs(joint_data.offset) > 0.1:
                    # 超过0.1认为是危险操作
                    errors.append(
                        f"关节 {joint_data.name} 的偏移值 {joint_data.offset:.4f} "
                        f"超过安全范围(±0.1)，可能导致机器人损坏"
                    )
                else:
                    # 超过0.05给出警告
                    warnings.append(
                        f"关节 {joint_data.name} 的偏移值 {joint_data.offset:.4f} "
                        f"超过建议范围(±0.05)，请谨慎操作"
                    )
        
        # 如果有严重错误，抛出验证异常
        if errors:
            raise ValueError(f"参数验证失败: {'; '.join(errors)}")
        
        # 将警告信息附加到请求中（在API层处理）
        if warnings and hasattr(cls, '_warnings'):
            cls._warnings.extend(warnings)
        elif warnings:
            cls._warnings = warnings
            
        return joint_data_list


class CalibrationFileReadResponse(BaseModel):
    """标定文件读取响应"""
    file_type: str
    joint_data: List[JointDataSchema]
    warnings: List[str] = []


# === 头手标定增强Schemas ===
class HeadHandCalibrationStartRequest(BaseModel):
    """头手标定开始请求"""
    calibration_type: str = Field(default="head_hand", description="标定类型")
    script_path: str = Field(
        default="./scripts/joint_cali/One_button_start.sh", 
        description="标定脚本路径"
    )
    include_head: bool = Field(default=True, description="是否包含头部标定")
    include_arms: bool = Field(default=True, description="是否包含手臂标定")
    arm_selection: Optional[str] = Field(
        default="both", 
        description="手臂选择: left, right, both"
    )


class CalibrationConfigCheckResponse(BaseModel):
    """标定配置检查响应"""
    virtual_env_ready: bool = Field(..., description="虚拟环境是否就绪")
    apriltag_ready: bool = Field(..., description="AprilTag是否就绪")
    rosbag_files_ready: bool = Field(..., description="rosbag文件是否就绪")
    camera_ready: bool = Field(..., description="相机是否就绪")
    network_ready: bool = Field(..., description="网络是否就绪")
    upper_computer_connected: bool = Field(..., description="上位机是否连接")


class CalibrationModeRequest(BaseModel):
    """标定模式请求"""
    mode: str = Field(..., description="标定模式: cali, cali_arm, cali_leg")
    additional_params: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="额外参数"
    )


class CalibrationExecuteRequest(BaseModel):
    """执行标定请求"""
    calibration_mode: str = Field(..., description="标定模式: full_body, arms_only, legs_only")
    command: Optional[str] = Field(None, description="要执行的命令，如果不提供将使用默认命令")