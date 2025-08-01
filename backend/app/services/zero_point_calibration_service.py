import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from app.services.ssh_service import ssh_service
from app.services.calibration_file_service import calibration_file_service, JointData
from app.api.websocket import connection_manager
from app.services.calibration_data_parser import calibration_data_parser

logger = logging.getLogger(__name__)


class ZeroPointStep(Enum):
    """零点标定步骤"""
    CONFIRM_TOOLS = "confirm_tools"          # 步骤1: 确认安装工具
    READ_CONFIG = "read_config"              # 步骤2: 读取当前配置
    INITIALIZE_ZERO = "initialize_zero"      # 步骤3: 初始化零点
    REMOVE_TOOLS = "remove_tools"            # 步骤4: 移除辅助工装


class ZeroPointStatus(Enum):
    """零点标定状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolConfirmation:
    """工具确认信息"""
    tool_name: str
    description: str
    image_path: str
    confirmed: bool = False


@dataclass
class ZeroPointSession:
    """零点标定会话"""
    session_id: str
    robot_id: str
    calibration_type: str  # "full_body", "arms_only", "legs_only"
    current_step: ZeroPointStep
    status: ZeroPointStatus
    start_time: datetime
    current_joint_data: List[JointData]
    original_joint_data: List[JointData]
    step_progress: Dict[str, Any]
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ZeroPointCalibrationService:
    """零点标定分步流程服务"""
    
    def __init__(self):
        self.active_sessions: Dict[str, ZeroPointSession] = {}
        
        # 工具确认列表
        self.tool_confirmations = {
            "full_body": [
                ToolConfirmation(
                    tool_name="安装工装",
                    description="将辅助工装插入腿部的插销中",
                    image_path="/static/images/install_leg_tools.jpg"
                ),
                ToolConfirmation(
                    tool_name="安装工装",
                    description="将辅助工装插入脚部的插销中",
                    image_path="/static/images/install_foot_tools.jpg"
                ),
                ToolConfirmation(
                    tool_name="摆好手臂",
                    description="手臂自然下垂，摆正两边",
                    image_path="/static/images/adjust_arms.jpg"
                ),
                ToolConfirmation(
                    tool_name="摆正头部",
                    description="头部左右居中，头部都面保持直立",
                    image_path="/static/images/adjust_head.jpg"
                )
            ],
            "arms_only": [
                ToolConfirmation(
                    tool_name="摆好手臂",
                    description="手臂自然下垂，摆正两边",
                    image_path="/static/images/adjust_arms.jpg"
                ),
                ToolConfirmation(
                    tool_name="摆正头部",
                    description="头部左右居中，头部都面保持直立",
                    image_path="/static/images/adjust_head.jpg"
                )
            ],
            "legs_only": [
                ToolConfirmation(
                    tool_name="安装工装",
                    description="将辅助工装插入腿部的插销中",
                    image_path="/static/images/install_leg_tools.jpg"
                ),
                ToolConfirmation(
                    tool_name="安装工装",
                    description="将辅助工装插入脚部的插销中",
                    image_path="/static/images/install_foot_tools.jpg"
                )
            ]
        }
    
    async def start_zero_point_calibration(
        self, 
        robot_id: str, 
        calibration_type: str = "full_body"
    ) -> ZeroPointSession:
        """开始零点标定流程"""
        logger.info(f"开始零点标定: robot_id={robot_id}, calibration_type={calibration_type}")
        
        # 清理已完成或失败的会话
        self._cleanup_finished_sessions()
        
        # 检查是否已有进行中的会话
        for session_id, session in list(self.active_sessions.items()):
            if (session.robot_id == robot_id and 
                session.status in [ZeroPointStatus.IN_PROGRESS, ZeroPointStatus.WAITING_USER]):
                # 检查会话是否已经超时（超过5分钟）
                session_age = (datetime.now() - session.start_time).total_seconds()
                if session_age > 300:  # 5分钟
                    logger.warning(f"会话 {session_id} 已超时（{session_age:.0f}秒），自动清理")
                    session.status = ZeroPointStatus.CANCELLED
                    del self.active_sessions[session_id]
                else:
                    # 如果会话较新，也可以选择强制清理
                    logger.warning(f"会话 {session_id} 存在时间：{session_age:.0f}秒")
                    if session_age > 60:  # 超过1分钟的会话可以考虑清理
                        logger.info(f"强制清理会话 {session_id}")
                        session.status = ZeroPointStatus.CANCELLED
                        del self.active_sessions[session_id]
                    else:
                        raise Exception(f"机器人 {robot_id} 已有正在进行的零点标定任务（会话存在{session_age:.0f}秒）")
        
        # 检查机器人连接状态 - 在模拟器模式下，优先检查SSH服务连接状态，如果失败则跳过检查
        if not ssh_service.use_simulator:
            if not ssh_service.is_connected(robot_id):
                raise Exception(f"机器人 {robot_id} 未连接")
        else:
            # 模拟器模式下，确保模拟器连接状态正确
            if robot_id not in ssh_service.connections:
                logger.warning(f"模拟器中机器人 {robot_id} 未在SSH连接列表中，尝试重新连接")
                # 在模拟器模式下，直接设置连接状态
                ssh_service.connections[robot_id] = "simulator"
                ssh_service.simulator.is_connected = True
        
        # 创建新会话
        session_id = f"zero_point_{robot_id}_{int(datetime.now().timestamp())}"
        
        session = ZeroPointSession(
            session_id=session_id,
            robot_id=robot_id,
            calibration_type=calibration_type,
            current_step=ZeroPointStep.CONFIRM_TOOLS,
            status=ZeroPointStatus.IN_PROGRESS,
            start_time=datetime.now(),
            current_joint_data=[],
            original_joint_data=[],
            step_progress={}
        )
        
        self.active_sessions[session_id] = session
        
        # 初始化步骤1：工具确认
        await self._initialize_tool_confirmation(session)
        
        # 广播状态更新
        await self._broadcast_session_update(session)
        
        return session
    
    async def _initialize_tool_confirmation(self, session: ZeroPointSession):
        """初始化工具确认步骤"""
        session.step_progress["tool_confirmations"] = [
            asdict(tool) for tool in self.tool_confirmations.get(session.calibration_type, [])
        ]
        session.step_progress["all_tools_confirmed"] = False
        
        logger.info(f"会话 {session.session_id} 开始工具确认步骤")
    
    async def confirm_tool(self, session_id: str, tool_index: int) -> bool:
        """确认工具安装"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.CONFIRM_TOOLS:
            raise Exception("当前不在工具确认步骤")
        
        tool_confirmations = session.step_progress.get("tool_confirmations", [])
        if 0 <= tool_index < len(tool_confirmations):
            tool_confirmations[tool_index]["confirmed"] = True
            
            # 检查是否所有工具都已确认
            all_confirmed = all(tool["confirmed"] for tool in tool_confirmations)
            session.step_progress["all_tools_confirmed"] = all_confirmed
            
            await self._broadcast_session_update(session)
            
            if all_confirmed:
                # 自动进入下一步
                await self._proceed_to_read_config(session)
            
            return True
        
        return False
    
    async def _proceed_to_read_config(self, session: ZeroPointSession):
        """进入读取配置步骤"""
        session.current_step = ZeroPointStep.READ_CONFIG
        session.status = ZeroPointStatus.IN_PROGRESS
        session.step_progress["config_loaded"] = False
        
        # 先广播进入步骤2的状态
        await self._broadcast_session_update(session)
        
        # 延迟一下确保前端收到步骤2状态
        await asyncio.sleep(0.3)
        
        try:
            # 清空之前的数据
            session.original_joint_data = []
            session.current_joint_data = []
            
            # 读取当前配置
            if session.calibration_type in ["full_body", "arms_only"]:
                arms_data = await calibration_file_service.read_arms_zero_data(session.robot_id)
                session.original_joint_data.extend(arms_data)
            
            if session.calibration_type in ["full_body", "legs_only"]:
                legs_data = await calibration_file_service.read_legs_offset_data(session.robot_id)
                session.original_joint_data.extend(legs_data)
            
            # 获取当前关节位置
            current_positions = await calibration_file_service.get_current_joint_positions(session.robot_id)
            
            # 更新当前数据
            session.current_joint_data = []
            for joint in session.original_joint_data:
                joint.current_position = current_positions.get(joint.id, 0.0)
                session.current_joint_data.append(joint)
            
            # 数据验证
            warnings = await calibration_file_service.validate_joint_data(session.current_joint_data)
            session.warnings = warnings
            
            session.step_progress["config_loaded"] = True
            session.step_progress["joint_count"] = len(session.current_joint_data)
            session.step_progress["warnings_count"] = len(warnings)
            
            logger.info(f"会话 {session.session_id} 完成配置读取，发现 {len(warnings)} 个警告")
            
            # 广播步骤2的完成状态（带有数据）
            await self._broadcast_session_update(session)
            
            # 延迟更长时间，确保前端有时间处理步骤2的数据
            await asyncio.sleep(1.0)
            
            # 步骤2完成后，自动调用confirm_config_and_proceed进入步骤3
            logger.info(f"会话 {session.session_id} 准备调用confirm_config_and_proceed，当前步骤: {session.current_step.value}")
            await self.confirm_config_and_proceed(session.session_id)
            
        except Exception as e:
            logger.error(f"读取配置失败: {str(e)}", exc_info=True)
            # 检查是否是confirm_config_and_proceed抛出的异常
            if "当前不在配置读取步骤" in str(e):
                logger.warning(f"会话 {session.session_id} 在调用confirm_config_and_proceed时步骤不正确: {session.current_step.value}")
            session.status = ZeroPointStatus.FAILED
            session.error_message = str(e)
            await self._broadcast_session_update(session)
    
    async def confirm_config_and_proceed(self, session_id: str, modified_joints: Optional[List[Dict]] = None) -> bool:
        """确认配置并进入初始化零点步骤"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.READ_CONFIG:
            raise Exception("当前不在配置读取步骤")
        
        try:
            # 如果用户修改了关节数据，应用修改
            if modified_joints:
                joint_dict = {joint.id: joint for joint in session.current_joint_data}
                for mod_joint in modified_joints:
                    joint_id = mod_joint.get("id")
                    if joint_id in joint_dict:
                        if "zero_position" in mod_joint:
                            joint_dict[joint_id].zero_position = float(mod_joint["zero_position"])
                        if "offset" in mod_joint:
                            joint_dict[joint_id].offset = float(mod_joint["offset"])
            
            # 只是更新到步骤3，不立即开始标定
            session.current_step = ZeroPointStep.INITIALIZE_ZERO
            session.status = ZeroPointStatus.IN_PROGRESS
            session.step_progress["ready_to_calibrate"] = True
            
            logger.info(f"会话 {session.session_id} 进入步骤3：准备标定")
            await self._broadcast_session_update(session)
            
            return True
            
        except Exception as e:
            logger.error(f"确认配置失败: {str(e)}")
            session.status = ZeroPointStatus.FAILED
            session.error_message = str(e)
            await self._broadcast_session_update(session)
            return False
    
    async def _proceed_to_initialize_zero(self, session: ZeroPointSession):
        """开始执行标定 - 进入步骤4执行实际标定"""
        # 标定执行应该在步骤4（移除工装）进行，而不是步骤3
        session.current_step = ZeroPointStep.REMOVE_TOOLS
        session.status = ZeroPointStatus.IN_PROGRESS
        
        # 更新步骤进度
        session.step_progress["calibration_started"] = True
        await self._broadcast_session_update(session)
        
        try:
            # 启动标定程序（根据类型选择不同命令）
            if session.calibration_type == "full_body":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true"
            elif session.calibration_type == "arms_only":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true"
            elif session.calibration_type == "legs_only":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_leg:=true"
            else:
                raise Exception(f"不支持的标定类型: {session.calibration_type}")
            
            logger.info(f"会话 {session.session_id} 执行标定命令: {command}")
            
            # 模拟执行标定流程
            if ssh_service.use_simulator:
                await self._simulate_zero_point_process(session)
            else:
                await self._execute_real_zero_point_process(session, command)
            
        except Exception as e:
            logger.error(f"初始化零点失败: {str(e)}")
            session.status = ZeroPointStatus.FAILED
            session.error_message = str(e)
            await self._broadcast_session_update(session)
    
    async def _simulate_zero_point_process(self, session: ZeroPointSession):
        """模拟零点标定流程 - 启动真正的模拟器标定脚本"""
        # 启动模拟器的零点标定脚本
        script_id = ssh_service.simulator.start_calibration_script("zero_point")
        session.step_progress["script_id"] = script_id
        
        logger.info(f"会话 {session.session_id} 启动模拟器标定脚本: {script_id}")
        
        # 监控脚本执行
        while ssh_service.simulator.is_script_running(script_id):
            # 获取脚本输出
            output = ssh_service.simulator.get_script_output(script_id)
            if output:
                lines = output.split('\n')
                for line in lines:
                    if line.strip():
                        # 广播日志到前端
                        await self._broadcast_log(session, line)
                        
                        # 检查并解析Slave位置数据
                        await self._process_calibration_output_line(session, line)
                        
                        # 检查是否需要用户输入
                        if any(prompt in line for prompt in ["(y/N)", "(y/n)", "按 'o'"]):
                            session.status = ZeroPointStatus.WAITING_USER
                            session.step_progress["user_prompt"] = line
                            await self._broadcast_session_update(session)
                            
                            # 等待用户响应
                            await self._wait_for_user_response(session, script_id, line)
                            
                            session.status = ZeroPointStatus.IN_PROGRESS
                            await self._broadcast_session_update(session)
            
            await asyncio.sleep(0.1)
        
        # 脚本执行完成
        logger.info(f"会话 {session.session_id} 标定脚本执行完成")
        
        # 保存标定结果
        await self._save_calibration_results(session)
        
        # 进入最后步骤
        await self._proceed_to_remove_tools(session)
    
    async def _wait_for_user_response(self, session: ZeroPointSession, script_id: str, prompt: str):
        """自动响应用户交互"""
        # 直接自动确认，不等待用户
        await asyncio.sleep(1)  # 短暂延迟模拟响应时间
        
        # 根据不同的提示使用不同的默认响应
        if "stand_robot" in script_id or "站立命令" in prompt:
            default_response = "o"  # 发送站立命令
        elif "save_zero_point" in script_id or "保存" in prompt:
            default_response = "c"  # 确认保存
        else:
            default_response = "y"  # 默认确认
        
        # 发送自动响应到模拟器脚本
        ssh_service.simulator.send_script_input(script_id, default_response)
        await self._broadcast_log(session, f"自动确认: {default_response}")
        logger.info(f"会话 {session.session_id} 自动响应: {default_response}")
    
    async def _broadcast_log(self, session: ZeroPointSession, log_line: str):
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
    
    async def _process_calibration_output_line(self, session: ZeroPointSession, line: str):
        """处理标定输出中的每一行，提取Slave位置数据"""
        try:
            # 使用数据解析器解析Slave位置数据
            positions = calibration_data_parser.parse_slave_positions(line)
            
            if positions:
                # 处理解析到的位置数据
                for pos_data in positions:
                    logger.info(f"会话 {session.session_id} 解析到位置数据: Slave {pos_data.slave_id} = {pos_data.position}")
                    
                    # 更新会话中的关节数据
                    await self._update_joint_position_data(session, pos_data)
                    
                    # 广播位置数据更新
                    await self._broadcast_position_data(session, pos_data)
            
            # 检查是否有重要的标定状态信息
            self._check_calibration_status_keywords(session, line)
            
        except Exception as e:
            logger.warning(f"处理标定输出行时出错: {line} - {str(e)}")
    
    async def _update_joint_position_data(self, session: ZeroPointSession, pos_data):
        """更新会话中的关节位置数据"""
        # 查找对应的关节数据并更新当前位置
        for joint in session.current_joint_data:
            if joint.id == pos_data.slave_id:
                # 更新当前位置为实际测量的位置
                joint.current_position = pos_data.position
                # 如果这是标定过程的结果，也可以更新偏移值
                joint.offset = pos_data.position - joint.zero_position
                logger.debug(f"更新关节 {joint.name} (ID:{joint.id}) 位置: {pos_data.position}")
                return
        
        # 如果找不到对应的关节，创建新的关节数据
        from app.services.calibration_file_service import JointData
        new_joint = JointData(
            id=pos_data.slave_id,
            name=pos_data.joint_name or f"joint_{pos_data.slave_id:02d}",
            current_position=pos_data.position,
            zero_position=0.0,
            offset=pos_data.position,
            status="normal"
        )
        session.current_joint_data.append(new_joint)
        logger.info(f"创建新关节数据: {new_joint.name} (ID:{new_joint.id})")
    
    async def _broadcast_position_data(self, session: ZeroPointSession, pos_data):
        """广播位置数据更新"""
        message = {
            "type": "slave_position_update",
            "data": {
                "session_id": session.session_id,
                "robot_id": session.robot_id,
                "slave_id": pos_data.slave_id,
                "position": pos_data.position,
                "joint_name": pos_data.joint_name,
                "raw_line": pos_data.raw_line
            }
        }
        await connection_manager.send_to_robot_subscribers(session.robot_id, message)
    
    def _check_calibration_status_keywords(self, session: ZeroPointSession, line: str):
        """检查标定状态关键词"""
        line_lower = line.lower()
        
        # 检查标定完成状态
        if any(keyword in line_lower for keyword in [
            "calibration complete", "标定完成", "校准完成",
            "calibration finished", "calibration done"
        ]):
            session.step_progress["calibration_status"] = "completed"
            logger.info(f"会话 {session.session_id} 检测到标定完成")
        
        # 检查标定失败状态
        elif any(keyword in line_lower for keyword in [
            "calibration failed", "标定失败", "校准失败",
            "calibration error", "error in calibration"
        ]):
            session.step_progress["calibration_status"] = "failed"
            logger.warning(f"会话 {session.session_id} 检测到标定失败")
        
        # 检查警告信息
        elif any(keyword in line_lower for keyword in [
            "warning", "警告", "warn", "caution"
        ]):
            if "calibration_warnings" not in session.step_progress:
                session.step_progress["calibration_warnings"] = []
            session.step_progress["calibration_warnings"].append(line.strip())
            logger.warning(f"会话 {session.session_id} 检测到警告: {line.strip()}")
    
    async def get_calibration_summary(self, session_id: str) -> dict:
        """获取标定结果汇总"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        # 收集所有的日志输出用于解析
        all_output = "\n".join(session.step_progress.get("calibration_logs", []))
        
        # 使用解析器获取汇总信息
        summary = calibration_data_parser.parse_calibration_summary(all_output)
        
        # 验证数据完整性
        positions = calibration_data_parser.parse_slave_positions(all_output)
        is_valid, validation_messages = calibration_data_parser.validate_position_data(positions)
        
        # 组合汇总结果
        result = {
            "session_id": session_id,
            "calibration_type": session.calibration_type,
            "current_step": session.current_step.value,
            "status": session.status.value,
            "summary": summary,
            "validation": {
                "is_valid": is_valid,
                "messages": validation_messages
            },
            "joint_count": len(session.current_joint_data),
            "position_data_count": len(positions),
            "step_progress": session.step_progress
        }
        
        return result
    
    async def _execute_real_zero_point_process(self, session: ZeroPointSession, command: str):
        """执行真实零点标定流程"""
        try:
            logger.info(f"会话 {session.session_id} 开始执行真实零点标定")
            
            # 创建输出回调函数
            async def output_callback(output: str):
                if not output:
                    return
                
                lines = output.split('\n')
                for line in lines:
                    if line.strip():
                        # 广播日志到前端
                        await self._broadcast_log(session, line)
                        
                        # 检查并解析Slave位置数据
                        await self._process_calibration_output_line(session, line)
                        
                        # 检查是否需要用户输入
                        if any(prompt in line.lower() for prompt in ["(y/n)", "按 'o'", "press 'o'", "输入", "input", "按下'o'", "按o键"]):
                            await self._broadcast_log(session, f"检测到交互提示: {line}")
                            await self._broadcast_log(session, "自动进行确认...")
                            
                            # 记录提示信息供自动响应使用
                            session.step_progress["last_prompt"] = line
                            session.step_progress["auto_response"] = True
                            await self._broadcast_session_update(session)
                            
                            # 直接自动响应，不需要等待
                            asyncio.create_task(self._wait_for_user_response_real(session))
            
            # 使用交互式命令执行
            session_id = f"calibration_{session.session_id}"
            success, error = await ssh_service.execute_command_interactive(
                session.robot_id,
                command,
                output_callback,
                session_id
            )
            
            if not success:
                raise Exception(f"标定命令执行失败: {error}")
            
            # 标定完成
            logger.info(f"会话 {session.session_id} 零点标定执行完成")
            
            # 保存标定结果
            await self._save_calibration_results(session)
            
            # 进入最后步骤
            await self._proceed_to_remove_tools(session)
            
        except Exception as e:
            logger.error(f"执行真实零点标定失败: {str(e)}", exc_info=True)
            session.status = ZeroPointStatus.FAILED
            session.error_message = str(e)
            await self._broadcast_session_update(session)
            
            # 清理进程
            if not ssh_service.use_simulator:
                await ssh_service.cleanup_calibration_processes(session.robot_id)
            
            raise
    
    async def _wait_for_user_response_real(self, session: ZeroPointSession):
        """自动响应用户交互（真实模式）"""
        # 短暂延迟后自动发送响应
        await asyncio.sleep(2)  # 给系统一些时间准备
        
        # 根据当前上下文确定响应
        if "等待按键" in session.step_progress.get("last_prompt", "") or "press" in session.step_progress.get("last_prompt", "").lower():
            default_response = "o"  # 站立命令
        elif "确认" in session.step_progress.get("last_prompt", "") or "save" in session.step_progress.get("last_prompt", "").lower():
            default_response = "c"  # 确认保存
        else:
            default_response = "y"  # 默认确认
        
        # 发送到交互式会话
        session_id = f"calibration_{session.session_id}"
        await ssh_service.send_input_to_session(session_id, default_response + "\n")
        await self._broadcast_log(session, f"自动响应: {default_response}")
        logger.info(f"会话 {session.session_id} 自动发送响应: {default_response}")
    
    async def _save_calibration_results(self, session: ZeroPointSession):
        """保存标定结果"""
        try:
            if session.calibration_type in ["full_body", "arms_only"]:
                # 过滤手臂数据
                arms_data = [joint for joint in session.current_joint_data if joint.id <= 14]
                success = await calibration_file_service.write_arms_zero_data(session.robot_id, arms_data)
                if not success:
                    raise Exception("保存手臂零点数据失败")
            
            if session.calibration_type in ["full_body", "legs_only"]:
                # 过滤腿部数据
                legs_data = [joint for joint in session.current_joint_data if joint.id <= 14]
                success = await calibration_file_service.write_legs_offset_data(session.robot_id, legs_data)
                if not success:
                    raise Exception("保存腿部偏移数据失败")
            
            session.step_progress["calibration_saved"] = True
            logger.info(f"会话 {session.session_id} 标定结果保存成功")
            
        except Exception as e:
            logger.error(f"保存标定结果失败: {str(e)}")
            raise
    
    async def _proceed_to_remove_tools(self, session: ZeroPointSession):
        """进入移除工装步骤"""
        session.current_step = ZeroPointStep.REMOVE_TOOLS
        session.status = ZeroPointStatus.WAITING_USER
        
        session.step_progress["calibration_completed"] = True
        session.step_progress["ready_to_remove_tools"] = True
        
        logger.info(f"会话 {session.session_id} 标定完成，等待移除工装")
        await self._broadcast_session_update(session)
    
    async def confirm_tools_removed(self, session_id: str) -> bool:
        """确认工装已移除"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.REMOVE_TOOLS:
            raise Exception("当前不在移除工装步骤")
        
        # 完成标定
        session.status = ZeroPointStatus.COMPLETED
        session.step_progress["tools_removed"] = True
        session.step_progress["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"会话 {session.session_id} 零点标定完成")
        await self._broadcast_session_update(session)
        
        return True
    
    async def start_calibration_execution(self, session_id: str) -> bool:
        """开始执行标定（在步骤3点击一键标零时调用）"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.INITIALIZE_ZERO:
            raise Exception("当前不在初始化零点步骤")
        
        # 开始执行标定
        await self._proceed_to_initialize_zero(session)
        
        return True
    
    async def send_user_response(self, session_id: str, response: str) -> bool:
        """发送用户响应"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.status != ZeroPointStatus.WAITING_USER:
            raise Exception("当前不在等待用户响应状态")
        
        # 设置用户响应
        session.user_response = response
        
        # 触发响应事件
        if hasattr(session, 'user_response_event'):
            session.user_response_event.set()
        
        logger.info(f"会话 {session.session_id} 收到用户响应: {response}")
        
        return True
    
    async def cancel_calibration(self, session_id: str) -> bool:
        """取消标定"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        session.status = ZeroPointStatus.CANCELLED
        logger.info(f"会话 {session.session_id} 已取消")
        
        # 取消交互式会话
        if not ssh_service.use_simulator:
            interactive_session_id = f"calibration_{session.session_id}"
            await ssh_service.cancel_interactive_session(interactive_session_id)
            
            # 清理所有标定相关进程
            await ssh_service.cleanup_calibration_processes(session.robot_id)
        
        await self._broadcast_session_update(session)
        
        return True
    
    async def get_session(self, session_id: str) -> Optional[ZeroPointSession]:
        """获取会话"""
        return self.active_sessions.get(session_id)
    
    async def get_robot_session(self, robot_id: str) -> Optional[ZeroPointSession]:
        """获取机器人的当前会话"""
        for session in self.active_sessions.values():
            if session.robot_id == robot_id and session.status in [
                ZeroPointStatus.IN_PROGRESS, 
                ZeroPointStatus.WAITING_USER
            ]:
                return session
        return None
    
    async def execute_calibration_command(self, session_id: str, calibration_mode: str, command: str = None) -> bool:
        """执行标定命令（一键标零）- 启动机器人控制系统并等待用户交互"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.INITIALIZE_ZERO:
            raise Exception("只能在初始化零点步骤执行标定")
        
        # 根据模式选择正确的roslaunch命令
        if not command:
            if calibration_mode == "full_body":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_leg:=true cali_arm:=true"
            elif calibration_mode == "arms_only":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true"
            elif calibration_mode == "legs_only":
                command = "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_leg:=true"
            else:
                raise Exception(f"不支持的标定模式: {calibration_mode}")
        
        logger.info(f"会话 {session.session_id} 执行标定命令: {command}")
        session.step_progress["calibration_command"] = command
        session.step_progress["calibration_mode"] = calibration_mode
        
        # 广播开始信息
        await self._broadcast_log(session, f"🚀 启动{calibration_mode}标定系统...")
        await self._broadcast_log(session, f"执行命令: {command}")
        
        # 在模拟器中执行
        if ssh_service.use_simulator:
            # 模拟完整的标定流程，包括用户交互
            await self._simulate_full_calibration_process(session, calibration_mode, command)
        else:
            # 真实执行roslaunch命令
            await self._execute_real_calibration_process(session, command)
        
        await self._broadcast_session_update(session)
        return True
    
    async def _simulate_full_calibration_process(self, session: ZeroPointSession, calibration_mode: str, command: str):
        """模拟完整的标定流程，包括用户交互"""
        # 1. 模拟系统启动
        await self._broadcast_log(session, "正在启动机器人控制系统...")
        await asyncio.sleep(2)
        await self._broadcast_log(session, "机器人控制系统已启动")
        await asyncio.sleep(1)
        
        # 2. 模拟机器人缩腿
        await self._broadcast_log(session, "机器人开始缩腿动作...")
        await asyncio.sleep(3)
        await self._broadcast_log(session, "机器人缩腿完成")
        
        # 3. 自动发送站立命令
        await self._broadcast_log(session, "")
        await self._broadcast_log(session, "✅ 自动确认机器人缩腿完成")
        await self._broadcast_log(session, "自动发送站立命令 'o'")
        
        # 不设置等待状态，直接处理
        session.step_progress["user_prompt"] = "自动确认并发送站立命令"
        await self._broadcast_session_update(session)
        
        # 自动响应
        await self._wait_for_user_response(session, "stand_robot", "确认机器人状态")
        
        # 4. 发送站立命令
        session.status = ZeroPointStatus.IN_PROGRESS
        await self._broadcast_log(session, "发送站立命令 'o' 到机器人...")
        await asyncio.sleep(2)
        await self._broadcast_log(session, "机器人开始站立...")
        await asyncio.sleep(5)
        await self._broadcast_log(session, "机器人站立完成")
        
        # 5. 显示关节位置信息
        await self._broadcast_log(session, "")
        await self._broadcast_log(session, "读取当前关节位置...")
        await asyncio.sleep(2)
        
        if calibration_mode == "full_body":
            # 模拟显示真实的关节位置数据
            calibration_values = [
                (9.6946716, 63535.0, 39.6),
                (3.9207458, 14275.0, 11.79),
                (12.5216674, 45590.0, 42.43),
                (-37.2605896, -244191.0, 42.43),
                (15.8138275, 207275.0, 8.49),
                (-2.7354431, -35854.0, 8.49),
                (5.8642578, 38432.0, 39.6),
                (-16.8491821, -61346.0, 11.79),
                (-18.9975585, -69168.0, 42.43),
                (-64.5283508, -422893.0, 42.43),
                (-31.0607147, -407119.0, 8.49),
                (49.7427368, 651988.0, 8.49),
                (26.8544311, 97774.0, 14.99),
                (-19.9171142, -72516.0, 14.99)
            ]
            
            # 更新会话中的关节数据，保存标定后的位置值
            for i, (position, encoder, current) in enumerate(calibration_values, 1):
                await self._broadcast_log(session, f"000000{3040+i*10}1: Slave {i} actual position {position:.7f},Encoder {encoder:.7f}")
                await asyncio.sleep(0.1)
                await self._broadcast_log(session, f"000000{3040+i*10+1}1: Rated current {current:.7f}")
                await asyncio.sleep(0.1)
                
                # 更新关节数据中的当前位置（这将成为新的零点）
                for joint in session.current_joint_data:
                    if joint.id == i:
                        joint.current_position = position
                        break
        
        # 6. 自动确认保存零点
        await self._broadcast_log(session, "")
        await self._broadcast_log(session, "✅ 零点校准完成")
        await self._broadcast_log(session, "自动保存当前位置作为零点")
        
        # 不设置等待状态
        session.step_progress["user_prompt"] = "自动确认保存零点"
        await self._broadcast_session_update(session)
        
        # 自动响应
        await self._wait_for_user_response(session, "save_zero_point", "确认保存零点")
        
        # 7. 保存零点数据
        session.status = ZeroPointStatus.IN_PROGRESS
        await self._broadcast_log(session, "保存零点数据到配置文件...")
        await asyncio.sleep(1)
        await self._broadcast_log(session, "零点数据已保存到 ~/.config/lejuconfig/offset.csv")
        await self._broadcast_log(session, " 标定完成！")
        
        # 更新会话状态 - 标定完成后进入步骤4显示结果
        session.current_step = ZeroPointStep.REMOVE_TOOLS  # 进入步骤4
        session.step_progress["calibration_completed"] = True
        await self._broadcast_session_update(session)
    
    async def _execute_real_calibration_process(self, session: ZeroPointSession, command: str):
        """执行真实的标定流程"""
        try:
            # 执行roslaunch命令
            await self._broadcast_log(session, f"执行命令: {command}")
            success, stdout, stderr = await ssh_service.execute_command(session.robot_id, command)
            
            if not success:
                raise Exception(f"标定命令执行失败: {stderr}")
            
            # 处理标定输出
            if stdout:
                lines = stdout.split('\n')
                for line in lines:
                    if line.strip():
                        await self._broadcast_log(session, line)
                        
                        # 检查并解析Slave位置数据
                        await self._process_calibration_output_line(session, line)
                        
                        # 检查是否需要用户输入
                        if any(prompt in line.lower() for prompt in ["按", "press", "input", "输入"]):
                            await self._broadcast_log(session, f"检测到交互提示: {line}")
                            await self._broadcast_log(session, "自动进行确认...")
                            
                            # 记录提示信息
                            session.step_progress["user_prompt"] = line
                            session.step_progress["last_prompt"] = line
                            session.step_progress["auto_response"] = True
                            await self._broadcast_session_update(session)
                            
                            # 自动响应
                            await self._wait_for_user_response(session, "user_input", line)
            
            # 更新会话状态
            session.step_progress["calibration_completed"] = True
            await self._broadcast_session_update(session)
            
        except Exception as e:
            logger.error(f"执行真实标定失败: {str(e)}")
            raise
    
    async def _execute_real_calibration(self, session: ZeroPointSession, command: str):
        """执行真实标定"""
        # 执行真实的标定命令
        success, stdout, stderr = await ssh_service.execute_command(session.robot_id, command)
        
        if not success:
            raise Exception(f"标定命令执行失败: {stderr}")
        
        # 处理标定输出
        if stdout:
            lines = stdout.split('\n')
            for line in lines:
                if line.strip():
                    await self._broadcast_log(session, line)
                    
                    # 检查并解析Slave位置数据
                    await self._process_calibration_output_line(session, line)
        
        # 更新会话状态
        session.step_progress["calibration_completed"] = True
    
    async def save_zero_point_data(self, session_id: str) -> bool:
        """保存零点数据到配置文件"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.REMOVE_TOOLS:
            raise Exception("只能在移除工装步骤保存零点")
        
        logger.info(f"会话 {session.session_id} 保存零点数据")
        
        # 保存到配置文件
        try:
            # 根据标定类型保存对应的数据
            if session.calibration_type in ["full_body", "arms_only"]:
                # 保存手臂零点数据到 arms_zero.yaml
                arms_data = [j for j in session.current_joint_data if 2 <= j.id <= 15]  # 手臂关节 2-15
                if arms_data:
                    await calibration_file_service.write_arms_zero_data(session.robot_id, arms_data)
                    await self._broadcast_log(session, " 手臂零点数据已保存到 ~/.config/lejuconfig/arms_zero.yaml")
            
            if session.calibration_type in ["full_body", "legs_only"]:
                # 保存腿部偏移数据到 offset.csv
                # 注意：这里保存的是从标定中获取的实际位置值（actual position）
                legs_data = [j for j in session.current_joint_data if 1 <= j.id <= 14]  # 腿部关节 1-14
                if legs_data:
                    # 使用实际位置作为偏移值保存到 offset.csv
                    for joint in legs_data:
                        # 将 actual position 值作为偏移量
                        joint.offset = joint.current_position
                    
                    await calibration_file_service.write_legs_offset_data(session.robot_id, legs_data)
                    await self._broadcast_log(session, " 腿部零点数据已保存到 ~/.config/lejuconfig/offset.csv")
            
            await self._broadcast_log(session, " 所有零点数据已保存到配置文件")
            
            # 标记为完成
            session.status = ZeroPointStatus.COMPLETED
            await self._broadcast_session_update(session)
            
            return True
            
        except Exception as e:
            logger.error(f"保存零点数据失败: {str(e)}")
            raise
    
    async def validate_calibration(self, session_id: str) -> bool:
        """执行标定验证（运行roslaunch使机器人缩腿）"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        if session.current_step != ZeroPointStep.REMOVE_TOOLS:
            raise Exception("只能在移除工装步骤执行验证")
        
        try:
            validation_command = "roslaunch humanoid_controllers load_kuavo_real.launch"
            logger.info(f"会话 {session.session_id} 执行验证命令: {validation_command}")
            
            await self._broadcast_log(session, f"🚀 执行验证命令: {validation_command}")
            await self._broadcast_log(session, "⚠️ 注意：机器人将进行缩腿动作，请确保周围环境安全！")
            
            if ssh_service.use_simulator:
                # 模拟验证过程
                await asyncio.sleep(2)
                await self._broadcast_log(session, "正在启动机器人控制系统...")
                await asyncio.sleep(1)
                await self._broadcast_log(session, "机器人开始缩腿...")
                await asyncio.sleep(2)
                await self._broadcast_log(session, " 验证完成，机器人已进入零点位置")
            else:
                # 真实执行
                success, stdout, stderr = await ssh_service.execute_command(session.robot_id, validation_command)
                if not success:
                    raise Exception(f"验证命令执行失败: {stderr}")
            
            session.step_progress["validation_completed"] = True
            await self._broadcast_session_update(session)
            return True
            
        except Exception as e:
            logger.error(f"执行验证失败: {str(e)}")
            raise
    
    async def go_to_step(self, session_id: str, target_step: ZeroPointStep) -> bool:
        """跳转到指定步骤"""
        session = self.active_sessions.get(session_id)
        if not session:
            raise Exception("会话不存在")
        
        logger.info(f"会话 {session.session_id} 请求跳转到步骤 {target_step.value}")
        
        # 如果是返回步骤2，需要重新加载配置
        if target_step == ZeroPointStep.READ_CONFIG:
            # 清空之前的数据
            session.original_joint_data = []
            session.current_joint_data = []
            session.warnings = []
            # 只清除部分进度，保留一些必要的状态
            session.step_progress.pop("config_loaded", None)
            session.step_progress.pop("joint_count", None)
            session.step_progress.pop("warnings_count", None)
            session.step_progress.pop("ready_to_calibrate", None)
            # 重新执行步骤2的逻辑
            await self._proceed_to_read_config(session)
        else:
            # 其他步骤只更新状态
            session.current_step = target_step
            session.status = ZeroPointStatus.IN_PROGRESS
            await self._broadcast_session_update(session)
        
        return True
    
    def _cleanup_finished_sessions(self):
        """清理已完成或失败的会话"""
        finished_sessions = []
        for session_id, session in self.active_sessions.items():
            if session.status in [ZeroPointStatus.COMPLETED, ZeroPointStatus.FAILED, ZeroPointStatus.CANCELLED]:
                finished_sessions.append(session_id)
        
        for session_id in finished_sessions:
            logger.info(f"清理已完成的会话: {session_id}")
            del self.active_sessions[session_id]
    
    async def _broadcast_session_update(self, session: ZeroPointSession):
        """广播会话状态更新"""
        message = {
            "type": "zero_point_calibration_update",
            "data": {
                "session_id": session.session_id,
                "robot_id": session.robot_id,
                "calibration_type": session.calibration_type,
                "current_step": session.current_step.value,
                "status": session.status.value,
                "step_progress": session.step_progress,
                "warnings": session.warnings,
                "error_message": session.error_message,
                "joint_data_count": len(session.current_joint_data)
            }
        }
        await connection_manager.send_to_robot_subscribers(session.robot_id, message)


# 全局零点标定服务实例
zero_point_calibration_service = ZeroPointCalibrationService()