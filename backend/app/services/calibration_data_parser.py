import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SlavePositionData:
    """Slave位置数据"""
    slave_id: int
    position: float
    joint_name: Optional[str] = None
    timestamp: Optional[str] = None
    raw_line: Optional[str] = None


class CalibrationDataParser:
    """标定数据解析器 - 专门解析'Slave xx actual position'等标定输出"""
    
    def __init__(self):
        # 各种可能的Slave位置数据格式的正则表达式
        self.slave_position_patterns = [
            # 标准格式: "Slave 01 actual position: 0.123456"
            r'Slave\s+(\d+)\s+actual\s+position:\s*([-+]?\d*\.?\d+)',
            
            # 变体格式: "Slave01 actual position: 0.123456"
            r'Slave(\d+)\s+actual\s+position:\s*([-+]?\d*\.?\d+)',
            
            # 带单位格式: "Slave 01 actual position: 0.123456 rad"
            r'Slave\s+(\d+)\s+actual\s+position:\s*([-+]?\d*\.?\d+)\s*(?:rad|deg)?',
            
            # Joint格式: "Joint 01 position: 0.123456"
            r'Joint\s+(\d+)\s+position:\s*([-+]?\d*\.?\d+)',
            
            # 表格格式: "01    0.123456    actual"
            r'(\d+)\s+([-+]?\d*\.?\d+)\s+actual',
            
            # ROS格式: "[slave_01] position: 0.123456"
            r'\[slave_(\d+)\]\s+position:\s*([-+]?\d*\.?\d+)',
        ]
        
        # 关节名称映射（基于常见机器人配置）
        self.joint_name_map = {
            1: "left_hip_yaw", 2: "left_hip_roll", 3: "left_hip_pitch",
            4: "left_knee_pitch", 5: "left_ankle_pitch", 6: "left_ankle_roll",
            7: "right_hip_yaw", 8: "right_hip_roll", 9: "right_hip_pitch", 
            10: "right_knee_pitch", 11: "right_ankle_pitch", 12: "right_ankle_roll",
            13: "left_shoulder_pitch", 14: "left_shoulder_roll", 15: "left_shoulder_yaw",
            16: "left_elbow_pitch", 17: "right_shoulder_pitch", 18: "right_shoulder_roll",
            19: "right_shoulder_yaw", 20: "right_elbow_pitch",
            21: "neck_pitch", 22: "neck_yaw"
        }
    
    def parse_slave_positions(self, output_text: str) -> List[SlavePositionData]:
        """
        解析标定输出中的Slave位置数据
        
        Args:
            output_text: 标定程序的输出文本
            
        Returns:
            解析出的Slave位置数据列表
        """
        positions = []
        
        if not output_text:
            return positions
        
        # 按行分割文本
        lines = output_text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # 尝试各种格式的正则表达式
            for pattern in self.slave_position_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    try:
                        slave_id = int(match.group(1))
                        position = float(match.group(2))
                        
                        # 获取关节名称
                        joint_name = self.joint_name_map.get(slave_id, f"joint_{slave_id:02d}")
                        
                        position_data = SlavePositionData(
                            slave_id=slave_id,
                            position=position,
                            joint_name=joint_name,
                            raw_line=line
                        )
                        positions.append(position_data)
                        
                        logger.debug(f"解析到位置数据: Slave {slave_id} -> {position} ({joint_name})")
                        break
                        
                    except (ValueError, IndexError) as e:
                        logger.warning(f"解析行 {line_num} 时出错: {line} - {str(e)}")
                        continue
        
        logger.info(f"从输出中解析到 {len(positions)} 个Slave位置数据")
        return positions
    
    def parse_calibration_summary(self, output_text: str) -> Dict[str, Any]:
        """
        解析标定过程的总结信息
        
        Args:
            output_text: 标定程序的输出文本
            
        Returns:
            标定总结信息字典
        """
        summary = {
            "total_slaves": 0,
            "successful_readings": 0,
            "failed_readings": 0,
            "position_data": [],
            "warnings": [],
            "errors": [],
            "calibration_status": "unknown"
        }
        
        # 解析Slave位置数据
        positions = self.parse_slave_positions(output_text)
        summary["position_data"] = [
            {
                "slave_id": pos.slave_id,
                "position": pos.position,
                "joint_name": pos.joint_name
            }
            for pos in positions
        ]
        summary["successful_readings"] = len(positions)
        
        # 检测标定状态
        if "calibration complete" in output_text.lower():
            summary["calibration_status"] = "completed"
        elif "calibration failed" in output_text.lower():
            summary["calibration_status"] = "failed"
        elif "error" in output_text.lower():
            summary["calibration_status"] = "error"
        elif len(positions) > 0:
            summary["calibration_status"] = "data_collected"
        
        # 检测警告和错误
        lines = output_text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if "warning" in line_lower or "warn" in line_lower:
                summary["warnings"].append(line.strip())
            elif "error" in line_lower or "failed" in line_lower:
                summary["errors"].append(line.strip())
        
        # 计算总的Slave数量（基于检测到的最大slave_id）
        if positions:
            summary["total_slaves"] = max(pos.slave_id for pos in positions)
        
        return summary
    
    def validate_position_data(self, positions: List[SlavePositionData]) -> Tuple[bool, List[str]]:
        """
        验证位置数据的完整性和合理性
        
        Args:
            positions: Slave位置数据列表
            
        Returns:
            (is_valid, validation_messages): 验证结果和消息列表
        """
        messages = []
        is_valid = True
        
        if not positions:
            return False, ["未检测到任何Slave位置数据"]
        
        # 检查数据完整性
        slave_ids = [pos.slave_id for pos in positions]
        expected_slaves = set(range(1, max(slave_ids) + 1))
        actual_slaves = set(slave_ids)
        
        missing_slaves = expected_slaves - actual_slaves
        if missing_slaves:
            messages.append(f"缺失Slave数据: {sorted(missing_slaves)}")
            is_valid = False
        
        # 检查重复数据
        duplicates = []
        seen_slaves = set()
        for pos in positions:
            if pos.slave_id in seen_slaves:
                duplicates.append(pos.slave_id)
            seen_slaves.add(pos.slave_id)
        
        if duplicates:
            messages.append(f"发现重复的Slave数据: {sorted(set(duplicates))}")
        
        # 检查位置值的合理性
        unreasonable_positions = []
        for pos in positions:
            # 检查位置值是否在合理范围内（一般关节位置在-π到π之间）
            if abs(pos.position) > 10.0:  # 10弧度约572度，明显超出关节范围
                unreasonable_positions.append(f"Slave {pos.slave_id}: {pos.position}")
        
        if unreasonable_positions:
            messages.append(f"检测到异常位置值: {unreasonable_positions}")
            is_valid = False
        
        # 如果没有问题
        if is_valid and not messages:
            messages.append(f"成功解析 {len(positions)} 个Slave位置数据，数据完整且合理")
        
        return is_valid, messages
    
    def format_positions_for_offset_csv(self, positions: List[SlavePositionData]) -> str:
        """
        将位置数据格式化为offset.csv格式
        
        Args:
            positions: Slave位置数据列表
            
        Returns:
            CSV格式的字符串
        """
        if not positions:
            return ""
        
        # 按slave_id排序
        sorted_positions = sorted(positions, key=lambda x: x.slave_id)
        
        # 生成CSV内容
        csv_lines = ["# Generated from calibration actual positions"]
        csv_lines.append("joint_name,slave_id,offset")
        
        for pos in sorted_positions:
            joint_name = pos.joint_name or f"joint_{pos.slave_id:02d}"
            csv_lines.append(f"{joint_name},{pos.slave_id},{pos.position:.6f}")
        
        return '\n'.join(csv_lines)
    
    def extract_calibration_logs(self, output_text: str) -> List[Dict[str, str]]:
        """
        提取标定过程中的重要日志信息
        
        Args:
            output_text: 标定程序的输出文本
            
        Returns:
            结构化的日志信息列表
        """
        logs = []
        
        # 重要日志模式
        important_patterns = [
            (r'Calibration\s+(started|begin|initialized)', 'info', '标定开始'),
            (r'Calibration\s+(completed|finished|done)', 'success', '标定完成'),
            (r'Calibration\s+(failed|error)', 'error', '标定失败'),
            (r'Slave\s+\d+\s+actual\s+position', 'data', 'Slave位置数据'),
            (r'Warning:', 'warning', '警告信息'),
            (r'Error:', 'error', '错误信息'),
            (r'roslaunch.*launch', 'info', 'ROS启动'),
            (r'Saving.*offset\.csv', 'info', '保存配置文件'),
        ]
        
        lines = output_text.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            for pattern, log_type, description in important_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    logs.append({
                        'line_number': line_num,
                        'type': log_type,
                        'description': description,
                        'content': line,
                        'raw_line': line
                    })
                    break
        
        return logs


# 全局解析器实例
calibration_data_parser = CalibrationDataParser()