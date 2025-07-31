# KUAVO Studio API 接口文档

## 概述

KUAVO Studio 提供 RESTful API 和 WebSocket 接口，用于管理和控制 KUAVO 人形机器人。

- **基础URL**: `http://localhost:8001`
- **API版本**: v1
- **认证方式**: 暂无（后续可添加 JWT 认证）

## API 端点

### 1. 机器人管理

#### 1.1 获取机器人列表

**端点**: `GET /api/v1/robots`

**描述**: 获取所有已添加的机器人列表

**响应示例**:
```json
[
  {
    "id": 1,
    "name": "Robot001",
    "ip_address": "192.168.1.100",
    "port": 22,
    "ssh_user": "leju",
    "connection_status": "connected",
    "hardware_model": "KUAVO_V1.0",
    "software_version": "1.2.3",
    "sn": "KV100123456",
    "created_at": "2024-01-20T10:00:00",
    "updated_at": "2024-01-20T10:00:00"
  }
]
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
  "ssh_password": "password123"
}
```

**响应示例**:
```json
{
  "id": 1,
  "name": "Robot001",
  "ip_address": "192.168.1.100",
  "port": 22,
  "ssh_user": "leju",
  "connection_status": "disconnected",
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
- `robot_id` (integer): 机器人ID

**响应示例**: 同 1.1 中的单个机器人对象

**错误响应**:
- `404 Not Found`: 机器人未找到

#### 1.4 删除机器人

**端点**: `DELETE /api/v1/robots/{robot_id}`

**描述**: 删除指定的机器人

**路径参数**:
- `robot_id` (integer): 机器人ID

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

**描述**: 测试与机器人的SSH连接（不保存连接）

**请求体**:
```json
{
  "ip_address": "192.168.1.100",
  "port": 22,
  "username": "leju",
  "password": "password123"
}
```

**响应示例**:
```json
{
  "success": true,
  "robot_info": {
    "hardware_model": "KUAVO_V1.0",
    "software_version": "1.2.3",
    "sn": "KV100123456"
  }
}
```

**错误响应示例**:
```json
{
  "success": false,
  "error": "连接失败：认证失败，请检查用户名和密码"
}
```

#### 2.2 连接机器人

**端点**: `POST /api/v1/robots/{robot_id}/connect`

**描述**: 建立与机器人的SSH连接

**路径参数**:
- `robot_id` (integer): 机器人ID

**响应示例**:
```json
{
  "message": "连接成功",
  "status": "connected",
  "robot_info": {
    "hardware_model": "KUAVO_V1.0",
    "software_version": "1.2.3",
    "sn": "KV100123456"
  }
}
```

**错误响应**:
- `404 Not Found`: 机器人未找到
- `400 Bad Request`: 连接失败（包含错误详情）

#### 2.3 断开连接

**端点**: `POST /api/v1/robots/{robot_id}/disconnect`

**描述**: 断开与机器人的SSH连接

**路径参数**:
- `robot_id` (integer): 机器人ID

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
- `robot_id` (integer): 机器人ID

**响应示例**:
```json
{
  "message": "状态已重置"
}
```

### 3. 标定管理

#### 3.1 全身零点标定

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration`

**描述**: 启动全身零点标定流程

**路径参数**:
- `robot_id` (integer): 机器人ID

**响应示例**:
```json
{
  "session_id": "cal_1_1705741200",
  "robot_id": 1,
  "calibration_type": "zero_point",
  "status": "pending"
}
```

**标定流程说明**:
- 步骤1: 标定准备 - 确认工具安装
- 步骤2: 读取配置文件 - 加载完成后自动进入步骤3
- 步骤3: 初始化零点 - 执行标定脚本，支持交互式用户输入
- 步骤4: 标定结果 - 显示position数据

**错误响应**:
- `404 Not Found`: 机器人未找到
- `400 Bad Request`: 机器人未连接或已有标定任务进行中

#### 3.2 读取标定文件数据

**端点**: `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/data`

**描述**: 读取标定配置文件内容

**路径参数**:
- `robot_id` (integer): 机器人ID
- `file_type` (string): 文件类型 (offset, arms_zero, motor_config)

**响应示例**:
```json
{
  "file_path": "/home/lab/.config/lejuconfig/offset.csv",
  "content": [
    {"joint_name": "neck_pitch", "offset": 0.02, "description": "颈部俯仰关节"},
    {"joint_name": "neck_yaw", "offset": -0.01, "description": "颈部偏航关节"}
  ]
}
```

#### 3.3 更新标定文件数据

**端点**: `PUT /api/v1/robots/{robot_id}/calibration-files/{file_type}/data`

**描述**: 更新标定配置文件内容

**请求体**:
```json
{
  "data": [
    {"joint_name": "neck_pitch", "offset": 0.03},
    {"joint_name": "neck_yaw", "offset": -0.02}
  ]
}
```

**响应示例**:
```json
{
  "message": "文件更新成功",
  "backup_file": "/home/lab/.config/lejuconfig/offset.csv.bak.1705741200"
}
```

#### 3.3.1 零点标定步骤导航

**端点**: `POST /api/v1/robots/{robot_id}/zero-point-calibration/step`

**描述**: 导航到指定的标定步骤

**路径参数**:
- `robot_id` (string): 机器人ID

**请求体**:
```json
{
  "step": 2  // 目标步骤 (1-4)
}
```

**响应示例**:
```json
{
  "message": "已切换到步骤 2"
}
```

**错误响应**:
- `404 Not Found`: 没有找到标定会话
- `400 Bad Request`: 无效的步骤号或步骤切换被禁止

#### 3.4 头手标定环境检查

**端点**: `GET /api/v1/robots/{robot_id}/calibration-config-check`

**描述**: 执行头手标定前的环境预检查

**响应示例**:
```json
{
  "environment_checks": [
    {"item": "sudo权限", "status": "passed", "description": "用户具有sudo权限"},
    {"item": "虚拟环境", "status": "passed", "description": "kuavo虚拟环境已激活"},
    {"item": "AprilTag检测", "status": "failed", "description": "未检测到AprilTag"},
    {"item": "网络连接", "status": "passed", "description": "192.168.26.1连接正常"},
    {"item": "rosbag文件", "status": "passed", "description": "找到标定数据文件"},
    {"item": "标定工具", "status": "passed", "description": "标定程序运行正常"},
    {"item": "密码配置", "status": "passed", "description": "SSH密钥配置正确"}
  ],
  "overall_status": "warning",
  "ready_for_calibration": false
}
```

#### 3.5 启动头手标定

**端点**: `POST /api/v1/robots/{robot_id}/head-hand-calibration`

**描述**: 启动头手标定流程，执行One_button_start.sh脚本

**响应示例**:
```json
{
  "session_id": "head_hand_cal_1_1705741200",
  "robot_id": 1,
  "calibration_type": "head_hand",
  "status": "running",
  "message": "头手标定已启动"
}
```

#### 3.6 保存头手标定结果

**端点**: `POST /api/v1/robots/{robot_id}/head-hand-calibration/save`

**描述**: 保存头手标定结果到系统

**响应示例**:
```json
{
  "message": "标定结果保存成功",
  "saved_files": [
    "/home/lab/.config/lejuconfig/arms_zero.yaml",
    "/home/lab/.config/lejuconfig/head_calibration.yaml"
  ],
  "backup_files": [
    "/home/lab/.config/lejuconfig/arms_zero.yaml.bak.1705741200"
  ]
}
```

#### 3.7 发送用户响应

**端点**: `POST /api/v1/robots/{robot_id}/calibrations/response`

**描述**: 发送用户对标定提示的响应（支持实时交互式输入）

**路径参数**:
- `robot_id` (integer): 机器人ID

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

#### 3.8 停止标定

**端点**: `DELETE /api/v1/robots/{robot_id}/calibrations/current`

**描述**: 停止当前正在进行的标定

**路径参数**:
- `robot_id` (integer): 机器人ID

**响应示例**:
```json
{
  "message": "标定已停止"
}
```

**错误响应**:
- `404 Not Found`: 没有正在进行的标定任务

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
    "robot_id": 1,
    "status": "connected",
    "timestamp": "2024-01-20T10:00:00"
  }
}
```

#### 6. 标定状态更新

**服务器发送**:
```json
{
  "type": "calibration_status",
  "data": {
    "session_id": "cal_1_1705741200",
    "robot_id": 1,
    "calibration_type": "zero_point",
    "status": "waiting_for_user",
    "current_step": 1,
    "user_prompt": "是否启动机器人控制系统？(y/N):",
    "error_message": null
  }
}
```

**状态说明**:
- `pending`: 等待开始
- `running`: 运行中
- `waiting_for_user`: 等待用户输入
- `parsing_data`: 正在解析数据(新增)
- `success`: 成功完成
- `failed`: 失败

**步骤进度**:
标定状态更新中还包含 `step_progress` 字段，用于跟踪当前步骤信息：
```json
{
  "current_step": 2,
  "total_steps": 4,
  "step_name": "读取配置文件",
  "is_loading": true,
  "user_prompt": null
}
```

#### 7. 标定日志

**服务器发送**:
```json
{
  "type": "calibration_log",
  "data": {
    "session_id": "cal_1_1705741200",
    "robot_id": 1,
    "log": "[INFO] 正在启动机器人控制系统..."
  }
}
```

#### 8. 错误消息

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
| 500 | 服务器内部错误 |

## 使用示例

### Python 示例

```python
import requests
import json
import websocket

# 基础配置
base_url = "http://localhost:8001/api/v1"

# 1. 添加机器人
robot_data = {
    "name": "TestRobot",
    "ip_address": "192.168.1.100",
    "port": 22,
    "ssh_user": "leju",
    "ssh_password": "password123"
}

response = requests.post(f"{base_url}/robots", json=robot_data)
robot = response.json()
robot_id = robot["id"]

# 2. 连接机器人
response = requests.post(f"{base_url}/robots/{robot_id}/connect")
print(response.json())

# 3. 启动标定
calibration_data = {"calibration_type": "zero_point"}
response = requests.post(f"{base_url}/robots/{robot_id}/calibrations", json=calibration_data)
calibration = response.json()

# 4. WebSocket连接监听标定状态
def on_message(ws, message):
    data = json.loads(message)
    if data["type"] == "calibration_status":
        status = data["data"]["status"]
        if status == "waiting_for_user":
            # 发送用户响应
            response_data = {"response": "y"}
            requests.post(f"{base_url}/robots/{robot_id}/calibrations/response", 
                         json=response_data)

ws = websocket.WebSocketApp(f"ws://localhost:8001/ws/client-001",
                           on_message=on_message)
ws.run_forever()
```

### JavaScript 示例

```javascript
// 基础配置
const API_BASE = 'http://localhost:8001/api/v1';
const WS_BASE = 'ws://localhost:8001';

// 1. 添加机器人
async function addRobot() {
    const response = await fetch(`${API_BASE}/robots`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            name: 'TestRobot',
            ip_address: '192.168.1.100',
            port: 22,
            ssh_user: 'leju',
            ssh_password: 'password123'
        })
    });
    return await response.json();
}

// 2. WebSocket连接
function connectWebSocket(robotId) {
    const ws = new WebSocket(`${WS_BASE}/ws/client-001`);
    
    ws.onopen = () => {
        // 订阅机器人
        ws.send(JSON.stringify({
            type: 'subscribe',
            robot_id: robotId.toString()
        }));
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('收到消息:', data);
        
        if (data.type === 'calibration_status') {
            handleCalibrationStatus(data.data);
        }
    };
}
```

