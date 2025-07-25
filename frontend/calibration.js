// API配置
const API_BASE_URL = 'http://localhost:8001/api/v1';
const WS_BASE_URL = 'ws://localhost:8001';

// 全局变量
let robots = [];
let selectedRobot = null;
let selectedCalibrationType = null;
let calibrationSession = null;
let ws = null;
let currentStep = 1;

// 关节名称映射
const jointNames = [
    { name: '头部', id: 'head' },
    { name: '左肩1', id: 'l_shoulder_1' },
    { name: '左肩2', id: 'l_shoulder_2' },
    { name: '左肩3', id: 'l_shoulder_3' },
    { name: '左肘', id: 'l_elbow' },
    { name: '左腕1', id: 'l_wrist_1' },
    { name: '左腕2', id: 'l_wrist_2' },
    { name: '右肩1', id: 'r_shoulder_1' },
    { name: '右肩2', id: 'r_shoulder_2' },
    { name: '右肩3', id: 'r_shoulder_3' },
    { name: '右肘', id: 'r_elbow' },
    { name: '右腕1', id: 'r_wrist_1' },
    { name: '右腕2', id: 'r_wrist_2' }
];

// DOM元素
const deviceSelect = document.getElementById('deviceSelect');
const calibrationTypes = document.getElementById('calibrationTypes');
const calibrationProcess = document.getElementById('calibrationProcess');
const calibrationLogs = document.getElementById('calibrationLogs');
const successScreen = document.getElementById('successScreen');
const errorScreen = document.getElementById('errorScreen');
const calibrationDataTable = document.getElementById('calibrationDataTable');
const jointDataBody = document.getElementById('jointDataBody');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadRobots();
});

// WebSocket连接
function initWebSocket() {
    const clientId = 'calibration-client-' + Date.now();
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
    switch (message.type) {
        case 'calibration_status':
            handleCalibrationStatus(message.data);
            break;
        case 'calibration_log':
            handleCalibrationLog(message.data);
            break;
        case 'calibration_data':
            handleCalibrationData(message.data);
            break;
    }
}

// 处理标定状态
function handleCalibrationStatus(data) {
    if (data.status === 'waiting_for_user' && data.user_prompt) {
        // 创建用户确认对话框
        if (confirm(data.user_prompt)) {
            sendCalibrationResponse('y');
        } else {
            sendCalibrationResponse('n');
        }
    } else if (data.status === 'success') {
        showSuccessScreen();
    } else if (data.status === 'failed') {
        showErrorScreen(data.error_message);
    } else if (data.status === 'progress') {
        updateProgress(data.step);
    }
}

// 处理标定日志
function handleCalibrationLog(data) {
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    logLine.textContent = data.log;
    calibrationLogs.appendChild(logLine);
    calibrationLogs.scrollTop = calibrationLogs.scrollHeight;
}

// 处理标定数据
function handleCalibrationData(data) {
    if (data.joint_data) {
        updateJointDataTable(data.joint_data);
    }
}

// 加载机器人列表
async function loadRobots() {
    try {
        const response = await fetch(`${API_BASE_URL}/robots`);
        robots = await response.json();
        
        // 只显示已连接的机器人
        const connectedRobots = robots.filter(r => r.connection_status === 'connected');
        
        deviceSelect.innerHTML = '<option value="">请选择设备</option>';
        connectedRobots.forEach(robot => {
            const option = document.createElement('option');
            option.value = robot.id;
            option.textContent = `${robot.name} (${robot.ip_address})`;
            deviceSelect.appendChild(option);
        });
        
        if (connectedRobots.length === 0) {
            alert('没有已连接的设备，请先连接设备');
            window.location.href = 'index.html';
        }
    } catch (error) {
        console.error('加载机器人列表失败:', error);
        alert('加载设备列表失败');
    }
}

// 设备选择变化
deviceSelect.addEventListener('change', (e) => {
    selectedRobot = robots.find(r => r.id === e.target.value);
    if (selectedRobot) {
        calibrationTypes.style.display = 'grid';
    } else {
        calibrationTypes.style.display = 'none';
    }
});

// 选择标定类型
function selectCalibrationType(type) {
    if (!selectedRobot) {
        alert('请先选择设备');
        return;
    }
    
    selectedCalibrationType = type;
    startCalibration();
}

// 开始标定
async function startCalibration() {
    try {
        // 订阅机器人更新
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'subscribe',
                robot_id: selectedRobot.id
            }));
        }
        
        // 隐藏选择界面，显示标定过程
        calibrationTypes.style.display = 'none';
        calibrationProcess.style.display = 'block';
        
        // 设置标题
        document.getElementById('processTitle').textContent = 
            selectedCalibrationType === 'zero_point' ? '全身零点标定进行中' : '头手标定进行中';
        
        // 清空日志
        calibrationLogs.innerHTML = '<div class="log-line">Starting calibration process...</div>';
        
        // 显示数据表格（仅零点标定）
        if (selectedCalibrationType === 'zero_point') {
            calibrationDataTable.style.display = 'block';
            initializeJointDataTable();
        }
        
        // 调用API开始标定
        const response = await fetch(`${API_BASE_URL}/robots/${selectedRobot.id}/calibrations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                calibration_type: selectedCalibrationType
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            calibrationSession = {
                session_id: result.session_id,
                robot_id: selectedRobot.id,
                calibration_type: selectedCalibrationType
            };
        } else {
            const error = await response.json();
            alert('启动标定失败：' + error.detail);
            backToSelection();
        }
    } catch (error) {
        console.error('启动标定失败:', error);
        alert('启动标定失败：网络错误');
        backToSelection();
    }
}

// 停止标定
async function stopCalibration() {
    if (!calibrationSession || !confirm('确定要停止标定吗？')) {
        return;
    }
    
    try {
        await fetch(
            `${API_BASE_URL}/robots/${calibrationSession.robot_id}/calibrations/current`,
            { method: 'DELETE' }
        );
        
        // 取消订阅
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'unsubscribe',
                robot_id: calibrationSession.robot_id
            }));
        }
        
        backToSelection();
    } catch (error) {
        console.error('停止标定失败:', error);
    }
}

// 发送标定响应
async function sendCalibrationResponse(response) {
    if (!calibrationSession) return;
    
    try {
        await fetch(
            `${API_BASE_URL}/robots/${calibrationSession.robot_id}/calibrations/response`,
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

// 更新进度
function updateProgress(step) {
    // 更新当前步骤
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step${i}`);
        if (i < step) {
            stepElement.classList.add('completed');
            stepElement.classList.remove('active');
        } else if (i === step) {
            stepElement.classList.add('active');
            stepElement.classList.remove('completed');
        } else {
            stepElement.classList.remove('active', 'completed');
        }
    }
    currentStep = step;
}

// 初始化关节数据表格
function initializeJointDataTable() {
    jointDataBody.innerHTML = '';
    jointNames.forEach(joint => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${joint.name}</td>
            <td>0.000</td>
            <td>0.000</td>
            <td>0.000</td>
            <td>0.000</td>
            <td>0</td>
            <td>0</td>
        `;
        jointDataBody.appendChild(row);
    });
}

// 更新关节数据表格
function updateJointDataTable(jointData) {
    const rows = jointDataBody.getElementsByTagName('tr');
    jointData.forEach((data, index) => {
        if (rows[index]) {
            const cells = rows[index].getElementsByTagName('td');
            cells[1].textContent = data.left.toFixed(3);
            cells[2].textContent = data.right.toFixed(3);
            cells[3].textContent = data.left_offset.toFixed(3);
            cells[4].textContent = data.right_offset.toFixed(3);
            cells[5].textContent = data.left_encoder;
            cells[6].textContent = data.right_encoder;
        }
    });
}

// 显示成功界面
function showSuccessScreen() {
    calibrationProcess.style.display = 'none';
    successScreen.style.display = 'block';
    
    // 播放成功音效（如果有）
    // new Audio('success.mp3').play();
}

// 显示错误界面
function showErrorScreen(errorMessage) {
    calibrationProcess.style.display = 'none';
    errorScreen.style.display = 'block';
    
    // 更新错误原因
    if (errorMessage) {
        const errorReasons = document.getElementById('errorReasons');
        errorReasons.innerHTML = `<li>${errorMessage}</li>`;
    }
}

// 查看标定报告
function viewCalibrationReport() {
    alert('标定报告功能开发中...');
}

// 返回选择界面
function backToSelection() {
    calibrationProcess.style.display = 'none';
    successScreen.style.display = 'none';
    errorScreen.style.display = 'none';
    calibrationTypes.style.display = 'grid';
    calibrationSession = null;
    currentStep = 1;
}

// 重新标定
function retryCalibration() {
    backToSelection();
    if (selectedCalibrationType) {
        selectCalibrationType(selectedCalibrationType);
    }
}