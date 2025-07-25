from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./kuavo_studio.db"
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # SSH默认配置
    SSH_DEFAULT_PORT: int = 22
    SSH_DEFAULT_USER: str = "leju"
    SSH_TIMEOUT: int = 10
    
    # WebSocket配置
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # 标定脚本路径
    CALIBRATION_SCRIPT_ZERO_POINT: str = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true"
    CALIBRATION_SCRIPT_HEAD_HAND: str = "/root/kuavo_ws/src/kuavo-ros-opensource/scripts/joint_cali/One_button_start.sh"
    
    class Config:
        env_file = ".env"


settings = Settings()