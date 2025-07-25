from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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