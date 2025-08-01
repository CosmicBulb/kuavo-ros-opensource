# KUAVO Studio - 机器人管理系统

KUAVO Studio 是一个基于Web的KUAVO人形机器人管理和标定系统，提供设备管理、零点标定、头手标定、关节调试等完整功能。

## 功能特性

### 设备管理
- **机器人设备管理**: 添加、删除、查看机器人设备，支持分页显示
  - 分页功能：支持自定义每页显示数量（5、10、20、50条）
  - 智能页码显示：超过7页时显示省略号
  - 设备类型区分：支持上位机/下位机分类管理
- **SSH连接管理**: 通过SSH连接/断开机器人，支持连接状态实时监控
- **网络环境验证**: 自动检测设备网络环境（ping测试、延迟检查、子网验证）
- **设备信息获取**: 自动读取设备详细信息
  - 机器人型号 (robot_model)
  - 机器人版本 (robot_version)
  - 机器人SN号 (robot_sn)
  - 机器人软件版本 (robot_software_version)
  - 末端执行器型号 (end_effector_model)
- **实时状态监控**: 服务状态、电量、故障码等实时更新
- **连接诊断**: 详细的连接测试和错误诊断信息
- **双重查找**: 支持ID和SN号双重查找机制

### 零点标定系统
- **完整4步标定流程**: 确认工具→读取配置→初始化零点→移除工具
- **一键标定功能**: 自动执行 `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true`
- **标定模式选择**: 支持全身、仅手臂、仅腿部三种标定模式
- **实时数据解析**: 智能提取"Slave xx actual position"数据，支持多种输出格式
- **关节调试功能**: 实时发送 `rostopic pub /kuavo_arm_traj sensor_msgs/JointState` 命令
- **数据完整性验证**: 标定数据验证和异常检测
- **会话管理**: 完整的标定会话生命周期管理
- **实时状态推送**: WebSocket实时标定状态和日志推送

### 头手标定(ETH)系统
- **7项环境预检查**: 虚拟环境、AprilTag检测、rosbag文件、相机设备、网络连接、上位机连接
- **自动化脚本执行**: 执行 `One_button_start.sh` 脚本的完整自动化
- **双SSH架构**: 下位机控制 + 上位机(192.168.26.1)连接管理
- **交互自动化**: expect脚本自动处理用户交互确认
- **实时进度监控**: 标定进度和日志实时输出
- **头部标定**: AprilTag位姿数据采集和处理
- **手臂标定**: 双臂关节校准(左臂7关节+右臂7关节)
- **结果保存**: 自动保存到 `arms_zero.yaml` 和相关配置文件

### 标定数据管理
- **配置文件管理**: 支持 `arms_zero.yaml` 和 `offset.csv` 文件的读写操作
- **关节映射系统**: 
  - 手臂: ID 1-12 → joint_02-joint_13, ID 13-14 → neck_01-neck_02
  - 腿部: ID 1-14 → 左腿6个+右腿6个+肩部2个
- **安全参数验证**: 关节参数修改幅度限制(建议≤0.05，强制≤0.1)
- **数据备份机制**: 自动备份原始文件，支持回滚操作
- **原子操作保证**: 临时文件+移动确保数据完整性
- **实时参数监控**: 关节参数范围警告和错误提示

### 实时通信与监控
- **WebSocket实时通信**: 双向实时通信支持
- **标定状态推送**: 零点标定和头手标定状态实时更新
- **日志流传输**: 标定日志实时推送和解析
- **连接状态监控**: 机器人和上位机连接状态实时监控
- **错误恢复机制**: 异常处理和状态恢复
- **会话管理**: 完整的会话生命周期管理

### 开发与测试支持
- **完整模拟器**: 无需硬件的完整开发测试环境
- **ROS命令模拟**: roslaunch和rostopic命令完整模拟
- **标定流程模拟**: 真实的标定流程和用户交互模拟
- **配置文件模拟**: 模拟配置文件读写操作
- **网络模拟**: 模拟网络环境和SSH连接

## 技术栈

### 后端
- **FastAPI** - 高性能异步Web框架
- **SQLAlchemy + SQLite** - ORM和轻量级数据库
- **Paramiko** - SSH远程通信和命令执行
- **WebSocket** - 实时双向通信
- **Asyncio** - 异步并发处理
- **Pydantic** - 数据验证和序列化
- **ptyprocess** - 伪终端支持交互式命令

### 前端
- **原生HTML/CSS/JavaScript** - 轻量级前端实现
- **WebSocket客户端** - 实时通信
- **响应式设计** - 适配不同设备
- **标定向导界面** - 分步式用户体验

### 工具与集成
- **ROS Noetic** - 机器人操作系统集成
- **expect** - 自动化用户交互脚本
- **AprilTag** - 视觉标定标签支持
- **Docker** - 容器化部署支持

## 快速开始

### 1. 环境要求
- Python 3.8+
- pip
- 现代浏览器(支持WebSocket)
- （可选）ROS Noetic环境

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
   - 设备类型（选择上位机或下位机）
   - IP地址
   - SSH端口（默认22）
   - SSH用户名（默认leju）
   - SSH密码
3. 系统会自动进行：
   - **网络环境验证**：检测设备是否在同一网络环境
   - **连接测试**：验证SSH连接和认证
   - **设备信息获取**：读取硬件型号、软件版本、SN号等

#### 设备列表管理
- **分页浏览**：设备列表支持分页显示，可自定义每页显示数量
- **设备类型标识**：列表中显示设备类型（上位机/下位机）
- **实时状态更新**：通过WebSocket实时更新设备连接状态

#### 连接/断开设备
- 在设备卡片上点击"连接"/"断开"按钮
- 连接状态会通过WebSocket实时更新
- 绿色圆点表示已连接，灰色表示未连接

### 零点标定

#### 完整标定流程
1. **确保设备已连接**
2. **选择"零点标定"**
3. **按照4步向导完成标定**：
   - **步骤1**: 确认工具安装(辅助工装安装确认)
   - **步骤2**: 读取当前配置(显示关节数据和当前位置)
   - **步骤3**: 初始化零点(执行一键标定脚本)
   - **步骤4**: 移除辅助工装(标定完成确认)

#### 一键标定功能
- 在步骤3中点击"一键标定"按钮
- 系统自动执行相应的roslaunch命令：
  - 全身标定: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true cali_leg:=true`
  - 仅手臂: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_arm:=true`
  - 仅腿部: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true cali_leg:=true`

#### 关节调试功能
- 在关节数据表格中修改目标位置
- 点击"调试关节"按钮
- 系统发送 `rostopic pub /kuavo_arm_traj sensor_msgs/JointState` 命令
- 实时查看关节运动效果

#### 数据保存和验证
- 标定完成后可预览结果数据
- 支持保存到配置文件（arms_zero.yaml / offset.csv）
- 支持标定结果验证（机器人缩腿测试）

### 头手标定

#### 环境检查
1. **确保设备已连接**
2. **选择"头手标定(ETH)"**
3. **系统自动进行7项环境检查**：
   - 虚拟环境是否就绪
   - AprilTag配置是否存在
   - rosbag文件是否完整
   - 相机设备是否可用
   - 网络连接是否正常
   - 上位机是否已连接

#### 自动化标定流程
1. **环境检查通过后启动标定**
2. **系统自动执行标定脚本**：
   - 自动处理用户交互确认
   - 实时显示标定进度和日志
   - 头部AprilTag数据采集
   - 双臂关节校准处理
3. **标定完成后确认保存结果**

## API文档

后端启动后，可访问自动生成的API文档：
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### API使用示例

#### 分页获取设备列表
```bash
# 获取第1页，每页10条
GET /api/v1/robots/?page=1&page_size=10

# 响应格式
{
  "items": [...],  // 设备列表
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 25,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

### 核心API端点

#### 设备管理
- `GET /api/v1/robots/` - 获取设备列表（支持分页）
- `POST /api/v1/robots/` - 添加新设备
- `GET /api/v1/robots/{robot_id}` - 获取设备详情
- `GET /api/v1/robots/{robot_id}/status` - 获取设备实时状态
- `DELETE /api/v1/robots/{robot_id}` - 删除设备
- `POST /api/v1/robots/{robot_id}/connect` - 连接设备
- `POST /api/v1/robots/{robot_id}/disconnect` - 断开设备
- `POST /api/v1/robots/test-connection` - 测试设备连接

#### 零点标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration` - 启动零点标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/go-to-step` - 步骤导航
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/execute-calibration` - 执行一键标定
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/joint-debug` - 关节调试
- `GET /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/summary` - 获取标定汇总
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/save-zero-point` - 保存零点数据
- `POST /api/v1/robots/{robot_id}/zero-point-calibration/{session_id}/validate` - 验证标定结果

#### 标定文件管理
- `GET /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 读取标定数据
- `PUT /api/v1/robots/{robot_id}/calibration-files/{file_type}/data` - 保存标定数据

#### 头手标定
- `GET /api/v1/robots/{robot_id}/calibration-config-check` - 环境检查
- `POST /api/v1/robots/{robot_id}/head-hand-calibration` - 启动头手标定
- `POST /api/v1/robots/{robot_id}/head-hand-calibration/save` - 保存标定结果

#### 上位机管理
- `POST /api/v1/robots/{robot_id}/upper-computer/connect` - 连接上位机
- `DELETE /api/v1/robots/{robot_id}/upper-computer/connect` - 断开上位机
- `GET /api/v1/robots/{robot_id}/upper-computer/status` - 获取上位机状态
- `POST /api/v1/robots/{robot_id}/upper-computer/command` - 执行上位机命令

## 项目结构

```
kuavo-studio/
├── backend/                          # 后端服务
│   ├── app/
│   │   ├── api/v1/                   # API路由
│   │   │   ├── robots.py             # 设备管理API
│   │   │   └── calibration.py        # 标定管理API (1382行完整实现)
│   │   ├── core/                     # 核心配置
│   │   ├── models/                   # 数据库模型
│   │   ├── schemas/                  # Pydantic数据模型
│   │   │   └── calibration.py        # 标定数据验证 (214行完整验证)
│   │   ├── services/                 # 业务服务层
│   │   │   ├── ssh_service.py                    # SSH连接管理(支持PTY交互)
│   │   │   ├── zero_point_calibration_service.py # 零点标定逻辑(4步完整流程)
│   │   │   ├── calibration_file_service.py       # 标定文件管理(522行完整实现)
│   │   │   └── calibration_data_parser.py        # 标定数据解析器(Slave位置提取)
│   │   └── simulator/                # 机器人模拟器
│   │       ├── robot_simulator.py    # 完整模拟器实现(634行)
│   │       └── mock_config_files.py  # 模拟配置文件
│   ├── main.py                       # 生产模式入口
│   ├── run_simulator_8001.py         # 模拟器模式入口
│   └── requirements.txt              # 依赖列表
├── frontend/                         # 前端界面
│   ├── index.html                    # 主页面
│   ├── calibration_new.html          # 标定页面
│   ├── device_script.js              # 设备管理逻辑
│   ├── calibration_script.js         # 标定逻辑
│   ├── device_styles.css             # 设备管理样式
│   ├── calibration_styles.css        # 标定页面样式
│   └── start_frontend.py             # 前端服务器
├── 打开前端界面.html                 # 快速入口
├── README.md                         # 项目文档
├── HANDOVER_GUIDE.md                 # 开发交接文档
└── API_DOCUMENTATION.md              # API详细文档
```

## 数据格式和规范

### 角度单位
所有角度数据使用**弧度(radian)**作为单位，而非度数。

### 关节映射
- **手臂关节** (arms_zero.yaml):
  - ID 1-12: 对应 joint_02 到 joint_13 (左臂6个 + 右臂6个)
  - ID 13-14: 对应 neck_01, neck_02 (头部2个)
- **腿部关节** (offset.csv):
  - ID 1-14: 左腿6个 + 右腿6个 + 肩部2个

### 配置文件路径
- 手臂零点配置: `/home/lab/.config/lejuconfig/arms_zero.yaml`
- 腿部偏移配置: `/home/lab/.config/lejuconfig/offset.csv`

### ROS话题和命令
- **关节调试话题**: `/kuavo_arm_traj`
- **消息类型**: `sensor_msgs/JointState`
- **标定启动命令**: `roslaunch humanoid_controllers load_kuavo_real.launch cali:=true`

## 安全注意事项

### 生产环境安全
1. **网络安全**：
   - 使用HTTPS加密通信
   - 配置CORS白名单
   - 实施API认证机制
   - SSH密码应加密存储

2. **操作安全**：
   - 标定过程不可逆，请谨慎操作
   - 确保机器人处于安全状态
   - 严格遵循标定向导提示
   - 关节参数修改建议幅度≤0.05弧度

### 网络要求
- 确保能够访问机器人的SSH端口(22)
- WebSocket需要稳定的网络连接
- 头手标定需要访问上位机192.168.26.1
- 建议在同一局域网内操作以确保稳定性

### 系统要求
- 支持SSH连接的机器人系统
- ROS环境(Noetic推荐)
- 标定工具和AprilTag(头手标定)
- 足够的磁盘空间用于日志和备份文件

## 开发指南

### 模拟器模式
项目包含完整的机器人模拟器，支持无硬件开发：
- **完整功能模拟**: SSH连接、命令执行、标定流程
- **ROS命令模拟**: roslaunch和rostopic命令支持
- **用户交互模拟**: 标定脚本用户交互模拟
- **数据生成**: 真实的标定数据和关节位置模拟
- **自动化测试**: 支持完整的标定流程测试

### 扩展功能

#### 添加新的标定类型
1. 在 `zero_point_calibration_service.py` 中添加新的工具确认配置
2. 更新前端页面和逻辑
3. 添加对应的API端点
4. 更新模拟器支持

#### 添加新的API端点
1. 在 `app/api/v1/` 中创建新的路由文件
2. 在 `app/api/v1/__init__.py` 中注册路由
3. 创建对应的schema和service
4. 更新API文档

#### 扩展数据解析格式
在 `calibration_data_parser.py` 中添加新的正则表达式模式：
```python
SLAVE_POSITION_PATTERNS.append(r'新的解析模式正则表达式')
```

### 测试和验证
```bash
# 启动后端（模拟器模式）
cd backend
python run_simulator_8001.py

# 启动前端
cd frontend
python start_frontend.py

# 访问API文档
# http://localhost:8001/docs
```

## 故障排查

### 连接问题
- **连接失败**: 检查IP地址、端口、用户名密码是否正确
- **连接超时**: 确认SSH服务运行，检查网络连通性和防火墙设置
- **认证失败**: 验证SSH凭据，检查用户权限和密钥配置
- **网络验证失败**: 确保设备在同一网段，检查ping连通性
- **CORS错误**: 确保后端服务正确启动，检查浏览器控制台错误信息

### 标定问题
- **标定无响应**: 查看浏览器控制台，检查WebSocket连接状态
- **脚本执行失败**: 确认机器人程序运行正常，检查ROS环境和节点状态
- **环境检查失败**: 验证虚拟环境、AprilTag配置、rosbag文件完整性
- **关节调试失败**: 检查ROS话题发布和机器人响应状态
- **数据解析错误**: 查看标定日志，确认输出格式匹配解析规则

### 数据问题
- **关节参数验证失败**: 检查偏移值是否超过安全范围(±0.1)
- **文件读写错误**: 检查文件路径和权限，确认备份机制正常
- **数据格式错误**: 确认角度单位为弧度，检查关节ID映射

### WebSocket问题
- **连接断开**: 实现客户端自动重连机制，检查网络稳定性
- **消息丢失**: 调整心跳间隔，检查消息处理逻辑
- **状态不同步**: 确认订阅状态，检查消息广播机制

### 数据库问题
- **数据库错误**: 删除 `kuavo_studio.db` 文件重新初始化
- **权限问题**: 检查文件读写权限和目录访问权限
- **数据丢失**: 检查数据库备份和恢复机制

## 性能优化建议

### 后端优化
- 使用数据库连接池
- 实现API请求缓存
- 优化WebSocket消息频率
- 定期清理过期会话数据

### 前端优化
- 实现WebSocket自动重连
- 优化大量日志显示性能
- 使用虚拟滚动处理长列表
- 实现数据懒加载

### 网络优化
- 启用HTTP/2支持
- 实现请求压缩
- 优化WebSocket心跳间隔
- 使用CDN加速静态资源

## 功能特性总结

### 已实现功能 (100%)
-  完整的设备管理(CRUD)，支持分页显示
-  设备类型区分（上位机/下位机）
-  前端分页组件（页码导航、每页数量选择）
-  SSH连接管理和状态监控
-  设备信息自动获取和实时状态更新
-  零点标定4步完整流程
-  一键标定和关节调试
-  头手标定3步完整流程
-  实时WebSocket通信
-  标定文件管理(arms_zero.yaml, offset.csv)
-  关节参数安全验证
-  完整模拟器支持
-  7项环境预检查
-  用户交互自动化
-  数据解析和验证
-  上位机管理
-  进程管理和清理
-  支持新旧API格式兼容

## 支持与文档

### 详细文档
- **API接口文档**: `API_DOCUMENTATION.md`
- **开发交接文档**: `HANDOVER_GUIDE.md`
- **在线API文档**: http://localhost:8001/docs
- **ReDoc文档**: http://localhost:8001/redoc

### 技术支持
如有问题，请查阅上述文档或检查：
1. 后端服务是否正常启动
2. 前端WebSocket连接是否正常
3. 机器人SSH连接是否稳定
4. ROS环境是否配置正确

### 贡献指南
1. Fork项目到个人仓库
2. 创建特性分支进行开发
3. 提交代码并创建Pull Request
4. 确保通过所有测试用例
5. 更新相关文档

---

**版本**: 1.2.0  
**最后更新**: 2025-08-01  
**开发状态**: 生产就绪  
**License**: MIT