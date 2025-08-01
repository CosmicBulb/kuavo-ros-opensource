"""
模拟零点标定配置文件内容
"""

# arms_zero.yaml 示例内容（使用弧度值）
MOCK_ARMS_ZERO_YAML = """# 上半身零点配置文件
# 2-7: 左臂, 8-13: 右臂, 14-15: 头部
joint_02: 0.0
joint_03: -0.262
joint_04: 0.785
joint_05: -0.524
joint_06: 0.0
joint_07: 0.0
joint_08: 0.0
joint_09: 0.262
joint_10: -0.785
joint_11: 0.524
joint_12: 0.0
joint_13: 0.0
neck_01: 0.0  # yaw
neck_02: 0.0  # pitch
"""

# offset.csv 示例内容（使用弧度值）
MOCK_OFFSET_CSV = """0.0
0.0
-0.524
1.047
-0.524
0.0
0.0
0.0
-0.524
1.047
-0.524
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