import paramiko
import asyncio
from typing import Optional, Tuple, Dict, Any, Callable, AsyncGenerator
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import os
import socket
import subprocess
import ipaddress
import time
import threading
import queue
import select

logger = logging.getLogger(__name__)


class SSHService:
    """SSH服务封装类，支持机器人和上位机双重连接"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.upper_connections: Dict[str, paramiko.SSHClient] = {}  # 上位机连接
        self.interactive_sessions: Dict[str, Dict[str, Any]] = {}  # 交互式会话
        self.use_simulator = os.getenv("USE_ROBOT_SIMULATOR", "false").lower() == "true"
        
        if self.use_simulator:
            from app.simulator.robot_simulator import robot_simulator
            self.simulator = robot_simulator
            logger.info("使用机器人模拟器模式")
    
    async def connect(self, robot_id: str, host: str, port: int, 
                     username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        建立SSH连接
        返回: (成功标志, 错误信息)
        """
        if self.use_simulator:
            # 使用模拟器，在线程池中执行以避免阻塞
            loop = asyncio.get_event_loop()
            success, error = await loop.run_in_executor(
                self.executor,
                self.simulator.connect,
                host, port, username, password
            )
            if success:
                # 模拟器中使用robot_id作为连接标识
                self.connections[robot_id] = "simulator"
            return success, error
        
        try:
            # 在线程池中执行阻塞的SSH操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._sync_connect, 
                robot_id, host, port, username, password
            )
            return result
        except Exception as e:
            logger.error(f"SSH连接失败: {str(e)}")
            return False, str(e)
    
    def _sync_connect(self, robot_id: str, host: str, port: int, 
                     username: str, password: str) -> Tuple[bool, Optional[str]]:
        """同步的SSH连接方法"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            self.connections[robot_id] = client
            return True, None
        except paramiko.AuthenticationException:
            return False, "认证失败，请检查用户名和密码"
        except paramiko.SSHException as e:
            return False, f"SSH连接错误: {str(e)}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    async def disconnect(self, robot_id: str) -> bool:
        """断开SSH连接"""
        # 清理相关的标定会话
        await self._cleanup_calibration_sessions(robot_id)
        
        if self.use_simulator:
            if robot_id in self.connections:
                del self.connections[robot_id]
                # 在线程池中执行以避免阻塞
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self.executor,
                    self.simulator.disconnect
                )
            return True
            
        if robot_id in self.connections:
            try:
                self.connections[robot_id].close()
                del self.connections[robot_id]
                return True
            except Exception as e:
                logger.error(f"断开连接失败: {str(e)}")
                return False
        return True
    
    async def _cleanup_calibration_sessions(self, robot_id: str):
        """清理标定会话"""
        try:
            # 导入标定服务时可能会有循环导入问题，所以在这里延迟导入
            from app.services.zero_point_calibration_service import zero_point_calibration_service
            from app.services.calibration_service import calibration_service
            
            # 清理零点标定会话
            session = await zero_point_calibration_service.get_robot_session(robot_id)
            if session:
                await zero_point_calibration_service.cancel_calibration(session.session_id)
                logger.info(f"已取消机器人 {robot_id} 的零点标定会话")
            
            # 清理普通标定会话
            regular_session = calibration_service.get_robot_session(robot_id)
            if regular_session:
                await calibration_service.stop_calibration(regular_session.session_id)
                logger.info(f"已停止机器人 {robot_id} 的标定会话")
                
        except Exception as e:
            logger.warning(f"清理标定会话时出错: {str(e)}")
    
    async def execute_command(self, robot_id: str, command: str) -> Tuple[bool, str, str]:
        """
        执行SSH命令
        返回: (成功标志, stdout, stderr)
        """
        if robot_id not in self.connections:
            return False, "", "未建立连接"
        
        if self.use_simulator:
            # 在线程池中执行以避免阻塞
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self.simulator.execute_command,
                command
            )
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._sync_execute_command,
                robot_id, command
            )
            return result
        except Exception as e:
            logger.error(f"执行命令失败: {str(e)}")
            return False, "", str(e)
    
    def _sync_execute_command(self, robot_id: str, command: str) -> Tuple[bool, str, str]:
        """同步的命令执行方法"""
        try:
            client = self.connections[robot_id]
            stdin, stdout, stderr = client.exec_command(command)
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            return True, stdout_data, stderr_data
        except Exception as e:
            return False, "", str(e)
    
    async def execute_command_interactive(
        self, 
        robot_id: str, 
        command: str,
        output_callback: Optional[Callable[[str], asyncio.Future]] = None,
        session_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        执行交互式命令，支持实时输出
        
        Args:
            robot_id: 机器人ID
            command: 要执行的命令
            output_callback: 输出回调函数，用于实时处理输出
            session_id: 会话ID，用于管理交互式会话
            
        Returns:
            (成功标志, 错误信息)
        """
        if self.use_simulator:
            # 模拟器模式下使用模拟器的交互式执行
            return await self._execute_simulator_interactive(robot_id, command, output_callback, session_id)
        
        try:
            loop = asyncio.get_event_loop()
            # 在线程池中执行交互式命令
            return await loop.run_in_executor(
                self.executor,
                self._sync_execute_interactive,
                robot_id, command, output_callback, session_id, loop
            )
        except Exception as e:
            logger.error(f"执行交互式命令失败: {str(e)}")
            return False, str(e)
    
    def _sync_execute_interactive(
        self, 
        robot_id: str, 
        command: str,
        output_callback: Optional[Callable],
        session_id: Optional[str],
        loop: asyncio.AbstractEventLoop
    ) -> Tuple[bool, str]:
        """同步的交互式命令执行"""
        try:
            if robot_id not in self.connections:
                return False, "未建立连接"
            
            client = self.connections[robot_id]
            
            # 创建交互式shell
            transport = client.get_transport()
            channel = transport.open_session()
            channel.get_pty()  # 获取伪终端
            channel.set_combine_stderr(True)  # 合并stderr到stdout
            
            # 设置非阻塞模式
            channel.setblocking(0)
            
            # 保存会话信息
            if session_id:
                self.interactive_sessions[session_id] = {
                    'channel': channel,
                    'robot_id': robot_id,
                    'command': command,
                    'start_time': time.time(),
                    'active': True
                }
            
            # 执行命令
            channel.exec_command(command)
            
            # 读取输出
            output_buffer = ""
            while True:
                # 检查会话是否被取消
                if session_id and session_id in self.interactive_sessions:
                    if not self.interactive_sessions[session_id].get('active', True):
                        logger.info(f"会话 {session_id} 被取消")
                        channel.close()
                        break
                
                # 检查通道是否关闭
                if channel.closed or channel.exit_status_ready():
                    # 读取剩余数据
                    while channel.recv_ready():
                        data = channel.recv(4096).decode('utf-8', errors='ignore')
                        output_buffer += data
                        if output_callback and data:
                            asyncio.run_coroutine_threadsafe(
                                output_callback(data), loop
                            )
                    break
                
                # 使用select检查是否有数据可读
                readable, _, _ = select.select([channel], [], [], 0.1)
                
                if readable:
                    data = channel.recv(4096).decode('utf-8', errors='ignore')
                    output_buffer += data
                    
                    # 调用回调函数处理输出
                    if output_callback and data:
                        asyncio.run_coroutine_threadsafe(
                            output_callback(data), loop
                        )
                
                # 短暂休眠避免CPU占用过高
                time.sleep(0.01)
            
            # 获取退出状态
            exit_status = channel.recv_exit_status() if channel.exit_status_ready() else 0
            
            # 清理会话
            if session_id and session_id in self.interactive_sessions:
                del self.interactive_sessions[session_id]
            
            if exit_status == 0:
                return True, ""
            else:
                return False, f"命令退出状态: {exit_status}"
                
        except Exception as e:
            logger.error(f"交互式命令执行失败: {str(e)}", exc_info=True)
            if session_id and session_id in self.interactive_sessions:
                del self.interactive_sessions[session_id]
            return False, str(e)
    
    async def send_input_to_session(self, session_id: str, input_data: str) -> bool:
        """
        向交互式会话发送输入
        
        Args:
            session_id: 会话ID
            input_data: 要发送的输入数据
            
        Returns:
            是否成功发送
        """
        if self.use_simulator:
            # 模拟器模式
            if hasattr(self.simulator, 'send_script_input'):
                self.simulator.send_script_input(session_id, input_data)
                return True
            return False
        
        try:
            if session_id not in self.interactive_sessions:
                logger.warning(f"会话 {session_id} 不存在")
                return False
            
            session = self.interactive_sessions[session_id]
            channel = session['channel']
            
            if channel.closed:
                logger.warning(f"会话 {session_id} 的通道已关闭")
                return False
            
            # 发送输入
            channel.send(input_data.encode('utf-8'))
            return True
            
        except Exception as e:
            logger.error(f"发送输入失败: {str(e)}")
            return False
    
    async def cancel_interactive_session(self, session_id: str) -> bool:
        """
        取消交互式会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功取消
        """
        if session_id in self.interactive_sessions:
            session = self.interactive_sessions[session_id]
            session['active'] = False
            
            # 尝试终止进程
            if 'channel' in session:
                channel = session['channel']
                try:
                    # 发送Ctrl+C
                    channel.send(b'\x03')
                    await asyncio.sleep(0.1)
                    
                    # 如果还在运行，强制关闭
                    if not channel.closed:
                        channel.close()
                except:
                    pass
            
            return True
        return False
    
    async def kill_process_by_pattern(self, robot_id: str, pattern: str) -> Tuple[bool, str]:
        """
        根据模式杀死进程
        
        Args:
            robot_id: 机器人ID
            pattern: 进程名称模式
            
        Returns:
            (成功标志, 错误信息)
        """
        try:
            # 使用pkill命令
            command = f"pkill -f '{pattern}'"
            success, stdout, stderr = await self.execute_command(robot_id, command)
            
            # pkill返回0表示找到并杀死了进程，1表示没找到进程
            # 两种情况都认为是成功的
            return True, ""
            
        except Exception as e:
            logger.error(f"杀死进程失败: {str(e)}")
            return False, str(e)
    
    async def cleanup_calibration_processes(self, robot_id: str):
        """
        清理标定相关进程
        
        Args:
            robot_id: 机器人ID
        """
        # 需要清理的进程模式
        patterns = [
            "roslaunch.*load_kuavo_real.*cali",
            "roslaunch.*humanoid_controllers",
            "python.*calibration",
            "One_button_start.sh"
        ]
        
        for pattern in patterns:
            await self.kill_process_by_pattern(robot_id, pattern)
        
        # 等待一下让进程完全退出
        await asyncio.sleep(0.5)
    
    async def _execute_simulator_interactive(
        self,
        robot_id: str,
        command: str,
        output_callback: Optional[Callable],
        session_id: Optional[str]
    ) -> Tuple[bool, str]:
        """模拟器模式下的交互式执行"""
        try:
            # 启动模拟器脚本
            script_id = self.simulator.start_calibration_script("custom", command)
            
            if session_id:
                self.interactive_sessions[session_id] = {
                    'script_id': script_id,
                    'robot_id': robot_id,
                    'command': command,
                    'active': True
                }
            
            # 监控脚本执行
            while self.simulator.is_script_running(script_id):
                # 检查是否被取消
                if session_id and session_id in self.interactive_sessions:
                    if not self.interactive_sessions[session_id].get('active', True):
                        self.simulator.stop_script(script_id)
                        break
                
                # 获取输出
                output = self.simulator.get_script_output(script_id)
                if output and output_callback:
                    await output_callback(output)
                
                await asyncio.sleep(0.1)
            
            # 清理会话
            if session_id and session_id in self.interactive_sessions:
                del self.interactive_sessions[session_id]
            
            return True, ""
            
        except Exception as e:
            logger.error(f"模拟器交互式执行失败: {str(e)}")
            return False, str(e)
    
    async def get_robot_info(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """获取机器人信息"""
        # 首先尝试读取 robot_info.json
        success, stdout, stderr = await self.execute_command(
            robot_id, 
            "cat /etc/robot_info.json 2>/dev/null || echo '{}'"
        )
        
        if success and stdout:
            try:
                robot_info = json.loads(stdout.strip())
            except:
                robot_info = {}
        else:
            robot_info = {}
        
        # 获取软件版本信息
        success, sw_version_out, _ = await self.execute_command(
            robot_id,
            "rosversion humanoid_controllers 2>/dev/null || echo 'version 1.2.3'"
        )
        
        # 获取硬件型号（从环境变量）
        success, model_out, _ = await self.execute_command(
            robot_id,
            "echo $ROBOT_VERSION"
        )
        
        # 获取机器人版本（从配置文件）
        success, robot_ver_out, _ = await self.execute_command(
            robot_id,
            "cat /home/lab/kuavo_robot_hardware/version.txt 2>/dev/null || echo 'version 1.2.3'"
        )
        
        # 组合信息（匹配界面显示的字段）
        result = {
            # 基本信息
            "robot_model": robot_info.get("model", "Kuavo 4 pro"),  # 机器人型号
            "robot_version": robot_ver_out.strip() if success and robot_ver_out else "version 1.2.3",  # 机器人版本
            "robot_sn": robot_info.get("sn", "qwert3459592sfag"),  # 机器人SN号
            "robot_software_version": sw_version_out.strip() if sw_version_out else "version 1.2.3",  # 机器人软件版本
            "end_effector_model": robot_info.get("end_effector", "灵巧手"),  # 末端执行器型号
            
            # 兼容旧字段
            "hardware_model": robot_info.get("model", "Kuavo 4 pro"),
            "software_version": sw_version_out.strip() if sw_version_out else "version 1.2.3",
            "sn_number": robot_info.get("sn", "qwert3459592sfag"),
            "end_effector_type": robot_info.get("end_effector", "灵巧手")
        }
        
        # 根据ROBOT_VERSION映射硬件型号
        if model_out and model_out.strip():
            version_map = {
                "45": "Kuavo 4.5",
                "4pro": "Kuavo 4 pro",
                "40": "Kuavo 4.0", 
                "30": "Kuavo 3.0"
            }
            mapped_model = version_map.get(model_out.strip(), f"Kuavo {model_out.strip()}")
            result["robot_model"] = mapped_model
            result["hardware_model"] = mapped_model
        
        return result
    
    async def get_robot_status(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """获取机器人连接状态信息（电量、服务状态、故障码等）"""
        if not self.is_connected(robot_id):
            return {
                "service_status": "断开",
                "battery_level": "断开",
                "error_code": ""
            }
        
        # 检查ROS服务状态
        success, ros_out, _ = await self.execute_command(
            robot_id,
            "rosnode list 2>/dev/null | grep -q controller && echo '正常' || echo '断开'"
        )
        service_status = ros_out.strip() if success and ros_out else "断开"
        
        # 获取电量信息（假设有电量查询命令）
        success, battery_out, _ = await self.execute_command(
            robot_id,
            "cat /sys/class/power_supply/BAT0/capacity 2>/dev/null || echo ''"
        )
        battery_level = f"{battery_out.strip()}%" if success and battery_out.strip() else "断开"
        
        # 获取故障码（假设有故障码查询命令）
        success, error_out, _ = await self.execute_command(
            robot_id,
            "cat /var/log/robot/error_code 2>/dev/null || echo ''"
        )
        error_code = error_out.strip() if success and error_out.strip() else ""
        
        return {
            "service_status": service_status,
            "battery_level": battery_level,
            "error_code": error_code
        }
    
    def is_connected(self, robot_id: str) -> bool:
        """检查是否已连接"""
        if self.use_simulator:
            # 在模拟器模式下，如果机器人ID在连接列表中，就认为已连接
            # 这样可以避免模拟器状态不一致的问题
            if robot_id in self.connections:
                return True
            # 如果不在连接列表中，但模拟器显示已连接，也可以认为连接正常
            return self.simulator.is_connected
        return robot_id in self.connections and self.connections[robot_id].get_transport() is not None
    
    async def connect_to_upper_computer(
        self, 
        robot_id: str,
        upper_host: str = "192.168.26.1",
        upper_port: int = 22,
        upper_username: str = "kuavo",
        upper_password: str = "leju_kuavo"
    ) -> Tuple[bool, Optional[str]]:
        """
        连接到上位机
        返回: (成功标志, 错误信息)
        """
        if self.use_simulator:
            # 模拟器模式下，模拟上位机连接
            loop = asyncio.get_event_loop()
            success, error = await loop.run_in_executor(
                self.executor,
                self.simulator.connect_upper_computer,
                upper_host, upper_port, upper_username, upper_password
            )
            if success:
                self.upper_connections[robot_id] = "simulator_upper"
            return success, error
        
        try:
            # 在线程池中执行阻塞的SSH操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._sync_connect_upper, 
                robot_id, upper_host, upper_port, upper_username, upper_password
            )
            return result
        except Exception as e:
            logger.error(f"上位机SSH连接失败: {str(e)}")
            return False, str(e)
    
    def _sync_connect_upper(self, robot_id: str, host: str, port: int, 
                           username: str, password: str) -> Tuple[bool, Optional[str]]:
        """同步的上位机SSH连接方法"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            self.upper_connections[robot_id] = client
            return True, None
        except paramiko.AuthenticationException:
            return False, "上位机认证失败，请检查用户名和密码"
        except paramiko.SSHException as e:
            return False, f"上位机SSH连接错误: {str(e)}"
        except Exception as e:
            return False, f"上位机连接失败: {str(e)}"
    
    async def disconnect_upper_computer(self, robot_id: str) -> bool:
        """断开上位机SSH连接"""
        if self.use_simulator:
            if robot_id in self.upper_connections:
                del self.upper_connections[robot_id]
                # 在线程池中执行以避免阻塞
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self.executor,
                    self.simulator.disconnect_upper_computer
                )
            return True
            
        if robot_id in self.upper_connections:
            try:
                self.upper_connections[robot_id].close()
                del self.upper_connections[robot_id]
                return True
            except Exception as e:
                logger.error(f"断开上位机连接失败: {str(e)}")
                return False
        return True
    
    async def execute_upper_command(self, robot_id: str, command: str) -> Tuple[bool, str, str]:
        """
        在上位机执行SSH命令
        返回: (成功标志, stdout, stderr)
        """
        if robot_id not in self.upper_connections:
            return False, "", "未建立上位机连接"
        
        if self.use_simulator:
            # 在线程池中执行以避免阻塞
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self.simulator.execute_upper_command,
                command
            )
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._sync_execute_upper_command,
                robot_id, command
            )
            return result
        except Exception as e:
            logger.error(f"执行上位机命令失败: {str(e)}")
            return False, "", str(e)
    
    def _sync_execute_upper_command(self, robot_id: str, command: str) -> Tuple[bool, str, str]:
        """同步的上位机命令执行方法"""
        try:
            client = self.upper_connections[robot_id]
            stdin, stdout, stderr = client.exec_command(command)
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            return True, stdout_data, stderr_data
        except Exception as e:
            return False, "", str(e)
    
    def is_upper_connected(self, robot_id: str) -> bool:
        """检查上位机是否已连接"""
        if self.use_simulator:
            return robot_id in self.upper_connections and self.simulator.is_upper_connected
        return robot_id in self.upper_connections and self.upper_connections[robot_id].get_transport() is not None
    
    async def validate_network_environment(self, robot_host: str, local_host: str = None) -> Tuple[bool, str]:
        """
        验证设备和系统是否在同一网络环境下
        检查：
        1. 网络可达性（ping测试）
        2. 网络延迟（确保在合理范围内）
        3. 网段匹配（检查是否在同一子网）
        
        Args:
            robot_host: 机器人IP地址
            local_host: 本地系统IP地址（可选，自动检测）
            
        Returns:
            (is_valid, message): 验证结果和详细信息
        """
        # 模拟器模式下直接返回成功
        if self.use_simulator:
            return True, "模拟器模式：网络验证通过"
            
        try:
            # 1. 获取本地IP地址
            if not local_host:
                local_host = await self._get_local_ip()
            
            # 2. 验证IP地址格式
            try:
                robot_ip = ipaddress.ip_address(robot_host)
                local_ip = ipaddress.ip_address(local_host)
            except ValueError as e:
                return False, f"IP地址格式无效: {str(e)}"
            
            # 3. 检查网络可达性（ping测试）
            ping_success, ping_time = await self._ping_test(robot_host)
            if not ping_success:
                return False, f"设备不可达，无法ping通 {robot_host}，请检查网络连接"
            
            # 4. 检查网络延迟
            if ping_time > 100:  # 延迟超过100ms认为网络环境不佳
                return False, f"网络延迟过高({ping_time:.1f}ms)，可能不在同一网络环境"
            
            # 5. 检查网段匹配（假设使用常见的/24子网）
            try:
                # 尝试常见的子网掩码
                for prefix_len in [24, 16, 8]:
                    local_network = ipaddress.ip_network(f"{local_host}/{prefix_len}", strict=False)
                    if robot_ip in local_network:
                        return True, f"网络验证通过：设备在同一网络环境下（延迟{ping_time:.1f}ms）"
                
                # 如果不在同一子网，但可以ping通，可能是跨网段路由
                return True, f"设备可达但可能跨网段（延迟{ping_time:.1f}ms），建议检查网络配置"
                
            except Exception as e:
                # 网段检查失败，但ping成功，仍然认为可用
                return True, f"网络可达（延迟{ping_time:.1f}ms），但无法确定网段信息"
                
        except Exception as e:
            logger.error(f"网络环境验证失败: {str(e)}")
            return False, f"网络环境验证失败: {str(e)}"
    
    async def _get_local_ip(self) -> str:
        """获取本地IP地址"""
        try:
            # 方法1：通过socket连接获取本地IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # 连接到一个不存在的地址来获取本地IP
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                return local_ip
        except Exception:
            try:
                # 方法2：通过hostname获取
                local_ip = socket.gethostbyname(socket.gethostname())
                if local_ip != "127.0.0.1":
                    return local_ip
            except Exception:
                pass
        
        # 默认返回localhost（在某些环境下可能获取不到真实IP）
        return "127.0.0.1"
    
    async def _ping_test(self, host: str, timeout: int = 5) -> Tuple[bool, float]:
        """
        执行ping测试
        
        Args:
            host: 目标主机
            timeout: 超时时间（秒）
            
        Returns:
            (success, avg_time): 是否成功和平均延迟时间(ms)
        """
        # 模拟器模式下返回模拟结果
        if self.use_simulator:
            return True, 10.0  # 模拟10ms延迟
            
        try:
            import platform
            import asyncio
            
            # 根据操作系统选择ping命令
            system = platform.system().lower()
            if system == "windows":
                cmd = ["ping", "-n", "3", "-w", str(timeout * 1000), host]
            else:
                cmd = ["ping", "-c", "3", "-W", str(timeout), host]
            
            # 在线程池中执行ping命令
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._run_ping_command,
                cmd
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"Ping测试失败: {str(e)}")
            return False, 0.0
    
    def _run_ping_command(self, cmd) -> Tuple[bool, float]:
        """同步执行ping命令"""
        try:
            import platform
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                # 解析ping输出获取平均时间
                output = result.stdout
                system = platform.system().lower()
                
                if system == "windows":
                    # Windows: "平均 = 1ms" 或 "Average = 1ms"
                    import re
                    match = re.search(r'[平均|Average]\s*=\s*(\d+)ms', output)
                    if match:
                        avg_time = float(match.group(1))
                        return True, avg_time
                else:
                    # Linux/Mac: "round-trip min/avg/max/stddev = 1.0/2.0/3.0/0.5 ms"
                    import re
                    match = re.search(r'min/avg/max/[^=]*=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms', output)
                    if match:
                        avg_time = float(match.group(1))
                        return True, avg_time
                
                # 如果无法解析具体时间，但ping成功，返回默认值
                return True, 1.0
            else:
                return False, 0.0
                
        except subprocess.TimeoutExpired:
            return False, 0.0
        except Exception as e:
            logger.warning(f"执行ping命令出错: {str(e)}")
            return False, 0.0
    
    def cleanup(self):
        """清理所有连接"""
        if self.use_simulator:
            self.simulator.disconnect()
            self.simulator.disconnect_upper_computer()
            
        # 清理机器人连接
        for robot_id in list(self.connections.keys()):
            try:
                if not self.use_simulator:
                    self.connections[robot_id].close()
            except:
                pass
        self.connections.clear()
        
        # 清理上位机连接
        for robot_id in list(self.upper_connections.keys()):
            try:
                if not self.use_simulator:
                    self.upper_connections[robot_id].close()
            except:
                pass
        self.upper_connections.clear()
        
        self.executor.shutdown(wait=True)


# 全局SSH服务实例
ssh_service = SSHService()