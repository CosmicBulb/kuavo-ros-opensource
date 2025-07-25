import asyncio
import random
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading
import queue


class RobotSimulator:
    """机器人模拟器，用于测试标定功能"""
    
    def __init__(self):
        self.is_connected = False
        self.robot_info = {
            "model": "Kuavo 4 pro",
            "sn": "SIM123456789",
            "end_effector": "灵巧手",
            "version": "1.2.3-sim"
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
        """模拟断开连接"""
        self.is_connected = False
        # 停止所有运行的脚本
        for script_id in list(self.running_scripts.keys()):
            self.stop_script(script_id)
        return True
    
    def execute_command(self, command: str) -> tuple[bool, str, str]:
        """模拟执行命令"""
        if not self.is_connected:
            return False, "", "未连接"
        
        # 模拟不同命令的响应
        if "cat /etc/robot_info.json" in command:
            return True, json.dumps(self.robot_info), ""
        
        elif "rosversion" in command:
            return True, "1.2.3-sim", ""
        
        elif "echo $ROBOT_VERSION" in command:
            return True, "45", ""
        
        else:
            return True, f"Command executed: {command}", ""
    
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
        
        # 模拟电机位置输出
        self._write_output("0000003041: Slave 1 actual position 9.6946716,Encoder 63535.0000000")
        self._write_output("0000003051: Rated current 39.6000000")
        self._write_output("0000003061: Slave 2 actual position 3.9207458,Encoder 14275.0000000")
        self._write_output("0000003071: Rated current 11.7900000")
        self._write_output("0000003081: Slave 3 actual position 12.5216674,Encoder 45590.0000000")
        self._write_output("0000003091: Rated current 42.4300000")
        self._write_output("0000003101: Slave 4 actual position -37.2605896,Encoder -244191.0000000")
        self._write_output("0000003111: Rated current 42.4300000")
        self._write_output("0000003121: Slave 5 actual position 15.8138275,Encoder 207275.0000000")
        self._write_output("0000003131: Rated current 8.4900000")
        self._write_output("0000003142: Slave 6 actual position -2.7354431,Encoder -35854.0000000")
        self._write_output("0000003151: Rated current 8.4900000")
        self._write_output("0000003161: Slave 7 actual position 5.8642578,Encoder 38432.0000000")
        self._write_output("0000003171: Rated current 39.6000000")
        self._write_output("0000003183: Slave 8 actual position -16.8491821,Encoder -61346.0000000")
        self._write_output("0000003192: Rated current 11.7900000")
        self._write_output("0000003201: Slave 9 actual position -18.9975585,Encoder -69168.0000000")
        self._write_output("0000003211: Rated current 42.4300000")
        self._write_output("0000003221: Slave 10 actual position -64.5283508,Encoder -422893.0000000")
        self._write_output("0000003231: Rated current 42.4300000")
        self._write_output("0000003241: Slave 11 actual position -31.0607147,Encoder -407119.0000000")
        self._write_output("0000003251: Rated current 8.4900000")
        self._write_output("0000003261: Slave 12 actual position 49.7427368,Encoder 651988.0000000")
        self._write_output("0000003272: Rated current 8.4900000")
        self._write_output("0000003281: Slave 13 actual position 26.8544311,Encoder 97774.0000000")
        self._write_output("0000003291: Rated current 14.9900000")
        self._write_output("0000003301: Slave 14 actual position -19.9171142,Encoder -72516.0000000")
        self._write_output("0000003311: Rated current 14.9900000")
        
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
        
        # 步骤3：询问是否开始
        self._write_output("\n是否开始一键标定流程？(y/n): ")
        
        response = await self._wait_for_input()
        if response.lower() != 'y':
            self._write_output("用户取消操作")
            self.is_running = False
            return
        
        # 步骤4：启动下位机
        self._write_output("\n步骤2: 准备启动下位机launch文件...")
        await asyncio.sleep(1)
        self._write_output("编译ROS包...")
        for pkg in ["humanoid_controllers", "motion_capture_ik", "mobile_manipulator_controllers"]:
            self._write_output(f"  编译 {pkg}...")
            await asyncio.sleep(0.5)
        self._write_output("✓ 编译完成")
        
        # 步骤5：启动机器人控制系统
        self._write_output("\n步骤2.5: 启动机器人控制系统...")
        self._write_output("是否启动机器人控制系统？(y/N): ")
        
        response = await self._wait_for_input()
        if response.lower() != 'y':
            self._write_output("跳过机器人控制系统启动")
        else:
            self._write_output("准备启动机器人控制系统...")
            self._write_output("在后台启动机器人控制系统...")
            await asyncio.sleep(2)
            self._write_output("✓ 机器人控制系统已在后台启动")
            
            # 等待缩腿
            self._write_output("\n机器人状态确认")
            self._write_output("请观察机器人状态：")
            self._write_output("- 机器人应该会有缩腿动作")
            self._write_output("- 等待机器人完成缩腿动作后，需要发送站立命令")
            self._write_output("\n请确认机器人已经上电，按回车继续...")
            
            await self._wait_for_input()
            
            self._write_output("机器人将开始运动，是否继续？(y/n): ")
            response = await self._wait_for_input()
            if response.lower() != 'y':
                self._write_output("用户取消")
                self.is_running = False
                return
            
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
        
        # 步骤7：头部标定
        self._write_output("\n步骤4: 启动头部标定...")
        self._write_output("请确认：")
        self._write_output("1. 标定工具已安装在机器人躯干上")
        self._write_output("2. AprilTag已正确贴在标定工具上")
        self._write_output("3. 上位机相机正常工作")
        self._write_output("是否继续头部标定？(y/N): ")
        
        response = await self._wait_for_input()
        if response.lower() == 'y':
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
        else:
            self._write_output("跳过头部标定")
        
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
        
        await self._wait_for_input()
        
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


# 全局模拟器实例
robot_simulator = RobotSimulator()