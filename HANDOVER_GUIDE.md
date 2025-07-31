# KUAVO Studio 后端交接文档

## 项目概述

KUAVO Studio 是一个用于管理和控制 KUAVO 人形机器人的后端服务系统。该系统提供了完整的 RESTful API 和 WebSocket 接口，支持设备管理、SSH 连接控制、实时标定等功能。

## 技术架构

### 核心技术栈
- **Web框架**: FastAPI (异步高性能)
- **数据库**: SQLAlchemy + SQLite (可切换至 PostgreSQL/MySQL)
- **SSH通信**: Paramiko
- **WebSocket**: FastAPI WebSocket
- **异步支持**: asyncio
- **依赖注入**: FastAPI 内置 DI

### 项目结构
```
backend/
├── app/
│   ├── api/              # API路由层
│   │   ├── v1/          # API v1版本
│   │   │   ├── __init__.py      # 路由聚合
│   │   │   ├── robots.py        # 机器人CRUD
│   │   │   └── calibration.py   # 标定管理
│   │   └── websocket.py         # WebSocket端点
│   ├── core/            # 核心配置
│   │   ├── config.py    # 应用配置
│   │   └── database.py  # 数据库配置
│   ├── models/          # 数据库模型
│   │   └── robot.py     # 机器人模型
│   ├── schemas/         # Pydantic模式
│   │   ├── robot.py     # 机器人数据模式
│   │   └── calibration.py # 标定数据模式
│   ├── services/        # 业务逻辑层
│   │   ├── ssh_service.py                    # SSH连接管理+网络验证
│   │   ├── calibration_service.py            # 基础标定服务
│   │   ├── zero_point_calibration_service.py # 零点标定专用服务
│   │   ├── calibration_file_service.py       # 标定文件管理
│   │   └── calibration_data_parser.py        # 标定数据解析器
│   └── simulator/       # 模拟器
│       └── robot_simulator.py     # 机器人模拟器
├── main.py             # 生产模式应用入口
├── run_simulator_8001.py  # 模拟器模式入口
└── requirements.txt    # 依赖列表
```

## 核心功能模块

### 1. 设备管理模块
- **功能**: 机器人设备的增删改查
- **关键文件**: 
  - `app/api/v1/robots.py` - API端点
  - `app/models/robot.py` - 数据模型
  - `app/schemas/robot.py` - 数据验证

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

### 3. 标定管理模块
- **功能**: 执行机器人标定流程
- **关键文件**:
  - `app/api/v1/calibration.py` - API端点
  - `app/services/calibration_service.py` - 标定逻辑
  - `app/services/zero_point_calibration_service.py` - 零点标定专用服务
  - `app/services/calibration_data_parser.py` - 数据解析器
- **支持的标定类型**:
  - `zero_point`: 全身零点标定
  - `head_hand`: 头手标定
- **功能**:
  - **关节参数安全验证**: 修改幅度限制(建议≤0.05，强制≤0.1)
  - **Robust数据解析**: 智能提取"Slave xx actual position"数据
  - 多种输出格式的正则表达式匹配
  - 实时参数范围警告和错误提示

### 4. WebSocket通信
- **功能**: 实时状态推送
- **关键文件**: 
  - `app/api/websocket.py` - WebSocket管理
- **消息类型**:
  - 连接状态更新
  - 标定进度推送
  - 标定日志实时输出

### 5. 模拟器模式
- **功能**: 无需硬件的开发测试
- **关键文件**: 
  - `app/simulator/robot_simulator.py`
- **启用方式**: 
  - 设置环境变量 `USE_ROBOT_SIMULATOR=true`

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

3. **启动标定**
```bash
curl -X POST http://localhost:8001/api/v1/robots/1/calibrations \
  -H "Content-Type: application/json" \
  -d '{"calibration_type": "zero_point"}'
```

## 开发注意事项

### 1. 异步编程
- 所有 I/O 操作使用 async/await
- SSH 操作在线程池中执行避免阻塞
- WebSocket 使用异步消息处理

### 2. 错误处理
- 统一的异常处理机制
- 详细的错误日志记录
- 用户友好的错误消息

### 3. 安全考虑
- SSH 密码加密存储（生产环境）
- API 认证机制（待实现）
- CORS 配置限制

### 4. 性能优化
- 数据库查询优化
- 连接池管理
- 异步并发处理

## 常见问题

### Q1: 如何添加新的标定类型？
A: 在 `calibration_service.py` 的 `interaction_patterns` 中添加新的交互模式配置。

### Q2: 如何扩展机器人信息字段？
A: 
1. 修改 `models/robot.py` 添加字段
2. 更新 `schemas/robot.py` 
3. 创建数据库迁移

### Q3: 如何处理SSH连接超时？
A: 在 `config.py` 中调整 `SSH_TIMEOUT` 配置。

### Q4: WebSocket 连接断开如何处理？
A: 客户端应实现自动重连机制，服务端有心跳检测。

### Q5: 如何调整关节参数验证阈值？
A: 修改 `schemas/calibration.py` 中的验证阈值常量(JOINT_CHANGE_WARNING_THRESHOLD, JOINT_CHANGE_ERROR_THRESHOLD)。

### Q6: 网络验证失败如何处理？
A: 检查 `ssh_service.py:validate_network_environment()` 返回的详细错误信息，通常是子网不匹配或网络延迟过高。

### Q7: 如何扩展标定数据解析格式？
A: 在 `calibration_data_parser.py` 的 `SLAVE_POSITION_PATTERNS` 列表中添加新的正则表达式模式。

### Q8: 交互式命令执行如何工作？
A: 使用 `ssh_service.py:execute_command_interactive()` 方法，它通过PTY（伪终端）支持实时输出和用户输入。

### Q9: 零点标定步骤2到步骤3的自动流转如何关闭？
A: 在 `zero_point_calibration_service.py` 中修改 `_proceed_to_read_config` 方法，移除自动调用 `self.go_to_step(session, 3)` 的逻辑。

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

### 1. 网络环境验证服务
**文件**: `app/services/ssh_service.py:validate_network_environment()`

**功能**:
- 跨平台ping测试(Windows/Linux/macOS)
- 网络延迟检测和性能评估
- 子网验证：确保设备在同一网段
- 详细的网络诊断信息
- **模拟器模式优化**: 模拟器中直接返回成功，避免执行真实ping命令

**使用场景**: 设备连接前自动验证网络环境

### 2. 关节参数安全验证
**文件**: `app/schemas/calibration.py:JointDataUpdateRequest`

**功能**:
- Schema级别参数验证
- 多层安全检查(0.05建议阈值，0.1强制限制)
- 详细的警告和错误消息
- 防止危险的关节参数修改

**安全机制**:
```python
# 警告: >0.05
# 错误: >0.1
@validator('joint_data')
def validate_joint_data_changes(cls, joint_data_list):
    # 自动验证每个关节的修改幅度
```

### 3. 标定数据解析器
**文件**: `app/services/calibration_data_parser.py`

**功能**:
- 专用的正则表达式解析引擎
- 处理多种"Slave xx actual position"格式
- 数据完整性验证
- 异常检测和错误恢复

**支持格式**:
- 标准格式：`Slave 01 actual position 9.6946716`
- 带时间戳：`30400001: Slave 01 actual position 9.6946716`
- 带编码器：`Slave 01 actual position 9.6946716,Encoder 63535.0`

### 4. 交互式命令执行服务
**文件**: `app/services/ssh_service.py:execute_command_interactive()`

**功能**:
- 通过PTY（伪终端）执行交互式命令
- 支持实时输出流式传输
- 支持用户输入响应（通过send_input_to_session）
- 会话管理和取消机制
- 进程清理和资源管理

**使用场景**: 零点标定、头手标定等需要用户交互的脚本执行

### 5. 进程管理和清理
**文件**: `app/services/ssh_service.py:cleanup_calibration_processes()`

**功能**:
- 根据模式清理标定相关进程
- 支持的进程模式：
  - roslaunch.*load_kuavo_real.*cali
  - roslaunch.*humanoid_controllers
  - python.*calibration
  - One_button_start.sh
- 会话断开时自动清理
- 标定取消时强制终止进程

**使用场景**: 标定取消、连接断开、异常恢复


如有问题，请查阅：
- API文档: `API_DOCUMENTATION.md`
- 项目README: `README.md`
- 在线API文档: http://localhost:8001/docs

---

交接日期: 2024-07-30
版本: 1.0.0