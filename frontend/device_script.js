// KUAVO Studio Device Management Script - 与标定界面风格保持一致
const API_BASE_URL = 'http://localhost:8001/api/v1';
const WS_BASE_URL = 'ws://localhost:8001';

// Global variables
let robots = [];
let ws = null;

// DOM elements
const robotsList = document.getElementById('robotsList');
const addRobotBtn = document.getElementById('addRobotBtn');
const addRobotModal = document.getElementById('addRobotModal');
const addRobotForm = document.getElementById('addRobotForm');
const closeModal = document.getElementById('closeModal');
const robotDetailModal = document.getElementById('robotDetailModal');
const closeDetailModal = document.getElementById('closeDetailModal');
const deviceConfirmModal = document.getElementById('deviceConfirmModal');
const closeDeviceConfirmModal = document.getElementById('closeDeviceConfirmModal');
const cancelDeviceConfirm = document.getElementById('cancelDeviceConfirm');
const confirmDeviceAdd = document.getElementById('confirmDeviceAdd');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressLogs = document.getElementById('progressLogs');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadRobots();
    setupEventListeners();
    setupTabs();
});

// WebSocket connection
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

// Handle WebSocket messages
function handleWebSocketMessage(message) {
    console.log('WebSocket消息:', message);
    
    switch (message.type) {
        case 'robot_status':
            handleRobotStatusUpdate(message.data);
            break;
        default:
            console.log('未处理的消息类型:', message.type);
    }
}

// Handle robot status updates
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

// Setup event listeners
function setupEventListeners() {
    addRobotBtn.addEventListener('click', () => {
        addRobotModal.style.display = 'flex';
    });
    
    closeModal.addEventListener('click', () => {
        closeAddRobotModal();
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
    
    confirmDeviceAdd.addEventListener('click', confirmAddDevice);
    
    addRobotForm.addEventListener('submit', handleAddRobot);
    
    // Close modals when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === addRobotModal) {
            closeAddRobotModal();
        }
        if (event.target === robotDetailModal) {
            robotDetailModal.style.display = 'none';
        }
        if (event.target === deviceConfirmModal) {
            deviceConfirmModal.style.display = 'none';
        }
    });
}

// Setup tabs functionality
function setupTabs() {
    document.addEventListener('click', (event) => {
        if (event.target.classList.contains('tab-btn')) {
            const tabId = event.target.getAttribute('data-tab');
            const tabContainer = event.target.closest('.modal-body');
            
            // Remove active class from all tabs and panels in this container
            tabContainer.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            tabContainer.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
            
            // Add active class to clicked tab
            event.target.classList.add('active');
            
            // Show corresponding panel
            const panel = tabContainer.querySelector(`#${tabId}Tab`);
            if (panel) {
                panel.classList.add('active');
            }
        }
    });
}

// Close add robot modal and reset form
function closeAddRobotModal() {
    addRobotModal.style.display = 'none';
    addRobotForm.reset();
    progressSection.style.display = 'none';
    progressFill.style.width = '0%';
    progressLogs.innerHTML = '';
}

// Load robots from API
async function loadRobots() {
    try {
        const response = await fetch(`${API_BASE_URL}/robots`);
        robots = await response.json();
        renderRobots();
    } catch (error) {
        console.error('加载机器人列表失败:', error);
        showToast('加载设备列表失败', 'error');
    }
}

// Render robots list
function renderRobots() {
    robotsList.innerHTML = '';
    
    if (robots.length === 0) {
        robotsList.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 120 120" fill="none">
                    <circle cx="60" cy="60" r="50" fill="#ff9800" opacity="0.2"/>
                    <path d="M40 45h40v30H40z" fill="#ff9800"/>
                    <circle cx="50" cy="55" r="3" fill="white"/>
                    <circle cx="70" cy="55" r="3" fill="white"/>
                    <rect x="55" y="65" width="10" height="3" rx="1.5" fill="white"/>
                </svg>
                <div class="empty-title">暂无任何机器人设备</div>
            </div>
        `;
        return;
    }
    
    robots.forEach(robot => {
        const item = createDeviceItem(robot);
        robotsList.appendChild(item);
    });
}

// Create device item
function createDeviceItem(robot) {
    const item = document.createElement('div');
    item.className = 'device-item';
    
    const statusClass = robot.connection_status === 'connected' ? 'connected' : 
                       robot.connection_status === 'connecting' ? 'connecting' : 
                       'disconnected';
    
    const connectBtnText = robot.connection_status === 'connected' ? '断开' :
                          robot.connection_status === 'connecting' ? '连接中...' : '连接';
    
    const connectBtnClass = robot.connection_status === 'connected' ? 'disconnect' :
                           robot.connection_status === 'connecting' ? 'connect' : 'connect';
    
    const connectBtnDisabled = robot.connection_status === 'connecting';
    
    item.innerHTML = `
        <div class="device-status ${statusClass}"></div>
        <div class="device-name">${robot.name}</div>
        <div class="device-info">
            <span>端口: ${robot.port}</span>
            <span>IP: ${robot.ip_address}</span>
        </div>
        <div class="device-actions">
            <button class="action-btn details" onclick="showRobotDetail('${robot.id}')">详情</button>
            <button class="action-btn ${connectBtnClass}" 
                    onclick="${robot.connection_status === 'connected' ? 'disconnectRobot' : 'connectRobot'}('${robot.id}')"
                    ${connectBtnDisabled ? 'disabled' : ''}>
                ${connectBtnText}
            </button>
            <button class="action-btn delete" onclick="deleteRobot('${robot.id}')">删除</button>
        </div>
    `;
    
    return item;
}

// Handle add robot form submission
async function handleAddRobot(event) {
    event.preventDefault();
    
    const formData = new FormData(addRobotForm);
    const robotData = Object.fromEntries(formData);
    robotData.port = 22; // Set default SSH port
    
    // Show progress section
    progressSection.style.display = 'block';
    showProgress(0, 'Configuration initialize......');
    
    try {
        // Simulate progress steps
        await sleep(1000);
        showProgress(30, 'Configuration initialize......completed');
        await sleep(500);
        
        showProgress(60, 'Model import......');
        await sleep(1000);
        showProgress(80, 'Model import......completed');
        await sleep(500);
        
        showProgress(100, 'Device......completed');
        await sleep(500);
        
        // Test connection
        const testResponse = await fetch(`${API_BASE_URL}/robots/test-connection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(robotData)
        });
        
        if (!testResponse.ok) {
            const error = await testResponse.json();
            throw new Error(error.detail || '连接测试失败');
        }
        
        const testResult = await testResponse.json();
        
        if (!testResult.success) {
            throw new Error('无法连接到设备');
        }
        
        // Show device confirmation dialog
        addRobotModal.style.display = 'none';
        showDeviceConfirmation(robotData, testResult.device_info);
        
    } catch (error) {
        console.error('连接测试失败:', error);
        showToast('连接失败：' + error.message, 'error');
        progressSection.style.display = 'none';
    }
}

// Show progress
function showProgress(percent, message) {
    progressFill.style.width = percent + '%';
    const logElement = document.createElement('div');
    logElement.textContent = message;
    progressLogs.appendChild(logElement);
    progressLogs.scrollTop = progressLogs.scrollHeight;
}

// Show device confirmation dialog
function showDeviceConfirmation(robotData, deviceInfo) {
    // Fill device information
    document.getElementById('confirmHardwareModel').textContent = deviceInfo.hardware_model || 'Kuavo 4 pro';
    document.getElementById('confirmSoftwareVersion').textContent = deviceInfo.software_version || 'version 1.2.3';
    document.getElementById('confirmSnNumber').textContent = deviceInfo.sn_number || 'qwert3459592sfag';
    document.getElementById('confirmEndEffector').textContent = deviceInfo.end_effector_type || '夹爪手';
    
    // Store robot data for confirmation
    window.pendingRobotData = {
        ...robotData,
        ...deviceInfo
    };
    
    deviceConfirmModal.style.display = 'flex';
}

// Confirm device addition
async function confirmAddDevice() {
    if (!window.pendingRobotData) return;
    
    deviceConfirmModal.style.display = 'none';
    
    try {
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
            showToast('设备添加成功！', 'success');
            
            // Auto connect
            await connectRobot(newRobot.id);
        } else {
            const error = await response.json();
            showToast('添加失败：' + error.detail, 'error');
        }
    } catch (error) {
        console.error('添加设备失败:', error);
        showToast('添加失败：网络错误', 'error');
    } finally {
        window.pendingRobotData = null;
        closeAddRobotModal();
    }
}

// Connect robot
async function connectRobot(robotId) {
    try {
        // Update status to connecting
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
            showToast('连接失败：' + error.detail, 'error');
            await loadRobots();
        } else {
            const result = await response.json();
            if (result.status === 'connected') {
                const robotIndex = robots.findIndex(r => r.id === robotId);
                if (robotIndex !== -1) {
                    robots[robotIndex].connection_status = 'connected';
                    renderRobots();
                }
                showToast('连接成功！', 'success');
            } else {
                await loadRobots();
            }
        }
    } catch (error) {
        console.error('连接失败:', error);
        showToast('连接失败：网络错误', 'error');
        await loadRobots();
    }
}

// Disconnect robot
async function disconnectRobot(robotId) {
    try {
        const response = await fetch(`${API_BASE_URL}/robots/${robotId}/disconnect`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            showToast('断开失败：' + error.detail, 'error');
        } else {
            await loadRobots();
            showToast('设备已断开连接', 'info');
        }
    } catch (error) {
        console.error('断开失败:', error);
        showToast('断开失败：网络错误', 'error');
    }
}

// Delete robot
async function deleteRobot(robotId) {
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
            showToast('设备删除成功', 'success');
        } else {
            const error = await response.json();
            showToast('删除失败：' + error.detail, 'error');
        }
    } catch (error) {
        console.error('删除失败:', error);
        showToast('删除失败：网络错误', 'error');
    }
}

// Show robot detail
async function showRobotDetail(robotId) {
    const robot = robots.find(r => r.id === robotId);
    if (!robot) return;
    
    // Fill basic info
    const basicContent = document.getElementById('robotDetailContent');
    basicContent.innerHTML = `
        <div class="info-item">
            <span class="info-label">设备名称：</span>
            <span class="info-value">${robot.name}</span>
        </div>
        <div class="info-item">
            <span class="info-label">IP地址：</span>
            <span class="info-value">${robot.ip_address}</span>
        </div>
        <div class="info-item">
            <span class="info-label">SSH端口：</span>
            <span class="info-value">${robot.port}</span>
        </div>
        <div class="info-item">
            <span class="info-label">SSH用户：</span>
            <span class="info-value">${robot.ssh_user}</span>
        </div>
        <div class="info-item">
            <span class="info-label">硬件型号：</span>
            <span class="info-value">${robot.hardware_model || '未知'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">软件版本：</span>
            <span class="info-value">${robot.software_version || '未知'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">SN号：</span>
            <span class="info-value">${robot.sn_number || '未知'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">末端执行器：</span>
            <span class="info-value">${robot.end_effector_type || '未知'}</span>
        </div>
    `;
    
    // Fill connection info
    const connectionContent = document.getElementById('connectionInfo');
    connectionContent.innerHTML = `
        <div class="info-item">
            <span class="info-label">端口：</span>
            <span class="info-value">${robot.port}</span>
        </div>
        <div class="info-item">
            <span class="info-label">IP地址：</span>
            <span class="info-value">${robot.ip_address}</span>
        </div>
        <div class="info-item">
            <span class="info-label">连接状态：</span>
            <span class="info-value">${robot.connection_status === 'connected' ? '成功' : '断开'}</span>
        </div>
        <div class="info-item">
            <span class="info-label">xx端口：</span>
            <span class="info-value">断开</span>
        </div>
        <div class="info-item">
            <span class="info-label">电量：</span>
            <span class="info-value">断开</span>
        </div>
        <div class="info-item">
            <span class="info-label">故障码：</span>
            <span class="info-value">xxxx</span>
        </div>
    `;
    
    // Update connect button
    const connectBtn = document.getElementById('connectDeviceBtn');
    if (robot.connection_status === 'connected') {
        connectBtn.textContent = '断开';
        connectBtn.className = 'btn btn-danger';
        connectBtn.onclick = () => disconnectRobot(robotId);
    } else {
        connectBtn.textContent = '连接';
        connectBtn.className = 'btn btn-primary';
        connectBtn.onclick = () => connectRobot(robotId);
    }
    
    robotDetailModal.style.display = 'flex';
}

// Utility functions
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (document.body.contains(toast)) {
            document.body.removeChild(toast);
        }
    }, 3000);
}