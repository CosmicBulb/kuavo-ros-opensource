# KUAVO Studio - 机器人管理系统

这是一个基于Web的KUAVO人形机器人管理和标定系统，提供设备管理和交互式标定功能。

## 功能特性

### 设备管理
- 添加、删除机器人设备
- 通过SSH连接/断开机器人
- 查看设备详细信息（硬件型号、软件版本、SN号等）
- 实时连接状态监控

### 机器人标定
- **全身零点标定**：机器人关节零点校准
- **头手标定**：头部和手部的精确标定
- 实时日志显示
- 交互式用户确认流程
- WebSocket实时状态更新

## 技术栈

### 后端
- **FastAPI** - 高性能Web框架
- **SQLite** - 轻量级数据库
- **Paramiko** - SSH通信
- **WebSocket** - 实时通信
- **SQLAlchemy** - ORM框架

### 前端
- 原生HTML/CSS/JavaScript
- WebSocket客户端
- 响应式设计

## 快速开始

### 1. 安装后端依赖

```bash
cd kuavo-studio/backend
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd kuavo-studio/backend
python main.py
```

后端服务将在 http://localhost:8000 启动

### 3. 启动前端

直接在浏览器中打开 `kuavo-studio/frontend/index.html` 文件即可。

或者使用Python的简单HTTP服务器：

```bash
cd kuavo-studio/frontend
python -m http.server 8080
```

然后访问 http://localhost:8080

## 使用说明

### 添加设备
1. 点击右上角"添加设备"按钮
2. 填写设备信息：
   - 设备名称（唯一）
   - IP地址
   - SSH端口（默认22）
   - SSH用户名（默认leju）
   - SSH密码
3. 系统会自动测试连接并获取机器人信息

### 连接/断开设备
- 在设备卡片上点击"连接"/"断开"按钮
- 连接状态会实时更新

### 执行标定
1. 确保设备已连接
2. 选择标定类型：
   - **全身标定**：执行全身关节零点标定
   - **头手标定**：执行头部和手部标定
3. 标定过程中：
   - 实时查看执行日志
   - 根据提示进行确认操作
   - 可随时停止标定

## API文档

后端启动后，可访问自动生成的API文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
kuavo-studio/
├── backend/
│   ├── app/
│   │   ├── api/          # API路由
│   │   ├── core/         # 核心配置
│   │   ├── models/       # 数据模型
│   │   ├── schemas/      # Pydantic模型
│   │   └── services/     # 业务服务
│   ├── main.py          # 应用入口
│   └── requirements.txt  # 依赖列表
├── frontend/
│   ├── index.html       # 主页面
│   ├── styles.css       # 样式
│   └── script.js        # 前端逻辑
└── README.md

```

## 注意事项

1. **安全性**：
   - 生产环境中应使用HTTPS
   - SSH密码应加密存储
   - 配置CORS白名单

2. **标定操作**：
   - 标定过程不可逆，请谨慎操作
   - 确保机器人处于安全状态
   - 遵循标定提示进行操作

3. **网络要求**：
   - 确保能够访问机器人的SSH端口
   - WebSocket需要稳定的网络连接

## 开发说明

### 扩展标定类型
在 `calibration_service.py` 中的 `interaction_patterns` 添加新的交互模式：

```python
self.interaction_patterns = {
    "new_calibration": [
        (r"匹配模式", "默认响应"),
        # ...
    ]
}
```

### 添加新的API端点
1. 在 `app/api/v1/` 中创建新的路由文件
2. 在 `app/api/v1/__init__.py` 中注册路由
3. 创建对应的schema和service

## 故障排查

### 连接失败
- 检查IP地址和端口是否正确
- 确认SSH服务正在运行
- 验证用户名和密码

### 标定无响应
- 查看浏览器控制台错误
- 检查WebSocket连接状态
- 确认机器人程序正常运行

### 数据库错误
- 删除 `kuavo_studio.db` 文件重新初始化
- 检查文件权限

## License

本项目仅供学习和研究使用。