from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RobotBase(BaseModel):
    name: str = Field(..., description="设备名称")
    ip_address: str = Field(..., description="IP地址")
    port: int = Field(default=22, description="SSH端口")
    ssh_user: str = Field(..., description="SSH用户名")


class RobotCreate(RobotBase):
    ssh_password: str = Field(..., description="SSH密码")
    # 可选字段，从test-connection结果传入
    hardware_model: Optional[str] = None
    software_version: Optional[str] = None
    sn_number: Optional[str] = None
    end_effector_type: Optional[str] = None


class RobotUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None


class RobotResponse(RobotBase):
    id: str
    connection_status: str
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