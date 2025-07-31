import os
import yaml
import csv
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json

from app.services.ssh_service import ssh_service

logger = logging.getLogger(__name__)


@dataclass
class JointData:
    """关节数据"""
    id: int
    name: str
    current_position: float
    zero_position: float
    offset: float
    status: str = "normal"  # normal, warning, error
    
    
@dataclass
class CalibrationFileInfo:
    """标定文件信息"""
    file_path: str
    file_type: str  # arms_zero, legs_offset
    exists: bool
    last_modified: Optional[datetime]
    backup_count: int
    file_size: int


class CalibrationFileService:
    """标定文件管理服务"""
    
    def __init__(self):
        self.arms_zero_path = "/home/lab/.config/lejuconfig/arms_zero.yaml"
        self.legs_offset_path = "/home/lab/.config/lejuconfig/offset.csv"
        self.config_dir = "/home/lab/.config/lejuconfig"
        
        # 关节名称映射
        self.arm_joint_names = {
            1: "左臂01", 2: "左臂02", 3: "左臂03", 4: "左臂04", 5: "左臂05", 6: "左臂06",
            7: "右臂01", 8: "右臂02", 9: "右臂03", 10: "右臂04", 11: "右臂05", 12: "右臂06",
            13: "头部01(yaw)", 14: "头部02(pitch)"
        }
        
        self.leg_joint_names = {
            1: "左腿01", 2: "左腿02", 3: "左腿03", 4: "左腿04", 5: "左腿05", 6: "左腿06",
            7: "右腿01", 8: "右腿02", 9: "右腿03", 10: "右腿04", 11: "右腿05", 12: "右腿06",
            13: "左肩部", 14: "右肩部"
        }
    
    async def get_file_info(self, robot_id: str, file_type: str) -> CalibrationFileInfo:
        """获取标定文件信息"""
        if file_type == "arms_zero":
            file_path = self.arms_zero_path
        elif file_type == "legs_offset":
            file_path = self.legs_offset_path
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        # 检查文件是否存在
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"test -f {file_path} && echo 'exists' || echo 'not_exists'"
        )
        
        exists = success and "exists" in stdout
        
        if not exists:
            return CalibrationFileInfo(
                file_path=file_path,
                file_type=file_type,
                exists=False,
                last_modified=None,
                backup_count=0,
                file_size=0
            )
        
        # 获取文件信息
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"stat -c '%Y %s' {file_path}"
        )
        
        last_modified = None
        file_size = 0
        
        if success and stdout.strip():
            parts = stdout.strip().split()
            if len(parts) >= 2:
                try:
                    timestamp = int(parts[0])
                    last_modified = datetime.fromtimestamp(timestamp)
                    file_size = int(parts[1])
                except ValueError:
                    pass
        
        # 获取备份文件数量
        backup_dir = f"{self.config_dir}/backup"
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"ls {backup_dir}/{os.path.basename(file_path)}.* 2>/dev/null | wc -l"
        )
        
        backup_count = 0
        if success and stdout.strip().isdigit():
            backup_count = int(stdout.strip())
        
        return CalibrationFileInfo(
            file_path=file_path,
            file_type=file_type,
            exists=exists,
            last_modified=last_modified,
            backup_count=backup_count,
            file_size=file_size
        )
    
    async def read_arms_zero_data(self, robot_id: str) -> List[JointData]:
        """读取手臂零点数据"""
        # 如果是模拟器模式，直接返回模拟数据
        if ssh_service.use_simulator:
            return self._generate_mock_arms_data()
        
        # 首先检查文件是否存在
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"test -f {self.arms_zero_path} && echo 'ok' || echo 'not_found'"
        )
        
        if not success or "not_found" in stdout:
            # 文件不存在，返回默认数据
            return [
                JointData(
                    id=i,
                    name=self.arm_joint_names.get(i, f"电机{i}"),  # 使用get避免KeyError
                    current_position=0.0,
                    zero_position=0.0,
                    offset=0.0,
                    status="warning"
                )
                for i in range(2, 16)  # 2-15号电机
            ]
        
        # 读取YAML文件
        success, content, stderr = await ssh_service.execute_command(
            robot_id, f"cat {self.arms_zero_path}"
        )
        
        if not success:
            raise Exception(f"读取手臂零点文件失败: {stderr}")
        
        try:
            yaml_data = yaml.safe_load(content)
            joint_data_list = []
            
            for i in range(1, 15):
                joint_name = f"joint_{i:02d}" if i < 13 else f"neck_{i-12:02d}"
                zero_position = yaml_data.get(joint_name, 0.0)
                
                joint_data_list.append(JointData(
                    id=i,
                    name=self.arm_joint_names[i],
                    current_position=0.0,  # 需要从实时数据获取
                    zero_position=zero_position,
                    offset=zero_position,
                    status="normal"
                ))
            
            return joint_data_list
            
        except yaml.YAMLError as e:
            raise Exception(f"解析手臂零点文件失败: {str(e)}")
    
    def _generate_mock_arms_data(self) -> List[JointData]:
        """生成模拟手臂数据"""
        import random
        mock_data = []
        
        # 生成更真实的模拟数据
        base_positions = {
            1: 0.0, 2: -15.0, 3: 45.0, 4: -30.0, 5: 0.0, 6: 0.0,  # 左臂
            7: 0.0, 8: 15.0, 9: -45.0, 10: 30.0, 11: 0.0, 12: 0.0,  # 右臂
            13: 0.0, 14: 0.0  # 头部
        }
        
        for i in range(1, 15):
            # 生成一些随机但合理的关节数据
            base_pos = base_positions.get(i, 0.0)
            current_pos = base_pos + random.uniform(-2, 2)  # 当前位置有小幅偏差
            zero_pos = base_pos + random.uniform(-0.5, 0.5)  # 零点位置接近基准
            
            # 随机设置一些警告状态
            status = "normal"
            if random.random() < 0.1:  # 10%概率出现警告
                status = "warning"
            
            mock_data.append(JointData(
                id=i,
                name=self.arm_joint_names[i],
                current_position=current_pos,
                zero_position=zero_pos,
                offset=current_pos - zero_pos,
                status=status
            ))
        
        logger.info(f"生成了 {len(mock_data)} 个手臂关节的模拟数据")
        return mock_data
    
    def _generate_mock_legs_data(self) -> List[JointData]:
        """生成模拟腿部数据"""
        import random
        mock_data = []
        
        # 生成更真实的腿部数据
        base_positions = {
            1: 0.0, 2: 0.0, 3: -30.0, 4: 60.0, 5: -30.0, 6: 0.0,  # 左腿
            7: 0.0, 8: 0.0, 9: -30.0, 10: 60.0, 11: -30.0, 12: 0.0,  # 右腿
            13: 0.0, 14: 0.0  # 肩部
        }
        
        for i in range(1, 15):
            # 生成一些随机但合理的关节数据
            base_pos = base_positions.get(i, 0.0)
            current_pos = base_pos + random.uniform(-3, 3)  # 腿部偏差稍大
            zero_pos = base_pos + random.uniform(-1, 1)
            
            # 随机设置状态
            status = "normal"
            if random.random() < 0.15:  # 15%概率出现警告
                status = "warning"
            
            mock_data.append(JointData(
                id=i,
                name=self.leg_joint_names[i],
                current_position=current_pos,
                zero_position=zero_pos,
                offset=current_pos - zero_pos,
                status=status
            ))
        
        logger.info(f"生成了 {len(mock_data)} 个腿部关节的模拟数据")
        return mock_data

    async def read_legs_offset_data(self, robot_id: str) -> List[JointData]:
        """读取腿部偏移数据"""
        # 如果是模拟器模式，直接返回模拟数据
        if ssh_service.use_simulator:
            return self._generate_mock_legs_data()
        
        # 检查文件是否存在
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"test -f {self.legs_offset_path} && echo 'ok' || echo 'not_found'"
        )
        
        if not success or "not_found" in stdout:
            # 文件不存在，返回默认数据
            return [
                JointData(
                    id=i,
                    name=self.leg_joint_names[i],
                    current_position=0.0,
                    zero_position=0.0,
                    offset=0.0,
                    status="warning"
                )
                for i in range(1, 15)
            ]
        
        # 读取CSV文件
        success, content, stderr = await ssh_service.execute_command(
            robot_id, f"cat {self.legs_offset_path}"
        )
        
        if not success:
            raise Exception(f"读取腿部偏移文件失败: {stderr}")
        
        try:
            lines = content.strip().split('\n')
            joint_data_list = []
            
            for i, line in enumerate(lines[:14], 1):
                try:
                    offset_value = float(line.strip())
                except ValueError:
                    offset_value = 0.0
                
                joint_data_list.append(JointData(
                    id=i,
                    name=self.leg_joint_names[i],
                    current_position=0.0,  # 需要从实时数据获取
                    zero_position=0.0,
                    offset=offset_value,
                    status="normal"
                ))
            
            # 如果文件行数不足14行，补齐
            while len(joint_data_list) < 14:
                i = len(joint_data_list) + 1
                joint_data_list.append(JointData(
                    id=i,
                    name=self.leg_joint_names[i],
                    current_position=0.0,
                    zero_position=0.0,
                    offset=0.0,
                    status="warning"
                ))
            
            return joint_data_list
            
        except Exception as e:
            raise Exception(f"解析腿部偏移文件失败: {str(e)}")
    
    async def write_arms_zero_data(self, robot_id: str, joint_data: List[JointData]) -> bool:
        """写入手臂零点数据"""
        try:
            # 先备份原文件
            await self._backup_file(robot_id, self.arms_zero_path)
            
            # 构建YAML数据
            yaml_data = {}
            
            for joint in joint_data:
                if joint.id <= 12:
                    key = f"joint_{joint.id:02d}"
                else:
                    key = f"neck_{joint.id-12:02d}"
                yaml_data[key] = float(joint.zero_position)
            
            # 生成YAML内容
            yaml_content = yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True)
            
            # 写入临时文件，然后移动到目标位置
            temp_file = f"{self.arms_zero_path}.tmp"
            
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id, f"cat > {temp_file} << 'EOF'\n{yaml_content}\nEOF"
            )
            
            if not success:
                raise Exception(f"写入临时文件失败: {stderr}")
            
            # 原子性移动文件
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id, f"mv {temp_file} {self.arms_zero_path}"
            )
            
            if not success:
                raise Exception(f"移动文件失败: {stderr}")
            
            return True
            
        except Exception as e:
            logger.error(f"写入手臂零点文件失败: {str(e)}")
            return False
    
    async def write_legs_offset_data(self, robot_id: str, joint_data: List[JointData]) -> bool:
        """写入腿部偏移数据"""
        try:
            # 先备份原文件
            await self._backup_file(robot_id, self.legs_offset_path)
            
            # 构建CSV内容
            csv_lines = []
            for joint in sorted(joint_data, key=lambda x: x.id):
                csv_lines.append(str(joint.offset))
            
            csv_content = '\n'.join(csv_lines)
            
            # 写入临时文件，然后移动到目标位置
            temp_file = f"{self.legs_offset_path}.tmp"
            
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id, f"cat > {temp_file} << 'EOF'\n{csv_content}\nEOF"
            )
            
            if not success:
                raise Exception(f"写入临时文件失败: {stderr}")
            
            # 原子性移动文件
            success, stdout, stderr = await ssh_service.execute_command(
                robot_id, f"mv {temp_file} {self.legs_offset_path}"
            )
            
            if not success:
                raise Exception(f"移动文件失败: {stderr}")
            
            return True
            
        except Exception as e:
            logger.error(f"写入腿部偏移文件失败: {str(e)}")
            return False
    
    async def _backup_file(self, robot_id: str, file_path: str):
        """备份文件"""
        if not file_path:
            return
        
        backup_dir = f"{self.config_dir}/backup"
        
        # 确保备份目录存在
        await ssh_service.execute_command(robot_id, f"mkdir -p {backup_dir}")
        
        # 检查文件是否存在
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, f"test -f {file_path} && echo 'exists' || echo 'not_exists'"
        )
        
        if success and "exists" in stdout:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{os.path.basename(file_path)}.{timestamp}.bak"
            backup_path = f"{backup_dir}/{backup_name}"
            
            await ssh_service.execute_command(robot_id, f"cp {file_path} {backup_path}")
            logger.info(f"文件已备份: {backup_path}")
    
    async def get_current_joint_positions(self, robot_id: str) -> Dict[int, float]:
        """获取当前关节位置（从ROS topic或硬件读取）"""
        # 这里需要根据实际情况实现
        # 可能需要订阅 /joint_states topic 或通过其他方式获取
        
        # 模拟数据，实际实现时需要替换
        if ssh_service.use_simulator:
            # 模拟器模式下返回更真实的模拟数据
            import random
            positions = {}
            
            # 基于手臂和腿部的典型位置生成当前位置
            # 上半身：2-15号电机
            arm_base = {
                2: 0.0, 3: -15.0, 4: 45.0, 5: -30.0, 6: 0.0, 7: 0.0,  # 左臂
                8: 0.0, 9: 15.0, 10: -45.0, 11: 30.0, 12: 0.0, 13: 0.0,  # 右臂
                14: 0.0, 15: 0.0  # 头部
            }
            # 下半身：1-14号电机
            leg_base = {
                1: 0.0, 2: 0.0, 3: -30.0, 4: 60.0, 5: -30.0, 6: 0.0,  # 左腿
                7: 0.0, 8: 0.0, 9: -30.0, 10: 60.0, 11: -30.0, 12: 0.0,  # 右腿
                13: 0.0, 14: 0.0  # 躯干肩部
            }
            
            # 上半身位置
            for i in range(2, 16):
                base = arm_base.get(i, 0.0)
                positions[i] = base + random.uniform(-2, 2)
            
            # 下半身位置
            for i in range(1, 15):
                base = leg_base.get(i, 0.0)
                positions[i] = base + random.uniform(-3, 3)
            
            logger.info(f"模拟器模式：生成了关节位置")
            return positions
        
        # 实际硬件获取关节位置的命令
        success, stdout, stderr = await ssh_service.execute_command(
            robot_id, "rostopic echo -n 1 /joint_states | grep -A 20 'position:'"
        )
        
        positions = {}
        if success and stdout:
            # 解析关节位置数据
            # 这里需要根据实际的 ROS topic 格式进行解析
            try:
                # 简化的解析逻辑，实际可能需要更复杂的处理
                lines = stdout.split('\n')
                position_values = []
                for line in lines:
                    if line.strip() and line.strip().replace('-', '').replace('.', '').isdigit():
                        position_values.append(float(line.strip()))
                
                for i, pos in enumerate(position_values[:14], 1):
                    positions[i] = pos
                    
            except Exception as e:
                logger.warning(f"解析关节位置数据失败: {str(e)}")
        
        # 如果没有获取到数据，返回默认值
        if not positions:
            # 为所有可能的关节返回默认值
            positions = {}
            for i in range(1, 16):  # 1-15号电机
                positions[i] = 0.0
        
        return positions
    
    async def validate_joint_data(self, joint_data: List[JointData]) -> List[str]:
        """验证关节数据"""
        warnings = []
        
        for joint in joint_data:
            # 检查数值范围
            if abs(joint.zero_position) > 10.0:  # 假设零点不应该超过10弧度
                warnings.append(f"{joint.name}: 零点值异常 ({joint.zero_position:.3f})")
            
            if abs(joint.offset) > 5.0:  # 假设偏移不应该超过5弧度
                warnings.append(f"{joint.name}: 偏移值异常 ({joint.offset:.3f})")
            
            # 检查当前位置与零点的差异
            diff = abs(joint.current_position - joint.zero_position)
            if diff > 3.0:  # 假设差异不应该超过3弧度
                warnings.append(f"{joint.name}: 当前位置与零点差异较大 ({diff:.3f})")
        
        return warnings


# 全局标定文件服务实例
calibration_file_service = CalibrationFileService()