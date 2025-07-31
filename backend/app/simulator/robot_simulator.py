import asyncio
import random
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading
import queue
from .mock_config_files import get_mock_arms_zero_yaml, get_mock_offset_csv


class RobotSimulator:
    """机器人模拟器，用于测试标定功能"""
    
    def __init__(self):
        self.is_connected = False
        self.is_upper_connected = False  # 上位机连接状态
        self.robot_info = {
            "model": "Kuavo 4 pro",
            "sn": "SIM123456789",
            "end_effector": "灵巧手",
            "version": "1.2.3-sim"
        }
        self.upper_info = {
            "model": "Upper Computer",
            "python_version": "3.8.10",
            "opencv_version": "4.5.2",
            "apriltag_available": True
        }
        self.processes = {}
        self.running_scripts = {}
        
    def connect(self, host: str, port: int, username: str, password: str) -> tuple[bool, Optional[str]]:
        """模拟SSH连接"""
        # 移除阻塞的sleep，改为立即返回
        # 如果需要模拟延迟，应该在调用方使用asyncio.sleep
        
        # 模拟验证
        if password == "wrong_password":
            return False, "认证失败，请检查用户名和密码"
        
        if host == "unreachable.host":
            return False, "连接超时"
        
        self.is_connected = True
        return True, None
    
    def disconnect(self) -> bool:
        """模拟断开机器人连接"""
        self.is_connected = False
        # 停止所有运行的脚本
        for script_id in list(self.running_scripts.keys()):
            self.stop_script(script_id)
        return True
    
    def connect_upper_computer(self, host: str, port: int, username: str, password: str) -> tuple[bool, Optional[str]]:
        """模拟上位机SSH连接"""
        # 模拟验证
        if password == "wrong_password":
            return False, "上位机认证失败，请检查用户名和密码"
        
        if host == "unreachable.host":
            return False, "上位机连接超时"
        
        # 模拟检查上位机状态
        if host != "192.168.26.1" and not host.startswith("192.168.26."):
            return False, "上位机IP地址不在预期范围内"
        
        self.is_upper_connected = True
        return True, None
    
    def disconnect_upper_computer(self) -> bool:
        """模拟断开上位机连接"""
        self.is_upper_connected = False
        return True
    
    def execute_command(self, command: str) -> tuple[bool, str, str]:
        """模拟在机器人执行命令"""
        if not self.is_connected:
            return False, "", "未连接"
        
        # 模拟不同命令的响应
        if "cat /etc/robot_info.json" in command:
            return True, json.dumps(self.robot_info), ""
        
        elif "rosversion" in command:
            return True, "1.2.3-sim", ""
        
        elif "echo $ROBOT_VERSION" in command:
            return True, "45", ""
        
        # 模拟读取零点配置文件
        elif "cat" in command and "arms_zero.yaml" in command:
            return True, get_mock_arms_zero_yaml(), ""
        
        elif "cat" in command and "offset.csv" in command:
            return True, get_mock_offset_csv(), ""
        
        # 模拟文件存在检查
        elif "test -f" in command and "arms_zero.yaml" in command:
            return True, "ok", ""
        
        elif "test -f" in command and "offset.csv" in command:
            return True, "ok", ""
        
        # 模拟创建目录
        elif "mkdir -p" in command:
            return True, "", ""
        
        # 模拟文件写入
        elif "cat >" in command or "mv" in command:
            return True, "", ""
        
        # === 头手标定环境检查命令支持 ===
        
        # 1. sudo权限检查
        elif "sudo -n true" in command:
            return True, "ok", ""
        
        # 2. roscore检查
        elif "which roscore" in command:
            return True, "/opt/ros/noetic/bin/roscore", ""
        
        # 3. 虚拟环境检查
        elif "test -d /home/lab/kuavo_venv/joint_cali" in command:
            return True, "exists", ""
        
        # 4. 相机设备检查
        elif "ls /dev/video*" in command and "wc -l" in command:
            return True, "2", ""  # 模拟有2个相机设备
        
        # 5. AprilTag配置文件检查  
        elif "test -f" in command and "tags.yaml" in command:
            return True, "exists", ""
        
        # 6. rosbag文件检查
        elif "ls" in command and "hand_move_demo_*.bag" in command and "wc -l" in command:
            return True, "2", ""  # 模拟有2个bag文件 (left, right)
        
        # 7. 头手标定备份文件检查
        elif "ls" in command and "arms_zero.yaml*.bak" in command:
            return True, "/home/lab/.config/lejuconfig/arms_zero.yaml.head_cali.bak", ""
        
        # 8. 文件时间戳检查
        elif "stat -c %y" in command and "head_cali.bak" in command:
            return True, "2024-01-30 15:30:45.123456789 +0800", ""
        
        # 9. expect工具检查和安装
        elif "which expect" in command:
            return True, "/usr/bin/expect", ""
        elif "apt-get update" in command and "apt-get install" in command and "expect" in command:
            return True, "expect installed successfully", ""
        
        else:
            return True, f"Robot command executed: {command}", ""
    
    def execute_upper_command(self, command: str) -> tuple[bool, str, str]:
        """模拟在上位机执行命令"""
        if not self.is_upper_connected:
            return False, "", "上位机未连接"
        
        # 模拟上位机命令响应
        if "python3 --version" in command:
            return True, "Python 3.8.10", ""
        
        elif "which python3" in command:
            return True, "/usr/bin/python3", ""
        
        elif "pip list | grep opencv" in command:
            return True, "opencv-python                  4.5.2.54", ""
        
        elif "pip list | grep apriltag" in command:
            return True, "apriltag                      3.1.4", ""
        
        elif "ls -la /dev/video*" in command:
            return True, "crw-rw----+ 1 root video 81, 0 Jan 30 10:00 /dev/video0\ncrw-rw----+ 1 root video 81, 1 Jan 30 10:00 /dev/video1", ""
        
        elif "nvidia-smi" in command:
            return True, "NVIDIA-SMI 470.86       Driver Version: 470.86       CUDA Version: 11.4", ""
        
        elif "rosrun apriltag_detection apriltag_detector.py" in command:
            return True, "AprilTag detector started successfully", ""
        
        elif "pkill -f apriltag" in command:
            return True, "AprilTag processes terminated", ""
        
        else:
            return True, f"Upper computer command executed: {command}", ""
    
    def start_calibration_script(self, script_type: str) -> str:
        """启动标定脚本"""
        script_id = f"{script_type}_{int(time.time())}"
        
        if script_type == "zero_point":
            script = ZeroPointCalibrationScript()
        elif script_type == "head_hand":
            script = HeadHandCalibrationScript()
        else:
            raise ValueError(f"Unknown script type: {script_type}")
        
        self.running_scripts[script_id] = script
        
        # 启动脚本线程
        thread = threading.Thread(target=script.run, daemon=True)
        thread.start()
        
        return script_id
    
    def get_script_output(self, script_id: str) -> Optional[str]:
        """获取脚本输出"""
        if script_id in self.running_scripts:
            return self.running_scripts[script_id].get_output()
        return None
    
    def send_script_input(self, script_id: str, input_data: str):
        """发送输入到脚本"""
        if script_id in self.running_scripts:
            self.running_scripts[script_id].send_input(input_data)
    
    def stop_script(self, script_id: str):
        """停止脚本"""
        if script_id in self.running_scripts:
            self.running_scripts[script_id].stop()
            del self.running_scripts[script_id]
    
    def is_script_running(self, script_id: str) -> bool:
        """检查脚本是否在运行"""
        return script_id in self.running_scripts and self.running_scripts[script_id].is_running


class CalibrationScript:
    """标定脚本基类"""
    
    def __init__(self):
        self.output_buffer = []
        self.input_queue = queue.Queue()  # 使用线程安全的队列
        self.is_running = False
        self.current_step = 0
        self._lock = threading.Lock()
        self._loop = None
        self._async_queue = None
        
    def run(self):
        """运行脚本的主循环"""
        self.is_running = True
        asyncio.run(self._run_with_queue())
        
    async def _run_with_queue(self):
        """创建异步队列并运行"""
        self._async_queue = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        
        # 启动一个任务来从线程安全队列转移到异步队列
        transfer_task = asyncio.create_task(self._transfer_input())
        
        try:
            await self._async_run()
        finally:
            transfer_task.cancel()
            
    async def _transfer_input(self):
        """从线程安全队列转移输入到异步队列"""
        while self.is_running:
            try:
                # 非阻塞地检查输入
                input_data = self.input_queue.get_nowait()
                await self._async_queue.put(input_data)
            except queue.Empty:
                await asyncio.sleep(0.1)
                
    async def _async_run(self):
        """异步运行逻辑，子类需要实现"""
        raise NotImplementedError
        
    def get_output(self) -> Optional[str]:
        """获取并清空输出缓冲区"""
        with self._lock:
            if self.output_buffer:
                output = "\n".join(self.output_buffer)
                self.output_buffer = []
                return output
        return None
    
    def send_input(self, input_data: str):
        """发送输入"""
        self.input_queue.put(input_data)
    
    def stop(self):
        """停止脚本"""
        self.is_running = False
        
    def _write_output(self, text: str):
        """写入输出"""
        with self._lock:
            # 按行分割并添加
            lines = text.split('\n')
            for line in lines:
                if line:  # 忽略空行
                    self.output_buffer.append(line)
    
    async def _wait_for_input(self, timeout: float = 300) -> str:
        """等待用户输入"""
        try:
            # 使用 asyncio 的超时机制
            return await asyncio.wait_for(self._async_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            self._write_output("\n等待输入超时")
            return ""


class ZeroPointCalibrationScript(CalibrationScript):
    """零点标定脚本模拟"""
    
    async def _async_run(self):
        """模拟零点标定流程"""
        # 步骤1：启动提示
        self._write_output("===========================================")
        self._write_output("       机器人零点标定程序")
        self._write_output("===========================================")
        await asyncio.sleep(1)
        
        # 步骤2：询问是否启动控制系统
        self._write_output("检查机器人状态...")
        await asyncio.sleep(2)
        self._write_output("是否启动机器人控制系统？(y/N): ")
        
        # 等待用户输入
        response = await self._wait_for_input()
        if response.lower() != 'y':
            self._write_output("用户取消操作")
            self.is_running = False
            return
        
        # 步骤3：启动控制系统
        self._write_output("正在启动机器人控制系统...")
        for i in range(5):
            self._write_output(f"初始化子系统 {i+1}/5...")
            await asyncio.sleep(0.5)
        
        # 步骤4：电机使能
        self._write_output("\n开始使能电机...")
        await asyncio.sleep(1)
        
        # 模拟完整的电机位置输出
        slave_positions = [
            (1, 9.6946716, 63535.0, 39.6),
            (2, 3.9207458, 14275.0, 11.79),
            (3, 12.5216674, 45590.0, 42.43),
            (4, -37.2605896, -244191.0, 42.43),
            (5, 15.8138275, 207275.0, 8.49),
            (6, -2.7354431, -35854.0, 8.49),
            (7, 5.8642578, 38432.0, 39.6),
            (8, -16.8491821, -61346.0, 11.79),
            (9, -18.9975585, -69168.0, 42.43),
            (10, -64.5283508, -422893.0, 42.43),
            (11, -31.0607147, -407119.0, 8.49),
            (12, 49.7427368, 651988.0, 8.49),
            (13, 26.8544311, 97774.0, 14.99),
            (14, -19.9171142, -72516.0, 14.99)
        ]
        
        for slave_id, position, encoder, current in slave_positions:
            timestamp = 3040 + slave_id * 10
            self._write_output(f"{timestamp:010d}1: Slave {slave_id:02d} actual position {position:.7f},Encoder {encoder:.7f}")
            await asyncio.sleep(0.1)
            self._write_output(f"{timestamp+5:010d}1: Rated current {current:.7f}")
            await asyncio.sleep(0.1)
        
        await asyncio.sleep(1)
        
        # 步骤5：等待按o启动
        self._write_output("\n电机使能完成！")
        self._write_output("按 'o' 启动机器人（进入站立状态）: ")
        
        response = await self._wait_for_input()
        if response.lower() != 'o':
            self._write_output("未按o，退出程序")
            self.is_running = False
            return
        
        # 步骤6：机器人站立
        self._write_output("机器人开始站立...")
        for i in range(3):
            self._write_output(f"站立进度: {(i+1)*33}%")
            await asyncio.sleep(1)
        self._write_output("机器人站立完成！")
        
        # 步骤7：询问是否开始标定
        await asyncio.sleep(1)
        self._write_output("\n是否开始标定？(y/n): ")
        
        response = await self._wait_for_input()
        if response.lower() != 'y':
            self._write_output("用户取消标定")
            self.is_running = False
            return
        
        # 步骤8：执行标定
        self._write_output("\n开始执行标定...")
        self._write_output("请确认机器人关节已摆放到零位")
        await asyncio.sleep(2)
        
        self._write_output("正在读取当前关节位置...")
        await asyncio.sleep(1)
        
        self._write_output("标定数据：")
        for i in range(14):
            position = random.uniform(-10, 10)
            self._write_output(f"关节{i+1}: {position:.6f}")
        
        # 步骤9：确认保存
        await asyncio.sleep(1)
        self._write_output("\n请确认标定数据是否正确？(y/n): ")
        
        response = await self._wait_for_input()
        if response.lower() != 'y':
            self._write_output("标定取消")
            self.is_running = False
            return
        
        # 步骤10：保存标定结果
        self._write_output("\n是否保存标定结果？(y/n): ")
        
        response = await self._wait_for_input()
        if response.lower() == 'y':
            self._write_output("正在保存标定数据到 ~/.config/lejuconfig/offset.csv...")
            await asyncio.sleep(1)
            self._write_output("标定数据保存成功！")
            self._write_output("\n零点标定完成！")
        else:
            self._write_output("未保存标定数据")
        
        self.is_running = False


class HeadHandCalibrationScript(CalibrationScript):
    """头手标定脚本模拟"""
    
    async def _async_run(self):
        """模拟头手标定流程"""
        # 步骤1：启动提示
        self._write_output("===========================================================")
        self._write_output("           机器人关节标定一键启动脚本")
        self._write_output("===========================================================")
        await asyncio.sleep(1)
        
        # 步骤2：环境检查
        self._write_output("步骤1: 检查环境...")
        await asyncio.sleep(0.5)
        self._write_output("✓ Python环境检查通过")
        self._write_output("✓ ROS环境检查通过")
        self._write_output("✓ 标定工具检查通过")
        await asyncio.sleep(1)
        
        # 步骤3：自动开始（模拟自动化）
        self._write_output("\n是否开始一键标定流程？(y/n): ")
        self._write_output("自动响应: y")
        await asyncio.sleep(0.5)
        
        # 步骤4：启动下位机
        self._write_output("\n步骤2: 准备启动下位机launch文件...")
        await asyncio.sleep(1)
        self._write_output("编译ROS包...")
        for pkg in ["humanoid_controllers", "motion_capture_ik", "mobile_manipulator_controllers"]:
            self._write_output(f"  编译 {pkg}...")
            await asyncio.sleep(0.5)
        self._write_output("✓ 编译完成")
        
        # 步骤5：启动机器人控制系统（自动响应）
        self._write_output("\n步骤2.5: 启动机器人控制系统...")
        self._write_output("是否启动机器人控制系统？(y/N): ")
        self._write_output("自动响应: y")
        await asyncio.sleep(0.5)
        
        self._write_output("准备启动机器人控制系统...")
        self._write_output("在后台启动机器人控制系统...")
        await asyncio.sleep(2)
        self._write_output("✓ 机器人控制系统已在后台启动")
        
        # 等待缩腿（自动响应）
        self._write_output("\n机器人状态确认")
        self._write_output("请观察机器人状态：")
        self._write_output("- 机器人应该会有缩腿动作")
        self._write_output("- 等待机器人完成缩腿动作后，需要发送站立命令")
        self._write_output("\n请确认机器人已经上电，按回车继续...")
        self._write_output("自动响应: 回车")
        await asyncio.sleep(1)
        
        self._write_output("机器人将开始运动，是否继续？(y/n): ")
        self._write_output("自动响应: y")
        await asyncio.sleep(0.5)
        
        # 模拟缩腿和站立
        self._write_output("\n机器人开始缩腿...")
        await asyncio.sleep(3)
        self._write_output("缩腿完成")
        
        self._write_output("\n发送站立命令 'o' 到机器人控制系统...")
        await asyncio.sleep(2)
        self._write_output("机器人开始站立...")
        await asyncio.sleep(3)
        self._write_output("✓ 机器人站立完成")
        
        # 步骤6：启动AprilTag识别
        self._write_output("\n步骤3: 启动上位机AprilTag识别系统...")
        self._write_output("检查Python环境...")
        await asyncio.sleep(0.5)
        self._write_output("使用Python脚本启动上位机...")
        await asyncio.sleep(1)
        self._write_output("✓ 上位机AprilTag识别系统启动完成")
        
        # 步骤7：头部标定（自动响应）
        self._write_output("\n步骤4: 启动头部标定...")
        self._write_output("请确认：")
        self._write_output("1. 标定工具已安装在机器人躯干上")
        self._write_output("2. AprilTag已正确贴在标定工具上")
        self._write_output("3. 上位机相机正常工作")
        self._write_output("是否继续头部标定？(y/N): ")
        self._write_output("自动响应: y")
        await asyncio.sleep(0.5)
        
        self._write_output("\n开始头部标定...")
        self._write_output("激活虚拟环境和设置环境...")
        await asyncio.sleep(1)
        
        # 模拟头部标定过程
        self._write_output("执行头部标定...")
        self._write_output("移动头部到标定位置1...")
        await asyncio.sleep(2)
        self._write_output("采集数据点1/5")
        await asyncio.sleep(1)
        
        for i in range(2, 6):
            self._write_output(f"移动头部到标定位置{i}...")
            await asyncio.sleep(2)
            self._write_output(f"采集数据点{i}/5")
            await asyncio.sleep(1)
        
        self._write_output("\n计算标定参数...")
        await asyncio.sleep(2)
        self._write_output("标定误差: 0.003mm (良好)")
        self._write_output("✓ 头部标定完成！")
        self._write_output("备份文件: /home/lab/.config/lejuconfig/arms_zero.yaml.head_cali.bak")
        
        # 步骤8：手臂标定
        self._write_output("\n步骤5: 启动手臂标定...")
        await asyncio.sleep(1)
        self._write_output("执行手臂标定脚本...")
        
        # 模拟手臂标定
        self._write_output("开始手臂标定流程...")
        for arm in ["左臂", "右臂"]:
            self._write_output(f"\n标定{arm}...")
            for j in range(1, 8):
                self._write_output(f"  关节{j}标定中...")
                await asyncio.sleep(0.5)
            self._write_output(f"✓ {arm}标定完成")
        
        self._write_output("\n手臂标定完成")
        self._write_output("标定完成，按任意键退出...")
        self._write_output("自动响应: 回车")
        await asyncio.sleep(1)
        
        # 完成
        self._write_output("\n" + "="*51)
        self._write_output(" ▄▄▄▄                   ██              ")
        self._write_output(" ▀▀██                   ▀▀              ")
        self._write_output("   ██       ▄████▄    ████     ██    ██ ")
        self._write_output("   ██      ██▄▄▄▄██     ██     ██    ██ ")
        self._write_output("   ██      ██▀▀▀▀▀▀     ██     ██    ██ ")
        self._write_output("   ██▄▄▄   ▀██▄▄▄▄█     ██     ██▄▄▄███ ")
        self._write_output("    ▀▀▀▀     ▀▀▀▀▀      ██      ▀▀▀▀ ▀▀ ")
        self._write_output("                     ████▀              ")
        self._write_output("="*51)
        
        self.is_running = False


    def get_upper_info(self) -> Dict[str, Any]:
        """获取上位机信息"""
        if not self.is_upper_connected:
            return {}
        return self.upper_info.copy()


# 全局模拟器实例
robot_simulator = RobotSimulator()