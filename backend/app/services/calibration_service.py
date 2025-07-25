import asyncio
import paramiko
from typing import Dict, Optional, Callable
import logging
import re
from datetime import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor
import os
import socket

from app.services.ssh_service import ssh_service
from app.api.websocket import connection_manager

logger = logging.getLogger(__name__)


class CalibrationSession:
    """标定会话类"""
    
    def __init__(self, session_id: str, robot_id: str, calibration_type: str):
        self.session_id = session_id
        self.robot_id = robot_id
        self.calibration_type = calibration_type
        self.status = "pending"
        self.current_step = 0
        self.logs = []
        self.user_prompt = None
        self.process_handle = None
        self.ssh_channel = None
        self.monitoring_task = None
        self.user_response_event = asyncio.Event()
        self.user_response = None
        self.simulator_script_id = None  # 用于模拟器
        
    async def cleanup(self):
        """清理资源"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.ssh_channel:
            self.ssh_channel.close()
        if self.process_handle:
            try:
                self.process_handle.terminate()
            except:
                pass
        if self.simulator_script_id and ssh_service.use_simulator:
            ssh_service.simulator.stop_script(self.simulator_script_id)


class CalibrationService:
    """标定服务"""
    
    def __init__(self):
        self.sessions: Dict[str, CalibrationSession] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.active_calibrations = {}  # 用于监控器访问
        
        # 定义交互点模式
        self.interaction_patterns = {
            "zero_point": [
                (r"是否启动机器人控制系统.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"按.*[oO].*启动机器人", "o"),
                (r"是否开始标定.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"请确认.*是否正确.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"是否保存标定结果.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                # 增加更多可能的提示格式
                (r"确认.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"继续.*[\(（][yY]/[nN][\)）][:：]?", "y")
            ],
            "head_hand": [
                (r"是否开始一键标定流程.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"是否启动机器人控制系统.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"请确认机器人已经上电.*回车继续", "\n"),
                (r"机器人将开始运动.*是否继续.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"是否继续头部标定.*[\(（][yY]/[nN][\)）][:：]?", "y"),
                (r"标定完成.*按任意键退出", "\n"),
                # 增加更多可能的提示格式
                (r"按回车键继续", "\n"),
                (r"按Enter继续", "\n")
            ]
        }
    
    async def start_calibration(self, robot_id: str, calibration_type: str) -> CalibrationSession:
        """开始标定"""
        # 检查是否已有正在进行的标定
        for session in self.sessions.values():
            if session.robot_id == robot_id and session.status in ["running", "waiting_for_user"]:
                raise Exception("该机器人已有正在进行的标定任务")
        
        # 创建新会话
        session_id = f"cal_{robot_id}_{int(datetime.now().timestamp())}"
        session = CalibrationSession(session_id, robot_id, calibration_type)
        self.sessions[session_id] = session
        
        # 启动标定任务
        session.monitoring_task = asyncio.create_task(
            self._run_calibration(session)
        )
        
        # 添加到活动标定中供监控器使用
        self.active_calibrations[robot_id] = {
            "session_id": session_id,
            "calibration_type": calibration_type,
            "is_running": True,
            "progress": 1,
            "success": False,
            "error_message": None
        }
        
        return session
    
    async def _run_calibration(self, session: CalibrationSession):
        """运行标定流程"""
        try:
            session.status = "running"
            await self._broadcast_status(session)
            
            # 获取SSH连接
            if session.robot_id not in ssh_service.connections:
                raise Exception("机器人未连接")
            
            # 如果使用模拟器
            if ssh_service.use_simulator:
                await self._run_simulator_calibration(session)
            else:
                await self._run_real_calibration(session)
            
        except Exception as e:
            logger.error(f"标定失败: {str(e)}")
            session.status = "failed"
            session.error_message = str(e)
            await self._broadcast_status(session)
        
        finally:
            await session.cleanup()
    
    async def _run_simulator_calibration(self, session: CalibrationSession):
        """运行模拟器标定"""
        # 启动模拟器脚本
        session.simulator_script_id = ssh_service.simulator.start_calibration_script(
            session.calibration_type
        )
        
        # 更新活动标定中的script_id
        if session.robot_id in self.active_calibrations:
            self.active_calibrations[session.robot_id]["script_id"] = session.simulator_script_id
        
        # 监控输出
        while ssh_service.simulator.is_script_running(session.simulator_script_id):
            # 获取输出
            output = ssh_service.simulator.get_script_output(session.simulator_script_id)
            if output:
                lines = output.split('\n')
                for line in lines:
                    if line.strip():
                        session.logs.append(line)
                        await self._broadcast_log(session, line)
                        
                        # 检查交互点
                        for pattern, default_response in self.interaction_patterns.get(session.calibration_type, []):
                            if re.search(pattern, line, re.IGNORECASE):
                                session.status = "waiting_for_user"
                                session.user_prompt = line
                                await self._broadcast_status(session)
                                
                                # 等待用户响应
                                session.user_response_event.clear()
                                await session.user_response_event.wait()
                                
                                # 发送响应到模拟器
                                response = session.user_response or default_response
                                ssh_service.simulator.send_script_input(
                                    session.simulator_script_id, 
                                    response
                                )
                                
                                session.status = "running"
                                session.user_prompt = None
                                await self._broadcast_status(session)
                                break
            
            await asyncio.sleep(0.1)
        
        # 标定完成
        session.status = "success"
        await self._broadcast_status(session)
    
    async def _run_real_calibration(self, session: CalibrationSession):
        """运行真实标定"""
        ssh_client = ssh_service.connections[session.robot_id]
        
        # 根据标定类型选择命令
        if session.calibration_type == "zero_point":
            command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true"
        else:  # head_hand
            command = "/root/kuavo_ws/src/kuavo-ros-opensource/scripts/joint_cali/One_button_start.sh"
        
        # 创建交互式SSH通道
        channel = ssh_client.invoke_shell()
        session.ssh_channel = channel
        
        # 设置通道参数
        channel.settimeout(0.1)  # 设置非阻塞模式
        channel.set_combine_stderr(True)  # 合并stderr到stdout
        
        # 等待shell准备就绪
        await asyncio.sleep(0.5)
        
        # 清空初始输出
        try:
            initial_data = channel.recv(4096)
            logger.debug(f"清空初始输出: {repr(initial_data)}")
        except socket.timeout:
            pass
        
        # 发送命令
        logger.info(f"发送标定命令: {command}")
        channel.send(f"{command}\n")
        
        # 监控输出
        buffer = ""
        interaction_patterns = self.interaction_patterns.get(session.calibration_type, [])
        last_buffer_check = ""
        
        while True:
            try:
                # 尝试读取数据
                data = channel.recv(1024).decode('utf-8', errors='ignore')
                if data:
                    logger.debug(f"接收到原始数据: {repr(data)}")
                    buffer += data
                    
                    # 按行处理
                    lines = buffer.split('\n')
                    
                    # 处理完整的行
                    for line in lines[:-1]:
                        if line.strip():
                            session.logs.append(line)
                            await self._broadcast_log(session, line)
                            
                            # 检查交互点
                            for pattern, default_response in interaction_patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    logger.info(f"检测到用户提示: {line}")
                                    session.status = "waiting_for_user"
                                    session.user_prompt = line
                                    await self._broadcast_status(session)
                                    
                                    # 等待用户响应
                                    session.user_response_event.clear()
                                    await session.user_response_event.wait()
                                    
                                    # 发送响应
                                    response = session.user_response or default_response
                                    channel.send(f"{response}\n")
                                    logger.info(f"发送用户响应: {response}")
                                    
                                    session.status = "running"
                                    session.user_prompt = None
                                    await self._broadcast_status(session)
                                    break
                    
                    # 保留未完成的行
                    buffer = lines[-1]
                    
                    # 检查缓冲区中的部分内容是否包含提示
                    # 处理没有换行符的提示
                    if buffer and buffer != last_buffer_check:
                        for pattern, default_response in interaction_patterns:
                            if re.search(pattern, buffer, re.IGNORECASE):
                                logger.info(f"在缓冲区检测到用户提示: {buffer}")
                                session.logs.append(buffer)
                                await self._broadcast_log(session, buffer)
                                
                                session.status = "waiting_for_user"
                                session.user_prompt = buffer
                                await self._broadcast_status(session)
                                
                                # 等待用户响应
                                session.user_response_event.clear()
                                await session.user_response_event.wait()
                                
                                # 发送响应
                                response = session.user_response or default_response
                                channel.send(f"{response}\n")
                                logger.info(f"发送用户响应: {response}")
                                
                                session.status = "running"
                                session.user_prompt = None
                                await self._broadcast_status(session)
                                buffer = ""  # 清空缓冲区
                                break
                        last_buffer_check = buffer
            
            except socket.timeout:
                # 超时是正常的，检查缓冲区
                # 如果缓冲区有内容且超过一定时间没有新数据，也要检查是否是提示
                if buffer and buffer.strip():
                    for pattern, default_response in interaction_patterns:
                        if re.search(pattern, buffer, re.IGNORECASE):
                            logger.info(f"超时后在缓冲区检测到用户提示: {buffer}")
                            session.logs.append(buffer)
                            await self._broadcast_log(session, buffer)
                            
                            session.status = "waiting_for_user"
                            session.user_prompt = buffer
                            await self._broadcast_status(session)
                            
                            # 等待用户响应
                            session.user_response_event.clear()
                            await session.user_response_event.wait()
                            
                            # 发送响应
                            response = session.user_response or default_response
                            channel.send(f"{response}\n")
                            logger.info(f"发送用户响应: {response}")
                            
                            session.status = "running"
                            session.user_prompt = None
                            await self._broadcast_status(session)
                            buffer = ""  # 清空缓冲区
                            break
            except Exception as e:
                if "closed" in str(e).lower():
                    # 通道关闭，标定结束
                    break
                else:
                    logger.error(f"读取输出错误: {str(e)}")
                    raise
            
            # 检查是否结束
            if not channel.get_transport().is_active():
                break
            
            await asyncio.sleep(0.1)
        
        # 标定完成
        session.status = "success"
        await self._broadcast_status(session)
    
    async def send_user_response(self, session_id: str, response: str):
        """发送用户响应"""
        session = self.sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.status != "waiting_for_user":
            raise Exception("当前不在等待用户输入状态")
        
        session.user_response = response
        session.user_response_event.set()
    
    async def stop_calibration(self, session_id: str):
        """停止标定"""
        session = self.sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        await session.cleanup()
        session.status = "failed"
        session.error_message = "用户取消"
        await self._broadcast_status(session)
        
        del self.sessions[session_id]
    
    async def _broadcast_status(self, session: CalibrationSession):
        """广播状态更新"""
        message = {
            "type": "calibration_status",
            "data": {
                "session_id": session.session_id,
                "robot_id": session.robot_id,
                "calibration_type": session.calibration_type,
                "status": session.status,
                "current_step": session.current_step,
                "user_prompt": session.user_prompt,
                "error_message": getattr(session, 'error_message', None)
            }
        }
        await connection_manager.send_to_robot_subscribers(session.robot_id, message)
    
    async def _broadcast_log(self, session: CalibrationSession, log_line: str):
        """广播日志"""
        message = {
            "type": "calibration_log",
            "data": {
                "session_id": session.session_id,
                "robot_id": session.robot_id,
                "log": log_line
            }
        }
        await connection_manager.send_to_robot_subscribers(session.robot_id, message)
    
    def get_session(self, session_id: str) -> Optional[CalibrationSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def get_robot_active_sessions(self, robot_id: str) -> list[CalibrationSession]:
        """获取机器人的所有活动会话"""
        active_sessions = []
        for session in self.sessions.values():
            if session.robot_id == robot_id and session.status in ["running", "waiting_for_user", "pending"]:
                active_sessions.append(session)
        return active_sessions
    
    def get_robot_session(self, robot_id: str) -> Optional[CalibrationSession]:
        """获取机器人的当前会话"""
        for session in self.sessions.values():
            if session.robot_id == robot_id and session.status in ["running", "waiting_for_user"]:
                return session
        return None


# 全局标定服务实例
calibration_service = CalibrationService()


# 为监控器添加的方法
def check_user_prompt(self, robot_id: str) -> Optional[str]:
    """检查是否有用户提示"""
    session = self.get_robot_session(robot_id)
    if session and session.status == "waiting_for_user":
        return session.user_prompt
    return None

def get_calibration_output(self, robot_id: str) -> Optional[str]:
    """获取标定输出"""
    if robot_id in self.active_calibrations:
        cal = self.active_calibrations[robot_id]
        if cal.get("script_id") and ssh_service.use_simulator:
            return ssh_service.simulator.get_script_output(cal["script_id"])
    return None

def is_calibration_running(self, robot_id: str) -> bool:
    """检查标定是否在运行"""
    if robot_id in self.active_calibrations:
        cal = self.active_calibrations[robot_id]
        if cal.get("script_id") and ssh_service.use_simulator:
            return ssh_service.simulator.is_script_running(cal["script_id"])
        return cal.get("is_running", False)
    return False

def cleanup_calibration(self, robot_id: str):
    """清理标定会话"""
    if robot_id in self.active_calibrations:
        del self.active_calibrations[robot_id]
    # 也清理sessions
    for session_id, session in list(self.sessions.items()):
        if session.robot_id == robot_id:
            del self.sessions[session_id]

# 将方法添加到类中
CalibrationService.check_user_prompt = check_user_prompt
CalibrationService.get_calibration_output = get_calibration_output
CalibrationService.is_calibration_running = is_calibration_running
CalibrationService.cleanup_calibration = cleanup_calibration