import paramiko
import asyncio
from typing import Optional, Tuple, Dict, Any
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import os

logger = logging.getLogger(__name__)


class SSHService:
    """SSH服务封装类"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.connections: Dict[str, paramiko.SSHClient] = {}
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
        
        # 获取其他信息
        # 获取版本信息
        success, version_out, _ = await self.execute_command(
            robot_id,
            "rosversion humanoid_controllers 2>/dev/null || echo 'unknown'"
        )
        
        # 获取硬件型号（从环境变量）
        success, model_out, _ = await self.execute_command(
            robot_id,
            "echo $ROBOT_VERSION"
        )
        
        # 组合信息
        result = {
            "hardware_model": robot_info.get("model", "Kuavo 4 pro"),
            "software_version": version_out.strip() if success else "unknown",
            "sn_number": robot_info.get("sn", "unknown"),
            "end_effector_type": robot_info.get("end_effector", "灵巧手")
        }
        
        # 根据ROBOT_VERSION映射硬件型号
        if model_out and model_out.strip():
            version_map = {
                "45": "Kuavo 4.5",
                "40": "Kuavo 4.0", 
                "30": "Kuavo 3.0"
            }
            result["hardware_model"] = version_map.get(model_out.strip(), f"Kuavo {model_out.strip()}")
        
        return result
    
    def is_connected(self, robot_id: str) -> bool:
        """检查是否已连接"""
        if self.use_simulator:
            return robot_id in self.connections and self.simulator.is_connected
        return robot_id in self.connections and self.connections[robot_id].get_transport() is not None
    
    def cleanup(self):
        """清理所有连接"""
        if self.use_simulator:
            self.simulator.disconnect()
            
        for robot_id in list(self.connections.keys()):
            try:
                if not self.use_simulator:
                    self.connections[robot_id].close()
            except:
                pass
        self.connections.clear()
        self.executor.shutdown(wait=True)


# 全局SSH服务实例
ssh_service = SSHService()