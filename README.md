# KUAVO Studio - 机器人管理系统

这是一个基于Web的KUAVO人形机器人管理和标定系统，提供设备管理和交互式标定功能。

## 功能特性

### 设备管理
- 添加、删除机器人设备
- 通过SSH连接/断开机器人
- **网络环境验证**：自动检测设备是否在同一网络(ping测试、延迟检查、子网验证)
- 查看设备详细信息（硬件型号、软件版本、SN号等）
- 实时连接状态监控
- 连接测试和详细诊断信息

### 机器人标定
- **全身零点标定**：完整的关节零点校准流程
  - 4步分步标定向导(确认工具→读取配置→初始化零点→移除工具)
  - 实时执行`roslaunch humanoid_controllers load_kuavo_real.launch cali:=true`
  - **Robust数据解析**：智能提取"Slave xx actual position"数据
  - 支持多种输出格式的正则表达式匹配
  - 数据完整性验证和异常检测
  - 保存到`~/.config/lejuconfig/offset.csv`
  - **关节参数安全验证**：修改幅度限制(建议≤0.05，强制≤0.1)
  - 实时参数范围警告和错误提示
  - 预览标定结果和验证功能

- **头手标定(ETH)**：头部和手部的精确标定
  - 执行`One_button_start.sh`脚本的完整自动化
  - **7项环境预检查**：sudo权限、虚拟环境、AprilTag检测、网络连接、rosbag文件、标定工具、密码配置
  - 自动化用户交互处理(expect脚本)
  - **双SSH架构**：下位机控制 + 上位机(192.168.26.1)连接
  - 实时进度监控和日志输出
  - 头部标定：AprilTag位姿数据采集
  - 手臂标定：双臂关节校准(左臂7关节+右臂7关节)
  - 结果保存到`arms_zero.yaml`和配置文件

### 标定数据管理
- **文件操作原子性**：备份机制和回滚能力
- **标定历史追踪**：完整的操作日志和状态记录
- **数据验证**：关节数据完整性检查
- **配置文件管理**：offset.csv和arms_zero.yaml的读写操作

### 实时通信与监控
- WebSocket实时状态更新
- 标定进度实时显示
- **Slave位置数据实时广播**
- 交互式用户确认流程
- 实时日志流传输和解析
- **错误恢复机制**：异常处理和状态恢复

## 技术栈

### 后端
- **FastAPI** - 高性能异步Web框架
- **SQLAlchemy + SQLite** - ORM和轻量级数据库
- **Paramiko** - SSH远程通信
- **WebSocket** - 实时双向通信
- **Asyncio** - 异步并发处理

### 前端
- 原生HTML/CSS/JavaScript
- WebSocket客户端实时通信
- 响应式设计
- 标定向导界面

## 快速开始

### 1. 环境要求
- Python 3.8+
- pip
- 现代浏览器(支持WebSocket)

### 2. 安装后端依赖

```bash
cd kuavo-studio/backend
pip install -r requirements.txt
```

### 3. 启动后端服务

**生产模式**(连接真实机器人):
```bash
cd kuavo-studio/backend
python main.py
```

**模拟器模式**(推荐开发使用):
```bash
cd kuavo-studio/backend
python run_simulator_8001.py
```

后端服务将在 http://localhost:8001 启动

### 4. 启动前端

**方法一**：直接在浏览器中打开 `kuavo-studio/frontend/index.html` 文件

**方法二**：使用Python HTTP服务器：
```bash
cd kuavo-studio/frontend
python start_frontend.py
```
然后访问 http://localhost:8081

**方法三**：双击打开 `打开前端界面.html` 文件

## 使用指南

### 设备管理

#### 添加设备
1. 点击右上角"添加设备"按钮
2. 填写设备信息：
   - 设备名称（唯一标识，不可重名）
   - IP地址
   - SSH端口（默认22）
   - SSH用户名（默认leju）
   - SSH密码
3. 系统会自动进行：
   - **网络环境验证**：检测设备是否在同一网络环境
   - **连接测试**：验证SSH连接和认证
   - **设备信息获取**：读取硬件型号、软件版本、SN号等

#### 连接/断开设备
- 在设备卡片上点击"连接"/"断开"按钮
- 连接状态会通过WebSocket实时更新
- 绿色圆点表示已连接，灰色表示未连接

### 标定操作

#### 全身零点标定
1. 确保设备已连接
2. 选择"全身零点标定"
3. 按照向导完成4个步骤：
   - **步骤1**: 标定准备(确认工具安装)
   - **步骤2**: 读取当前配置(显示关节数据)
   - **步骤3**: 初始化零点(执行标定脚本)
   - **步骤4**: 标定结果(显示position数据)
4. 支持关节参数单独调试
5. 可预览标定结果和保存零点

#### 头手标定
1. 确保设备已连接
2. 选择"头手标定(ETH)"
3. 按照向导完成3个步骤：
   - **步骤1**: 标定准备(环境检查)
   - **步骤2**: 执行标定(运行One_button_start.sh)
   - **步骤3**: 标定结果(完成状态显示)
4. 系统会自动处理所有用户交互
5. 实时查看标定进度和日志输出

## API文档

后端启动后，可访问自动生成的API文档：
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### 核心API端点

#### 设备管理
- `GET /api/v1/robots/` - 获取设备列表
- `POST /api/v1/robots/` - 添加新设备
- `GET /api/v1/robots/{robot_id}` - 获取设备详情
- `DELETE /api/v1/robots/{robot_id}` - 删除设备
- `POST /api/v1/robots/{robot_id}/connect` - 连接设备
- `POST /api/v1/robots/{robot_id}/disconnect` - 断开设备

#### 零点标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration` - 启动零点标定
- `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 读取标定数据
- `PUT /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 更新标定数据

#### 头手标定
- `GET /api/v1/robots/{robot_id}/calibration-config-check` - 环境检查
- `POST /api/v1/robots/{robot_id}/head-hand-calibration` - 启动头手标定
- `POST /api/v1/robots/{robot_id}/head-hand-calibration/save` - 保存标定结果

## 项目结构

```
kuavo-studio/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # API路由
│   │   │   ├── robots.py        # 设备管理API
│   │   │   └── calibration.py   # 标定管理API
│   │   ├── core/                # 核心配置
│   │   ├── models/              # 数据库模型
│   │   ├── schemas/             # Pydantic数据模型
│   │   ├── services/            # 业务服务层
│   │   │   ├── ssh_service.py            # SSH连接管理(支持PTY交互)
│   │   │   ├── zero_point_calibration_service.py  # 零点标定逻辑
│   │   │   └── calibration_file_service.py        # 标定文件管理
│   │   └── simulator/           # 机器人模拟器
│   ├── main.py                  # 生产模式入口
│   ├── run_simulator_8001.py    # 模拟器模式入口
│   └── requirements.txt         # 依赖列表
├── frontend/
│   ├── index.html               # 主页面
│   ├── calibration_new.html     # 标定页面
│   ├── script.js                # 主页面逻辑
│   ├── calibration_script.js    # 标定逻辑
│   ├── styles.css               # 样式文件
│   └── start_frontend.py        # 前端服务器
├── 打开前端界面.html            # 快速入口
├── README.md                    # 项目文档
├── HANDOVER_GUIDE.md           # 交接文档
└── API_DOCUMENTATION.md        # API详细文档
```

## 注意事项

### 安全考虑
1. **生产环境安全**：
   - 使用HTTPS加密通信
   - SSH密码应加密存储
   - 配置CORS白名单
   - 实施API认证机制

2. **标定安全**：
   - 标定过程不可逆，请谨慎操作
   - 确保机器人处于安全状态
   - 严格遵循标定向导提示
   - 建议修改关节参数幅度≤0.05

### 网络要求
- 确保能够访问机器人的SSH端口(22)
- WebSocket需要稳定的网络连接
- 头手标定需要访问上位机192.168.26.1

### 系统要求
- 支持SSH连接的机器人系统
- ROS环境(Noetic推荐)
- 标定工具和AprilTag(头手标定)

## 开发指南

### 模拟器模式
项目包含完整的机器人模拟器，支持无硬件开发：
- 模拟SSH连接和命令执行
- 模拟标定脚本输出和用户交互
- 完整的标定流程模拟
- 自动化测试支持

### 扩展功能

#### 添加新的标定类型
1. 在 `calibration_service.py` 中添加新的交互模式
2. 更新前端页面和逻辑
3. 添加对应的API端点

#### 添加新的API端点
1. 在 `app/api/v1/` 中创建新的路由文件
2. 在 `app/api/v1/__init__.py` 中注册路由
3. 创建对应的schema和service

### 验证安装
```bash
cd backend
python main.py
```

## 故障排查

### 连接问题
- **连接失败**: 检查IP地址、端口、用户名密码
- **连接超时**: 确认SSH服务运行，检查网络连通性
- **认证失败**: 验证SSH凭据，检查用户权限

### 标定问题
- **标定无响应**: 查看浏览器控制台，检查WebSocket连接
- **脚本执行失败**: 确认机器人程序运行正常，检查ROS环境
- **环境检查失败**: 验证虚拟环境、AprilTag配置、rosbag文件

### 数据库问题
- **数据库错误**: 删除 `kuavo_studio.db` 文件重新初始化
- **权限问题**: 检查文件读写权限

### WebSocket问题
- **连接断开**: 实现客户端自动重连机制
- **消息丢失**: 检查网络稳定性，调整心跳间隔

## 功能特性总结

### 已实现功能 (95%)
- 完整的设备管理(CRUD)
- SSH连接管理和状态监控
- 全身零点标定(4步向导)
- 头手标定(3步向导)
- 实时WebSocket通信
- 标定文件管理(offset.csv, arms_zero.yaml)
- 关节参数调试
- 模拟器支持
- 7项环境预检查
- 用户交互自动化

### 可扩展功能
- 标定历史记录管理
- 标定数据可视化
- 批量设备操作
- 用户权限管理
- 性能监控和告警

## 支持

如有问题，请查阅：
- **详细API文档**: `API_DOCUMENTATION.md`
- **开发交接文档**: `HANDOVER_GUIDE.md`
- **在线API文档**: http://localhost:8001/docs
- **在线API文档**: http://localhost:8001/redoc

---

**版本**: 1.0.0  
**最后更新**: 2024-07-30  
**开发状态**: 生产就绪