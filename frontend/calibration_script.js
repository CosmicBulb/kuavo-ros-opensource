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
        
        // 工具确认状态
        this.toolsConfirmed = [false, false, false, false];
        this.autoNextStepScheduled = false; // 防止重复设置定时器
        this.isLoadingConfig = false; // 防止重复加载配置
        this.lastLoggedStatus = {}; // 记录已输出的日志，避免重复
        
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
        
        // 工具确认按钮
        document.querySelectorAll('.tool-confirm-btn').forEach((btn, index) => {
            btn.addEventListener('click', () => this.confirmTool(index));
        });
        
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
        const wsUrl = `ws://localhost:8001/ws/calibration-client-${Date.now()}`;
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket连接已建立');
        };

        this.websocket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket连接已关闭');
            // 尝试重连
            setTimeout(() => this.setupWebSocket(), 3000);
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
                if (message.data && message.data.log) {
                    const log = message.data.log;
                    
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
                        // 其他日志信息，只在控制台显示
                        this.addCalibrationLog(log);
                    }
                }
                break;
            case 'calibration_status':
                this.updateCalibrationStatus(message.data);
                break;
            case 'robot_status':
                // 处理机器人状态更新
                console.log('机器人状态更新:', message.data);
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
            const response = await fetch(`${this.API_BASE_URL}/robots`);
            const robots = await response.json();
            
            const select = document.getElementById('robotSelect');
            select.innerHTML = '<option value="">请选择需要标定的设备</option>';
            
            robots.forEach(robot => {
                const option = document.createElement('option');
                option.value = robot.id;
                option.textContent = `${robot.name} (${robot.ip_address})`;
                option.dataset.status = robot.connection_status;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('加载设备列表失败:', error);
            this.showError('加载设备列表失败');
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
                this.currentSession = data.session_id;
                console.log('零点标定已启动:', data);
                
                // 订阅WebSocket更新
                this.subscribeToUpdates();
                
                // 重置工具确认状态
                this.toolsConfirmed = [false, false, false, false];
                this.updateToolConfirmButtons();
                
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

    async confirmTool(toolIndex) {
        if (!this.currentSession) return;

        try {
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/confirm-tool`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tool_index: toolIndex
                })
            });

            if (response.ok) {
                this.toolsConfirmed[toolIndex] = true;
                this.updateToolConfirmButtons();
                this.checkAllToolsConfirmed();
            } else {
                const error = await response.text();
                console.error('工具确认失败:', error);
            }
        } catch (error) {
            console.error('工具确认请求失败:', error);
        }
    }

    updateToolConfirmButtons() {
        document.querySelectorAll('.tool-confirm-btn').forEach((btn, index) => {
            if (this.toolsConfirmed[index]) {
                btn.textContent = '已确认';
                btn.disabled = true;
                btn.parentElement.classList.add('confirmed');
            }
        });
    }

    checkAllToolsConfirmed() {
        const allConfirmed = this.toolsConfirmed.every(confirmed => confirmed);
        document.getElementById('nextStepBtn').disabled = !allConfirmed;
        
        // 步骤1完成后，后端会自动进入步骤2和步骤3
        // 前端不需要主动调用nextStep，而是等待后端状态更新
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
        console.trace('调用栈'); // 打印调用栈
        
        // 如果是从步骤1进入步骤2，不要立即跳转，让后端控制流程
        if (this.currentStep === 1) {
            // 步骤1完成后，由后端控制进入步骤2并自动加载配置
            // 前端只需要等待后端的状态更新
            console.log('步骤1完成，等待后端处理...');
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
            
            // 合并数据 - 确保每个关节都有有效数据
            this.jointData = [];
            
            // 处理手臂数据
            if (armsData.joint_data && Array.isArray(armsData.joint_data)) {
                armsData.joint_data.forEach(joint => {
                    this.jointData.push({
                        id: joint.id,
                        name: joint.name || `关节${joint.id}`,
                        current_position: joint.current_position || 0,
                        zero_position: joint.zero_position || 0,
                        offset: joint.offset || 0,
                        status: joint.status || 'normal'
                    });
                });
            }
            
            // 处理腿部数据
            if (legsData.joint_data && Array.isArray(legsData.joint_data)) {
                legsData.joint_data.forEach(joint => {
                    // 避免重复ID
                    if (!this.jointData.find(j => j.id === joint.id)) {
                        this.jointData.push({
                            id: joint.id,
                            name: joint.name || `关节${joint.id}`,
                            current_position: joint.current_position || 0,
                            zero_position: joint.zero_position || 0,
                            offset: joint.offset || 0,
                            status: joint.status || 'normal'
                        });
                    }
                });
            }
            
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
            
            // 步骤2完成后，由于后端会自动进入步骤3，这里不需要额外操作
            // 只需要确保数据已经加载完成
            console.log('配置加载完成，关节数据数量:', this.jointData.length);
            
            // 标记数据已加载，供步骤3使用
            this.dataLoaded = true;
            
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

    showJointDataTable() {
        console.log('显示关节数据表格，当前步骤:', this.currentStep);
        console.log('关节数据:', this.jointData);
        
        const tbody = document.querySelector('#jointTable tbody');
        if (!tbody) {
            console.error('找不到关节数据表格tbody元素');
            return;
        }
        
        tbody.innerHTML = '';
        
        if (this.jointData && this.jointData.length > 0) {
            // 显示所有关节数据（手臂14个）
            const displayJoints = this.jointData;
            console.log('显示的关节数据:', displayJoints);
            console.log('关节数据数量:', displayJoints.length);
            
            displayJoints.forEach((joint, index) => {
                const row = document.createElement('tr');
                // 确保数值存在且为数字，否则使用默认值0
                const currentPos = (typeof joint.current_position === 'number' && !isNaN(joint.current_position)) ? joint.current_position : 0;
                const zeroPos = (typeof joint.zero_position === 'number' && !isNaN(joint.zero_position)) ? joint.zero_position : 0;
                const offset = (typeof joint.offset === 'number' && !isNaN(joint.offset)) ? joint.offset : 0;
                
                // 根据关节状态设置行样式
                if (joint.status === 'warning') {
                    row.style.backgroundColor = '#fff8e1';
                } else if (joint.status === 'error') {
                    row.style.backgroundColor = '#ffebee';
                }
                
                // 使用序号作为显示的关节编号（1-14）
                const displayId = index + 1;
                
                row.innerHTML = `
                    <td>${joint.name || `关节${displayId}`}</td>
                    <td>${currentPos.toFixed(3)}</td>
                    <td><input type="number" value="${zeroPos.toFixed(3)}" step="0.001" class="joint-input" data-joint-id="${joint.id}" data-field="zero_position"></td>
                    <td><input type="number" value="${offset.toFixed(3)}" step="0.001" class="joint-input" data-joint-id="${joint.id}" data-field="offset"></td>
                    <td><span class="joint-status ${joint.status || 'normal'}">${this.getStatusText(joint.status || 'normal')}</span></td>
                `;
                tbody.appendChild(row);
            });
            
            // 绑定输入事件
            document.querySelectorAll('.joint-input').forEach(input => {
                input.addEventListener('change', this.onJointDataChange.bind(this));
                input.addEventListener('focus', (e) => {
                    e.target.select(); // 聚焦时选中所有文本
                });
            });
            
            console.log(`成功显示 ${displayJoints.length} 个关节数据`);
            
            // 检查是否有警告或错误
            const hasWarnings = displayJoints.some(j => j.status === 'warning');
            const hasErrors = displayJoints.some(j => j.status === 'error');
            
            if (hasErrors) {
                this.addCalibrationLog('⚠️ 检测到关节数据错误，请检查并修正');
            } else if (hasWarnings) {
                this.addCalibrationLog('⚠️ 检测到关节数据警告，建议检查数值');
            } else {
                this.addCalibrationLog('✅ 关节数据正常');
            }
        } else {
            console.warn('没有关节数据可显示');
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px;">正在加载关节数据...</td></tr>';
            
            // 如果没有数据，可能需要重新加载
            if (!this.jointData || this.jointData.length === 0) {
                console.log('关节数据为空，尝试重新加载...');
                // 不要重复加载，只需要等待数据加载完成
                if (!this.isLoadingConfig) {
                    this.loadCurrentConfiguration();
                }
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

    onJointDataChange(event) {
        const input = event.target;
        const jointId = parseInt(input.dataset.jointId);
        const field = input.dataset.field;
        const value = parseFloat(input.value);
        
        // 更新本地数据
        const joint = this.jointData.find(j => j.id === jointId);
        if (joint) {
            joint[field] = value;
        }
        
        console.log(`关节${jointId}的${field}更新为:`, value);
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
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/execute-calibration`, {
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
    
    // 切换关节调试模式
    async toggleJointDebugMode() {
        if (this.isInDebugMode) {
            await this.exitJointDebugMode();
        } else {
            await this.enterJointDebugMode();
        }
    }
    
    // 关节调试模式
    async enterJointDebugMode() {
        console.log('进入关节调试模式...');
        this.addCalibrationLog('🔧 进入关节调试模式');
        
        try {
            // 先获取最新的关节数据
            await this.refreshJointData();
            
            // 启用关节数据表格的编辑功能
            const inputs = document.querySelectorAll('.joint-input');
            inputs.forEach(input => {
                input.disabled = false;
                input.style.backgroundColor = '#fff';
            });
            
            // 修改按钮状态
            const btn = document.getElementById('jointDebugBtn');
            if (btn) {
                btn.textContent = '退出调试';
                btn.classList.remove('btn-info');
                btn.classList.add('btn-warning');
            }
            
            this.isInDebugMode = true;
            this.addCalibrationLog('✅ 关节调试模式已启用，可以修改关节参数');
            
        } catch (error) {
            console.error('启动关节调试模式失败:', error);
            this.showError('启动关节调试模式失败: ' + error.message);
        }
    }
    
    // 退出关节调试模式
    async exitJointDebugMode() {
        console.log('退出关节调试模式...');
        
        try {
            // 保存修改的数据
            if (this.jointData && this.jointData.length > 0) {
                await this.saveJointData();
                this.addCalibrationLog('✅ 关节调试完成，数据已保存');
            }
        } catch (error) {
            console.error('保存关节数据失败:', error);
            this.addCalibrationLog('❌ 保存关节数据失败: ' + error.message);
            this.showError('保存关节数据失败: ' + error.message);
        }
        
        // 禁用表格编辑
        const inputs = document.querySelectorAll('.joint-input');
        inputs.forEach(input => {
            input.disabled = true;
            input.style.backgroundColor = '#f5f5f5';
        });
        
        // 恢复按钮状态
        const btn = document.getElementById('jointDebugBtn');
        if (btn) {
            btn.textContent = '关节调试';
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-info');
        }
        
        this.isInDebugMode = false;
    }
    
    // 执行头手标定（一键标零）
    async executeHeadHandCalibration() {
        try {
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
            
            // 启动头手标定脚本执行
            await this.startHeadHandCalibrationScript();
            
        } catch (error) {
            console.error('头手标定执行失败:', error);
            this.showHeadHandError('头手标定执行失败: ' + error.message);
        }
    }
    
    // 启动头手标定脚本
    async startHeadHandCalibrationScript() {
        try {
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
                
                // 实际应该通过WebSocket获取实时进度，这里暂时用模拟
                this.simulateHeadHandCalibrationProcess();
                
            } else {
                const error = await response.json();
                throw new Error(error.detail || '启动头手标定脚本失败');
            }
            
        } catch (error) {
            console.error('启动头手标定脚本失败:', error);
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
        console.log('重新开始头手标定...');
        
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
            console.log('正在读取关节数据...');
            
            // 读取当前关节配置文件数据（arms_zero.yaml 和 offset.csv）
            const [armsResponse, legsResponse] = await Promise.all([
                fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/arms_zero/data`),
                fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/legs_offset/data`)
            ]);
            
            if (!armsResponse.ok || !legsResponse.ok) {
                throw new Error('读取关节配置文件失败');
            }
            
            const armsData = await armsResponse.json();
            const legsData = await legsResponse.json();
            
            // 更新关节数据表格
            this.updateJointDataTable(armsData, legsData);
            
            console.log('关节数据读取完成');
            this.addCalibrationLog('📖 关节数据已更新');
            
        } catch (error) {
            console.error('读取关节数据失败:', error);
            this.addCalibrationLog('⚠️ 读取关节数据失败: ' + error.message);
            // 如果读取失败，加载默认的关节数据结构
            this.loadDefaultJointData();
        }
    }
    
    // 更新关节数据表格
    updateJointDataTable(armsData, legsData) {
        const tableBody = document.querySelector('#jointTable tbody');
        if (!tableBody) return;
        
        // 清空现有数据
        tableBody.innerHTML = '';
        
        // 创建关节数据数组
        this.jointData = [];
        
        // 添加手臂关节数据
        if (armsData && armsData.joints) {
            Object.entries(armsData.joints).forEach(([jointName, jointInfo]) => {
                this.jointData.push({
                    id: this.jointData.length + 1,
                    name: jointName,
                    current_position: jointInfo.current_position || 0.0,
                    zero_position: jointInfo.zero_position || 0.0,
                    offset: jointInfo.offset || 0.0,
                    status: 'normal',
                    type: 'arm'
                });
            });
        }
        
        // 添加腿部关节数据
        if (legsData && legsData.offsets) {
            legsData.offsets.forEach((offset, index) => {
                this.jointData.push({
                    id: this.jointData.length + 1,
                    name: `腿部${String(index + 1).padStart(2, '0')}`,
                    current_position: 0.0, // 腿部数据中可能没有当前位置
                    zero_position: 0.0,
                    offset: offset,
                    status: 'normal',
                    type: 'leg'
                });
            });
        }
        
        // 渲染表格
        this.renderJointDataTable();
    }
    
    // 渲染关节数据表格
    renderJointDataTable() {
        const tableBody = document.querySelector('#jointTable tbody');
        if (!tableBody || !this.jointData) return;
        
        tableBody.innerHTML = '';
        
        this.jointData.forEach(joint => {
            const row = document.createElement('tr');
            
            // 状态颜色
            const statusClass = joint.status === 'warning' ? 'warning' : 
                               joint.status === 'error' ? 'error' : 'normal';
            
            row.innerHTML = `
                <td>${joint.name}</td>
                <td>${joint.current_position.toFixed(6)}</td>
                <td>${joint.zero_position.toFixed(6)}</td>
                <td>
                    <input type="number" 
                           class="joint-input" 
                           value="${joint.offset.toFixed(6)}" 
                           step="0.01" 
                           min="-180" 
                           max="180" 
                           data-joint-id="${joint.id}"
                           disabled
                           style="background-color: #f5f5f5; border: 1px solid #ddd; padding: 4px; width: 100px;">
                </td>
                <td><span class="status-indicator ${statusClass}">${this.getStatusText(joint.status)}</span></td>
            `;
            
            tableBody.appendChild(row);
        });
        
        // 添加输入框变化监听器
        this.addJointInputListeners();
    }
    
    // 添加关节输入框监听器
    addJointInputListeners() {
        const inputs = document.querySelectorAll('.joint-input');
        inputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const jointId = parseInt(e.target.dataset.jointId);
                const newValue = parseFloat(e.target.value);
                
                // 更新内存中的数据
                const joint = this.jointData.find(j => j.id === jointId);
                if (joint) {
                    joint.offset = newValue;
                    
                    // 检查修改幅度警告
                    if (Math.abs(newValue) > 0.05) {
                        joint.status = 'warning';
                        this.addCalibrationLog(`⚠️ ${joint.name} 偏移量 ${newValue.toFixed(6)} 超过建议值(0.05)`);
                    } else {
                        joint.status = 'normal';
                    }
                    
                    // 更新状态显示
                    const row = e.target.closest('tr');
                    const statusSpan = row.querySelector('.status-indicator');
                    statusSpan.className = `status-indicator ${joint.status}`;
                    statusSpan.textContent = this.getStatusText(joint.status);
                }
            });
        });
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
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/save-zero-point`, {
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
            
            // 分别过滤手臂、头部和腿部数据
            const armAndHeadData = this.jointData.filter(j => j.type === 'arm' || j.type === 'head');
            const legData = this.jointData.filter(j => j.type === 'leg');
            
            // 保存手臂和头部数据到 arms_zero.yaml
            if (armAndHeadData.length > 0) {
                const armsPayload = {
                    joints: {}
                };
                
                armAndHeadData.forEach(joint => {
                    armsPayload.joints[joint.name] = {
                        current_position: joint.current_position,
                        zero_position: joint.zero_position,
                        offset: joint.offset
                    };
                });
                
                console.log('保存手臂和头部数据:', armsPayload);
                const armsResponse = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/calibration-files/arms_zero/data`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(armsPayload)
                });
                
                if (!armsResponse.ok) {
                    const error = await armsResponse.json();
                    throw new Error(`保存手臂数据失败: ${error.detail || armsResponse.statusText}`);
                }
                
                console.log('手臂和头部数据保存成功');
            }
            
            // 保存腿部数据到 offset.csv
            if (legData.length > 0) {
                const legOffsets = legData.map(joint => joint.offset);
                
                const legPayload = {
                    offsets: legOffsets
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
                    const error = await legResponse.json();
                    throw new Error(`保存腿部数据失败: ${error.detail || legResponse.statusText}`);
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
            const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/validate`, {
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
                const response = await fetch(`${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/confirm-tools-removed`, {
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
        
        // 保存会话ID
        if (data.session_id) {
            this.currentSession = data.session_id;
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
        this.toolsConfirmed = [false, false, false, false];
        this.lastLoggedStatus = {}; // 重置日志状态
        
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
                        `${this.API_BASE_URL}/robots/${this.currentRobot}/zero-point-calibration/${this.currentSession}/go-to-step`,
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