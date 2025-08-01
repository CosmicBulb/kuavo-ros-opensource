// KUAVO Studio 标定界面脚本

class CalibrationManager {
    constructor() {
        this.API_BASE_URL = 'http://localhost:8001/api/v1';
        this.websocket = null;
        this.currentRobot = null;
        this.currentSession = null;
        this.currentStep = 1;
        this.currentHeadHandStep = 1;
        this.calibrationType = null;
        
        this.autoNextStepScheduled = false; // 防止重复设置定时器
        this.isLoadingConfig = false; // 防止重复加载配置
        this.lastLoggedStatus = {}; // 记录已输出的日志，避免重复
        this.isProcessingStep = false; // 防止重复处理步骤切换
        this.isCalibrationInProgress = false; // 防止多次同时启动标定
        this.currentHeadHandSessionId = null; // 当前头手标定会话ID
        
        // WebSocket重连控制
        this.reconnectTimer = null;
        this.isReconnecting = false;
        
        this.init();
        this.setupWebSocket();
    }

    init() {
        this.loadRobots();
        this.bindEvents();
        this.setupStepNavigation();
    }

    bindEvents() {
        // 设备选择
        document.getElementById('robotSelect').addEventListener('change', this.onRobotSelect.bind(this));
        
        // 标定卡片点击
        document.querySelectorAll('.calibration-card').forEach(card => {
            card.addEventListener('click', this.onCalibrationCardClick.bind(this));
        });
        
        // 选择设备按钮
        document.getElementById('selectDeviceBtn').addEventListener('click', this.startCalibration.bind(this));
        
        
        // 步骤导航按钮
        document.getElementById('nextStepBtn').addEventListener('click', this.nextStep.bind(this));
        document.getElementById('headHandNextBtn').addEventListener('click', this.nextStep.bind(this));
        
        // 头手标定步骤2按钮
        const headHandOneClickBtn = document.getElementById('headHandOneClickBtn');
        if (headHandOneClickBtn) {
            headHandOneClickBtn.addEventListener('click', this.executeHeadHandCalibration.bind(this));
        }
        
        const headHandNextToStep3 = document.getElementById('headHandNextToStep3');
        if (headHandNextToStep3) {
            headHandNextToStep3.addEventListener('click', () => this.goToHeadHandStep(3));
        }
        
        // 头手标定步骤3按钮
        const headHandSaveBtn = document.getElementById('headHandSaveBtn');
        if (headHandSaveBtn) {
            headHandSaveBtn.addEventListener('click', this.saveHeadHandCalibration.bind(this));
        }
        
        const headHandRestartBtn = document.getElementById('headHandRestartBtn');
        if (headHandRestartBtn) {
            headHandRestartBtn.addEventListener('click', this.restartHeadHandCalibration.bind(this));
        }
        
        const headHandRetryBtn = document.getElementById('headHandRetryBtn');
        if (headHandRetryBtn) {
            headHandRetryBtn.addEventListener('click', this.restartHeadHandCalibration.bind(this));
        }
        
        // 步骤3按钮 - 一键标零和关节调试
        const oneClickZeroBtn = document.getElementById('oneClickZeroBtn');
        if (oneClickZeroBtn) {
            oneClickZeroBtn.addEventListener('click', this.executeOneClickZero.bind(this));
        }
        
        const jointDebugBtn = document.getElementById('jointDebugBtn');
        if (jointDebugBtn) {
            jointDebugBtn.addEventListener('click', this.toggleJointDebugMode.bind(this));
        }
        
        const nextToStep4Btn = document.getElementById('nextToStep4Btn');
        if (nextToStep4Btn) {
            nextToStep4Btn.addEventListener('click', this.proceedToStep4.bind(this));
        }
        
        // 步骤4按钮 - 预览和保存
        const previewResultBtn = document.getElementById('previewResultBtn');
        if (previewResultBtn) {
            previewResultBtn.addEventListener('click', this.previewCalibrationResult.bind(this));
        }
        
        const confirmCompletionBtn = document.getElementById('confirmCompletionBtn');
        if (confirmCompletionBtn) {
            confirmCompletionBtn.addEventListener('click', this.saveZeroPoint.bind(this));
        }
        
        // 步骤4的重新标定按钮
        const restartCalibrationBtn = document.getElementById('restartCalibrationBtn');
        if (restartCalibrationBtn) {
            restartCalibrationBtn.addEventListener('click', this.restartCalibration.bind(this));
        }
    }

    setupWebSocket() {
        // 如果已经在重连中，直接返回
        if (this.isReconnecting) {
            console.log('WebSocket正在重连中，跳过重复连接');
            return;
        }
        
        // 清理旧的连接
        if (this.websocket) {
            this.websocket.onclose = null; // 防止触发重连
            this.websocket.close();
            this.websocket = null;
        }
        
        // 清理重连定时器
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        const wsUrl = `ws://localhost:8001/ws/calibration-client-${Date.now()}`;
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket连接已建立');
            this.isReconnecting = false;
        };

        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket连接已关闭');
            this.websocket = null;
            
            // 只在非主动关闭的情况下重连
            if (!this.isReconnecting) {
                this.isReconnecting = true;
                console.log('将在3秒后尝试重连...');
                this.reconnectTimer = setTimeout(() => {
                    this.isReconnecting = false;
                    this.setupWebSocket();
                }, 3000);
            }
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket错误:', error);
        };
    }

    handleWebSocketMessage(message) {
        console.log('收到WebSocket消息:', message);
        
        switch(message.type) {
            case 'zero_point_calibration_update':
                this.updateZeroPointCalibrationStatus(message.data);
                break;
            case 'calibration_log':
                // 支持多种WebSocket消息格式
                let log = null;
                
                // 格式1: {type: 'calibration_log', data: {log: 'content'}}
                if (message.data && message.data.log) {
                    log = message.data.log;
                }
                // 格式2: {type: 'calibration_log', session_id: '...', data: 'content'}
                else if (message.data && typeof message.data === 'string') {
                    log = message.data;
                }
                // 格式3: {type: 'calibration_log', data: 'content'}
                else if (message.data) {
                    log = message.data;
                }
                // 格式4: 直接字符串
                else if (typeof message === 'string') {
                    log = message;
                }
                
                if (log) {
                    console.log('处理标定日志:', log); // 调试日志
                    
                    // 检查是否是位置信息
                    const positionMatch = log.match(/Slave (\d+) actual position ([\d.-]+),\s*Encoder ([\d.-]+)/);
                    const currentMatch = log.match(/Rated current ([\d.-]+)/);
                    
                    if (positionMatch || currentMatch) {
                        // 这是位置数据，显示在步骤4的位置信息区域
                        this.addPositionData(log);
                        
                        // 解析并保存Slave位置数据
                        if (positionMatch) {
                            const slaveData = {
                                slave: parseInt(positionMatch[1]),
                                position: parseFloat(positionMatch[2]),
                                encoder: parseFloat(positionMatch[3])
                            };
                            if (!this.lastCalibrationData) {
                                this.lastCalibrationData = [];
                            }
                            this.lastCalibrationData[slaveData.slave - 1] = slaveData;
                        }
                    } else {
                        // 其他日志信息，显示到对应界面（包括头手标定日志）
                        this.addCalibrationLog(log);
                    }
                } else {
                    console.warn('无法解析标定日志消息:', message);
                }
                break;
            case 'calibration_status':
                this.updateCalibrationStatus(message.data);
                break;
            case 'robot_status':
                // 处理机器人状态更新
                console.log('机器人状态更新:', message.data);
                // 如果设备连接状态发生变化，刷新设备列表
                if (message.data && (message.data.status === 'disconnected' || message.data.status === 'connected')) {
                    if (message.data.status === 'disconnected') {
                        // 如果断开的是当前选中的设备，清空选择
                        if (this.currentRobot === message.data.robot_id) {
                            this.currentRobot = null;
                            document.getElementById('robotSelect').value = '';
                            this.showError('当前设备已断开连接，请重新选择设备');
                        }
                    }
                    // 刷新在线设备列表
                    setTimeout(() => this.loadRobots(), 500); // 延迟一下确保后端状态已更新
                }
                break;
            case 'head_hand_calibration_error':
                // 只处理来自当前活动会话的错误消息
                if (message.session_id === this.currentHeadHandSessionId) {
                    console.error('头手标定失败:', message.error);
                    this.isCalibrationInProgress = false; // 清除标定进行中标志
                    this.currentHeadHandSessionId = null; // 清除会话ID
                    this.showHeadHandCalibrationFailure(message.error);
                } else {
                    console.log('忽略旧会话的错误消息:', message.session_id);
                }
                break;
            case 'head_hand_calibration_complete':
                // 只处理来自当前活动会话的完成消息
                if (message.session_id === this.currentHeadHandSessionId) {
                    console.log('头手标定完成:', message);
                    this.isCalibrationInProgress = false; // 清除标定进行中标志
                    this.currentHeadHandSessionId = null; // 清除会话ID
                    this.showHeadHandCalibrationSuccess();
                } else {
                    console.log('忽略旧会话的完成消息:', message.session_id);
                }
                break;
        }
    }

    updateCalibrationStatus(data) {
        console.log('标定状态更新:', data);
        
        if (data.status === 'waiting_for_user' && data.user_prompt) {
            // 显示用户提示，但在零点标定中一般会自动处理
            this.addCalibrationLog(`用户提示: ${data.user_prompt}`);
            
            // 自动发送响应（在零点标定中通常选择继续）
            if (this.calibrationSessionId) {
                this.sendCalibrationResponse('y');
            }
        } else if (data.status === 'success') {
            this.addCalibrationLog('✅ 零点标定完成！');
            this.addCalibrationLog('标定数据已保存到配置文件');
            
            // 恢复按钮状态
            document.getElementById('startCalibrationBtn').disabled = false;
            document.getElementById('startCalibrationBtn').textContent = '🚀 开始零点标定';
            
            // 标定成功时不自动跳转，让后端控制步骤流程
            // this.nextStep();
            
            // 更新完成状态
            setTimeout(() => {
                document.getElementById('confirmCompletionBtn').disabled = false;
            }, 1000);
            
        } else if (data.status === 'failed') {
            this.addCalibrationLog(`❌ 标定失败: ${data.error_message || '未知错误'}`);
            this.showError('标定失败: ' + (data.error_message || '未知错误'));
            
            // 恢复按钮状态
            document.getElementById('startCalibrationBtn').disabled = false;
            document.getElementById('startCalibrationBtn').textContent = '🚀 开始零点标定';
            
        } else if (data.status === 'running') {
            this.addCalibrationLog('🔄 标定正在运行...');
        }
    }

    showUserPromptDialog(prompt, sessionId) {
        // 防止重复弹窗
        if (this.currentPromptDialog) {
            return;
        }
        
        // 分析提示类型
        let dialogType = 'confirm';
        let defaultResponse = 'y';
        
        if (prompt.includes("(y/N)") || prompt.includes("(y/n)")) {
            dialogType = 'confirm';
            defaultResponse = 'y';
        } else if (prompt.includes("按 'o'") || prompt.includes("press 'o'")) {
            dialogType = 'button';
            defaultResponse = 'o';
        } else if (prompt.includes("回车") || prompt.includes("Enter")) {
            dialogType = 'ok';
            defaultResponse = '\n';
        }
        
        // 创建自定义弹窗
        const dialog = document.createElement('div');
        dialog.className = 'calibration-dialog-overlay';
        dialog.innerHTML = `
            <div class="calibration-dialog">
                <div class="dialog-header">
                    <h3>标定确认</h3>
                </div>
                <div class="dialog-content">
                    <p>${prompt}</p>
                </div>
                <div class="dialog-actions">
                    ${dialogType === 'confirm' ? `
                        <button class="btn btn-secondary" onclick="window.calibrationManager.respondToPrompt('n', '${sessionId}')">否(N)</button>
                        <button class="btn btn-primary" onclick="window.calibrationManager.respondToPrompt('y', '${sessionId}')">是(Y)</button>
                    ` : dialogType === 'button' ? `
                        <button class="btn btn-primary" onclick="window.calibrationManager.respondToPrompt('${defaultResponse}', '${sessionId}')">继续(${defaultResponse.toUpperCase()})</button>
                    ` : `
                        <button class="btn btn-primary" onclick="window.calibrationManager.respondToPrompt('\\n', '${sessionId}')">确定</button>
                    `}
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        this.currentPromptDialog = dialog;
        
        // 添加键盘事件监听
        const keyHandler = (e) => {
            if (dialogType === 'confirm') {
                if (e.key === 'y' || e.key === 'Y') {
                    this.respondToPrompt('y', sessionId);
                } else if (e.key === 'n' || e.key === 'N') {
                    this.respondToPrompt('n', sessionId);
                }
            } else if (dialogType === 'button' && e.key === defaultResponse) {
                this.respondToPrompt(defaultResponse, sessionId);
            } else if (e.key === 'Enter') {
                this.respondToPrompt(defaultResponse, sessionId);
            }
        };
        
        document.addEventListener('keydown', keyHandler);
        this.currentKeyHandler = keyHandler;
    }
    
    async respondToPrompt(response, sessionId) {
        // 移除弹窗
        if (this.currentPromptDialog) {
            this.currentPromptDialog.remove();
            this.currentPromptDialog = null;
        }
        
        // 移除键盘事件监听
        if (this.currentKeyHandler) {
            document.removeEventListener('keydown', this.currentKeyHandler);
            this.currentKeyHandler = null;
        }
        
        // 发送响应到后端
        await this.sendZeroPointCalibrationResponse(response, sessionId);
    }
    
    async sendZeroPointCalibrationResponse(response, sessionId) {
        if (!sessionId) return;
        
        try {
            const url = `${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${sessionId}/user-response`;
            const result = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ response })
            });
            
            if (result.ok) {
                this.addCalibrationLog(`用户响应: ${response}`);
            } else {
                console.error('发送用户响应失败:', await result.text());
            }
        } catch (error) {
            console.error('发送标定响应失败:', error);
        }
    }
    
    async sendCalibrationResponse(response) {
        if (!this.calibrationSessionId) return;
        
        try {
            await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibrations/response`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ response })
            });
        } catch (error) {
            console.error('发送标定响应失败:', error);
        }
    }

    async loadRobots() {
        try {
            // 调用新的在线设备API，只获取已连接的设备
            const response = await fetch(`${this.API_BASE_URL}/robots/online`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            // 处理分页响应格式
            let robots = [];
            if (data.items && Array.isArray(data.items)) {
                robots = data.items;
            } else if (Array.isArray(data)) {
                // 兼容旧格式
                robots = data;
            } else {
                console.error('未知的响应格式:', data);
                throw new Error('响应格式错误');
            }
            
            const select = document.getElementById('robotSelect');
            select.innerHTML = '<option value="">请选择需要标定的设备</option>';
            
            // 只显示在线设备
            if (robots.length === 0) {
                select.innerHTML = '<option value="">暂无在线设备</option>';
                select.disabled = true;
                this.showError('暂无在线设备，请先在设备管理中连接设备');
            } else {
                select.disabled = false;
                robots.forEach(robot => {
                    const option = document.createElement('option');
                    option.value = robot.id;
                    // 添加设备类型显示
                    const deviceType = robot.device_type === 'upper' ? '上位机' : '下位机';
                    option.textContent = `${robot.name} (${robot.ip_address}) - ${deviceType}`;
                    option.dataset.status = robot.connection_status;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('加载在线设备列表失败:', error);
            this.showError('加载在线设备列表失败: ' + error.message);
            const select = document.getElementById('robotSelect');
            select.innerHTML = '<option value="">加载设备失败</option>';
            select.disabled = true;
        }
    }

    onRobotSelect(event) {
        const robotId = event.target.value;
        const selectBtn = document.getElementById('selectDeviceBtn');
        
        if (robotId) {
            this.currentRobot = robotId;
            selectBtn.disabled = false;
            selectBtn.textContent = '请先选择需要标定的机器人';
            selectBtn.classList.remove('btn-select-device');
            selectBtn.classList.add('btn', 'btn-primary');
        } else {
            this.currentRobot = null;
            selectBtn.disabled = true;
            selectBtn.textContent = '请先选择需要标定的机器人';
            selectBtn.classList.add('btn-select-device');
            selectBtn.classList.remove('btn', 'btn-primary');
        }
    }

    onCalibrationCardClick(event) {
        const card = event.currentTarget;
        const type = card.dataset.type;
        
        // 移除所有卡片的选中状态
        document.querySelectorAll('.calibration-card').forEach(c => c.classList.remove('selected'));
        
        // 选中当前卡片
        card.classList.add('selected');
        this.calibrationType = type;
        
        // 更新按钮文本
        const selectBtn = document.getElementById('selectDeviceBtn');
        if (this.currentRobot) {
            if (type === 'zero_point') {
                selectBtn.textContent = '开始零点标定';
            } else if (type === 'head_hand') {
                selectBtn.textContent = '开始头手标定';
            }
        }
    }

    async startCalibration() {
        if (!this.currentRobot || !this.calibrationType) {
            this.showError('请先选择设备和标定类型');
            return;
        }

        try {
            // 检查设备连接状态
            const robotResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}`);
            const robot = await robotResponse.json();
            
            if (robot.connection_status !== 'connected') {
                this.showError('设备未连接，请先连接设备');
                return;
            }

            // 隐藏主界面，显示对应的标定流程
            document.getElementById('calibrationMain').style.display = 'none';
            
            if (this.calibrationType === 'zero_point') {
                document.getElementById('zeroPointCalibration').style.display = 'block';
                await this.startZeroPointCalibration();
            } else if (this.calibrationType === 'head_hand') {
                document.getElementById('headHandCalibration').style.display = 'block';
                await this.startHeadHandCalibration();
            }

        } catch (error) {
            console.error('启动标定失败:', error);
            this.showError('启动标定失败: ' + error.message);
        }
    }

    async startZeroPointCalibration() {
        try {
            // 首先尝试获取当前标定状态
            const currentResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/current`);
            if (currentResponse.ok) {
                const currentSession = await currentResponse.json();
                if (currentSession && (currentSession.status === 'in_progress' || currentSession.status === 'waiting_user')) {
                    // 有正在进行的会话，询问用户是否要取消
                    const shouldCancel = confirm('检测到有正在进行的标定任务。是否要取消之前的任务并开始新的标定？');
                    if (!shouldCancel) {
                        return;
                    }
                    // 尝试取消之前的会话
                    try {
                        const cancelResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${currentSession.session_id}`, {
                            method: 'DELETE'
                        });
                        if (!cancelResponse.ok) {
                            console.warn('取消会话响应不成功:', cancelResponse.status);
                        } else {
                            console.log('成功取消之前的标定会话');
                        }
                        // 等待一下让后端清理会话
                        await new Promise(resolve => setTimeout(resolve, 500));
                    } catch (e) {
                        console.warn('取消之前的会话失败:', e);
                    }
                }
            }

            // 启动新的标定会话
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    calibration_type: 'full_body'
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentSession = data;  // 保存整个响应对象，而不仅仅是session_id
                console.log('零点标定已启动:', data);
                console.log('保存的会话对象:', this.currentSession);
                
                // 订阅WebSocket更新
                this.subscribeToUpdates();
                
                
            } else {
                const error = await response.text();
                throw new Error(error);
            }
        } catch (error) {
            console.error('启动零点标定失败:', error);
            this.showError('启动零点标定失败: ' + error.message);
        }
    }

    async startHeadHandCalibration() {
        try {
            // 检查标定配置
            await this.checkCalibrationConfig();
            
            console.log('头手标定已启动');
        } catch (error) {
            console.error('启动头手标定失败:', error);
            this.showError('启动头手标定失败: ' + error.message);
        }
    }

    async checkCalibrationConfig() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-config-check`);
            const config = await response.json();
            
            // 更新检查项状态
            this.updateConfigCheckItems(config);
            
        } catch (error) {
            console.error('检查标定配置失败:', error);
            throw error;
        }
    }

    updateConfigCheckItems(config) {
        const checkItems = document.querySelectorAll('.check-item');
        const checkStatuses = [
            config.sudo_access,
            config.environment_ready,
            config.network_connected,
            config.apriltag_available,
            config.environment_ready,
            config.apriltag_available,
            config.rosbag_files_exist
        ];
        
        checkItems.forEach((item, index) => {
            const icon = item.querySelector('.check-icon');
            if (checkStatuses[index]) {
                icon.textContent = '✅';
                icon.style.color = '#4caf50';
            } else {
                icon.textContent = '❌';
                icon.style.color = '#f44336';
            }
        });
    }

    subscribeToUpdates() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'subscribe',
                robot_id: this.currentRobot
            }));
        }
    }




    nextStep() {
        console.log('nextStep 被调用，当前标定类型:', this.calibrationType);
        if (this.calibrationType === 'zero_point') {
            this.nextZeroPointStep();
        } else if (this.calibrationType === 'head_hand') {
            this.nextHeadHandStep();
        }
    }

    nextZeroPointStep() {
        console.log('nextZeroPointStep 被调用，当前步骤:', this.currentStep, '-> 下一步:', this.currentStep + 1);
        
        // 防止重复调用
        if (this.isProcessingStep) {
            console.log('正在处理步骤切换，忽略重复调用');
            return;
        }
        this.isProcessingStep = true;
        
        // 步骤1完成后直接进入步骤2
        if (this.currentStep === 1) {
            console.log('步骤1完成，切换到步骤2');
            this.currentStep = 2;
            this.updateStepIndicator(this.currentStep);
            
            // 显示步骤2内容
            document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
            document.getElementById('step2Content').classList.add('active');
            
            // 开始加载配置
            if (!this.isLoadingConfig) {
                this.loadCurrentConfiguration();
            }
            
            this.isProcessingStep = false;
            return;
        }
        
        this.currentStep++;
        
        // 更新步骤指示器
        this.updateStepIndicator(this.currentStep);
        
        // 显示对应步骤内容
        document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
        document.getElementById(`step${this.currentStep}Content`).classList.add('active');
        
        // 根据步骤执行相应逻辑
        switch(this.currentStep) {
            case 2:
                this.loadCurrentConfiguration();
                break;
            case 3:
                this.showJointDataTable();
                break;
            case 4:
                this.showCompletionStatus();
                break;
        }
        
        // 重置处理状态
        this.isProcessingStep = false;
    }

    nextHeadHandStep() {
        if (this.currentHeadHandStep === 1) {
            this.goToHeadHandStep(2);
        } else if (this.currentHeadHandStep === 2) {
            this.goToHeadHandStep(3);
        }
    }
    
    // 头手标定步骤导航
    goToHeadHandStep(step) {
        this.currentHeadHandStep = step;
        
        // 隐藏所有步骤面板
        document.querySelectorAll('#headHandCalibration .step-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        
        // 显示对应步骤面板
        const targetPanel = document.getElementById(`headHandStep${step}`);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }
        
        // 更新步骤指示器
        this.updateHeadHandStepIndicator(step);
        
        console.log(`头手标定切换到步骤${step}`);
    }
    
    // 更新头手标定步骤指示器
    updateHeadHandStepIndicator(activeStep) {
        const steps = document.querySelectorAll('#headHandCalibration .step-item');
        steps.forEach((step, index) => {
            if (index + 1 <= activeStep) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        });
    }
    
    // 上一步（头手标定）
    goToPreviousHeadHandStep() {
        if (this.currentHeadHandStep > 1) {
            this.goToHeadHandStep(this.currentHeadHandStep - 1);
        }
    }

    updateStepIndicator(step) {
        console.log(`更新步骤指示器到步骤${step}`);
        document.querySelectorAll('.step-item').forEach((item, index) => {
            item.classList.remove('active', 'completed');
            if (index + 1 < step) {
                item.classList.add('completed');
            } else if (index + 1 === step) {
                item.classList.add('active');
            }
        });
        
        // 同时更新步骤内容面板的显示
        document.querySelectorAll('.step-panel').forEach(panel => {
            panel.classList.remove('active');
            panel.style.display = 'none';
        });
        
        const activePanel = document.getElementById(`step${step}Content`);
        if (activePanel) {
            activePanel.classList.add('active');
            activePanel.style.display = 'block';
            console.log(`步骤${step}的内容面板已显示`);
        }
    }

    async loadCurrentConfiguration() {
        // 防止重复加载
        if (this.isLoadingConfig) {
            console.log('配置正在加载中，避免重复加载');
            return;
        }
        this.isLoadingConfig = true;
        
        try {
            // 显示加载动画
            const progressFill = document.querySelector('.progress-fill');
            if (progressFill) {
                progressFill.style.animation = 'progress 3s ease-in-out forwards';
            }
            
            // 更新加载日志显示
            const loadingLogs = document.querySelector('.loading-logs');
            if (loadingLogs) {
                loadingLogs.innerHTML = `
                    <p>·sence initialize......completed</p>
                    <p>·model import......completed</p>
                    <p>·device ......connected</p>
                    <p>·loading calibration data......</p>
                `;
            }
            
            console.log('开始加载配置数据...');
            
            // 加载手臂零点数据
            const armsResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/arms_zero/data`);
            if (!armsResponse.ok) {
                throw new Error(`加载手臂数据失败: ${armsResponse.status}`);
            }
            const armsData = await armsResponse.json();
            console.log('手臂数据:', armsData);
            
            // 加载腿部偏移数据
            const legsResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/legs_offset/data`);
            if (!legsResponse.ok) {
                throw new Error(`加载腿部数据失败: ${legsResponse.status}`);
            }
            const legsData = await legsResponse.json();
            console.log('腿部数据:', legsData);
            
            // 分别存储手臂和腿部数据
            this.armJointData = [];
            this.legJointData = [];
            
            // 处理手臂数据
            if (armsData.joint_data && Array.isArray(armsData.joint_data)) {
                this.armJointData = armsData.joint_data.map(joint => ({
                    id: joint.id,
                    name: joint.name || `关节${joint.id}`,
                    current_position: joint.current_position || 0,
                    zero_position: joint.zero_position || 0,
                    offset: joint.offset || 0,
                    status: joint.status || 'normal',
                    type: joint.id >= 13 && joint.id <= 14 ? 'head' : 'arm'
                }));
            }
            
            // 处理腿部数据
            if (legsData.joint_data && Array.isArray(legsData.joint_data)) {
                this.legJointData = legsData.joint_data.map(joint => ({
                    id: joint.id,
                    name: joint.name || `关节${joint.id}`,
                    current_position: joint.current_position || 0,
                    zero_position: joint.zero_position || 0,
                    offset: joint.offset || 0,
                    status: joint.status || 'normal',
                    type: 'leg'
                }));
            }
            
            // 为了兼容性，也创建合并的jointData
            this.jointData = [...this.armJointData];
            
            console.log('合并后的关节数据:', this.jointData);
            
            // 更新加载完成日志
            if (loadingLogs) {
                loadingLogs.innerHTML = `
                    <p>·sence initialize......completed</p>
                    <p>·model import......completed</p>
                    <p>·device ......connected</p>
                    <p>·loading calibration data......completed</p>
                    <p>·data validation......completed</p>
                `;
            }
            
            // 显示加载完成的信息
            const configInfo = document.querySelector('.config-info');
            if (configInfo) {
                const totalWarnings = (armsData.warnings?.length || 0) + (legsData.warnings?.length || 0);
                configInfo.innerHTML = `
                    <p>✅ 配置加载完成</p>
                    <p>关节数量: ${this.jointData.length}</p>
                    <p>警告数量: ${totalWarnings}</p>
                    ${totalWarnings > 0 ? '<p style="color: #ff9800;">⚠️ 存在警告，请检查关节数据</p>' : '<p style="color: #4caf50;">✓ 数据验证通过</p>'}
                `;
            }
            
            // 配置加载完成后，自动跳转到步骤3
            console.log('配置加载完成，关节数据数量:', this.jointData.length);
            
            // 标记数据已加载，供步骤3使用
            this.dataLoaded = true;
            
            // 自动跳转到步骤3
            setTimeout(() => {
                if (this.currentStep === 2) {
                    console.log('步骤2配置加载完成，自动跳转到步骤3');
                    this.nextZeroPointStep();
                }
            }, 1000); // 延迟1秒让用户看到加载完成状态
            
        } catch (error) {
            console.error('加载配置失败:', error);
            
            // 更新加载失败的显示
            const loadingLogs = document.querySelector('.loading-logs');
            if (loadingLogs) {
                loadingLogs.innerHTML += `<p style="color: #f44336;">·loading failed: ${error.message}</p>`;
            }
            
            const configInfo = document.querySelector('.config-info');
            if (configInfo) {
                configInfo.innerHTML = `<p style="color: #f44336;">❌ 配置加载失败: ${error.message}</p>`;
            }
            
            this.showError('加载配置失败: ' + error.message);
        } finally {
            this.isLoadingConfig = false;
        }
    }

    async showJointDataTable() {
        console.log('显示关节数据表格，当前步骤:', this.currentStep);
        console.log('关节数据:', this.jointData);
        
        // 在显示步骤3时，确保后端状态同步为initialize_zero
        if (this.currentStep === 3 && this.currentSession) {
            try {
                console.log('更新后端步骤状态为initialize_zero...');
                const response = await fetch(
                    `${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/go-to-step`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ step: 'initialize_zero' })
                    }
                );
                
                if (response.ok) {
                    console.log('后端步骤状态已更新为initialize_zero');
                } else {
                    console.warn('更新后端步骤状态失败:', response.status);
                }
            } catch (error) {
                console.error('更新后端步骤状态时出错:', error);
            }
        }
        
        // 直接调用renderJointDataTable来渲染表格
        this.renderJointDataTable();
        
        // 检查是否有警告或错误
        if (this.jointData && this.jointData.length > 0) {
            const hasWarnings = this.jointData.some(j => j.status === 'warning');
            const hasErrors = this.jointData.some(j => j.status === 'error');
            
            if (hasErrors) {
                this.addCalibrationLog('⚠️ 检测到关节数据错误，请检查并修正');
            } else if (hasWarnings) {
                this.addCalibrationLog('⚠️ 检测到关节数据警告，建议检查数值');
            } else {
                this.addCalibrationLog('✅ 关节数据正常');
            }
        }
    }

    getStatusText(status) {
        const statusMap = {
            'normal': '正常',
            'warning': '警告',
            'error': '错误'
        };
        return statusMap[status] || status;
    }


    // 一键标零功能
    async executeOneClickZero() {
        if (!this.currentSession) {
            this.showError('没有活动的标定会话');
            return;
        }
        
        try {
            console.log('执行一键标定...');
            this.addCalibrationLog('🎯 开始执行全身零点标定...');
            
            // 禁用按钮避免重复点击
            const btn = document.getElementById('oneClickZeroBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = '正在标定...';
            }
            
            // 调用API执行全身标定 - 使用正确的roslaunch命令
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/execute-calibration`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    calibration_mode: 'full_body'
                    // 让后端使用默认的完整标定命令：cali:=true cali_leg:=true cali_arm:=true
                })
            });
            
            if (response.ok) {
                this.addCalibrationLog('✅ 全身零点标定已启动');
                // 更新关节数据表格以反映新的零点
                await this.loadCurrentConfiguration();
            } else {
                const error = await response.json();
                throw new Error(error.detail || '一键标定失败');
            }
        } catch (error) {
            console.error('一键标定失败:', error);
            this.showError('一键标定失败: ' + error.message);
        } finally {
            // 恢复按钮状态
            const btn = document.getElementById('oneClickZeroBtn');
            if (btn) {
                btn.disabled = false;
                btn.textContent = '一键标定';
            }
        }
    }
    
    // 关节调试 - 发送ROS命令
    async toggleJointDebugMode() {
        console.log('执行关节调试...');
        
        try {
            // 检查是否在标定模式下
            if (!this.currentSession) {
                throw new Error('请先执行"一键标零"启动标定程序');
            }
            
            const jointDebugBtn = document.getElementById('jointDebugBtn');
            if (jointDebugBtn) {
                jointDebugBtn.disabled = true;
                jointDebugBtn.textContent = '执行中...';
            }
            
            // 只获取被修改的关节参数
            const modifiedInputs = document.querySelectorAll('.joint-zero-input[data-modified="true"]');
            
            if (modifiedInputs.length === 0) {
                throw new Error('没有修改任何关节参数');
            }
            
            // 构建请求数据 - 只包含被修改的关节
            const modifiedJoints = [];
            modifiedInputs.forEach(input => {
                const jointId = parseInt(input.dataset.jointId);
                const jointName = input.dataset.jointName;
                const position = parseFloat(input.value);
                
                // 从jointData中找到对应的关节信息
                const joint = this.jointData.find(j => j.id === jointId);
                if (joint) {
                    modifiedJoints.push({
                        id: jointId,
                        name: joint.name,
                        position: position
                    });
                }
            });
            
            if (modifiedJoints.length === 0) {
                throw new Error('没有找到有效的关节数据');
            }
            
            const requestData = {
                joints: modifiedJoints
            };
            
            console.log('发送关节调试命令:', requestData);
            console.log('当前会话信息:', this.currentSession);
            this.addCalibrationLog(`🔧 执行关节调试，调整 ${modifiedJoints.length} 个关节: ${modifiedJoints.map(j => `${j.name}=${j.position.toFixed(4)}`).join(', ')}`);
            
            // 获取session_id
            const sessionId = typeof this.currentSession === 'string' ? this.currentSession : this.currentSession?.session_id;
            
            if (!sessionId) {
                console.error('当前会话:', this.currentSession);
                throw new Error('未找到标定会话ID');
            }
            
            console.log('使用的session_id:', sessionId);
            
            // 调用后端API执行ROS命令
            const response = await fetch(
                `${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${sessionId}/joint-debug`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                }
            );
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '执行关节调试命令失败');
            }
            
            const result = await response.json();
            console.log('关节调试命令执行成功:', result);
            
            this.addCalibrationLog('✅ 关节调试命令执行成功');
            if (result.command_executed) {
                this.addCalibrationLog(`💡 执行的命令: rostopic pub -1 /kuavo_arm_traj ...`);
            }
            
            // 显示成功提示
            this.showSuccess('关节调试命令已发送，机器人正在移动到目标位置');
            
        } catch (error) {
            console.error('关节调试失败:', error);
            this.addCalibrationLog(`❌ 关节调试失败: ${error.message}`);
            this.showError('关节调试失败: ' + error.message);
        } finally {
            const jointDebugBtn = document.getElementById('jointDebugBtn');
            if (jointDebugBtn) {
                jointDebugBtn.disabled = false;
                jointDebugBtn.textContent = '关节调试';
            }
        }
    }
    
    // 执行头手标定（一键标零）
    async executeHeadHandCalibration() {
        // 防止多次同时启动
        if (this.isCalibrationInProgress) {
            console.log('头手标定已在进行中，忽略重复请求');
            return;
        }
        
        try {
            this.isCalibrationInProgress = true;
            console.log('开始执行头手标定...');
            
            // 禁用按钮
            const btn = document.getElementById('headHandOneClickBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = '执行中...';
            }
            
            // 显示进度区域
            const progressDiv = document.getElementById('headHandProgress');
            if (progressDiv) {
                progressDiv.style.display = 'block';
            }
            
            // 清空初始的静态日志内容，准备显示实时日志
            const logOutput = document.getElementById('headHandLogOutput');
            if (logOutput) {
                logOutput.innerHTML = '';
            }
            
            // 确保标定类型设置正确，以便日志正确路由
            this.calibrationType = 'head_hand';
            console.log('头手标定开始，标定类型设置为:', this.calibrationType);
            
            // 启动头手标定脚本执行
            await this.startHeadHandCalibrationScript();
            
        } catch (error) {
            console.error('头手标定执行失败:', error);
            this.currentHeadHandSessionId = null; // 清除会话ID
            this.showHeadHandCalibrationFailure('头手标定执行失败: ' + error.message);
        } finally {
            // 清除标定进行中标志
            this.isCalibrationInProgress = false;
            
            // 恢复按钮状态
            const btn = document.getElementById('headHandOneClickBtn');
            if (btn) {
                btn.disabled = false;
                btn.textContent = '一键标零';
            }
        }
    }
    
    // 启动头手标定脚本
    async startHeadHandCalibrationScript() {
        try {
            // 首先检查是否有正在进行的标定任务
            const currentResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibrations/current`);
            if (currentResponse.ok) {
                const currentSession = await currentResponse.json();
                if (currentSession && (currentSession.status === 'running' || currentSession.status === 'waiting_for_user')) {
                    // 有正在进行的会话，询问用户是否要取消
                    const shouldCancel = confirm('检测到有正在进行的标定任务。是否要取消之前的任务并开始新的头手标定？');
                    if (!shouldCancel) {
                        return;
                    }
                    // 尝试取消之前的会话
                    try {
                        // 清除旧的会话ID，避免收到旧会话的消息
                        this.currentHeadHandSessionId = null;
                        
                        // 首先尝试停止当前标定
                        const cancelResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibrations/current`, {
                            method: 'DELETE'
                        });
                        if (!cancelResponse.ok) {
                            console.warn('取消标定会话响应不成功:', cancelResponse.status);
                            
                            // 如果失败，尝试清理所有会话
                            console.log('尝试清理所有标定会话...');
                            const cleanupResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibrations/sessions`, {
                                method: 'DELETE'
                            });
                            if (cleanupResponse.ok) {
                                console.log('成功清理所有标定会话');
                            } else {
                                console.warn('清理会话也失败了:', cleanupResponse.status);
                            }
                        } else {
                            console.log('成功取消之前的标定会话');
                        }
                        // 等待较长时间让后端彻底清理会话
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    } catch (e) {
                        console.warn('取消之前的会话失败:', e);
                    }
                }
            }

            // 调用后端API执行One_button_start.sh脚本
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/head-hand-calibration`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    calibration_type: 'head_hand',
                    script_path: './scripts/joint_cali/One_button_start.sh'
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('头手标定脚本启动成功:', data);
                
                // 保存当前头手标定会话ID
                this.currentHeadHandSessionId = data.session_id;
                console.log('当前头手标定会话ID:', this.currentHeadHandSessionId);
                
                // 订阅WebSocket更新以接收脚本执行状态
                this.subscribeToUpdates();
                
            } else {
                const error = await response.json();
                throw new Error(error.detail || '启动头手标定脚本失败');
            }
            
        } catch (error) {
            console.error('启动头手标定脚本失败:', error);
            this.currentHeadHandSessionId = null; // 清除会话ID
            throw error;
        }
    }
    
    // 模拟头手标定过程
    simulateHeadHandCalibrationProcess() {
        const logOutput = document.getElementById('headHandLogOutput');
        const progressBar = document.getElementById('headHandProgressBar');
        
        const logs = [
            '检查虚拟环境和配置文件...',
            '✓ 虚拟环境存在',
            '✓ 头部标定配置文件存在',
            '当前头部标定配置：',
            'apriltag_id: 0',
            'apriltag_size: 0.088',
            'camera_topic: /camera/color/image_raw',
            '',
            '启动机器人控制系统...',
            '✓ 机器人控制系统已在后台启动',
            '等待系统初始化...',
            '',
            '开始头部标定...',
            '激活虚拟环境和设置环境...',
            '环境设置完成，开始头部标定...',
            'python3 ./scripts/joint_cali/head_cali.py --use_cali_tool',
            '',
            '启动相机节点...',
            '启动AprilTag识别系统...',
            '✓ 上位机AprilTag识别系统启动完成',
            '',
            '执行头部标定流程...',
            '正在收集标定数据...',
            '检测到AprilTag (ID: 0)',
            '收集头部位姿数据 1/10',
            '收集头部位姿数据 5/10',
            '收集头部位姿数据 10/10',
            '✓ 头部标定数据收集完成',
            '',
            '开始手臂标定...',
            '启用机器人移动功能...',
            '启用头部追踪...',
            '执行手臂示教运动...',
            '播放左手rosbag文件...',
            '播放右手rosbag文件...',
            '收集AprilTag位姿数据...',
            '过滤噪声数据...',
            '执行标定算法计算关节偏置...',
            '',
            '✓ 头部标定脚本执行完成',
            '✓ 手臂标定执行完成',
            '发现标定备份文件，头部标定已完成',
            '备份文件: /home/lab/.config/lejuconfig/arms_zero.yaml.head_cali.bak',
            '',
            '🎉 所有标定完成！'
        ];
        
        let logIndex = 0;
        let progress = 0;
        
        const logInterval = setInterval(() => {
            if (logIndex < logs.length) {
                // 添加日志
                if (logOutput) {
                    const logLine = document.createElement('p');
                    logLine.textContent = logs[logIndex];
                    logOutput.appendChild(logLine);
                    logOutput.scrollTop = logOutput.scrollHeight;
                }
                
                // 更新进度条
                progress = ((logIndex + 1) / logs.length) * 100;
                if (progressBar) {
                    progressBar.style.width = progress + '%';
                }
                
                logIndex++;
            } else {
                clearInterval(logInterval);
                
                // 标定完成，启用下一步按钮
                setTimeout(() => {
                    this.onHeadHandCalibrationComplete(true);
                }, 1000);
            }
        }, 800);
    }
    
    // 头手标定完成处理
    onHeadHandCalibrationComplete(success) {
        console.log('头手标定完成，成功:', success);
        
        // 恢复按钮状态
        const btn = document.getElementById('headHandOneClickBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = '一键标零';
        }
        
        // 启用下一步按钮
        const nextBtn = document.getElementById('headHandNextToStep3');
        if (nextBtn) {
            nextBtn.disabled = false;
        }
        
        if (success) {
            // 成功时自动进入步骤3并显示成功状态
            setTimeout(() => {
                this.goToHeadHandStep(3);
                this.showHeadHandSuccess();
            }, 2000);
        } else {
            // 失败时显示错误状态
            this.goToHeadHandStep(3);
            this.showHeadHandError('头手标定执行失败');
        }
    }
    
    // 显示头手标定成功状态
    showHeadHandSuccess() {
        const successResult = document.getElementById('headHandSuccessResult');
        const errorResult = document.getElementById('headHandErrorResult');
        
        if (successResult) successResult.style.display = 'block';
        if (errorResult) errorResult.style.display = 'none';
    }
    
    // 显示头手标定错误状态
    showHeadHandError(message) {
        const successResult = document.getElementById('headHandSuccessResult');
        const errorResult = document.getElementById('headHandErrorResult');
        
        if (successResult) successResult.style.display = 'none';
        if (errorResult) errorResult.style.display = 'block';
        
        console.error('头手标定错误:', message);
    }
    
    // 显示头手标定失败结果（在结果界面中显示）
    showHeadHandCalibrationFailure(errorMessage) {
        // 导航到头手标定结果步骤（步骤3）
        this.goToHeadHandStep(3);
        
        // 显示错误结果界面
        this.showHeadHandError(errorMessage);
        
        // 可选：在错误信息中显示具体的错误内容
        const errorResultDiv = document.getElementById('headHandErrorResult');
        if (errorResultDiv && errorMessage) {
            const errorMessageElement = errorResultDiv.querySelector('.error-message');
            if (errorMessageElement) {
                errorMessageElement.textContent = errorMessage;
            } else {
                // 如果没有专门的错误信息元素，可以在标题下方添加错误详情
                const titleElement = errorResultDiv.querySelector('h2');
                if (titleElement && !titleElement.nextElementSibling?.classList.contains('error-details')) {
                    const errorDetails = document.createElement('div');
                    errorDetails.className = 'error-details';
                    errorDetails.style.cssText = 'color: #dc3545; margin-bottom: 20px; font-size: 14px; word-wrap: break-word;';
                    errorDetails.textContent = errorMessage;
                    titleElement.parentNode.insertBefore(errorDetails, titleElement.nextSibling);
                }
            }
        }
        
        console.log('头手标定失败，显示在结果界面中:', errorMessage);
    }
    
    // 显示头手标定成功结果（在结果界面中显示）
    showHeadHandCalibrationSuccess() {
        // 导航到头手标定结果步骤（步骤3）
        this.goToHeadHandStep(3);
        
        // 显示成功结果界面
        this.showHeadHandSuccess();
        
        console.log('头手标定成功，显示在结果界面中');
    }
    
    // 保存头手标定结果
    async saveHeadHandCalibration() {
        try {
            console.log('保存头手标定结果...');
            
            // 调用后端API保存标定结果
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/head-hand-calibration/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                this.showSuccess('头手标定结果保存成功！');
                setTimeout(() => {
                    this.goBackToMain();
                }, 2000);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '保存头手标定结果失败');
            }
            
        } catch (error) {
            console.error('保存头手标定结果失败:', error);
            this.showError('保存头手标定结果失败: ' + error.message);
        }
    }
    
    // 重新开始头手标定
    restartHeadHandCalibration() {
        // 防止在标定进行中重启
        if (this.isCalibrationInProgress) {
            console.log('标定正在进行中，不能重启');
            return;
        }
        
        console.log('重新开始头手标定...');
        
        // 清除标定进行中状态，允许重新开始
        this.isCalibrationInProgress = false;
        
        // 清除会话ID
        this.currentHeadHandSessionId = null;
        
        // 重置状态
        this.currentHeadHandStep = 1;
        
        // 清除日志
        const logOutput = document.getElementById('headHandLogOutput');
        if (logOutput) {
            logOutput.innerHTML = `
                <p>·sence initialize......completed</p>
                <p>·model import......completed</p>  
                <p>·device .......</p>
            `;
        }
        
        // 重置进度条
        const progressBar = document.getElementById('headHandProgressBar');
        if (progressBar) {
            progressBar.style.width = '0%';
        }
        
        // 隐藏进度区域
        const progressDiv = document.getElementById('headHandProgress');
        if (progressDiv) {
            progressDiv.style.display = 'none';
        }
        
        // 重置按钮状态
        const btn = document.getElementById('headHandOneClickBtn');
        if (btn) {
            btn.disabled = false;
            btn.textContent = '一键标零';
        }
        
        const nextBtn = document.getElementById('headHandNextToStep3');
        if (nextBtn) {
            nextBtn.disabled = true;
        }
        
        // 回到步骤2
        this.goToHeadHandStep(2);
        
        this.showSuccess('已重置头手标定，可以重新开始');
    }
    
    // 刷新关节数据 - 从后端获取当前关节信息
    async refreshJointData() {
        try {
            console.log('正在刷新关节数据...');
            
            // 重新加载配置数据
            await this.loadCurrentConfiguration();
            
            console.log('关节数据刷新完成');
            this.addCalibrationLog('📖 关节数据已更新');
            
        } catch (error) {
            console.error('刷新关节数据失败:', error);
            this.addCalibrationLog('⚠️ 刷新关节数据失败: ' + error.message);
            // 如果读取失败，加载默认的关节数据结构
            this.loadDefaultJointData();
        }
    }
    
    
    // 渲染关节数据表格 - 新的紧凑布局
    renderJointDataTable() {
        const tableBody = document.querySelector('#jointTable tbody');
        if (!tableBody || !this.armJointData) return;
        
        tableBody.innerHTML = '';
        
        // 创建手臂关节映射
        const armJointMap = {};
        if (this.armJointData) {
            this.armJointData.forEach(joint => {
                armJointMap[joint.id] = joint;
            });
        }
        
        // 创建腿部关节映射
        const legJointMap = {};
        if (this.legJointData) {
            this.legJointData.forEach(joint => {
                legJointMap[joint.id] = joint;
            });
        }
        
        // 按照6行布局创建表格
        for (let i = 1; i <= 6; i++) {
            const row = document.createElement('tr');
            
            // 左臂关节 (ID: i)
            const leftArmJoint = armJointMap[i] || { name: `左臂 ${String(i).padStart(2, '0')}`, zero_position: 0 };
            
            // 右臂关节 (ID: i+6)
            const rightArmJoint = armJointMap[i + 6] || { name: `右臂 ${String(i).padStart(2, '0')}`, zero_position: 0 };
            
            // 左腿关节 (腿部数据也是从ID 1-6)
            const leftLegJoint = legJointMap[i] || { name: `左腿 ${String(i).padStart(2, '0')}`, zero_position: 0 };
            
            // 右腿关节 (腿部数据ID 7-12)
            const rightLegJoint = legJointMap[i + 6] || { name: `右腿 ${String(i).padStart(2, '0')}`, zero_position: 0 };
            
            // 头部关节 (只有前两行)
            let headJoint = null;
            let headValue = 'x.xxx';
            if (i === 1) {
                headJoint = armJointMap[13]; // 头部01 (yaw)
                headValue = headJoint ? headJoint.zero_position.toFixed(3) : 'x.xxx';
            } else if (i === 2) {
                headJoint = armJointMap[14]; // 头部02 (pitch)
                headValue = headJoint ? headJoint.zero_position.toFixed(3) : 'x.xxx';
            }
            
            // 特殊处理最后一列
            let lastColumnLabel = '';
            let lastColumnValue = 'x.xxx';
            let lastColumnJoint = null;
            
            if (i === 1) {
                lastColumnLabel = '头部01 (yaw)';
                lastColumnJoint = headJoint;
                lastColumnValue = headValue;
            } else if (i === 2) {
                lastColumnLabel = '头部02 (pitch)';
                lastColumnJoint = headJoint;
                lastColumnValue = headValue;
            } else if (i === 3) {
                lastColumnLabel = '左肩部';
                lastColumnJoint = legJointMap[13];
                if (lastColumnJoint) {
                    lastColumnValue = lastColumnJoint.zero_position.toFixed(3);
                }
            } else if (i === 4) {
                lastColumnLabel = '右肩部';
                lastColumnJoint = legJointMap[14];
                if (lastColumnJoint) {
                    lastColumnValue = lastColumnJoint.zero_position.toFixed(3);
                }
            } else {
                lastColumnLabel = '';
                lastColumnValue = '';
            }
            
            row.innerHTML = `
                <td style="font-size: 12px;">左臂 ${String(i).padStart(2, '0')}</td>
                <td>
                    <input type="number" 
                           class="joint-input joint-zero-input" 
                           value="${leftArmJoint.zero_position.toFixed(3)}" 
                           step="0.001" 
                           data-joint-id="${i}"
                           data-joint-name="${leftArmJoint.name}"
                           data-original-value="${leftArmJoint.zero_position.toFixed(4)}"
                           style="width: 60px; padding: 2px 4px; text-align: right; font-size: 12px;">
                </td>
                <td style="font-size: 12px;">右臂 ${String(i).padStart(2, '0')}</td>
                <td>
                    <input type="number" 
                           class="joint-input joint-zero-input" 
                           value="${rightArmJoint.zero_position.toFixed(3)}" 
                           step="0.001" 
                           data-joint-id="${i + 6}"
                           data-joint-name="${rightArmJoint.name}"
                           data-original-value="${rightArmJoint.zero_position.toFixed(4)}"
                           style="width: 60px; padding: 2px 4px; text-align: right; font-size: 12px;">
                </td>
                <td style="font-size: 12px;">左腿 ${String(i).padStart(2, '0')}</td>
                <td style="color: #999; font-size: 12px;">${leftLegJoint.zero_position !== undefined ? leftLegJoint.zero_position.toFixed(3) : 'x.xxx'}</td>
                <td style="font-size: 12px;">右腿 ${String(i).padStart(2, '0')}</td>
                <td style="color: #999; font-size: 12px;">${rightLegJoint.zero_position !== undefined ? rightLegJoint.zero_position.toFixed(3) : 'x.xxx'}</td>
                <td style="font-size: 12px;">${lastColumnLabel}</td>
                <td style="font-size: 12px;">
                    ${i <= 2 && headJoint ? 
                        `<input type="number" 
                               class="joint-input joint-zero-input" 
                               value="${parseFloat(headValue).toFixed(3)}" 
                               step="0.001" 
                               data-joint-id="${headJoint.id}"
                               data-joint-name="${headJoint.name}"
                               data-original-value="${headValue}"
                               style="width: 60px; padding: 2px 4px; text-align: right; font-size: 12px;">` 
                        : (lastColumnValue !== '' ? `<span style="color: #999;">${lastColumnValue}</span>` : '')}
                </td>
            `;
            
            tableBody.appendChild(row);
        }
        
        // 添加事件监听器
        const inputs = tableBody.querySelectorAll('.joint-zero-input');
        inputs.forEach(input => {
            // 标记原始值，用于识别哪些值被修改了
            input.addEventListener('input', (e) => {
                const originalValue = parseFloat(e.target.dataset.originalValue);
                const currentValue = parseFloat(e.target.value);
                
                // 如果值改变了，添加修改标记
                if (Math.abs(originalValue - currentValue) > 0.0001) {
                    e.target.style.backgroundColor = '#ffffcc'; // 黄色背景表示已修改
                    e.target.dataset.modified = 'true';
                } else {
                    e.target.style.backgroundColor = '#fff';
                    e.target.dataset.modified = 'false';
                }
                
                this.onJointValueChange(e);
            });
        });
    }
    
    // 关节值改变事件处理
    onJointValueChange(event) {
        const input = event.target;
        const jointId = parseInt(input.dataset.jointId);
        const value = parseFloat(input.value);
        const originalValue = parseFloat(input.dataset.originalValue);
        
        // 更新内存中的数据
        const joint = this.jointData.find(j => j.id === jointId);
        if (joint) {
            joint.zero_position = value;
            
            // 计算修改量（偏移值）
            const offset = value - originalValue;
            
            // 检查修改量是否超出建议范围
            if (Math.abs(offset) > 0.05) {
                const warningMsg = `⚠️ ${joint.name} 修改量 ${offset.toFixed(4)} 超过建议值(±0.05)`;
                console.warn(warningMsg);
                // 可以显示一个临时提示，但不阻止修改
                this.showTemporaryWarning(warningMsg);
            }
            
            console.log(`关节 ${joint.name} 的值从 ${originalValue} 修改为 ${value}，变化量: ${offset.toFixed(4)}`);
        }
    }
    
    // 显示临时警告
    showTemporaryWarning(message) {
        // 查找或创建警告提示元素
        let warningDiv = document.getElementById('tempWarning');
        if (!warningDiv) {
            warningDiv = document.createElement('div');
            warningDiv.id = 'tempWarning';
            warningDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #ff9800;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                z-index: 10000;
                font-size: 14px;
            `;
            document.body.appendChild(warningDiv);
        }
        
        warningDiv.textContent = message;
        warningDiv.style.display = 'block';
        
        // 3秒后自动隐藏
        setTimeout(() => {
            warningDiv.style.display = 'none';
        }, 3000);
    }
    
    // 获取状态文本
    getStatusText(status) {
        switch (status) {
            case 'warning': return '警告';
            case 'error': return '错误';
            default: return '正常';
        }
    }
    
    // 加载默认关节数据（当读取失败时）
    loadDefaultJointData() {
        console.log('加载默认关节数据结构');
        
        // 创建默认的关节数据结构
        this.jointData = [];
        
        // 添加手臂关节
        const armJoints = [
            '左臂01', '左臂02', '左臂03', '左臂04', '左臂05', '左臂06',
            '右臂01', '右臂02', '右臂03', '右臂04', '右臂05', '右臂06'
        ];
        
        armJoints.forEach((name, index) => {
            this.jointData.push({
                id: index + 1,
                name: name,
                current_position: 0.0,
                zero_position: 0.0,
                offset: 0.0,
                status: 'normal',
                type: 'arm'
            });
        });
        
        // 添加头部关节
        ['头部01', '头部02'].forEach((name, index) => {
            this.jointData.push({
                id: this.jointData.length + 1,
                name: name,
                current_position: 0.0,
                zero_position: 0.0,
                offset: 0.0,
                status: 'normal',
                type: 'head'
            });
        });
        
        // 添加腿部关节
        const legJoints = [
            '左腿01', '左腿02', '左腿03', '左腿04', '左腿05', '左腿06',
            '右腿01', '右腿02', '右腿03', '右腿04', '右腿05', '右腿06'
        ];
        
        legJoints.forEach((name, index) => {
            this.jointData.push({
                id: this.jointData.length + 1,
                name: name,
                current_position: 0.0,
                zero_position: 0.0,
                offset: 0.0,
                status: 'normal',
                type: 'leg'
            });
        });
        
        // 渲染表格
        this.renderJointDataTable();
    }
    
    // 进入步骤4
    async proceedToStep4() {
        try {
            // 保存修改的关节数据
            if (this.jointData) {
                await this.saveJointData();
            }
            
            // 直接跳转到步骤4显示结果，不启动新的标定
            // 标定应该在步骤3通过"一键标定"按钮启动
            console.log('跳转到步骤4显示结果');
            this.currentStep = 4;
            this.updateStepIndicator(4);
            document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
            document.getElementById('step4Content').classList.add('active');
            
        } catch (error) {
            console.error('进入步骤4失败:', error);
            this.showError('进入步骤4失败: ' + error.message);
        }
    }
    
    // 保存零点
    // 重新标定 - 回到步骤3
    restartCalibration() {
        console.log('重新标定，回到步骤3');
        
        // 清空位置数据缓存
        this.cachedPositionData = [];
        
        // 清空状态缓存
        this.lastLoggedStatus = {};
        
        // 跳转到步骤3
        this.currentStep = 3;
        this.updateStepIndicator(3);
        
        // 显示对应步骤内容
        document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
        document.getElementById('step3Content').classList.add('active');
        
        // 重新加载配置数据
        this.loadCurrentConfiguration();
        
        // 显示提示
        this.showSuccess('已返回步骤3，可以重新进行标定');
    }
    
    async saveZeroPoint() {
        if (!this.currentSession) {
            this.showError('没有活动的标定会话');
            return;
        }
        
        try {
            console.log('保存零点数据...');
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/save-zero-point`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                this.addCalibrationLog('✅ 零点数据已保存到配置文件');
                this.showSuccess('零点数据保存成功！');
                setTimeout(() => {
                    this.goBackToMain();
                }, 2000);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '保存零点失败');
            }
        } catch (error) {
            console.error('保存零点失败:', error);
            this.showError('保存零点失败: ' + error.message);
        }
    }
    
    async startActualCalibration() {
        try {
            // 保存修改的关节数据
            if (this.jointData) {
                await this.saveJointData();
            }
            
            // 点击开始标定按钮后，先禁用按钮
            document.getElementById('startCalibrationBtn').disabled = true;
            document.getElementById('startCalibrationBtn').textContent = '标定进行中...';
            
            // 调用新的开始执行API
            await this.startCalibrationExecution();
            
            // 不要自动跳转到步骤4，等待后端通知
            // 标定会在步骤4执行，后端会控制何时进入步骤4
            
        } catch (error) {
            console.error('开始标定失败:', error);
            this.showError('开始标定失败: ' + error.message);
            // 恢复按钮状态
            document.getElementById('startCalibrationBtn').disabled = false;
            document.getElementById('startCalibrationBtn').textContent = '🚀 开始零点标定';
        }
    }

    async startCalibrationExecution() {
        // 此函数已弃用，现在使用 executeOneClickZero() 来启动标定
        // 为了避免重复启动标定，这里只是简单返回
        console.log('startCalibrationExecution 已弃用，请使用 executeOneClickZero');
        return;
    }


    async startRealZeroPointCalibration() {
        try {
            console.log('启动真实的零点标定流程...');
            
            // 调用后端API启动零点标定 - 使用专用的零点标定API
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    calibration_type: 'full_body'
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.calibrationSessionId = data.session_id;
                console.log('零点标定会话已启动:', data);
                
                // 订阅WebSocket更新
                this.subscribeToCalibrationUpdates();
                
                // 显示标定开始消息
                this.addCalibrationLog('零点标定已启动，等待标定脚本执行...');
                
            } else {
                const error = await response.json();
                throw new Error(error.detail || '启动标定失败');
            }
        } catch (error) {
            console.error('启动真实标定失败:', error);
            this.showError('启动标定失败: ' + error.message);
        }
    }

    subscribeToCalibrationUpdates() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'subscribe',
                robot_id: this.currentRobot
            }));
        }
    }

    addCalibrationLog(message) {
        // 步骤4现在不显示日志，而是显示位置信息
        // 如果需要显示日志，使用console.log
        console.log('标定日志:', message);
        
        // 如果是头手标定，也显示到头手标定界面
        if (this.calibrationType === 'head_hand') {
            this.addHeadHandCalibrationLog(message);
        }
    }
    
    // 添加头手标定日志到界面
    addHeadHandCalibrationLog(message) {
        const logOutput = document.getElementById('headHandLogOutput');
        if (logOutput) {
            console.log('添加头手标定日志到UI:', message); // 调试日志
            
            // 处理多行消息
            const lines = message.split('\n');
            
            lines.forEach(line => {
                if (line.trim()) { // 只处理非空行
                    // 创建新的日志行
                    const logLine = document.createElement('p');
                    logLine.textContent = line.trim();
                    logLine.style.margin = '2px 0';
                    logLine.style.fontSize = '12px';
                    logLine.style.color = '#e0e0e0';
                    
                    // 根据日志内容添加颜色
                    if (line.includes('✓') || line.includes('完成')) {
                        logLine.style.color = '#4caf50'; // 绿色表示成功
                    } else if (line.includes('步骤') || line.includes('===')) {
                        logLine.style.color = '#2196f3'; // 蓝色表示步骤
                    } else if (line.includes('标定中') || line.includes('采集数据')) {
                        logLine.style.color = '#ff9800'; // 橙色表示进行中
                    }
                    
                    // 添加到日志输出区域
                    logOutput.appendChild(logLine);
                }
            });
            
            // 滚动到底部
            const parentContainer = logOutput.parentElement;
            if (parentContainer) {
                parentContainer.scrollTop = parentContainer.scrollHeight;
            }
        } else {
            console.warn('找不到headHandLogOutput元素');
        }
    }
    
    addPositionData(message) {
        // 缓存位置数据，无论当前在哪个步骤
        if (!this.cachedPositionData) {
            this.cachedPositionData = [];
        }
        
        // 避免重复添加相同的数据
        if (!this.cachedPositionData.includes(message.trim())) {
            this.cachedPositionData.push(message.trim());
        }
        
        // 如果当前在步骤4，立即显示位置数据
        if (this.currentStep === 4) {
            this.displayPositionData();
        }
    }
    
    displayPositionData() {
        // 显示所有缓存的位置数据到步骤4
        const positionDataOutput = document.querySelector('#step4Content .position-data-output');
        if (positionDataOutput && this.cachedPositionData) {
            // 清空现有内容，然后显示所有缓存的数据
            positionDataOutput.innerHTML = this.cachedPositionData.join('\n') + '\n';
            positionDataOutput.scrollTop = positionDataOutput.scrollHeight;
        }
    }

    addCalibrationLogToStep3(message) {
        // 在步骤3的控制台输出
        const step3ConsoleOutput = document.querySelector('#step3Content .console-output');
        if (step3ConsoleOutput) {
            step3ConsoleOutput.innerHTML += message + '\n';
            step3ConsoleOutput.scrollTop = step3ConsoleOutput.scrollHeight;
        }
    }

    async saveJointData() {
        if (!this.jointData || this.jointData.length === 0) {
            console.log('没有关节数据需要保存');
            return;
        }
        
        try {
            console.log('正在保存关节数据...');
            
            // 分别获取手臂、头部和腿部数据
            const armAndHeadData = this.armJointData || this.jointData.filter(j => j.type === 'arm' || j.type === 'head');
            const legData = this.legJointData || [];
            
            // 保存手臂和头部数据到 arms_zero.yaml
            if (armAndHeadData.length > 0) {
                const armsPayload = {
                    joint_data: armAndHeadData.map(joint => ({
                        id: joint.id,
                        name: joint.name,
                        current_position: joint.current_position || 0.0,
                        zero_position: joint.zero_position || 0.0,
                        offset: joint.offset || 0.0,
                        status: joint.status || 'normal'
                    }))
                };
                
                console.log('保存手臂和头部数据:', armsPayload);
                const armsResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/arms_zero/data`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(armsPayload)
                });
                
                if (!armsResponse.ok) {
                    const errorText = await armsResponse.text();
                    let errorDetail = armsResponse.statusText;
                    try {
                        const errorJson = JSON.parse(errorText);
                        errorDetail = errorJson.detail || errorDetail;
                    } catch (e) {
                        errorDetail = errorText || errorDetail;
                    }
                    throw new Error(`保存手臂数据失败: ${errorDetail}`);
                }
                
                console.log('手臂和头部数据保存成功');
            }
            
            // 保存腿部数据到 offset.csv
            if (legData && legData.length > 0) {
                const legPayload = {
                    joint_data: legData.map(joint => ({
                        id: joint.id,
                        name: joint.name,
                        current_position: joint.current_position || 0.0,
                        zero_position: joint.zero_position || 0.0,
                        offset: joint.offset || 0.0,
                        status: joint.status || 'normal'
                    }))
                };
                
                console.log('保存腿部数据:', legPayload);
                const legResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/legs_offset/data`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(legPayload)
                });
                
                if (!legResponse.ok) {
                    const errorText = await legResponse.text();
                    let errorDetail = legResponse.statusText;
                    try {
                        const errorJson = JSON.parse(errorText);
                        errorDetail = errorJson.detail || errorDetail;
                    } catch (e) {
                        errorDetail = errorText || errorDetail;
                    }
                    throw new Error(`保存腿部数据失败: ${errorDetail}`);
                }
                
                console.log('腿部数据保存成功');
            }
            
            console.log('所有关节数据保存完成');
            
        } catch (error) {
            console.error('保存关节数据失败:', error);
            throw error;
        }
    }

    simulateCalibrationProcess() {
        const consoleOutput = document.querySelector('.console-output');
        const logs = [
            '启动机器人控制系统...',
            '检查机器人状态...',
            '使能电机...',
            '读取当前关节位置...',
            'Slave 1 actual position 9.6946716,Encoder 63535.0000000',
            'Slave 2 actual position 3.9207458,Encoder 14275.0000000',
            '计算零点偏移...',
            '应用零点设置...',
            '验证零点准确性...',
            '保存标定数据到 ~/.config/lejuconfig/offset.csv...',
            '标定数据保存成功！',
            '零点标定完成！'
        ];
        
        let logIndex = 0;
        const logInterval = setInterval(() => {
            if (logIndex < logs.length) {
                consoleOutput.innerHTML += logs[logIndex] + '\n';
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                logIndex++;
            } else {
                clearInterval(logInterval);
            }
        }, 500);
    }

    showCompletionStatus() {
        // 显示完成状态
        console.log('标定完成');
    }
    
    async previewCalibrationResult() {
        console.log('预览标定结果...');
        
        // 获取标定后的位置信息
        const calibrationData = this.lastCalibrationData || [];
        
        if (calibrationData.length === 0 && (!this.jointData || this.jointData.length === 0)) {
            this.showError('没有可预览的标定数据');
            return;
        }
        
        // 创建预览弹窗
        const dialog = document.createElement('div');
        dialog.className = 'calibration-dialog-overlay';
        dialog.innerHTML = `
            <div class="calibration-dialog" style="max-width: 900px;">
                <div class="dialog-header">
                    <h3>标定结果确认</h3>
                </div>
                <div class="dialog-content" style="max-height: 500px; overflow-y: auto;">
                    <h4 style="margin-bottom: 15px;">完成后打印出位置信息作确认：</h4>
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; font-family: monospace; font-size: 13px; line-height: 1.6;">
                        ${calibrationData.length > 0 ? calibrationData.map((item, idx) => 
                            `Slave ${idx + 1} actual position ${item.position.toFixed(6)}, Encoder ${item.encoder.toFixed(7)}`
                        ).join('<br>') : this.jointData.map((joint, idx) => 
                            `Slave ${idx + 1} actual position ${joint.current_position.toFixed(6)}, Encoder ${(joint.current_position * 6553.5).toFixed(7)}`
                        ).join('<br>')}
                    </div>
                    <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                        <p style="margin: 0; color: #856404;">
                            <strong>⚠️ 注意：</strong>点击"确认预览"后执行 <code>roslaunch humanoid_controllers load_kuavo_real.launch</code> 
                            进行零点标定的机器人验证（运行后会直接缩腿）
                        </p>
                        <p style="margin: 10px 0 0 0; color: #856404;">
                            请关注好机器人围档环境，以免跌倒！
                        </p>
                    </div>
                </div>
                <div class="dialog-actions">
                    <button class="btn btn-secondary" onclick="this.parentElement.parentElement.parentElement.remove();">取消</button>
                    <button class="btn btn-primary" onclick="window.calibrationManager.executePreviewValidation(this);">确认预览</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
    }
    
    async executePreviewValidation(button) {
        // 关闭弹窗
        const dialog = button.closest('.calibration-dialog-overlay');
        if (dialog) {
            dialog.remove();
        }
        
        // 执行验证命令
        try {
            this.addCalibrationLog('🚀 执行机器人验证: roslaunch humanoid_controllers load_kuavo_real.launch');
            this.addCalibrationLog('⚠️ 注意：机器人将进行缩腿动作，请确保周围环境安全！');
            
            // 调用API执行验证
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                this.addCalibrationLog('✅ 验证命令已发送');
            } else {
                const error = await response.json();
                throw new Error(error.detail || '执行验证失败');
            }
        } catch (error) {
            console.error('执行验证失败:', error);
            this.showError('执行验证失败: ' + error.message);
        }
    }

    async completeCalibration() {
        try {
            if (this.currentSession) {
                // 如果有会话，确认完成
                const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/confirm-tools-removed`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    this.showSuccess('标定完成！');
                    setTimeout(() => this.goBackToMain(), 2000);
                } else {
                    const error = await response.text();
                    throw new Error(error);
                }
            } else {
                this.goBackToMain();
            }
        } catch (error) {
            console.error('完成标定失败:', error);
            this.showError('完成标定失败: ' + error.message);
        }
    }

    switchCalibrationOption(option) {
        document.querySelectorAll('.option-buttons .btn').forEach(btn => btn.classList.remove('active'));
        
        if (option === 'full_body') {
            document.getElementById('fullBodyBtn').classList.add('active');
        } else {
            document.getElementById('jointTestBtn').classList.add('active');
        }
    }

    setupStepNavigation() {
        // 设置步骤导航逻辑
    }

    getBackendStepName(frontendStep) {
        const stepMap = {
            1: 'confirm_tools',
            2: 'read_config', 
            3: 'initialize_zero',
            4: 'remove_tools'
        };
        return stepMap[frontendStep];
    }

    syncStepWithBackend(backendStep) {
        const stepMap = {
            'confirm_tools': 1,
            'read_config': 2,
            'initialize_zero': 3,
            'remove_tools': 4
        };
        
        const targetStep = stepMap[backendStep];
        if (targetStep && targetStep !== this.currentStep) {
            console.log(`同步步骤: 从${this.currentStep}到${targetStep}`);
            
            // 记录之前的步骤
            const previousStep = this.currentStep;
            this.currentStep = targetStep;
            this.updateStepIndicator(this.currentStep);
            
            // 显示对应步骤内容
            document.querySelectorAll('.step-panel').forEach(panel => {
                panel.classList.remove('active');
                panel.style.display = 'none';
            });
            const targetPanel = document.getElementById(`step${this.currentStep}Content`);
            if (targetPanel) {
                targetPanel.classList.add('active');
                targetPanel.style.display = 'block';
                console.log(`显示步骤${this.currentStep}的内容面板`);
            } else {
                console.error(`找不到步骤${this.currentStep}的内容面板`);
            }
            
            // 执行步骤相关逻辑
            switch(this.currentStep) {
                case 2:
                    // 步骤2: 加载配置，加载完成后后端会自动进入步骤3
                    console.log('进入步骤2，开始加载配置...');
                    // 清空之前的数据
                    this.jointData = [];
                    this.dataLoaded = false;
                    // 显示加载界面
                    const progressFill = document.querySelector('.progress-fill');
                    if (progressFill) {
                        progressFill.style.animation = 'none';
                        setTimeout(() => {
                            progressFill.style.animation = 'progress 3s ease-in-out forwards';
                        }, 10);
                    }
                    // 不要在这里调用loadCurrentConfiguration，让后端控制加载流程
                    // 后端会在加载完成后自动进入步骤3
                    break;
                case 3:
                    // 步骤3: 显示关节数据表格
                    // 由于后端会从步骤2自动跳转到步骤3，此时数据应该已经加载完成
                    console.log('进入步骤3，当前关节数据:', this.jointData?.length, '数据加载状态:', this.dataLoaded);
                    if (this.jointData && this.jointData.length > 0) {
                        console.log('步骤3：数据已准备好，直接显示');
                        this.showJointDataTable();
                    } else if (this.dataLoaded) {
                        // 数据标记为已加载但jointData为空，可能是异步问题
                        console.log('步骤3：等待数据同步...');
                        setTimeout(() => {
                            if (this.jointData && this.jointData.length > 0) {
                                console.log('数据已同步，显示关节表格');
                                this.showJointDataTable();
                            }
                        }, 100);
                    } else {
                        // 数据还没开始加载或正在加载中
                        console.log('步骤3：数据未准备好，等待加载完成...');
                        // 设置一个检查器，等待数据加载完成
                        const checkDataInterval = setInterval(() => {
                            if (this.dataLoaded && this.jointData && this.jointData.length > 0) {
                                console.log('数据加载完成，显示关节表格');
                                this.showJointDataTable();
                                clearInterval(checkDataInterval);
                            }
                        }, 200);
                        // 最多等待3秒
                        setTimeout(() => clearInterval(checkDataInterval), 3000);
                    }
                    // 步骤3显示一键标零按钮
                    const setZeroBtn = document.getElementById('setZeroBtn');
                    const startCalibrationBtn = document.getElementById('startCalibrationBtn');
                    if (setZeroBtn) {
                        setZeroBtn.style.display = 'inline-block';
                    }
                    if (startCalibrationBtn) {
                        startCalibrationBtn.textContent = '下一步';
                    }
                    
                    // 确保步骤3内容区域可见
                    const step3Panel = document.getElementById('step3Content');
                    if (step3Panel) {
                        // 强制显示步骤3面板
                        step3Panel.style.display = 'block';
                        step3Panel.classList.add('active');
                        // 隐藏步骤2面板
                        const step2Panel = document.getElementById('step2Content');
                        if (step2Panel) {
                            step2Panel.style.display = 'none';
                            step2Panel.classList.remove('active');
                        }
                    }
                    break;
                case 4:
                    this.showCompletionStatus();
                    // 显示缓存的位置数据
                    setTimeout(() => {
                        this.displayPositionData();
                    }, 100);
                    break;
            }
        }
    }

    updateZeroPointCalibrationStatus(data) {
        console.log('零点标定状态更新:', data);
        
        // 更新会话信息，保持对象结构
        if (data.session_id) {
            if (typeof this.currentSession === 'object' && this.currentSession !== null) {
                // 如果currentSession是对象，更新其属性
                this.currentSession.session_id = data.session_id;
                this.currentSession.current_step = data.current_step;
                this.currentSession.status = data.status;
            } else {
                // 如果currentSession不是对象，创建新对象
                this.currentSession = {
                    session_id: data.session_id,
                    current_step: data.current_step,
                    status: data.status
                };
            }
        }
        
        // 先根据后端步骤同步前端步骤
        if (data.current_step && data.current_step !== this.getBackendStepName(this.currentStep)) {
            this.syncStepWithBackend(data.current_step);
        }
        
        // 处理步骤2的配置加载数据
        if (data.current_step === 'read_config' && data.step_progress && data.step_progress.config_loaded) {
            // 步骤2配置已加载，更新关节数据
            if (data.joint_data_count > 0) {
                console.log('步骤2：配置已加载，准备接收关节数据');
                // 在步骤2时加载数据，为步骤3做准备
                if (this.currentStep === 2 && (!this.jointData || this.jointData.length === 0)) {
                    if (!this.isLoadingConfig) {
                        console.log('步骤2：开始加载关节数据');
                        this.loadCurrentConfiguration();
                    }
                }
            }
        }
        
        // 处理步骤3的关节数据
        if (data.current_step === 'initialize_zero' && data.step_progress && data.step_progress.ready_to_calibrate) {
            // 如果还没有关节数据，需要加载
            if (this.currentStep === 3 && (!this.jointData || this.jointData.length === 0)) {
                console.log('步骤3：需要加载关节数据');
                // 检查是否已经在加载中
                if (!this.isLoadingConfig && !this.dataLoaded) {
                    this.loadCurrentConfiguration();
                }
            }
        }
        
        // 处理步骤进度更新
        if (data.step_progress) {
            // 如果标定已开始，根据当前步骤处理
            if (data.step_progress.calibration_started && !this.lastLoggedStatus.calibration_started) {
                if (this.currentStep === 3) {
                    // 在步骤3启动标定时，准备跳转到步骤4
                    console.log('标定已启动，准备跳转到步骤4显示位置信息');
                } else if (this.currentStep === 4) {
                    this.addCalibrationLog('🚀 零点标定开始执行...');
                    this.addCalibrationLog('正在启动标定程序...');
                }
                this.lastLoggedStatus.calibration_started = true;
            }
            
            // 如果标定完成，自动跳转到步骤4显示位置信息
            if (data.step_progress.calibration_completed && this.currentStep === 3) {
                console.log('标定完成，自动跳转到步骤4');
                // 跳转到步骤4显示位置信息（不启动新的标定）
                this.currentStep = 4;
                this.updateStepIndicator(4);
                document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
                document.getElementById('step4Content').classList.add('active');
                
                // 显示缓存的位置数据
                setTimeout(() => {
                    this.displayPositionData();
                }, 500); // 稍微延迟确保DOM更新完成
            }
            
            // 如果有脚本ID，说明模拟器脚本已启动
            if (data.step_progress.script_id && !this.lastLoggedStatus[data.step_progress.script_id]) {
                if (this.currentStep === 4) {
                    this.addCalibrationLog('标定脚本已启动: ' + data.step_progress.script_id);
                }
                this.lastLoggedStatus[data.step_progress.script_id] = true;
            }
        }
        
        // 处理不同状态
        if (data.status === 'waiting_user' && data.step_progress && data.step_progress.user_prompt) {
            // 在步骤3或4时显示用户确认弹窗
            if (this.currentStep === 3 || this.currentStep === 4) {
                this.showUserPromptDialog(data.step_progress.user_prompt, data.session_id);
                // 根据步骤决定日志输出位置
                if (this.currentStep === 4) {
                    this.addCalibrationLog(`等待用户输入: ${data.step_progress.user_prompt}`);
                }
            }
        } else if (data.status === 'in_progress') {
            // 标定进行中
            if (this.currentStep === 4 && data.step_progress && data.step_progress.calibration_started && !this.lastLoggedStatus.in_progress) {
                this.addCalibrationLog('🔄 标定正在进行中...');
                this.lastLoggedStatus.in_progress = true;
            }
        } else if (data.status === 'completed') {
            this.addCalibrationLog('✅ 零点标定完成！');
            this.addCalibrationLog('标定数据已保存到配置文件');
            
            // 恢复按钮状态
            const startBtn = document.getElementById('startCalibrationBtn');
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.textContent = '🚀 开始零点标定';
            }
            
            // 显示完成状态
            const completionStatus = document.getElementById('completionStatus');
            if (completionStatus) {
                completionStatus.style.display = 'block';
            }
            
            // 启用完成按钮
            setTimeout(() => {
                const confirmBtn = document.getElementById('confirmCompletionBtn');
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                }
            }, 1000);
            
        } else if (data.status === 'failed') {
            this.addCalibrationLog(`❌ 标定失败: ${data.error_message || '未知错误'}`);
            this.showError('标定失败: ' + (data.error_message || '未知错误'));
            
            // 恢复按钮状态
            const startBtn = document.getElementById('startCalibrationBtn');
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.textContent = '🚀 开始零点标定';
            }
        }
    }


    updateCalibrationStatus(data) {
        console.log('标定状态更新:', data);
        
        // 处理头手标定成功状态
        if (data.calibration_type === 'head_hand' && data.status === 'success') {
            // 只处理来自当前活动会话的成功消息
            if (data.session_id === this.currentHeadHandSessionId) {
                console.log('头手标定成功，准备跳转到结果页面');
                this.isCalibrationInProgress = false;
                this.currentHeadHandSessionId = null;
                
                // 跳转到头手标定成功结果页面
                this.showHeadHandCalibrationSuccess();
            } else {
                console.log('忽略旧会话的成功消息:', data.session_id, '当前会话ID:', this.currentHeadHandSessionId);
            }
        }
    }

    goBackToMain() {
        // 隐藏所有标定流程界面
        document.getElementById('zeroPointCalibration').style.display = 'none';
        document.getElementById('headHandCalibration').style.display = 'none';
        
        // 显示主界面
        document.getElementById('calibrationMain').style.display = 'block';
        
        // 重置状态
        this.currentSession = null;
        this.currentStep = 1;
        this.calibrationType = null;
        this.lastLoggedStatus = {}; // 重置日志状态
        this.isProcessingStep = false; // 重置步骤处理状态
        
        // 清除选中状态
        document.querySelectorAll('.calibration-card').forEach(card => card.classList.remove('selected'));
        
        // 更新按钮
        const selectBtn = document.getElementById('selectDeviceBtn');
        selectBtn.textContent = '请先选择需要标定的机器人';
    }

    async goToPreviousStep() {
        if (this.currentStep > 1) {
            const targetStep = this.currentStep - 1;
            
            // 如果有活动会话且返回到步骤2，需要通知后端重新进入步骤2
            if (this.currentSession && targetStep === 2) {
                try {
                    // 调用后端API返回到步骤2
                    const response = await fetch(
                        `${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession.session_id}/go-to-step`,
                        {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ step: 'read_config' })
                        }
                    );
                    
                    if (!response.ok) {
                        throw new Error('返回步骤2失败');
                    }
                    
                    // 不要手动更新UI，等待后端通过WebSocket更新状态
                    console.log('已发送返回步骤2的请求，等待后端更新...');
                    
                    // 清空配置信息，准备重新加载
                    const configInfo = document.querySelector('.config-info');
                    if (configInfo) {
                        configInfo.innerHTML = '<p>正在重新加载配置...</p>';
                    }
                    
                } catch (error) {
                    console.error('返回上一步失败:', error);
                    this.showError('返回上一步失败: ' + error.message);
                }
            } else {
                // 其他步骤直接切换
                this.currentStep = targetStep;
                this.updateStepIndicator(this.currentStep);
                document.querySelectorAll('.step-panel').forEach(panel => panel.classList.remove('active'));
                document.getElementById(`step${this.currentStep}Content`).classList.add('active');
            }
        }
    }

    showError(message) {
        // 如果是会话冲突错误，提供重置选项
        if (message.includes('已有正在进行的零点标定任务')) {
            const resetChoice = confirm('错误: ' + message + '\n\n是否要清理之前的标定会话并重新开始？');
            if (resetChoice) {
                this.resetCalibrationSessions();
            }
        } else {
            // 简单的错误提示，可以用更好看的弹窗替代
            alert('错误: ' + message);
        }
    }

    async resetCalibrationSessions() {
        if (!this.currentRobot) return;
        
        try {
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibrations/sessions`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                const result = await response.json();
                alert('成功: ' + result.message);
                console.log('标定会话已重置');
            } else {
                const error = await response.json();
                alert('重置失败: ' + error.detail);
            }
        } catch (error) {
            console.error('重置标定会话失败:', error);
            alert('重置失败: ' + error.message);
        }
    }

    showSuccess(message) {
        // 简单的成功提示
        alert('成功: ' + message);
    }
}

// 全局函数
function goBackToMain() {
    window.calibrationManager.goBackToMain();
}

function goToPreviousStep() {
    window.calibrationManager.goToPreviousStep();
}

function goToPreviousHeadHandStep() {
    window.calibrationManager.goToPreviousHeadHandStep();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.calibrationManager = new CalibrationManager();
});

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    if (window.calibrationManager) {
        // 清理WebSocket连接
        if (window.calibrationManager.websocket) {
            window.calibrationManager.websocket.onclose = null;
            window.calibrationManager.websocket.close();
        }
        
        // 清理重连定时器
        if (window.calibrationManager.reconnectTimer) {
            clearTimeout(window.calibrationManager.reconnectTimer);
        }
    }
});

// 添加CSS样式
const style = document.createElement('style');
style.textContent = `
    .joint-input {
        width: 80px;
        padding: 4px 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 12px;
        text-align: center;
    }
    
    .joint-input:focus {
        outline: none;
        border-color: #1976d2;
        box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.1);
    }
    
    .loading-indicator {
        animation: fadeIn 0.3s ease;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .step-panel {
        animation: slideIn 0.3s ease;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(30px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    .calibration-dialog-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    }
    
    .calibration-dialog {
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        min-width: 400px;
        max-width: 500px;
        animation: dialogSlideIn 0.3s ease;
    }
    
    .calibration-dialog .dialog-header {
        padding: 20px;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .calibration-dialog .dialog-header h3 {
        margin: 0;
        font-size: 18px;
        color: #333;
    }
    
    .calibration-dialog .dialog-content {
        padding: 20px;
        font-size: 14px;
        color: #666;
        line-height: 1.6;
    }
    
    .calibration-dialog .dialog-actions {
        padding: 15px 20px;
        border-top: 1px solid #e0e0e0;
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }
    
    @keyframes dialogSlideIn {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);