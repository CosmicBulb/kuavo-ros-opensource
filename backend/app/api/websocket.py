from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import logging
import asyncio

from app.schemas.robot import RobotConnectionStatus

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.robot_subscriptions: Dict[str, List[str]] = {}  # robot_id -> [client_ids]
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket客户端 {client_id} 已连接")
    
    def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # 清理订阅
        for robot_id, subscribers in self.robot_subscriptions.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        
        logger.info(f"WebSocket客户端 {client_id} 已断开")
    
    async def send_message(self, client_id: str, message_type: str = None, data: dict = None, message: dict = None):
        """向特定客户端发送消息"""
        if client_id in self.active_connections:
            try:
                # 支持两种调用方式
                if message is None and message_type is not None:
                    message = {
                        "type": message_type,
                        "data": data
                    }
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败: {str(e)}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端"""
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败: {str(e)}")
                disconnected_clients.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def broadcast_robot_status(self, status: RobotConnectionStatus):
        """广播机器人状态更新"""
        message = {
            "type": "robot_status",
            "data": status.dict()
        }
        await self.broadcast(message)
    
    def subscribe_to_robot(self, client_id: str, robot_id: str):
        """订阅特定机器人的更新"""
        if robot_id not in self.robot_subscriptions:
            self.robot_subscriptions[robot_id] = []
        if client_id not in self.robot_subscriptions[robot_id]:
            self.robot_subscriptions[robot_id].append(client_id)
    
    def unsubscribe_from_robot(self, client_id: str, robot_id: str):
        """取消订阅特定机器人"""
        if robot_id in self.robot_subscriptions:
            if client_id in self.robot_subscriptions[robot_id]:
                self.robot_subscriptions[robot_id].remove(client_id)
    
    async def send_to_robot_subscribers(self, robot_id: str, message: dict):
        """向订阅特定机器人的客户端发送消息"""
        if robot_id in self.robot_subscriptions:
            for client_id in self.robot_subscriptions[robot_id]:
                await self.send_message(client_id, message=message)


# 创建全局连接管理器
connection_manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket端点"""
    await connection_manager.connect(websocket, client_id)
    
    try:
        # 发送欢迎消息
        await connection_manager.send_message(client_id, message={
            "type": "connection",
            "message": "WebSocket连接成功",
            "client_id": client_id
        })
        
        # 心跳任务
        async def heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)  # 每30秒发送一次心跳
                    await connection_manager.send_message(client_id, message={
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time()
                    })
                except:
                    break
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        # 接收消息
        while True:
            data = await websocket.receive_json()
            
            # 处理不同类型的消息
            if data.get("type") == "subscribe":
                robot_id = data.get("robot_id")
                if robot_id:
                    connection_manager.subscribe_to_robot(client_id, robot_id)
                    await connection_manager.send_message(client_id, message={
                        "type": "subscribed",
                        "robot_id": robot_id
                    })
            
            elif data.get("type") == "unsubscribe":
                robot_id = data.get("robot_id")
                if robot_id:
                    connection_manager.unsubscribe_from_robot(client_id, robot_id)
                    await connection_manager.send_message(client_id, message={
                        "type": "unsubscribed",
                        "robot_id": robot_id
                    })
            
            elif data.get("type") == "ping":
                await connection_manager.send_message(client_id, {
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端 {client_id} 正常断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
    finally:
        heartbeat_task.cancel()
        connection_manager.disconnect(client_id)


# 创建WebSocket路由器
websocket_router = APIRouter()
websocket_router.include_router(router)