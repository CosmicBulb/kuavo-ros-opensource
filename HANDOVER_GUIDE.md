# KUAVO Studio 后端交接文档

## 项目概述

KUAVO Studio 是一个用于管理和控制 KUAVO 人形机器人的后端服务系统。该系统提供了完整的 RESTful API 和 WebSocket 接口，支持设备管理、SSH 连接控制、零点标定、头手标定、关节调试等功能。

## 技术架构

### 核心技术栈
- **Web框架**: FastAPI (异步高性能)
- **数据库**: SQLAlchemy + SQLite (可切换至 PostgreSQL/MySQL)
- **SSH通信**: Paramiko
- **WebSocket**: FastAPI WebSocket
- **异步支持**: asyncio
- **依赖注入**: FastAPI 内置 DI
- **数据验证**: Pydantic
- **伪终端**: ptyprocess (支持交互式命令)

### 项目结构
```
backend/
├── app/
│   ├── api/              # API路由层
│   │   ├── v1/          # API v1版本
│   │   │   ├── __init__.py      # 路由聚合
│   │   │   ├── robots.py        # 机器人CRUD（支持分页）
│   │   │   ├── robots_fast.py   # 快速测试端点
│   │   │   └── calibration.py   # 标定管理（1382行完整API）
│   │   └── websocket.py         # WebSocket端点
│   ├── core/            # 核心配置
│   │   ├── config.py    # 应用配置
│   │   └── database.py  # 数据库配置
│   ├── models/          # 数据库模型
│   │   ├── robot.py     # 机器人模型（包含新字段）
│   │   └── calibration.py # 标定模型
│   ├── schemas/         # Pydantic模式
│   │   ├── robot.py     # 机器人数据模式（含分页）
│   │   └── calibration.py # 标定数据模式（214行完整验证）
│   ├── services/        # 业务逻辑层
│   │   ├── ssh_service.py                    # SSH连接管理+状态获取
│   │   ├── calibration_service.py            # 基础标定服务
│   │   ├── zero_point_calibration_service.py # 零点标定专用服务（完整4步流程）
│   │   ├── calibration_file_service.py       # 标定文件管理（522行完整实现）
│   │   └── calibration_data_parser.py        # 标定数据解析器（Slave位置提取）
│   └── simulator/       # 模拟器
│       ├── robot_simulator.py     # 机器人模拟器（634行完整实现）
│       └── mock_config_files.py   # 模拟配置文件
├── main.py             # 生产模式应用入口（含CORS配置）
├── run_simulator_8001.py  # 模拟器模式入口
└── requirements.txt    # 依赖列表
```

## 核心功能模块

### 1. 设备管理模块
- **功能**: 机器人设备的增删改查，支持分页和设备类型区分
- **关键文件**: 
  - `app/api/v1/robots.py` - API端点（含分页支持）
  - `app/models/robot.py` - 数据模型（新增字段）
  - `app/schemas/robot.py` - 数据验证（含分页模式）
- **特性**:
  - 支持ID和SN号双重查找
  - 连接状态实时更新
  - 设备类型区分：
    - device_type（设备类型：upper/lower）
    - 前端显示为上位机/下位机
  - 设备信息自动获取（新字段）：
    - robot_model（机器人型号）
    - robot_version（机器人版本）
    - robot_sn（机器人SN号）
    - robot_software_version（软件版本）
    - end_effector_model（末端执行器型号）
  - 实时状态监控：
    - service_status（服务状态）
    - battery_level（电量）
    - error_code（故障码）
  - 分页查询支持（page/page_size）

### 2. SSH连接管理
- **功能**: 管理与机器人的SSH连接
- **关键文件**: 
  - `app/services/ssh_service.py` - SSH服务
- **特性**:
  - 连接池管理
  - 自动重连机制
  - 命令执行封装
  - **网络环境验证**: ping测试、子网检查、延迟测量
  - 跨平台网络诊断工具
  - **交互式命令执行**: 支持实时输出和用户输入（通过PTY）
  - **进程管理**: 标定进程清理和会话管理
  - **模拟器模式优化**: 避免执行真实系统命令
  - **上位机管理**: 双SSH架构支持（下位机+上位机192.168.26.1）

### 3. 零点标定模块
- **功能**: 完整的4步零点标定流程
- **关键文件**:
  - `app/api/v1/calibration.py` - API端点（零点标定相关）
  - `app/services/zero_point_calibration_service.py` - 零点标定逻辑
  - `app/services/calibration_data_parser.py` - 数据解析器
- **标定流程**:
  1. **confirm_tools**: 确认安装工具（辅助工装安装）
  2. **read_config**: 读取当前配置（加载关节数据）
  3. **initialize_zero**: 初始化零点（执行ROS标定命令）
  4. **remove_tools**: 移除辅助工装（标定完成）
- **核心功能**:
  - **一键标定**: 自动执行 `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true`
  - **关节调试**: 实时发送 `rostopic pub /kuavo_arm_traj sensor_msgs/JointState`
  - **数据解析**: 智能提取"Slave xx actual position"数据
  - **会话管理**: 完整的会话生命周期管理
  - **实时通信**: WebSocket状态和日志推送

### 4. 标定文件管理模块
- **功能**: 标定配置文件的读写管理
- **关键文件**:
  - `app/services/calibration_file_service.py` - 文件管理服务
- **支持文件类型**:
  - `arms_zero`: `/home/lab/.config/lejuconfig/arms_zero.yaml` (手臂零点配置)
  - `legs_offset`: `/home/lab/.config/lejuconfig/offset.csv` (腿部偏移配置)
- **关节映射**:
  - 手臂: ID 1-12 → joint_02-joint_13, ID 13-14 → neck_01-neck_02
  - 腿部: ID 1-14 → 左腿6个+右腿6个+肩部2个
- **安全特性**:
  - **关节参数安全验证**: 修改幅度限制(建议≤0.05，强制≤0.1)
  - **数据完整性检查**: 关节数据验证和异常检测
  - **备份机制**: 自动备份原始文件
  - **原子操作**: 临时文件+移动确保数据完整性

### 5. 头手标定模块
- **功能**: ETH头手标定自动化
- **关键文件**: 
  - `app/api/v1/calibration.py` - 头手标定API
- **标定流程**:
  - **环境检查**: 7项预检查（虚拟环境、AprilTag、rosbag、相机、网络、上位机）
  - **脚本执行**: 自动执行 `One_button_start.sh` 
  - **交互处理**: expect脚本自动化用户交互
  - **双SSH架构**: 下位机控制 + 上位机(192.168.26.1)连接
- **自动化交互**:
  - "是否启动机器人控制系统？(y/N)" → 自动回复 "y"
  - "机器人是否已完成缩腿动作" → 自动回复 "y"  
  - "是否继续头部标定？(y/N)" → 自动回复 "y"
  - "按下回车键继续保存文件" → 自动回复回车
  - "标定已完成，是否应用新的零点位置" → 自动回复 "y"

### 6. WebSocket通信
- **功能**: 实时状态推送
- **关键文件**: 
  - `app/api/websocket.py` - WebSocket管理
- **消息类型**:
  - `connection_established`: 连接建立
  - `robot_status_update`: 机器人状态更新
  - `zero_point_calibration_status`: 零点标定状态更新
  - `calibration_log`: 标定日志实时推送
  - `head_hand_calibration_complete`: 头手标定完成通知
  - `error`: 错误消息

### 7. 模拟器模式
- **功能**: 无需硬件的开发测试
- **关键文件**: 
  - `app/simulator/robot_simulator.py` - 完整模拟器实现
  - `app/simulator/mock_config_files.py` - 模拟配置文件
- **启用方式**: 
  - 设置环境变量 `USE_ROBOT_SIMULATOR=true`
  - 或运行 `python run_simulator_8001.py`
- **模拟功能**:
  - SSH连接和命令执行模拟
  - ROS命令模拟（roslaunch、rostopic）
  - 标定脚本执行模拟
  - 文件读写模拟
  - 完整的标定流程模拟

### 8. 数据解析和验证
- **标定数据解析器** (`calibration_data_parser.py`):
  - 专用的正则表达式解析引擎
  - 处理多种"Slave xx actual position"格式
  - 数据完整性验证和异常检测
  - 支持格式：
    - `Slave 01 actual position 9.6946716`
    - `30400001: Slave 01 actual position 9.6946716,Encoder 63535.0`
    - `Rated current 42.43`

- **关节参数验证** (`schemas/calibration.py`):
  - Schema级别参数验证
  - 多层安全检查(0.05建议阈值，0.1强制限制)
  - 详细的警告和错误消息
  - 防止危险的关节参数修改

## 部署指南

### 开发环境

1. **安装依赖**
```bash
cd backend
pip install -r requirements.txt
```

2. **启动服务**
```bash
# 普通模式
python main.py

# 模拟器模式（推荐开发使用）
python run_simulator_8001.py
```

### 生产环境

1. **环境变量配置**
```bash
export KUAVO_PORT=8001
export DATABASE_URL=postgresql://user:pass@localhost/kuavo
export SECRET_KEY=your-secret-key-here
export USE_ROBOT_SIMULATOR=false
```

2. **使用 Gunicorn 部署**
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

3. **使用 Docker 部署**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

## 验证指南

### 验证后端服务
```bash
cd backend
# 生产模式
python main.py

# 或模拟器模式
python run_simulator_8001.py
```

### 验证前端服务
```bash
cd frontend
python start_frontend.py
```

### 验证API接口
启动后端后访问:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## API使用指南

详细的API文档请参考 `API_DOCUMENTATION.md`

### 核心API端点总览

#### 设备管理相关
- `GET /api/v1/robots/` - 获取设备列表（支持分页）
  - 参数：`page`（页码）、`page_size`（每页大小）
  - 返回：包含`items`和`pagination`的响应
- `POST /api/v1/robots/` - 添加新设备
- `GET /api/v1/robots/{robot_id}` - 获取设备详情
- `GET /api/v1/robots/{robot_id}/status` - 获取设备实时状态
- `DELETE /api/v1/robots/{robot_id}` - 删除设备
- `POST /api/v1/robots/{robot_id}/connect` - 连接设备
- `POST /api/v1/robots/{robot_id}/disconnect` - 断开设备
- `POST /api/v1/robots/test-connection` - 测试设备连接

#### 零点标定相关
- `POST /api/v1/robots/{robot_id}/zero-point-calibration` - 启动零点标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/go-to-step` - 步骤导航
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/execute-calibration` - 执行标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/joint-debug` - 关节调试
- `GET /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/summary` - 获取标定汇总
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/save-zero-point` - 保存零点数据
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/validate` - 验证标定

#### 标定文件管理
- `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 读取文件数据
- `PUT /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 保存文件数据

#### 头手标定相关
- `GET /api/v1/robots/{robot_id}/calibration-config-check` - 环境检查
- `POST /api/v1/robots/{robot_id}/head-hand-calibration` - 启动头手标定
- `POST /api/v1/robots/{robot_id}/head-hand-calibration/save` - 保存结果

#### 上位机管理
- `POST /api/v1/robots/{robot_id}/upper-computer/connect` - 连接上位机
- `DELETE /api/v1/robots/{robot_id}/upper-computer/connect` - 断开上位机
- `GET /api/v1/robots/{robot_id}/upper-computer/status` - 获取状态
- `POST /api/v1/robots/{robot_id}/upper-computer/command` - 执行命令

### 快速开始

1. **添加机器人**
```bash
curl -X POST http://localhost:8001/api/v1/robots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Robot001",
    "ip_address": "192.168.1.100",
    "port": 22,
    "ssh_user": "leju",
    "ssh_password": "password"
  }'
```

2. **连接机器人**
```bash
curl -X POST http://localhost:8001/api/v1/robots/1/connect
```

3. **启动零点标定**
```bash
curl -X POST http://localhost:8001/api/v1/robots/1/zero-point-calibration \
  -H "Content-Type: application/json" \
  -d '{"calibration_type": "full_body"}'
```

4. **执行一键标定**
```bash
curl -X POST http://localhost:8001/api/v1/robots/1/zero-point-calibration/{session_id}/execute-calibration \
  -H "Content-Type: application/json" \
  -d '{"calibration_mode": "full_body"}'
```

## 开发注意事项

### 1. 异步编程
- 所有 I/O 操作使用 async/await
- SSH 操作在线程池中执行避免阻塞
- WebSocket 使用异步消息处理
- PTY交互使用异步队列传输

### 2. 错误处理
- 统一的异常处理机制
- 详细的错误日志记录
- 用户友好的错误消息
- 422状态码用于数据验证失败

### 3. 安全考虑
- SSH 密码加密存储（生产环境）
- API 认证机制（待实现）
- CORS 配置限制
- 关节参数安全验证
- 进程清理和资源管理

### 4. 性能优化
- 数据库查询优化
- 连接池管理
- 异步并发处理
- WebSocket连接复用

### 5. 数据格式规范
- 所有角度使用弧度单位
- 关节ID映射固定规则
- 标定数据Schema验证
- 文件操作原子性

### 6. CORS配置
在 `main.py` 中配置了CORS中间件：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)
```

## 重要服务详解

### 1. 零点标定服务 (ZeroPointCalibrationService)
**文件**: `app/services/zero_point_calibration_service.py`

**核心类**:
- `ZeroPointStep`: 标定步骤枚举
- `ZeroPointStatus`: 标定状态枚举  
- `ZeroPointSession`: 标定会话数据类
- `ZeroPointCalibrationService`: 主服务类

**关键方法**:
- `start_zero_point_calibration()`: 启动标定流程
- `go_to_step()`: 步骤导航
- `execute_calibration_command()`: 执行标定命令
- `debug_joints()`: 关节调试
- `save_zero_point_data()`: 保存标定数据
- `get_calibration_summary()`: 获取标定汇总

**工具确认配置**:
```python
self.tool_confirmations = {
    "full_body": [
        ToolConfirmation("安装工装", "将辅助工装插入腿部的插销中", "/static/images/install_leg_tools.jpg"),
        ToolConfirmation("安装工装", "将辅助工装插入脚部的插销中", "/static/images/install_foot_tools.jpg"),
        ToolConfirmation("摆好手臂", "手臂自然下垂，摆正两边", "/static/images/adjust_arms.jpg"),
        ToolConfirmation("摆正头部", "头部左右居中，头部都面保持直立", "/static/images/adjust_head.jpg")
    ]
}
```

### 2. 标定文件服务 (CalibrationFileService)
**文件**: `app/services/calibration_file_service.py`

**核心功能**:
- 读写arms_zero.yaml和offset.csv
- 关节数据映射和转换
- 当前关节位置获取
- 数据验证和完整性检查
- 自动备份机制

**关节映射规则**:
```python
# 手臂关节映射 (ID 1-14)
for i in range(1, 15):
    if i <= 12:
        # ID 1-12 对应 joint_02 到 joint_13
        joint_name = f"joint_{i+1:02d}"
    else:
        # ID 13-14 对应 neck_01, neck_02
        joint_name = f"neck_{i-12:02d}"
```

**模拟数据生成**:
```python
# 使用弧度值的基准位置
base_positions = {
    1: 0.051, 2: 0.011, 3: 0.021, 4: -0.034, 5: -0.021, 6: 0.027,  # 左臂
    7: -0.021, 8: 0.0, 9: 0.0, 10: 0.0, 11: 0.0, 12: 0.0,  # 右臂
    13: 0.0, 14: 0.0  # 头部
}
```

### 3. SSH服务增强功能
**文件**: `app/services/ssh_service.py`

**设备信息获取**:
```python
async def get_robot_info(self, robot_id: str) -> Optional[Dict[str, Any]]:
    # 获取机器人详细信息
    # 自动读取配置文件和环境变量
    # 返回新格式的设备信息字段
```

**实时状态获取**:
```python
async def get_robot_status(self, robot_id: str) -> Optional[Dict[str, Any]]:
    # 获取实时状态信息
    # 检查ROS服务状态
    # 查询电量信息
    # 获取故障码
```

**网络环境验证**:
```python
async def validate_network_environment(self, host: str) -> Tuple[bool, str]:
    # 跨平台ping测试
    # 网络延迟检测和性能评估
    # 子网验证：确保设备在同一网段
    # 详细的网络诊断信息
```

**交互式命令执行**:
```python
async def execute_command_interactive(self, robot_id: str, command: str, output_callback=None):
    # 通过PTY（伪终端）执行交互式命令
    # 支持实时输出流式传输
    # 支持用户输入响应
    # 会话管理和取消机制
```

**进程管理和清理**:
```python
async def cleanup_calibration_processes(self, robot_id: str, mode="all"):
    # 根据模式清理标定相关进程
    # 支持的进程模式：
    # - roslaunch.*load_kuavo_real.*cali
    # - roslaunch.*humanoid_controllers
    # - python.*calibration
    # - One_button_start.sh
```

### 4. 标定数据解析器
**文件**: `app/services/calibration_data_parser.py`

**解析模式**:
```python
SLAVE_POSITION_PATTERNS = [
    r'Slave\s+(\d+)\s+actual\s+position\s+([\d\.\-]+)',
    r'(\d+):\s*Slave\s+(\d+)\s+actual\s+position\s+([\d\.\-]+)',
    r'Slave\s+(\d+)\s+actual\s+position\s+([\d\.\-]+),Encoder\s+([\d\.\-]+)'
]
```

**数据提取示例**:
- 输入: `"30400001: Slave 01 actual position 9.6946716,Encoder 63535.0"`
- 输出: `{1: 9.6946716}`

### 5. 模拟器完整实现
**文件**: `app/simulator/robot_simulator.py`

**ROS命令支持**:
```python
elif "roslaunch" in command and "load_kuavo_real.launch" in command:
    if "cali:=true" in command:
        output = "[模拟器] 启动机器人标定系统\n"
        if "cali_arm:=true" in command and "cali_leg:=true" in command:
            output += "[ INFO] 开始全身零点标定...\n"
```

**标定脚本模拟**:
```python
class ZeroPointCalibrationScript(CalibrationScript):
    async def _async_run(self):
        # 完整的零点标定流程模拟
        # 电机使能模拟
        # 用户交互模拟
        # 标定数据生成
```

## 常见问题

### Q1: 如何添加新的标定类型？
A: 
1. 在 `ZeroPointCalibrationService` 中添加新的工具确认配置
2. 在 `calibration_service.py` 中添加新的交互模式
3. 更新前端页面和逻辑
4. 添加对应的API端点

### Q2: 如何扩展机器人信息字段？
A: 
1. 修改 `models/robot.py` 添加字段
2. 更新 `schemas/robot.py` 
3. 创建数据库迁移
4. 更新相关API响应

### Q3: 如何处理SSH连接超时？
A: 在 `config.py` 中调整 `SSH_TIMEOUT` 配置，或在连接时传入超时参数。

### Q4: WebSocket 连接断开如何处理？
A: 客户端应实现自动重连机制，服务端有心跳检测。可以监听 `onclose` 事件并延时重连。

### Q5: 如何调整关节参数验证阈值？
A: 修改 `schemas/calibration.py` 中的验证阈值常量：
```python
# 在 validate_joint_data_changes 方法中
if abs(joint.offset) > 0.05:  # 建议阈值
if abs(joint.offset) > 0.1:   # 强制限制
```

### Q6: 网络验证失败如何处理？
A: 检查 `ssh_service.py:validate_network_environment()` 返回的详细错误信息，通常是：
- 子网不匹配：确保在同一网段
- 网络延迟过高：检查网络质量
- ping失败：检查防火墙设置

### Q7: 如何扩展标定数据解析格式？
A: 在 `calibration_data_parser.py` 的 `SLAVE_POSITION_PATTERNS` 列表中添加新的正则表达式：
```python
SLAVE_POSITION_PATTERNS.append(r'新的解析模式正则表达式')
```

### Q8: 交互式命令执行如何工作？
A: 使用 `ssh_service.py:execute_command_interactive()` 方法，它通过PTY（伪终端）支持：
- 实时输出捕获
- 用户输入发送
- 会话状态管理
- 进程清理

### Q9: 零点标定的自动步骤流转如何控制？
A: 在 `zero_point_calibration_service.py` 中：
- 步骤2到步骤3：调用 `self.go_to_step(session, ZeroPointStep.INITIALIZE_ZERO)`
- 可以通过修改流程逻辑来控制自动化程度

### Q10: 模拟器如何添加新的命令模拟？
A: 在 `robot_simulator.py` 的 `execute_command()` 方法中添加新的命令匹配：
```python
elif "your_new_command" in command:
    return True, "模拟输出", ""
```

### Q11: 如何处理标定数据的单位转换？
A: 系统统一使用弧度，如需转换：
```python
import math
degrees = radians * 180 / math.pi
radians = degrees * math.pi / 180
```

### Q12: 如何实现新的WebSocket消息类型？
A: 
1. 在 `websocket.py` 中添加消息处理逻辑
2. 在服务中调用 `connection_manager.broadcast()` 发送消息
3. 更新前端WebSocket消息处理

### Q13: 如何调整分页参数？
A: 修改 `schemas/robot.py` 中的 `PaginationParams`：
```python
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)  # 调整默认值和最大值
```

### Q14: 前端如何处理新的分页响应格式？
A: 前端需要检查响应格式：
```javascript
if (data.items && Array.isArray(data.items)) {
    robots = data.items;  // 新分页格式
} else if (Array.isArray(data)) {
    robots = data;  // 兼容旧格式
}
```

### Q15: 如何添加新的设备信息字段？
A: 需要更新三个地方：
1. `models/robot.py` - 添加数据库字段
2. `schemas/robot.py` - 更新响应模式
3. `ssh_service.py:get_robot_info()` - 获取新字段数据

## 监控和日志

### 日志配置
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 建议监控指标
- API 响应时间
- WebSocket 连接数
- 标定任务成功率
- SSH 连接状态
- 数据验证失败率
- 进程清理成功率

### 关键日志点
- SSH连接建立/断开
- 标定会话创建/完成
- 关节参数验证警告/错误
- 文件读写操作
- WebSocket连接状态变化

## 性能优化建议

### 1. 数据库优化
- 为robot_id添加索引
- 定期清理过期会话数据
- 使用连接池

### 2. WebSocket优化
- 实现连接心跳检测
- 限制消息频率
- 批量发送日志消息

### 3. SSH连接优化
- 连接复用
- 命令缓存
- 超时设置优化

### 4. 内存管理
- 定期清理完成的标定会话
- 限制日志缓冲区大小
- 优化大文件处理

## 扩展功能建议

### 1. 标定历史记录
- 标定结果存储
- 历史数据查询
- 标定效果对比

### 2. 批量设备操作
- 多设备同时标定
- 批量配置更新
- 集群管理

### 3. 高级监控
- 实时性能指标
- 异常告警
- 自动故障恢复

### 4. 安全增强
- JWT认证
- 角色权限管理
- 操作审计日志

## 最新更新（v1.2.0）

### 新增功能
1. **设备列表分页支持**
   - 新增分页响应格式
   - 支持 page/page_size 参数
   - 向后兼容旧格式
   - 前端分页组件实现：
     - 页码导航（智能省略号显示）
     - 每页数量选择（5、10、20、50条）
     - 分页信息显示

2. **设备类型区分**
   - 新增 device_type 字段（upper/lower）
   - 前端添加设备时可选择上位机/下位机
   - 设备列表显示设备类型
   - 设备详情显示设备类型

3. **设备信息字段扩展**
   - 新增详细的设备信息字段
   - 支持实时状态获取（电量、服务状态、故障码）
   - 新增 GET /api/v1/robots/{robot_id}/status 端点

4. **前端更新**
   - 实现完整的分页功能
   - 设备类型选择和显示
   - 更新设备管理和标定页面以支持新的分页格式
   - 修复了API路径问题（支持带/不带斜杠）
   - 改进了错误处理和提示

5. **CORS配置优化**
   - 添加了 expose_headers 配置
   - 确保跨域请求正常工作

### 数据库字段
最新数据库包含以下字段：
- device_type（设备类型）
- robot_model
- robot_version
- robot_sn
- robot_software_version
- end_effector_model
- service_status
- battery_level
- error_code

如有问题，请查阅：
- API文档: `API_DOCUMENTATION.md`
- 项目README: `README.md`
- 在线API文档: http://localhost:8001/docs

### 前端分页实现细节
**文件**: `frontend/device_script.js`

**核心变量**:
```javascript
let currentPage = 1;      // 当前页码
let pageSize = 10;        // 每页大小
let totalRobots = 0;      // 总记录数
let totalPages = 1;       // 总页数
```

**分页组件功能**:
- `loadRobots(page, size)`: 加载指定页的数据
- `updatePagination()`: 更新分页UI状态
- `generatePageNumbers()`: 生成页码（带省略号）
- `setupPagination()`: 设置分页事件监听

**页码显示逻辑**:
- 最多显示7个页码
- 当总页数超过7页时，使用省略号
- 始终显示第一页和最后一页
- 当前页前后各显示3页

---

**交接日期**: 2025-08-01  
**版本**: 1.2.0  
**开发状态**: 生产就绪