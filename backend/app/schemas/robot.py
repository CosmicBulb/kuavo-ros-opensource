from pydantic import BaseModel, Field
from typing import Optional, List, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class RobotBase(BaseModel):
    name: str = Field(..., description="设备名称")
    ip_address: str = Field(..., description="IP地址")
    port: int = Field(default=22, description="SSH端口")
    ssh_user: str = Field(..., description="SSH用户名")
    device_type: str = Field(default="lower", description="设备类型: upper(上位机) 或 lower(下位机)")


class RobotCreate(RobotBase):
    ssh_password: str = Field(..., description="SSH密码")
    device_type: str = Field(default="lower", description="设备类型: upper(上位机) 或 lower(下位机)")
    # 可选字段，从test-connection结果传入
    hardware_model: Optional[str] = None
    software_version: Optional[str] = None
    sn_number: Optional[str] = None
    end_effector_type: Optional[str] = None
    # 新字段名（从test-connection结果传入）
    robot_model: Optional[str] = None
    robot_version: Optional[str] = None
    robot_sn: Optional[str] = None
    robot_software_version: Optional[str] = None
    end_effector_model: Optional[str] = None


class RobotTestConnection(RobotBase):
    """测试连接请求，包含WebSocket客户端ID用于进度反馈"""
    ssh_password: str = Field(..., description="SSH密码")
    client_id: Optional[str] = Field(None, description="WebSocket客户端ID，用于接收进度更新")


class RobotUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    device_type: Optional[str] = None


class RobotResponse(RobotBase):
    id: str
    connection_status: str
    device_type: str  # 设备类型
    # 基本信息
    robot_model: Optional[str] = None  # 机器人型号
    robot_version: Optional[str] = None  # 机器人版本
    robot_sn: Optional[str] = None  # 机器人SN号
    robot_software_version: Optional[str] = None  # 机器人软件版本
    end_effector_model: Optional[str] = None  # 末端执行器型号
    # 连接状态
    service_status: Optional[str] = None  # 服务状态
    battery_level: Optional[str] = None  # 电量
    error_code: Optional[str] = None  # 故障码
    # 兼容旧字段
    hardware_model: Optional[str] = None
    software_version: Optional[str] = None
    sn_number: Optional[str] = None
    end_effector_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RobotConnectionStatus(BaseModel):
    robot_id: str
    status: str  # connecting, connected, disconnecting, disconnected
    message: Optional[str] = None


class PaginationParams(BaseModel):
    """分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=10, ge=1, le=100, description="每页大小，最大100")


class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total: int = Field(..., description="总记录数")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应"""
    items: List[T] = Field(..., description="数据列表")
    pagination: PaginationInfo = Field(..., description="分页信息")


class RobotListResponse(BaseModel):
    """机器人列表分页响应"""
    items: List[RobotResponse] = Field(..., description="机器人列表")
    pagination: PaginationInfo = Field(..., description="分页信息")