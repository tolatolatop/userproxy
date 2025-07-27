from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Callable, Awaitable, Dict, Any
import logging
from pydantic import BaseModel, ValidationError
import uuid
import json

import asyncio
import threading
import time

from .schemas import (
    ClientIdMessage,
    PingPongMessage,
    CommandMessage,
    CommandResultMessage,
    DataMessage,
    WebSocketMessage,
    MessageType
)

app = FastAPI()

access_logger = logging.getLogger("access")

Handler = Callable[[str, WebSocket, Dict[str, Any]], Awaitable[None]]


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.handlers: Dict[str, Handler] = {}
        self.client_map: Dict[str, WebSocket] = {}
        self.ws_to_id: Dict[WebSocket, str] = {}
        self.ping_task: asyncio.Task = None
        self.ping_interval: int = 20  # 20秒发送一次ping

    async def start_ping_task(self):
        """启动ping定时任务"""
        if self.ping_task is None or self.ping_task.done():
            self.ping_task = asyncio.create_task(self._ping_loop())
            logging.info("Ping定时任务已启动")

    async def stop_ping_task(self):
        """停止ping定时任务"""
        if self.ping_task and not self.ping_task.done():
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass
            logging.info("Ping定时任务已停止")

    async def _ping_loop(self):
        """ping循环任务"""
        while True:
            try:
                await asyncio.sleep(self.ping_interval)
                await self._send_ping_to_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Ping任务异常: {e}")

    async def _send_ping_to_all(self):
        """向所有活跃连接发送ping"""
        if not self.active_connections:
            return

        dead_connections = []
        for websocket in self.active_connections:
            try:
                ping_message = PingPongMessage(
                    type=MessageType.PING,
                    client_id=self.ws_to_id.get(websocket)
                )
                await websocket.send_json(ping_message.model_dump(mode='json'))
            except Exception as e:
                logging.warning(f"发送ping失败，连接可能已断开: {e}")
                dead_connections.append(websocket)

        # 清理断开的连接
        for dead_ws in dead_connections:
            self.disconnect(dead_ws)

    async def connect(self, websocket: WebSocket, client_id: str = None):
        await websocket.accept()

        if client_id is None:
            # 生成新的client_id
            client_id = str(uuid.uuid4())
            logging.info(f"新用户连接: {websocket.client}, client_id={client_id}")
            access_logger.info(
                f"CONNECT {websocket.client}, client_id={client_id}")
        else:
            # 使用指定的client_id重连
            logging.info(f"用户重连: {websocket.client}, client_id={client_id}")
            access_logger.info(
                f"RECONNECT {websocket.client}, client_id={client_id}")

            # 如果client_id已存在，断开旧连接
            if client_id in self.client_map:
                old_websocket = self.client_map[client_id]
                if old_websocket in self.active_connections:
                    self.active_connections.remove(old_websocket)
                self.ws_to_id.pop(old_websocket, None)
                try:
                    await old_websocket.close()
                except Exception:
                    pass
                logging.info(f"断开旧连接: client_id={client_id}")

        self.active_connections.append(websocket)
        self.client_map[client_id] = websocket
        self.ws_to_id[websocket] = client_id

        # 连接后可发送client_id给客户端
        client_id_message = ClientIdMessage(client_id=client_id)
        await websocket.send_json(client_id_message.model_dump(mode='json'))

        # 如果是第一个连接，启动ping任务
        if len(self.active_connections) == 1:
            await self.start_ping_task()

    def disconnect(self, websocket: WebSocket):
        client_id = self.ws_to_id.get(websocket)
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if client_id:
            self.client_map.pop(client_id, None)
            self.ws_to_id.pop(websocket, None)
        logging.info(f"用户断开: {websocket.client}, client_id={client_id}")
        access_logger.info(
            f"DISCONNECT {websocket.client}, client_id={client_id}")

        # 如果没有活跃连接了，停止ping任务
        if len(self.active_connections) == 0:
            asyncio.create_task(self.stop_ping_task())

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def handle_message(self, message: str, websocket: WebSocket):
        """处理接收到的WebSocket消息"""
        client_id = self.ws_to_id.get(websocket)
        context = {"client_id": client_id}

        try:
            # 尝试解析为JSON
            data = json.loads(message)
            message_type = data.get("type")

            # 记录消息接收
            logging.info(f"收到来自 {client_id} 的消息: {message_type}")

            # 查找对应的处理器
            handler = self.handlers.get(message_type)
            if handler:
                try:
                    await handler(data, websocket, context)
                except Exception as e:
                    logging.exception(f"处理器执行异常 {client_id}: {e}")
                    await websocket.send_json({"type": "error", "detail": str(e)})
            else:
                # 未定义的消息类型
                await self._handle_undefined_message(data, websocket, context)

        except json.JSONDecodeError:
            # 非JSON格式的消息
            logging.warning(f"收到非JSON格式消息 {client_id}: {message}")
            await self._handle_undefined_message({"raw_message": message}, websocket, context)
        except Exception as e:
            logging.exception(f"消息处理异常 {client_id}: {e}")
            await websocket.send_json({"type": "error", "detail": str(e)})

    async def _handle_undefined_message(self, data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
        """处理未定义的消息类型"""
        client_id = context.get("client_id")
        message_type = data.get("type", "unknown")

        # 记录未定义的消息类型
        logging.warning(f"未定义的消息类型 {client_id}: {message_type}")
        logging.debug(f"未定义消息内容 {client_id}: {data}")

        # 发送错误响应
        error_response = {
            "type": "error",
            "detail": f"未定义的消息类型: {message_type}",
            "supported_types": list(self.handlers.keys()),
            "original_message": data
        }
        await websocket.send_json(error_response)

    def handler(self, name: str):
        def decorator(func: Handler):
            self.handlers[name] = func
            return func
        return decorator


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                await manager.handle_message(data, websocket)
            except Exception as e:
                logging.exception(f"消息处理异常: {e}")
                await websocket.send_json({"type": "error", "detail": str(e)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        logging.exception(f"WebSocket连接异常: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/{client_id}")
async def websocket_reconnect_endpoint(websocket: WebSocket, client_id: str):
    """允许客户端使用特定ID重连的WebSocket端点"""
    try:
        await manager.connect(websocket, client_id)
        while True:
            data = await websocket.receive_text()
            try:
                await manager.handle_message(data, websocket)
            except Exception as e:
                logging.exception(f"消息处理异常: {e}")
                await websocket.send_json({"type": "error", "detail": str(e)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        logging.exception(f"WebSocket重连异常: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


# 注册消息处理器
@manager.handler("client_id")
async def client_id_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
    """处理客户端ID消息"""
    try:
        validated_message = ClientIdMessage.model_validate(data)
        client_id = context.get("client_id")
        logging.info(f"收到客户端ID确认 {client_id}: {validated_message.client_id}")
    except ValidationError as e:
        logging.warning(f"客户端ID消息验证失败: {e}")


@manager.handler("ping")
async def ping_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
    """处理ping消息"""
    try:
        validated_message = PingPongMessage.model_validate(data)
        client_id = context.get("client_id")

        # 收到ping，回复pong
        pong_message = PingPongMessage(
            type=MessageType.PONG,
            client_id=client_id
        )
        await websocket.send_json(pong_message.model_dump(mode='json'))
        logging.debug(f"回复pong给 {client_id}")
    except ValidationError as e:
        logging.warning(f"Ping消息验证失败: {e}")
        await websocket.send_json({"type": "error", "detail": f"消息格式错误: {str(e)}"})


@manager.handler("pong")
async def pong_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
    """处理pong消息"""
    try:
        validated_message = PingPongMessage.model_validate(data)
        client_id = context.get("client_id")
        logging.debug(f"收到来自 {client_id} 的pong响应")
    except ValidationError as e:
        logging.warning(f"Pong消息验证失败: {e}")


@manager.handler("command")
async def command_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
    """处理命令消息"""
    client_id = context.get("client_id")

    try:
        # 检查是否为命令结果消息
        if "success" in data:
            validated_message = CommandResultMessage.model_validate(data)
            logging.info(f"收到命令结果 {client_id}: 成功={validated_message.success}")

            # 命令结果消息：转发给原始发送者
            target_websocket = manager.client_map.get(
                validated_message.receiver)
            if target_websocket:
                await target_websocket.send_json(validated_message.model_dump(mode='json'))
                logging.info(f"命令结果已转发给 {validated_message.receiver}")
            else:
                logging.warning(
                    f"目标接收者 {validated_message.receiver} 不存在，无法转发命令结果")
        else:
            validated_message = CommandMessage.model_validate(data)
            logging.info(
                f"处理命令 {client_id}: {validated_message.command} -> {validated_message.receiver}")

            # 查找接收者
            receiver_websocket = manager.client_map.get(
                validated_message.receiver)
            if not receiver_websocket:
                # 接收者不存在，返回错误
                error_message = CommandResultMessage(
                    client_id=client_id,
                    receiver=validated_message.client_id,
                    request_id=validated_message.request_id or "default",
                    success=False,
                    error=f"接收者 '{validated_message.receiver}' 不存在",
                    timestamp=validated_message.timestamp
                )
                await websocket.send_json(error_message.model_dump(mode='json'))
                logging.warning(f"接收者 {validated_message.receiver} 不存在，命令执行失败")
            else:
                # 接收者存在，转发命令
                try:
                    await receiver_websocket.send_json(validated_message.model_dump(mode='json'))
                    logging.info(f"命令已转发给接收者 {validated_message.receiver}")
                except Exception as e:
                    # 转发失败，返回错误
                    error_message = CommandResultMessage(
                        client_id=client_id,
                        receiver=validated_message.client_id,
                        request_id=validated_message.request_id or "default",
                        success=False,
                        error=f"转发命令失败: {str(e)}",
                        timestamp=validated_message.timestamp
                    )
                    await websocket.send_json(error_message.model_dump(mode='json'))
                    logging.error(
                        f"转发命令给 {validated_message.receiver} 失败: {e}")

    except ValidationError as e:
        logging.warning(f"命令消息验证失败: {e}")
        await websocket.send_json({"type": "error", "detail": f"消息格式错误: {str(e)}"})


@manager.handler("data")
async def data_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
    """处理数据消息"""
    try:
        validated_message = DataMessage.model_validate(data)
        client_id = context.get("client_id")
        logging.info(
            f"处理数据消息 {client_id}: 分片 {validated_message.chunk_index}/{validated_message.total_chunks}")

        # 这里可以添加数据分片重组逻辑
        if validated_message.is_final:
            logging.info(
                f"数据消息完成 {client_id}: 总共 {validated_message.total_chunks} 个分片")

    except ValidationError as e:
        logging.warning(f"数据消息验证失败: {e}")
        await websocket.send_json({"type": "error", "detail": f"消息格式错误: {str(e)}"})


# 示例：可以添加自定义消息处理器
# @manager.handler("custom_message")
# async def custom_message_handler(data: Dict[str, Any], websocket: WebSocket, context: Dict[str, Any]):
#     # 自定义消息处理逻辑
#     pass
