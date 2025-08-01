# KUAVO Studio API 接口文档

## 概述

KUAVO Studio 提供 RESTful API 和 WebSocket 接口，用于管理和控制 KUAVO 人形机器人。

- **基础URL**: `http://localhost:8001`
- **API版本**: v1
- **认证方式**: 暂无（后续可添加 JWT 认证）

## 核心数据结构

### 关节数据结构 (JointDataSchema)

```json
{
  "id": 1,
  "name": "左臂01",
  "current_position": 0.051,
  "zero_position": 0.0,
  "offset": 0.051,
  "status": "normal"  // normal, warning, error  
}
```

### 机器人信息结构

```json
{
  "id": "1",
  "name": "Robot001",
  "ip_address": "192.168.1.100",
  "port": 22,
  "ssh_user": "leju",
  "connection_status": "connected",  // connected, disconnected, connecting
  "device_type": "lower",             // 设备类型: upper(上位机) 或 lower(下位机)
  // 新字段（推荐使用）
  "robot_model": "Kuavo 4 pro",        // 机器人型号
  "robot_version": "version 1.2.3",     // 机器人版本
  "robot_sn": "qwert3459592sfag",      // 机器人SN号
  "robot_software_version": "version 1.2.3",  // 机器人软件版本
  "end_effector_model": "灵巧手",      // 末端执行器型号
  "service_status": "正常",             // 服务状态
  "battery_level": "85%",               // 电量
  "error_code": "",                     // 故障码
  // 兼容旧字段
  "hardware_model": "Kuavo 4 pro",
  "software_version": "version 1.2.3",
  "sn_number": "qwert3459592sfag",
  "end_effector_type": "灵巧手",
  "created_at": "2024-01-20T10:00:00",
  "updated_at": "2024-01-20T10:00:00"
}
```

### 分页响应结构

```json
{
  "items": [...],  // 数据列表
  "pagination": {
    "page": 1,           // 当前页码
    "page_size": 10,     // 每页大小
    "total": 25,         // 总记录数
    "total_pages": 3,    // 总页数
    "has_next": true,    // 是否有下一页
    "has_prev": false    // 是否有上一页
  }
}
```

### 零点标定会话结构 (ZeroPointSessionResponse)

```json
{
  "session_id": "zp_cal_1_1722470400",
  "robot_id": "1",
  "calibration_type": "full_body",
  "current_step": "initialize_zero",
  "status": "in_progress",
  "start_time": "2024-08-01T10:00:00",
  "step_progress": {
    "current_step": 3,
    "total_steps": 4,
    "step_name": "初始化零点",
    "is_loading": false,
    "user_prompt": "是否启动机器人控制系统？(y/N):"
  },
  "warnings": [],
  "error_message": null,
  "joint_data": [
    {
      "id": 1,
      "name": "左臂01",
      "current_position": 0.051,
      "zero_position": 0.0,
      "offset": 0.051,
      "status": "normal"
    }
  ]
}
```

## API 端点

### 1. 机器人管理

#### 1.1 获取机器人列表

**端点**: `GET /api/v1/robots`

**描述**: 获取已添加的机器人列表，支持分页

**请求参数**:
- `page`: 页码，从1开始（可选，默认1）
- `page_size`: 每页大小（可选，默认10，最大100）
- `skip`: 跳过记录数（已废弃，建议使用page）
- `limit`: 限制记录数（已废弃，建议使用page_size）

**响应示例**:
```json
{
  "items": [
    {
      "id": "1",
      "name": "Robot001",
      "ip_address": "192.168.1.100",
      "port": 22,
      "ssh_user": "leju",
      "connection_status": "connected",
      "device_type": "lower",
      "robot_model": "Kuavo 4 pro",
      "robot_version": "version 1.2.3",
      "robot_sn": "qwert3459592sfag",
      "robot_software_version": "version 1.2.3",
      "end_effector_model": "灵巧手",
      "service_status": "正常",
      "battery_level": "85%",
      "error_code": "",
      "hardware_model": "Kuavo 4 pro",
      "software_version": "version 1.2.3",
      "sn_number": "qwert3459592sfag",
      "end_effector_type": "灵巧手",
      "created_at": "2024-01-20T10:00:00",
      "updated_at": "2024-01-20T10:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 15,
    "total_pages": 2,
    "has_next": true,
    "has_prev": false
  }
}
```

**使用示例**:
```bash
# 获取第2页，每页5条记录
GET /api/v1/robots?page=2&page_size=5

# 向后兼容：使用skip和limit
GET /api/v1/robots?skip=10&limit=5
```

#### 1.2 创建机器人

**端点**: `POST /api/v1/robots`

**描述**: 添加新的机器人设备

**请求体**:
```json
{
  "name": "Robot001",
  "ip_address": "192.168.1.100",
  "port": 22,
  "ssh_user": "leju",
  "ssh_password": "password123",
  "device_type": "lower"  // 可选，设备类型: upper(上位机) 或 lower(下位机)，默认为 lower
}
```

**响应示例**:
```json
{
  "id": "1",
  "name": "Robot001",
  "ip_address": "192.168.1.100",
  "port": 22,
  "ssh_user": "leju",
  "connection_status": "disconnected",
  "device_type": "lower",
  "created_at": "2024-01-20T10:00:00",
  "updated_at": "2024-01-20T10:00:00"
}
```

**错误响应**:
- `400 Bad Request`: 机器人名称已存在

#### 1.3 获取单个机器人

**端点**: `GET /api/v1/robots/{robot_id}`

**描述**: 根据ID获取机器人详细信息

**路径参数**:
- `robot_id` (string): 机器人ID或SN号

**响应示例**: 同 1.1 中的单个机器人对象

**错误响应**:
- `404 Not Found`: 机器人未找到

#### 1.4 获取机器人实时状态

**端点**: `GET /api/v1/robots/{robot_id}/status`

**描述**: 获取机器人实时状态信息（电量、服务状态、故障码等）

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "robot_id": "1",
  "connection_status": "connected",
  "service_status": "正常",
  "battery_level": "85%",
  "error_code": ""
}
```

**状态说明**:
- 如果机器人未连接，状态值将显示为"断开"
- 连接后会实时获取并更新数据库中的状态信息

**错误响应**:
- `404 Not Found`: 机器人未找到

#### 1.5 删除机器人

**端点**: `DELETE /api/v1/robots/{robot_id}`

**描述**: 删除指定的机器人

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "机器人删除成功"
}
```

**错误响应**:
- `404 Not Found`: 机器人未找到

### 2. 连接管理

#### 2.1 测试连接

**端点**: `POST /api/v1/robots/test-connection`

**描述**: 测试与机器人的SSH连接并获取设备信息（不保存连接）

**请求体**:
```json
{
  "name": "Robot001",
  "ip_address": "192.168.1.100",
  "port": 22,
  "ssh_user": "leju",
  "ssh_password": "password123",
  "device_type": "lower"  // 可选，设备类型: upper(上位机) 或 lower(下位机)，默认为 lower
}
```

**响应示例**:
```json
{
  "success": true,
  "device_info": {
    "name": "Robot001",
    "ip_address": "192.168.1.100",
    "device_type": "lower",
    // 新字段（推荐使用）
    "robot_model": "Kuavo 4 pro",
    "robot_version": "version 1.2.3",
    "robot_sn": "qwert3459592sfag",
    "robot_software_version": "version 1.2.3",
    "end_effector_model": "灵巧手",
    // 兼容旧字段
    "hardware_model": "Kuavo 4 pro",
    "software_version": "version 1.2.3",
    "sn_number": "qwert3459592sfag",
    "end_effector_type": "灵巧手"
  },
  "network_info": {
    "network_validation": "网络环境验证成功，延迟: 5ms"
  }
}
```

**错误响应示例**:
```json
{
  "detail": "设备不在同一网络下，无法连接: 目标设备不在同一子网(192.168.1.x)"
}
```

**功能说明**:
- 首先验证网络环境（ping测试、子网检查）
- 然后尝试SSH连接
- 成功后获取设备信息
- 返回包含新旧两套字段名的响应，确保兼容性

#### 2.2 连接机器人

**端点**: `POST /api/v1/robots/{robot_id}/connect`

**描述**: 建立与机器人的SSH连接

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "连接成功",
  "status": "connected"
}
```

**说明**:
- 连接成功后，系统会自动获取并更新机器人的详细信息
- 可通过 `GET /api/v1/robots/{robot_id}` 获取完整信息
- 可通过 `GET /api/v1/robots/{robot_id}/status` 获取实时状态

**错误响应**:
- `404 Not Found`: 机器人未找到
- `400 Bad Request`: 连接失败（包含错误详情）

#### 2.3 断开连接

**端点**: `POST /api/v1/robots/{robot_id}/disconnect`

**描述**: 断开与机器人的SSH连接

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "断开成功"
}
```

#### 2.4 重置状态

**端点**: `POST /api/v1/robots/{robot_id}/reset-status`

**描述**: 重置机器人连接状态（用于错误恢复）

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "状态已重置"
}
```

### 3. 零点标定管理

#### 3.1 启动零点标定

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration`

**描述**: 启动零点标定流程

**路径参数**:
- `robot_id` (string): 机器人ID

**请求体**:
```json
{
  "calibration_type": "full_body"  // full_body, arms_only, legs_only
}
```

**响应示例**:
```json
{
  "session_id": "zp_cal_1_1722470400",
  "message": "零点标定流程已启动",
  "current_step": "confirm_tools",
  "status": "not_started"
}
```

**标定流程说明**:
- 步骤1: confirm_tools - 确认安装工具
- 步骤2: read_config - 读取当前配置，加载关节数据
- 步骤3: initialize_zero - 初始化零点，执行标定脚本
- 步骤4: remove_tools - 移除辅助工装，标定完成

**错误响应**:
- `404 Not Found`: 机器人未找到
- `400 Bad Request`: 机器人未连接或已有标定任务进行中

#### 3.2 零点标定步骤导航

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/go-to-step`

**描述**: 导航到指定的标定步骤

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**请求体**:
```json
{
  "step": "initialize_zero"  // confirm_tools, read_config, initialize_zero, remove_tools
}
```

**响应示例**:
```json
{
  "message": "已跳转到步骤 initialize_zero"
}
```

**错误响应**:
- `404 Not Found`: 没有找到标定会话
- `400 Bad Request`: 无效的步骤名称

#### 3.3 执行一键标定

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/execute-calibration`

**描述**: 执行一键标定命令

**路径参数**:
- `robot_id` (string): 机器人ID  
- `session_id` (string): 标定会话ID

**请求体**:
```json
{
  "calibration_mode": "full_body",  // full_body, arms_only, legs_only
  "command": "roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true cali_leg:=true"  // 可选，不提供将使用默认命令
}
```

**响应示例**:
```json
{
  "message": "full_body标定已启动"
}
```

**默认命令映射**:
- `full_body`: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true cali_leg:=true`
- `arms_only`: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true`
- `legs_only`: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_leg:=true`

**错误响应**:
- `404 Not Found`: 标定会话不存在
- `400 Bad Request`: 当前步骤不允许执行标定

#### 3.4 关节调试

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/joint-debug`

**描述**: 调试指定关节到目标位置

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**请求体**:
```json
{
  "joints": [
    {"id": 1, "name": "joint_02", "position": 0.051},
    {"id": 2, "name": "joint_03", "position": 0.011}
  ]
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "成功调整 2 个关节",
  "command_executed": "rostopic pub -1 /kuavo_arm_traj sensor_msgs/JointState \"header: {seq: 0, stamp: {secs: 0, nsecs: 0}, frame_id: ''}\nname: ['joint_02', 'joint_03']\nposition: [0.051, 0.011]\nvelocity: []\neffort: []\" ",
  "error": null
}
```

**ROS命令格式**:
系统会自动构建 `sensor_msgs/JointState` 消息并发布到 `/kuavo_arm_traj` 话题。

**错误响应**:
- `404 Not Found`: 标定会话不存在
- `400 Bad Request`: 关节数据无效

#### 3.5 获取当前零点标定状态

**端点**: `GET /api/v1/robots/{robot_id}/zero-point-calibration/current`

**描述**: 获取当前零点标定状态

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "session_id": "zp_cal_1_1722470400",
  "robot_id": "1",
  "calibration_type": "full_body",
  "current_step": "initialize_zero",
  "status": "waiting_user",
  "start_time": "2024-08-01T10:00:00",
  "step_progress": {
    "current_step": 3,
    "total_steps": 4,
    "step_name": "初始化零点",
    "is_loading": false,
    "user_prompt": "是否启动机器人控制系统？(y/N):"
  },
  "warnings": [],
  "error_message": null,
  "joint_data": []
}
```

**状态说明**:
- `not_started`: 未开始
- `in_progress`: 进行中  
- `waiting_user`: 等待用户输入
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

#### 3.6 获取标定汇总

**端点**: `GET /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/summary`

**描述**: 获取标定结果汇总，包括解析的Slave位置数据

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**响应示例**:
```json
{
  "session_id": "zp_cal_1_1722470400",
  "calibration_type": "full_body",
  "status": "completed",
  "parsed_positions": {
    "1": 9.6946716,
    "2": 3.9207458,
    "3": 12.5216674
  },
  "position_count": 14,
  "raw_logs": [
    "30400001: Slave 01 actual position 9.6946716,Encoder 63535.0",
    "30400151: Slave 02 actual position 3.9207458,Encoder 14275.0"
  ],
  "warnings": []
}
```

#### 3.7 保存零点数据

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/save-zero-point`

**描述**: 保存零点数据到配置文件

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**响应示例**:
```json
{
  "message": "零点数据已保存到配置文件"
}
```

#### 3.8 验证标定结果

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/validate`

**描述**: 执行零点标定验证（运行roslaunch让机器人缩腿）

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**响应示例**:
```json
{
  "message": "零点标定验证已启动"
}
```

#### 3.9 取消零点标定

**端点**: `DELETE /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}`

**描述**: 取消零点标定会话

**路径参数**:
- `robot_id` (string): 机器人ID
- `session_id` (string): 标定会话ID

**响应示例**:
```json
{
  "message": "标定已取消"
}
```

### 4. 标定文件管理

#### 4.1 获取标定文件信息

**端点**: `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/info`

**描述**: 获取标定文件的基本信息

**路径参数**:
- `robot_id` (string): 机器人ID
- `file_type` (string): 文件类型 (arms_zero, legs_offset)

**响应示例**:
```json
{
  "file_path": "/home/lab/.config/lejuconfig/arms_zero.yaml",
  "file_type": "arms_zero",
  "exists": true,
  "last_modified": "2024-01-20T10:00:00",
  "backup_count": 3,
  "file_size": 1024
}
```

#### 4.2 读取标定文件数据

**端点**: `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/data`

**描述**: 读取标定配置文件内容

**路径参数**:
- `robot_id` (string): 机器人ID
- `file_type` (string): 文件类型 (arms_zero, legs_offset)

**响应示例**:
```json
{
  "file_type": "arms_zero",
  "joint_data": [
    {
      "id": 1,
      "name": "左臂01",
      "current_position": 0.051,
      "zero_position": 0.0,
      "offset": 0.051,
      "status": "normal"
    },
    {
      "id": 2,
      "name": "左臂02", 
      "current_position": 0.011,
      "zero_position": 0.0,
      "offset": 0.011,
      "status": "normal"
    }
  ],
  "warnings": []
}
```

**关节映射说明**:
- **手臂关节** (`arms_zero`):
  - ID 1-12: 对应 joint_02 到 joint_13 (左臂6个 + 右臂6个)
  - ID 13-14: 对应 neck_01, neck_02 (头部2个)
- **腿部关节** (`legs_offset`):
  - ID 1-14: 左腿6个 + 右腿6个 + 肩部2个

#### 4.3 保存关节数据

**端点**: `PUT /api/v1/robots/{robot_id}/calibration-files/{file_type}/data`

**描述**: 保存关节数据到标定配置文件

**路径参数**:
- `robot_id` (string): 机器人ID
- `file_type` (string): 文件类型 (arms_zero, legs_offset)

**请求体**:
```json
{
  "joint_data": [
    {
      "id": 1,
      "name": "左臂01",
      "current_position": 0.051,
      "zero_position": 0.0,
      "offset": 0.051,
      "status": "normal"
    },
    {
      "id": 2,
      "name": "左臂02",
      "current_position": 0.011,
      "zero_position": 0.0,
      "offset": 0.011,
      "status": "normal"
    }
  ]
}
```

**验证规则**:
- 偏移值 `offset` 建议范围: ±0.05（会产生警告）
- 偏移值 `offset` 强制限制: ±0.1（会阻止保存）

**响应示例**:
```json
{
  "message": "标定数据保存成功",
  "warnings": [
    "关节 左臂01 的偏移值 0.0600 超过建议范围(±0.05)，请谨慎操作"
  ]
}
```

**错误响应**:
```json
{
  "detail": "参数验证失败: 关节 左臂01 的偏移值 0.15 超过安全范围(±0.1)，可能导致机器人损坏"
}
```

### 5. 头手标定管理

#### 5.1 头手标定环境检查

**端点**: `GET /api/v1/robots/{robot_id}/calibration-config-check`

**描述**: 执行头手标定前的环境预检查

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "virtual_env_ready": true,
  "apriltag_ready": true,
  "rosbag_files_ready": true,
  "camera_ready": true,
  "network_ready": true,
  "upper_computer_connected": true
}
```

**检查项目说明**:
- `virtual_env_ready`: 虚拟环境 `/home/lab/kuavo_venv/joint_cali` 是否存在
- `apriltag_ready`: AprilTag配置文件 `tags.yaml` 是否存在
- `rosbag_files_ready`: rosbag文件 `hand_move_demo_*.bag` 是否存在（≥2个）
- `camera_ready`: 相机设备 `/dev/video*` 是否可用
- `network_ready`: sudo权限和roscore是否可用
- `upper_computer_connected`: 上位机是否已连接

#### 5.2 启动头手标定

**端点**: `POST /api/v1/robots/{robot_id}/head-hand-calibration`

**描述**: 启动头手标定流程，执行One_button_start.sh脚本

**路径参数**:
- `robot_id` (string): 机器人ID

**请求体**:
```json
{
  "calibration_type": "head_hand",
  "script_path": "./scripts/joint_cali/One_button_start.sh",
  "include_head": true,
  "include_arms": true,
  "arm_selection": "both"  // left, right, both
}
```

**响应示例**:
```json
{
  "session_id": "head_hand_cal_1_1722470400",
  "message": "头手标定已启动",
  "script_path": "./scripts/joint_cali/One_button_start.sh"
}
```

**自动化交互处理**:
系统会使用expect脚本自动处理以下用户交互：
- "是否启动机器人控制系统？(y/N)" → 自动回复 "y"
- "机器人是否已完成缩腿动作" → 自动回复 "y"  
- "是否继续头部标定？(y/N)" → 自动回复 "y"
- "按下回车键继续保存文件" → 自动回复回车
- "标定已完成，是否应用新的零点位置" → 自动回复 "y"

#### 5.3 保存头手标定结果

**端点**: `POST /api/v1/robots/{robot_id}/head-hand-calibration/save`

**描述**: 确认保存头手标定结果

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "头手标定结果已确认保存",
  "status": {
    "head_calibration_saved": true,
    "backup_file": "/home/lab/.config/lejuconfig/arms_zero.yaml.head_cali.bak",
    "save_time": "2024-01-30 15:30:45"
  }
}
```

### 6. 上位机管理

#### 6.1 连接上位机

**端点**: `POST /api/v1/robots/{robot_id}/upper-computer/connect`

**描述**: 连接上位机SSH

**路径参数**:
- `robot_id` (string): 机器人ID

**查询参数**:
- `upper_host` (string, optional): 上位机IP地址，默认 "192.168.26.1"
- `upper_port` (int, optional): 上位机SSH端口，默认 22
- `upper_username` (string, optional): 上位机用户名，默认 "kuavo"
- `upper_password` (string, optional): 上位机密码，默认 "leju_kuavo"

**响应示例**:
```json
{
  "message": "上位机连接成功",
  "upper_host": "192.168.26.1",
  "status": "connected"
}
```

#### 6.2 断开上位机连接

**端点**: `DELETE /api/v1/robots/{robot_id}/upper-computer/connect`

**描述**: 断开上位机SSH连接

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "上位机连接已断开",
  "status": "disconnected"
}
```

#### 6.3 获取上位机状态

**端点**: `GET /api/v1/robots/{robot_id}/upper-computer/status`

**描述**: 获取上位机连接状态

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "robot_id": "1",
  "upper_computer_connected": true,
  "status": "connected"
}
```

#### 6.4 执行上位机命令

**端点**: `POST /api/v1/robots/{robot_id}/upper-computer/command`

**描述**: 在上位机执行命令

**路径参数**:
- `robot_id` (string): 机器人ID

**查询参数**:
- `command` (string): 要执行的命令

**响应示例**:
```json
{
  "success": true,
  "stdout": "Python 3.8.10",
  "stderr": "",
  "command": "python3 --version"
}
```

### 7. 通用标定管理

#### 7.1 发送用户响应

**端点**: `POST /api/v1/robots/{robot_id}/calibrations/response`

**描述**: 发送用户对标定提示的响应（支持实时交互式输入）

**路径参数**:
- `robot_id` (string): 机器人ID

**请求体**:
```json
{
  "response": "y"  // 用户输入
}
```

**响应示例**:
```json
{
  "message": "响应已发送"
}
```

**交互说明**:
- 标定过程支持实时输出和交互式输入
- 系统会自动处理PTY（伪终端）交互 
- 支持所有标定脚本的用户提示响应

**错误响应**:
- `404 Not Found`: 没有活动的标定会话
- `400 Bad Request`: 当前不在等待用户输入状态

#### 7.2 停止标定

**端点**: `DELETE /api/v1/robots/{robot_id}/calibrations/current`

**描述**: 停止当前正在进行的标定

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "标定已停止"
}
```

**错误响应**:
- `404 Not Found`: 没有正在进行的标定任务

#### 7.3 清理标定会话

**端点**: `DELETE /api/v1/robots/{robot_id}/calibrations/sessions`

**描述**: 清理所有标定会话

**路径参数**:
- `robot_id` (string): 机器人ID

**响应示例**:
```json
{
  "message": "已清理 2 个标定会话",
  "cleaned_sessions": 2
}
```

## WebSocket 接口

### 连接端点

`ws://localhost:8001/ws/{client_id}`

**参数**:
- `client_id` (string): 客户端唯一标识符

### 消息类型

#### 1. 连接建立

**服务器发送**:
```json
{
  "type": "connection_established",
  "client_id": "client-001"
}
```

#### 2. 订阅机器人

**客户端发送**:
```json
{
  "type": "subscribe",
  "robot_id": "1"
}
```

**服务器响应**:
```json
{
  "type": "subscribed",
  "robot_id": "1"
}
```

#### 3. 取消订阅

**客户端发送**:
```json
{
  "type": "unsubscribe",
  "robot_id": "1"
}
```

**服务器响应**:
```json
{
  "type": "unsubscribed",
  "robot_id": "1"
}
```

#### 4. 心跳

**客户端发送**:
```json
{
  "type": "ping"
}
```

**服务器响应**:
```json
{
  "type": "pong"
}
```

#### 5. 机器人状态更新

**服务器发送**:
```json
{
  "type": "robot_status_update",
  "data": {
    "robot_id": "1",
    "status": "connected",
    "timestamp": "2024-08-01T10:00:00"
  }
}
```

#### 6. 零点标定状态更新

**服务器发送**:
```json
{
  "type": "zero_point_calibration_status",
  "data": {
    "session_id": "zp_cal_1_1722470400",
    "robot_id": "1",
    "calibration_type": "full_body",
    "current_step": "initialize_zero",
    "status": "waiting_user",
    "start_time": "2024-08-01T10:00:00",
    "step_progress": {
      "current_step": 3,
      "total_steps": 4,
      "step_name": "初始化零点",
      "is_loading": false,
      "user_prompt": "是否启动机器人控制系统？(y/N):"
    },
    "warnings": [],
    "error_message": null,
    "joint_data": []
  }
}
```

#### 7. 标定日志

**服务器发送**:
```json
{
  "type": "calibration_log",
  "data": {
    "session_id": "zp_cal_1_1722470400",
    "robot_id": "1",
    "log": "[INFO] 正在启动机器人控制系统...",
    "timestamp": "2024-08-01T10:00:00"
  }
}
```

#### 8. 头手标定完成

**服务器发送**:
```json
{
  "type": "head_hand_calibration_complete",
  "session_id": "head_hand_cal_1_1722470400",
  "robot_id": "1",
  "success": true,
  "error": null
}
```

#### 9. 错误消息

**服务器发送**:
```json
{
  "type": "error",
  "message": "未知消息类型: invalid_type"
}
```

## 错误码说明

| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求错误（参数错误、业务逻辑错误等） |
| 404 | 资源未找到 |
| 422 | 数据验证失败 |
| 500 | 服务器内部错误 |

## 字段命名规范说明

### 新旧字段对照表

系统同时支持新旧两套字段命名，确保向后兼容：

| 功能 | 新字段名（推荐） | 旧字段名（兼容） |
|------|-----------------|-----------------|
| 机器人型号 | robot_model | hardware_model |
| 机器人版本 | robot_version | - |
| 机器人SN号 | robot_sn | sn_number |
| 软件版本 | robot_software_version | software_version |
| 末端执行器 | end_effector_model | end_effector_type |

### 分页使用示例

```bash
# 获取第1页，每页10条（默认）
GET /api/v1/robots?page=1&page_size=10

# 获取第2页，每页5条
GET /api/v1/robots?page=2&page_size=5

# 获取全部记录（最多100条）
GET /api/v1/robots?page=1&page_size=100
```

**前端处理示例**:
```javascript
// 处理分页响应格式
async function loadRobots(page = 1, pageSize = 10) {
    const response = await fetch(`/api/v1/robots?page=${page}&page_size=${pageSize}`);
    const data = await response.json();
    
    let robots = [];
    let pagination = null;
    
    // 新分页格式
    if (data.items && Array.isArray(data.items)) {
        robots = data.items;
        pagination = data.pagination;
    } 
    // 兼容旧格式
    else if (Array.isArray(data)) {
        robots = data;
    }
    
    return { robots, pagination };
}
```

## 使用示例

### Python 示例

```python
import requests
import json
import websocket
import threading

# 基础配置
base_url = "http://localhost:8001/api/v1"

# 1. 获取机器人列表（带分页）
response = requests.get(f"{base_url}/robots?page=1&page_size=10")
data = response.json()
robots = data["items"]
pagination = data["pagination"]
print(f"共 {pagination['total']} 台设备，当前第 {pagination['page']} 页")

# 2. 测试连接
test_data = {
    "name": "TestRobot",
    "ip_address": "192.168.1.100",
    "port": 22,
    "ssh_user": "leju",
    "ssh_password": "password123",
    "device_type": "lower"  # 设备类型: upper/lower
}
response = requests.post(f"{base_url}/robots/test-connection", json=test_data)
test_result = response.json()
if test_result["success"]:
    device_info = test_result["device_info"]
    print(f"设备型号: {device_info['robot_model']}")
    print(f"设备类型: {device_info['device_type']}")

# 3. 添加机器人
robot_data = {
    "name": "TestRobot",
    "ip_address": "192.168.1.100",
    "port": 22,
    "ssh_user": "leju",
    "ssh_password": "password123",
    "device_type": "lower"  # 设备类型: upper/lower
}
response = requests.post(f"{base_url}/robots", json=robot_data)
robot = response.json()
robot_id = robot["id"]

# 4. 连接机器人
response = requests.post(f"{base_url}/robots/{robot_id}/connect")
print(response.json())

# 5. 获取机器人实时状态
response = requests.get(f"{base_url}/robots/{robot_id}/status")
status = response.json()
print(f"服务状态: {status['service_status']}")
print(f"电量: {status['battery_level']}")
print(f"故障码: {status['error_code']}")

# 6. 启动零点标定
calibration_data = {"calibration_type": "full_body"}
response = requests.post(f"{base_url}/robots/{robot_id}/zero-point-calibration", json=calibration_data)
calibration = response.json()
session_id = calibration["session_id"]

# 7. 跳转到步骤3
step_data = {"step": "initialize_zero"}
response = requests.post(f"{base_url}/robots/{robot_id}/zero-point-calibration/{session_id}/go-to-step", json=step_data)
print(response.json())

# 8. 执行一键标定
execute_data = {"calibration_mode": "full_body"}
response = requests.post(f"{base_url}/robots/{robot_id}/zero-point-calibration/{session_id}/execute-calibration", json=execute_data)
print(response.json())

# 9. 关节调试
debug_data = {
    "joints": [
        {"id": 1, "name": "joint_02", "position": 0.051},
        {"id": 2, "name": "joint_03", "position": 0.011}
    ]
}
response = requests.post(f"{base_url}/robots/{robot_id}/zero-point-calibration/{session_id}/joint-debug", json=debug_data)
print(response.json())

# 10. WebSocket连接监听标定状态
def on_message(ws, message):
    data = json.loads(message)
    print(f"收到消息: {data['type']}")
    
    if data["type"] == "zero_point_calibration_status":
        status_data = data["data"]
        if status_data["status"] == "waiting_user":
            # 发送用户响应
            response_data = {"response": "y"}
            requests.post(f"{base_url}/robots/{robot_id}/calibrations/response", 
                         json=response_data)

def on_open(ws):
    # 订阅机器人状态
    ws.send(json.dumps({
        "type": "subscribe",
        "robot_id": robot_id
    }))

ws = websocket.WebSocketApp(f"ws://localhost:8001/ws/client-001",
                           on_message=on_message,
                           on_open=on_open)

# 在新线程中运行WebSocket
ws_thread = threading.Thread(target=ws.run_forever)
ws_thread.daemon = True
ws_thread.start()
```

### JavaScript 示例

```javascript
// 基础配置
const API_BASE = 'http://localhost:8001/api/v1';
const WS_BASE = 'ws://localhost:8001';

// 1. 获取机器人列表（带分页）
async function getRobotList(page = 1, pageSize = 10) {
    const response = await fetch(`${API_BASE}/robots?page=${page}&page_size=${pageSize}`);
    const data = await response.json();
    
    // 处理新旧格式兼容
    let robots = [];
    let pagination = null;
    
    if (data.items && Array.isArray(data.items)) {
        robots = data.items;
        pagination = data.pagination;
        console.log(`共 ${pagination.total} 台设备，当前第 ${pagination.page} 页`);
    } else if (Array.isArray(data)) {
        robots = data;
    }
    
    return { robots, pagination };
}

// 2. 测试连接
async function testConnection(robotData) {
    const response = await fetch(`${API_BASE}/robots/test-connection`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(robotData)
    });
    const result = await response.json();
    
    if (result.success) {
        console.log(`设备型号: ${result.device_info.robot_model}`);
        console.log(`软件版本: ${result.device_info.robot_software_version}`);
    }
    
    return result;
}

// 3. 添加机器人
async function addRobot() {
    const response = await fetch(`${API_BASE}/robots`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: 'TestRobot',
            ip_address: '192.168.1.100',
            port: 22,
            ssh_user: 'leju',
            ssh_password: 'password123',
            device_type: 'lower'  // 设备类型: upper/lower
        })
    });
    return await response.json();
}

// 4. 获取机器人实时状态
async function getRobotStatus(robotId) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/status`);
    const status = await response.json();
    
    console.log(`服务状态: ${status.service_status}`);
    console.log(`电量: ${status.battery_level}`);
    console.log(`故障码: ${status.error_code}`);
    
    return status;
}

// 5. 启动零点标定
async function startZeroPointCalibration(robotId) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/zero-point-calibration`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            calibration_type: 'full_body'
        })
    });
    return await response.json();
}

// 6. 执行一键标定
async function executeCalibration(robotId, sessionId) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/zero-point-calibration/${sessionId}/execute-calibration`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            calibration_mode: 'full_body'
        })
    });
    return await response.json();
}

// 7. 关节调试
async function debugJoints(robotId, sessionId, joints) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/zero-point-calibration/${sessionId}/joint-debug`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            joints: joints
        })
    });
    return await response.json();
}

// 8. 保存关节数据
async function saveJointData(robotId, fileType, jointData) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/calibration-files/${fileType}/data`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            joint_data: jointData
        })
    });
    return await response.json();
}

// 9. 头手标定环境检查
async function checkCalibrationConfig(robotId) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/calibration-config-check`);
    return await response.json();
}

// 10. 启动头手标定
async function startHeadHandCalibration(robotId) {
    const response = await fetch(`${API_BASE}/robots/${robotId}/head-hand-calibration`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            calibration_type: 'head_hand',
            include_head: true,
            include_arms: true,
            arm_selection: 'both'
        })
    });
    return await response.json();
}

// 11. WebSocket连接
function connectWebSocket(robotId) {
    const ws = new WebSocket(`${WS_BASE}/ws/client-001`);
    
    ws.onopen = () => {
        console.log('WebSocket已连接');
        // 订阅机器人状态
        ws.send(JSON.stringify({
            type: 'subscribe',
            robot_id: robotId
        }));
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('收到消息:', data);
        
        switch(data.type) {
            case 'robot_status_update':
                console.log('机器人状态更新:', data.data.status);
                break;
            case 'zero_point_calibration_status':
                handleZeroPointStatus(data.data);
                break;
            case 'calibration_log':
                handleCalibrationLog(data.data);
                break;
            case 'head_hand_calibration_complete':
                handleHeadHandComplete(data);
                break;
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket连接已关闭');
        // 实现自动重连
        setTimeout(() => connectWebSocket(robotId), 3000);
    };
    
    return ws;
}

function handleZeroPointStatus(statusData) {
    console.log('零点标定状态:', statusData.status);
    console.log('当前步骤:', statusData.current_step);
    
    if (statusData.status === 'waiting_user' && statusData.step_progress.user_prompt) {
        console.log('等待用户输入:', statusData.step_progress.user_prompt);
        // 可以在此处弹出确认对话框
    }
}

function handleCalibrationLog(logData) {
    console.log('标定日志:', logData.log);
    // 在UI中显示日志
}

function handleHeadHandComplete(completeData) {
    if (completeData.success) {
        console.log('头手标定完成');
    } else {
        console.error('头手标定失败:', completeData.error);
    }
}

// 使用示例
async function main() {
    // 添加机器人
    const robot = await addRobot();
    const robotId = robot.id;
    
    // 建立WebSocket连接
    const ws = connectWebSocket(robotId);
    
    // 启动零点标定
    const calibration = await startZeroPointCalibration(robotId);
    const sessionId = calibration.session_id;
    
    // 跳转到步骤3
    await fetch(`${API_BASE}/robots/${robotId}/zero-point-calibration/${sessionId}/go-to-step`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({step: 'initialize_zero'})
    });
    
    // 执行一键标定
    await executeCalibration(robotId, sessionId);
}

// 启动示例
main().catch(console.error);
```

## 数据格式说明

### 关节数据数组

手臂关节数据（ID 1-14）：
- ID 1-12: 对应 joint_02 到 joint_13 (左臂6个 + 右臂6个)
- ID 13-14: 对应 neck_01, neck_02 (头部2个)

腿部关节数据（ID 1-14）：
- ID 1-12: 左腿6个 + 右腿6个
- ID 13-14: 左肩部 + 右肩部

### 角度单位

所有角度数据使用**弧度(radian)**作为单位，而非度数。

### 文件路径映射

- `arms_zero`: `/home/lab/.config/lejuconfig/arms_zero.yaml`
- `legs_offset`: `/home/lab/.config/lejuconfig/offset.csv`

### ROS话题和消息

- **关节调试话题**: `/kuavo_arm_traj`
- **消息类型**: `sensor_msgs/JointState`
- **标定启动命令**: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true`

---

**版本**: 1.2.0  
**最后更新**: 2025-08-01  
**开发状态**: 生产就绪