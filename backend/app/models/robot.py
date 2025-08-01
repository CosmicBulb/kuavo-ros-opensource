from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Robot(Base):
    __tablename__ = "robots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    ip_address = Column(String, nullable=False)
    port = Column(Integer, default=22)
    ssh_user = Column(String, nullable=False)
    ssh_password_stored = Column(Text)  # 生产环境应该加密
    connection_status = Column(String, default="disconnected")  # connected, disconnected, connecting
    
    # 设备类型
    device_type = Column(String, default="lower")  # 设备类型: upper(上位机), lower(下位机)
    
    # 基本信息
    robot_model = Column(String)  # 机器人型号
    robot_version = Column(String)  # 机器人版本
    robot_sn = Column(String)  # 机器人SN号
    robot_software_version = Column(String)  # 机器人软件版本
    end_effector_model = Column(String)  # 末端执行器型号
    
    # 连接状态相关
    service_status = Column(String, default="断开")  # 服务状态
    battery_level = Column(String, default="断开")  # 电量
    error_code = Column(String, default="")  # 故障码
    
    # 兼容旧字段
    hardware_model = Column(String)  # 已废弃，使用robot_model
    software_version = Column(String)  # 已废弃，使用robot_software_version
    sn_number = Column(String)  # 已废弃，使用robot_sn
    end_effector_type = Column(String)  # 已废弃，使用end_effector_model
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "port": self.port,
            "ssh_user": self.ssh_user,
            "connection_status": self.connection_status,
            "device_type": self.device_type,  # 设备类型
            # 基本信息
            "robot_model": self.robot_model or self.hardware_model,  # 机器人型号
            "robot_version": self.robot_version,  # 机器人版本
            "robot_sn": self.robot_sn or self.sn_number,  # 机器人SN号
            "robot_software_version": self.robot_software_version or self.software_version,  # 机器人软件版本
            "end_effector_model": self.end_effector_model or self.end_effector_type,  # 末端执行器型号
            # 连接状态
            "service_status": self.service_status,  # 服务状态
            "battery_level": self.battery_level,  # 电量
            "error_code": self.error_code,  # 故障码
            # 兼容旧字段
            "hardware_model": self.hardware_model,
            "software_version": self.software_version,
            "sn_number": self.sn_number,
            "end_effector_type": self.end_effector_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }