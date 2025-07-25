// API配置
const API_BASE_URL = 'http://localhost:8001/api/v1';
const WS_BASE_URL = 'ws://localhost:8001';

// 全局变量
let robots = [];
let ws = null;
let currentCalibrationSession = null;

// DOM元素
const robotsList = document.getElementById('robotsList');
const addRobotBtn = document.getElementById('addRobotBtn');
const addRobotModal = document.getElementById('addRobotModal');
const addRobotForm = document.getElementById('addRobotForm');
const closeModal = document.getElementById('closeModal');
const cancelAddRobot = document.getElementById('cancelAddRobot');
const robotDetailModal = document.getElementById('robotDetailModal');
const closeDetailModal = document.getElementById('closeDetailModal');
const calibrationPanel = document.getElementById('calibrationPanel');
const calibrationLogs = document.getElementById('calibrationLogs');
const stopCalibrationBtn = document.getElementById('stopCalibrationBtn');
const userPromptModal = document.getElementById('userPromptModal');
const userPromptMessage = document.getElementById('userPromptMessage');
const userPromptYes = document.getElementById('userPromptYes');
const userPromptNo = document.getElementById('userPromptNo');
const connectingModal = document.getElementById('connectingModal');
const connectingStatus = document.getElementById('connectingStatus');
const deviceConfirmModal = document.getElementById('deviceConfirmModal');
const closeDeviceConfirmModal = document.getElementById('closeDeviceConfirmModal');
const cancelDeviceConfirm = document.getElementById('cancelDeviceConfirm');
const confirmDeviceAdd = document.getElementById('confirmDeviceAdd');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadRobots();
    setupEventListeners();
});

// 页面关闭/刷新时的处理
window.addEventListener('beforeunload', async (event) => {
    // 如果有正在进行的标定，提示用户
    if (currentCalibrationSession) {
        event.preventDefault();
        event.returnValue = '有正在进行的标定任务，确定要离开吗？';
    }
});

// 页面卸载时停止标定
window.addEventListener('unload', async () => {
    if (currentCalibrationSession) {
        try {
            // 发送停止标定请求（使用sendBeacon确保请求被发送）
            const data = JSON.stringify({});
            navigator.sendBeacon(
                `${API_BASE_URL}/robots/${currentCalibrationSession.robot_id}/calibrations/current`,
                data
            );
        } catch (error) {
            console.error('停止标定失败:', error);
        }
    }
});

// WebSocket连接
function initWebSocket() {
    const clientId = 'web-client-' + Date.now();
    ws = new WebSocket(`${WS_BASE_URL}/ws/${clientId}`);
    
    ws.onopen = () => {
        console.log('WebSocket连接成功');
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket连接关闭，5秒后重连...');
        setTimeout(initWebSocket, 5000);
    };
}

// 处理WebSocket消息
function handleWebSocketMessage(message) {
    console.log('WebSocket消息:', message);
    
    // 处理消息格式问题
    if (message.type && typeof message.type === 'object') {
        // 如果type是对象，说明消息格式有问题
        console.error('消息格式错误，type应该是字符串:', message);
        return;
    }
    
    switch (message.type) {
        case 'robot_status':
            handleRobotStatusUpdate(message.data);
            break;
        case 'calibration_status':
            handleCalibrationStatus(message.data);
            break;
        case 'calibration_log':
            handleCalibrationLog(message.data);
            break;
        case 'connection':
        case 'heartbeat':
        case 'subscribed':
        case 'unsubscribed':
            // 忽略这些系统消息
            break;
        default:
            console.log('未处理的消息类型:', message.type);
    }
}

// 处理机器人状态更新
function handleRobotStatusUpdate(data) {
    if (data.status === 'deleted') {
        robots = robots.filter(r => r.id !== data.robot_id);
    } else {
        const robot = robots.find(r => r.id === data.robot_id);
        if (robot) {
            robot.connection_status = data.status;
        }
    }
    renderRobots();
}

// 处理标定状态
function handleCalibrationStatus(data) {
    console.log('收到标定状态更新:', data);
    
    if (data.status === 'waiting_for_user' && data.user_prompt) {
        console.log('显示用户提示:', data.user_prompt);
        showUserPrompt(data.user_prompt, data.robot_id);
    } else if (data.status === 'success' || data.status === 'failed') {
        if (data.status === 'success') {
            alert('标定完成！');
        } else {
            alert('标定失败：' + (data.error_message || '未知错误'));
        }
        calibrationPanel.style.display = 'none';
        currentCalibrationSession = null;
    } else if (data.status === 'running') {
        console.log('标定运行中，当前步骤:', data.current_step);
    }
}

// 处理标定日志
function handleCalibrationLog(data) {
    console.log('收到标定日志:', data);
    if (currentCalibrationSession && data.robot_id === currentCalibrationSession.robot_id) {
        const logLine = document.createElement('div');
        logLine.className = 'log-line';
        logLine.textContent = data.log;
        calibrationLogs.appendChild(logLine);
        calibrationLogs.scrollTop = calibrationLogs.scrollHeight;
    } else {
        console.log('日志被忽略，当前会话:', currentCalibrationSession);
    }
}

// 设置事件监听器
function setupEventListeners() {
    addRobotBtn.addEventListener('click', () => {
        addRobotModal.style.display = 'flex';
    });
    
    closeModal.addEventListener('click', () => {
        addRobotModal.style.display = 'none';
        addRobotForm.reset();
    });
    
    cancelAddRobot.addEventListener('click', () => {
        addRobotModal.style.display = 'none';
        addRobotForm.reset();
    });
    
    closeDetailModal.addEventListener('click', () => {
        robotDetailModal.style.display = 'none';
    });
    
    closeDeviceConfirmModal.addEventListener('click', () => {
        deviceConfirmModal.style.display = 'none';
    });
    
    cancelDeviceConfirm.addEventListener('click', () => {
        deviceConfirmModal.style.display = 'none';
    });
    
    addRobotForm.addEventListener('submit', handleAddRobot);
    
    stopCalibrationBtn.addEventListener('click', stopCalibration);
    
    userPromptYes.addEventListener('click', () => sendCalibrationResponse('y'));
    userPromptNo.addEventListener('click', () => sendCalibrationResponse('n'));
    
    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === addRobotModal) {
            addRobotModal.style.display = 'none';
            addRobotForm.reset();
        }
        if (event.target === robotDetailModal) {
            robotDetailModal.style.display = 'none';
        }
    });
}

// 加载机器人列表
async function loadRobots() {
    try {
        const response = await fetch(`${API_BASE_URL}/robots`);
        robots = await response.json();
        renderRobots();
    } catch (error) {
        console.error('加载机器人列表失败:', error);
        alert('加载设备列表失败');
    }
}

// 渲染机器人列表
function renderRobots() {
    robotsList.innerHTML = '';
    
    if (robots.length === 0) {
        robotsList.innerHTML = `
            <div class="empty-state">
                <svg class="empty-robot-icon" width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="60" cy="60" r="58" fill="#FFF3E0"/>
                    <path d="M60 20C53.3726 20 48 25.3726 48 32V42H42C38.6863 42 36 44.6863 36 48V78C36 81.3137 38.6863 84 42 84H78C81.3137 84 84 81.3137 84 78V48C84 44.6863 81.3137 42 78 42H72V32C72 25.3726 66.6274 20 60 20ZM54 32C54 28.6863 56.6863 26 60 26C63.3137 26 66 28.6863 66 32V42H54V32ZM48 60C48 57.7909 49.7909 56 52 56C54.2091 56 56 57.7909 56 60C56 62.2091 54.2091 64 52 64C49.7909 64 48 62.2091 48 60ZM64 60C64 57.7909 65.7909 56 68 56C70.2091 56 72 57.7909 72 60C72 62.2091 70.2091 64 68 64C65.7909 64 64 62.2091 64 60Z" fill="#FF9800"/>
                    <rect x="50" y="72" width="20" height="4" rx="2" fill="#FF9800"/>
                </svg>
                <h3 style="margin-top: 1rem; color: #666;">暂无任何机器人设备</h3>
                <p style="color: #999; font-size: 0.875rem; margin-top: 0.5rem;">请点击上方"添加设备"按钮添加新设备</p>
            </div>
        `;
        return;
    }
    
    robots.forEach(robot => {
        const card = createRobotCard(robot);
        robotsList.appendChild(card);
    });
}

// 创建机器人卡片
function createRobotCard(robot) {
    const card = document.createElement('div');
    card.className = 'robot-card';
    
    const statusClass = robot.connection_status === 'connected' ? 'status-connected' : 
                       robot.connection_status === 'connecting' ? 'status-connecting' : 
                       'status-disconnected';
    const statusText = robot.connection_status === 'connected' ? '已连接' :
                      robot.connection_status === 'connecting' ? '连接中' : '未连接';
    
    card.innerHTML = `
        <div class="robot-card-header">
            <h3 class="robot-name">${robot.name}</h3>
            <span class="robot-status ${statusClass}">${statusText}</span>
        </div>
        <div class="robot-info">
            <div>IP地址：${robot.ip_address}:${robot.port}</div>
            <div>型号：${robot.hardware_model || '未知'}</div>
            <div>版本：${robot.software_version || '未知'}</div>
        </div>
        <div class="robot-actions">
            ${robot.connection_status === 'disconnected' || robot.connection_status === 'connecting' ? 
                `<button class="btn btn-primary" onclick="connectRobot('${robot.id}')">连接</button>` :
                robot.connection_status === 'connected' ?
                `<button class="btn btn-secondary" onclick="disconnectRobot('${robot.id}')">断开</button>` :
                `<button class="btn btn-warning" onclick="connectRobot('${robot.id}')">重试连接</button>`
            }
            <button class="btn btn-secondary" onclick="showRobotDetail('${robot.id}')">详情</button>
            ${robot.connection_status === 'connected' ? 
                `<button class="btn btn-success" onclick="startCalibration('${robot.id}', 'zero_point')">全身标定</button>
                 <button class="btn btn-success" onclick="startCalibration('${robot.id}', 'head_hand')">头手标定</button>` :
                ''
            }
            <button class="btn btn-danger" onclick="deleteRobot('${robot.id}')">删除</button>
        </div>
    `;
    
    return card;
}

// 添加机器人 - 新流程
async function handleAddRobot(event) {
    event.preventDefault();
    
    const formData = new FormData(addRobotForm);
    const robotData = Object.fromEntries(formData);
    robotData.port = parseInt(robotData.port);
    
    // 隐藏添加表单，显示连接中对话框
    addRobotModal.style.display = 'none';
    connectingModal.style.display = 'flex';
    connectingStatus.textContent = '正在建立SSH连接...';
    
    try {
        // 先测试API是否可访问
        console.log('开始测试连接...', robotData);
        
        // 步骤1：测试连接
        // 使用简单的超时设置
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            console.log('连接超时，中止请求');
            controller.abort();
        }, 30000); // 30秒超时
        
        const testResponse = await fetch(`${API_BASE_URL}/robots/test-connection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(robotData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!testResponse.ok) {
            const error = await testResponse.json();
            throw new Error(error.detail || '连接测试失败');
        }
        
        const testResult = await testResponse.json();
        
        if (!testResult.success) {
            throw new Error('无法连接到设备');
        }
        
        connectingStatus.textContent = '获取设备信息...';
        
        // 步骤2：显示设备信息确认对话框
        connectingModal.style.display = 'none';
        deviceConfirmModal.style.display = 'flex';
        
        // 填充设备信息
        // document.getElementById('confirmDeviceName').textContent = testResult.device_info.name; // 元素不存在，注释掉
        const ipElement = document.getElementById('confirmIpAddress');
        if (ipElement) ipElement.textContent = testResult.device_info.ip_address;
        
        const modelElement = document.getElementById('confirmHardwareModel');
        if (modelElement) modelElement.textContent = testResult.device_info.hardware_model;
        
        const versionElement = document.getElementById('confirmSoftwareVersion');
        if (versionElement) versionElement.textContent = testResult.device_info.software_version;
        
        const snElement = document.getElementById('confirmSnNumber');
        if (snElement) snElement.textContent = testResult.device_info.sn_number;
        
        const endEffectorElement = document.getElementById('confirmEndEffector');
        if (endEffectorElement) endEffectorElement.textContent = testResult.device_info.end_effector_type;
        
        // 保存设备信息到临时变量
        window.pendingRobotData = {
            ...robotData,
            hardware_model: testResult.device_info.hardware_model,
            software_version: testResult.device_info.software_version,
            sn_number: testResult.device_info.sn_number,
            end_effector_type: testResult.device_info.end_effector_type
        };
        
    } catch (error) {
        console.error('连接测试失败:', error);
        connectingModal.style.display = 'none';
        
        // 处理超时错误
        if (error.name === 'AbortError') {
            alert('连接超时：设备响应时间过长，请检查网络连接');
        } else {
            alert('连接失败：' + error.message);
        }
        
        addRobotModal.style.display = 'flex'; // 重新显示添加表单
    }
}

// 确认添加设备
async function confirmAddDevice() {
    if (!window.pendingRobotData) return;
    
    deviceConfirmModal.style.display = 'none';
    
    try {
        // 步骤3：保存设备到数据库
        const response = await fetch(`${API_BASE_URL}/robots`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(window.pendingRobotData)
        });
        
        if (response.ok) {
            const newRobot = await response.json();
            robots.push(newRobot);
            renderRobots();
            addRobotForm.reset();
            alert('设备添加成功！正在连接...');
            
            // 自动连接新添加的设备
            await connectRobot(newRobot.id);
        } else {
            const error = await response.json();
            alert('添加失败：' + error.detail);
        }
    } catch (error) {
        console.error('添加设备失败:', error);
        alert('添加失败：网络错误');
    } finally {
        window.pendingRobotData = null;
    }
}

// 绑定确认按钮事件
confirmDeviceAdd.addEventListener('click', confirmAddDevice);

// 连接机器人
async function connectRobot(robotId) {
    try {
        // 先更新状态为connecting
        const robotIndex = robots.findIndex(r => r.id === robotId);
        if (robotIndex !== -1) {
            robots[robotIndex].connection_status = 'connecting';
            renderRobots();
        }
        
        const response = await fetch(`${API_BASE_URL}/robots/${robotId}/connect`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert('连接失败：' + error.detail);
            await loadRobots(); // 失败也要刷新状态
        } else {
            const result = await response.json();
            // 如果返回了状态，直接更新
            if (result.status === 'connected') {
                const robotIndex = robots.findIndex(r => r.id === robotId);
                if (robotIndex !== -1) {
                    robots[robotIndex].connection_status = 'connected';
                    renderRobots();
                }
                alert('连接成功！');
            } else {
                // 否则重新加载
                await loadRobots();
            }
        }
    } catch (error) {
        console.error('连接失败:', error);
        alert('连接失败：网络错误');
        // 失败后重新加载
        await loadRobots();
    }
}

// 断开连接
async function disconnectRobot(robotId) {
    // 检查是否有正在进行的标定
    if (currentCalibrationSession && currentCalibrationSession.robot_id === robotId) {
        if (!confirm('该设备正在进行标定，断开连接将终止标定过程。确定要继续吗？')) {
            return;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/robots/${robotId}/disconnect`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert('断开失败：' + error.detail);
        } else {
            // 如果是当前标定的机器人，清理标定状态
            if (currentCalibrationSession && currentCalibrationSession.robot_id === robotId) {
                calibrationPanel.style.display = 'none';
                currentCalibrationSession = null;
            }
            await loadRobots();
        }
    } catch (error) {
        console.error('断开失败:', error);
        alert('断开失败：网络错误');
    }
}

// 删除机器人
async function deleteRobot(robotId) {
    // 检查是否有正在进行的标定
    if (currentCalibrationSession && currentCalibrationSession.robot_id === robotId) {
        alert('该设备正在进行标定，请先停止标定再删除设备');
        return;
    }
    
    if (!confirm('确定要删除这个设备吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/robots/${robotId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            robots = robots.filter(r => r.id !== robotId);
            renderRobots();
        } else {
            const error = await response.json();
            alert('删除失败：' + error.detail);
        }
    } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败：网络错误');
    }
}

// 显示机器人详情
async function showRobotDetail(robotId) {
    const robot = robots.find(r => r.id === robotId);
    if (!robot) return;
    
    const detailContent = document.getElementById('robotDetailContent');
    detailContent.innerHTML = `
        <div class="detail-item">
            <span class="detail-label">设备名称：</span>
            <span class="detail-value">${robot.name}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">IP地址：</span>
            <span class="detail-value">${robot.ip_address}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">SSH端口：</span>
            <span class="detail-value">${robot.port}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">SSH用户：</span>
            <span class="detail-value">${robot.ssh_user}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">连接状态：</span>
            <span class="detail-value">${robot.connection_status}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">硬件型号：</span>
            <span class="detail-value">${robot.hardware_model || '未知'}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">软件版本：</span>
            <span class="detail-value">${robot.software_version || '未知'}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">SN号：</span>
            <span class="detail-value">${robot.sn_number || '未知'}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">末端执行器：</span>
            <span class="detail-value">${robot.end_effector_type || '未知'}</span>
        </div>
    `;
    
    robotDetailModal.style.display = 'flex';
}

// 开始标定
async function startCalibration(robotId, calibrationType) {
    try {
        // 订阅机器人更新
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'subscribe',
                robot_id: robotId
            }));
        }
        
        const response = await fetch(`${API_BASE_URL}/robots/${robotId}/calibrations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                calibration_type: calibrationType
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            currentCalibrationSession = {
                session_id: result.session_id,
                robot_id: robotId,
                calibration_type: calibrationType
            };
            
            // 显示标定面板
            calibrationPanel.style.display = 'block';
            calibrationLogs.innerHTML = '';
            document.getElementById('calibrationInfo').textContent = 
                `正在进行${calibrationType === 'zero_point' ? '全身零点标定' : '头手标定'}...`;
        } else {
            const error = await response.json();
            alert('启动标定失败：' + error.detail);
        }
    } catch (error) {
        console.error('启动标定失败:', error);
        alert('启动标定失败：网络错误');
    }
}

// 停止标定
async function stopCalibration() {
    if (!currentCalibrationSession) {
        console.error('没有活动的标定会话');
        alert('没有正在进行的标定');
        return;
    }
    
    if (!confirm('确定要停止标定吗？')) {
        return;
    }
    
    try {
        const response = await fetch(
            `${API_BASE_URL}/robots/${currentCalibrationSession.robot_id}/calibrations/current`,
            { method: 'DELETE' }
        );
        
        if (response.ok) {
            calibrationPanel.style.display = 'none';
            currentCalibrationSession = null;
            
            // 取消订阅
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'unsubscribe',
                    robot_id: currentCalibrationSession.robot_id
                }));
            }
        }
    } catch (error) {
        console.error('停止标定失败:', error);
    }
}

// 显示用户提示
function showUserPrompt(prompt, robotId) {
    userPromptMessage.textContent = prompt;
    userPromptModal.style.display = 'flex';
}

// 发送标定响应
async function sendCalibrationResponse(response) {
    userPromptModal.style.display = 'none';
    
    if (!currentCalibrationSession) return;
    
    try {
        await fetch(
            `${API_BASE_URL}/robots/${currentCalibrationSession.robot_id}/calibrations/response`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ response })
            }
        );
    } catch (error) {
        console.error('发送响应失败:', error);
    }
}