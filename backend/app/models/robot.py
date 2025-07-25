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
    hardware_model = Column(String)
    software_version = Column(String)
    sn_number = Column(String)
    end_effector_type = Column(String)
    
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
            "hardware_model": self.hardware_model,
            "software_version": self.software_version,
            "sn_number": self.sn_number,
            "end_effector_type": self.end_effector_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }