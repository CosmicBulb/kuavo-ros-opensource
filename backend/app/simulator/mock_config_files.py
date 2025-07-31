"""
模拟零点标定配置文件内容
"""

# arms_zero.yaml 示例内容
MOCK_ARMS_ZERO_YAML = """# 上半身零点配置文件
# 2-7: 左臂, 8-13: 右臂, 14-15: 头部
joint_02: 0.0
joint_03: -15.0
joint_04: 45.0
joint_05: -30.0
joint_06: 0.0
joint_07: 0.0
joint_08: 0.0
joint_09: 15.0
joint_10: -45.0
joint_11: 30.0
joint_12: 0.0
joint_13: 0.0
neck_01: 0.0  # yaw
neck_02: 0.0  # pitch
"""

# offset.csv 示例内容
MOCK_OFFSET_CSV = """0.0
0.0
-30.0
60.0
-30.0
0.0
0.0
0.0
-30.0
60.0
-30.0
0.0
0.0
0.0
"""

def get_mock_arms_zero_yaml():
    """获取模拟的arms_zero.yaml内容"""
    return MOCK_ARMS_ZERO_YAML

def get_mock_offset_csv():
    """获取模拟的offset.csv内容"""
    return MOCK_OFFSET_CSV