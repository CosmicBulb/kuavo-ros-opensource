from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class CalibrationSession(Base):
    __tablename__ = "calibration_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    robot_id = Column(String, ForeignKey("robots.id"), nullable=False)
    calibration_type = Column(String, nullable=False)  # zero_point, head_hand
    status = Column(String, default="pending")  # pending, running, waiting_for_user, success, failed
    current_step = Column(Integer, default=0)
    logs = Column(Text, default="")
    user_prompt = Column(Text)
    error_message = Column(Text)
    
    # 时间戳
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    def to_dict(self):
        return {
            "id": self.id,
            "robot_id": self.robot_id,
            "calibration_type": self.calibration_type,
            "status": self.status,
            "current_step": self.current_step,
            "logs": self.logs,
            "user_prompt": self.user_prompt,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }