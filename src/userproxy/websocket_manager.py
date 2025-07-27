from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Callable, Awaitable, Dict, Any
import logging
from pydantic import BaseModel
import uuid
import json

import asyncio
import threading
import time

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
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
            except Exception as e:
                logging.warning(f"发送ping失败，连接可能已断开: {e}")
                dead_connections.append(websocket)

        # 清理断开的连接
        for dead_ws in dead_connections:
            self.disconnect(dead_ws)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections.append(websocket)
        self.client_map[client_id] = websocket
        self.ws_to_id[websocket] = client_id
        logging.info(f"新用户连接: {websocket.client}, client_id={client_id}")
        access_logger.info(
            f"CONNECT {websocket.client}, client_id={client_id}")
        # 连接后可发送client_id给客户端
        await websocket.send_json({"type": "client_id", "client_id": client_id})

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
        context = {"client_id": self.ws_to_id.get(websocket)}
        for handler in self.handlers.values():
            try:
                await handler(message, websocket, context)
            except Exception as e:
                logging.exception(f"消息处理异常: {e}")
                await websocket.send_json({"type": "error", "detail": str(e)})

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


class HealthCheck(BaseModel):
    type: str = "ping"
    status: str = "pong"


@manager.handler("health_check")
async def health_check(message: str, websocket: WebSocket, context: Dict[str, Any]):
    if message == "ping":
        await websocket.send_json(HealthCheck().model_dump())


@manager.handler("pong")
async def pong_handler(message: str, websocket: WebSocket, context: Dict[str, Any]):
    """处理客户端对ping的响应"""
    try:
        data = json.loads(message)
        if data.get("type") == "pong":
            client_id = context.get("client_id")
            logging.debug(f"收到来自 {client_id} 的pong响应")
    except Exception as e:
        logging.debug(f"处理pong响应时出错: {e}")


class LargeMessageChunk(BaseModel):
    type: str = "large_message_chunk"
    name: str
    serial_id: int
    size: int
    chunk: str


@manager.handler("large_message_chunk")
async def large_message_chunk(message: str, websocket: WebSocket, context: Dict[str, Any]):
    if "large_message_chunk" in message:
        try:
            LargeMessageChunk.model_validate_json(message)
        except Exception as e:
            logging.exception(f"消息处理异常: {e}")
            await websocket.send_json({"type": "error", "detail": str(e)})
