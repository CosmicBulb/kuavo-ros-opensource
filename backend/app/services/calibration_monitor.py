import asyncio
import logging
import random
from app.services.calibration_service import calibration_service
from app.api.websocket import connection_manager

logger = logging.getLogger(__name__)


async def start_calibration_monitor():
    """启动标定监控后台任务"""
    logger.info("标定监控任务已启动")
    
    while True:
        try:
            await asyncio.sleep(0.5)  # 每0.5秒检查一次
            
            # 检查所有活动的标定会话
            for robot_id, session in calibration_service.active_calibrations.items():
                if not session.get("is_running"):
                    continue
                
                # 检查是否需要向用户发送提示
                prompt = calibration_service.check_user_prompt(robot_id)
                if prompt:
                    await connection_manager.send_to_robot_subscribers(
                        robot_id,
                        {
                            "type": "calibration_status",
                            "data": {
                                "robot_id": robot_id,
                                "status": "waiting_for_user",
                                "user_prompt": prompt
                            }
                        }
                    )
                
                # 获取标定输出日志
                log = calibration_service.get_calibration_output(robot_id)
                if log:
                    await connection_manager.send_to_robot_subscribers(
                        robot_id,
                        {
                            "type": "calibration_log",
                            "data": {
                                "robot_id": robot_id,
                                "log": log
                            }
                        }
                    )
                
                # 检查标定状态
                if not calibration_service.is_calibration_running(robot_id):
                    # 标定已完成
                    if session.get("success"):
                        await connection_manager.send_to_robot_subscribers(
                            robot_id,
                            {
                                "type": "calibration_status",
                                "data": {
                                    "robot_id": robot_id,
                                    "status": "success"
                                }
                            }
                        )
                    else:
                        await connection_manager.send_to_robot_subscribers(
                            robot_id,
                            {
                                "type": "calibration_status",
                                "data": {
                                    "robot_id": robot_id,
                                    "status": "failed",
                                    "error_message": session.get("error_message", "标定失败")
                                }
                            }
                        )
                    
                    # 清理会话
                    calibration_service.cleanup_calibration(robot_id)
                else:
                    # 发送进度更新
                    calibration_type = session.get("calibration_type")
                    if calibration_type == "zero_point":
                        # 模拟进度
                        progress = session.get("progress", 1)
                        if random.random() < 0.1:  # 10%概率更新进度
                            progress = min(progress + 1, 4)
                            session["progress"] = progress
                            
                            await connection_manager.send_to_robot_subscribers(
                                robot_id,
                                {
                                    "type": "calibration_status",
                                    "data": {
                                        "robot_id": robot_id,
                                        "status": "progress",
                                        "step": progress
                                    }
                                }
                            )
                            
                            # 发送模拟的关节数据
                            if progress == 2 and random.random() < 0.3:  # 步骤2时30%概率发送数据
                                joint_data = []
                                for i in range(13):  # 13个关节
                                    joint_data.append({
                                        "left": round(random.uniform(-30, 30), 3),
                                        "right": round(random.uniform(-30, 30), 3),
                                        "left_offset": round(random.uniform(-5, 5), 3),
                                        "right_offset": round(random.uniform(-5, 5), 3),
                                        "left_encoder": random.randint(10000, 100000),
                                        "right_encoder": random.randint(10000, 100000)
                                    })
                                
                                await connection_manager.send_to_robot_subscribers(
                                    robot_id,
                                    {
                                        "type": "calibration_data",
                                        "data": {
                                            "robot_id": robot_id,
                                            "joint_data": joint_data
                                        }
                                    }
                                )
                    
        except Exception as e:
            logger.error(f"标定监控任务错误: {str(e)}")
            await asyncio.sleep(5)  # 错误后等待5秒再继续