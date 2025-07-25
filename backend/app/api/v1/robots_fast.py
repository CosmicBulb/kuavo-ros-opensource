from fastapi import APIRouter, HTTPException, status
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 模拟的设备信息
MOCK_DEVICE_INFO = {
    "hardware_model": "Kuavo 4 pro",
    "software_version": "1.2.3-sim",
    "sn_number": "SIM123456789",
    "end_effector_type": "灵巧手"
}


@router.post("/test-connection-fast")
async def test_connection_fast(data: dict):
    """快速测试连接端点 - 直接返回模拟数据"""
    logger.info(f"快速测试连接: {data.get('ip_address')}")
    
    # 模拟短暂延迟
    await asyncio.sleep(0.5)
    
    return {
        "success": True,
        "device_info": {
            "name": data.get("name", "测试设备"),
            "ip_address": data.get("ip_address", "192.168.1.100"),
            "hardware_model": MOCK_DEVICE_INFO["hardware_model"],
            "software_version": MOCK_DEVICE_INFO["software_version"],
            "sn_number": MOCK_DEVICE_INFO["sn_number"],
            "end_effector_type": MOCK_DEVICE_INFO["end_effector_type"]
        }
    }