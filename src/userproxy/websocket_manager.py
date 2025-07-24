from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Callable, Awaitable, Dict, Any
import logging
from pydantic import BaseModel

app = FastAPI()

access_logger = logging.getLogger("access")

Handler = Callable[[str, WebSocket, Dict[str, Any]], Awaitable[None]]


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.handlers: Dict[str, Handler] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"新用户连接: {websocket.client}")
        access_logger.info(f"CONNECT {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logging.info(f"用户断开: {websocket.client}")
        access_logger.info(f"DISCONNECT {websocket.client}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def handle_message(self, message: str, websocket: WebSocket):
        context = {}
        for handler in self.handlers.values():
            await handler(message, websocket, context)

    def handler(self, func: Handler, name: str = None):
        self.handlers[name or func.__name__] = func
        return func


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(data, websocket)  # 先处理handler
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("有用户离开了聊天室")


class HealthCheck(BaseModel):
    type: str = "ping"
    status: str = "pong"


async def health_check(message: str, websocket: WebSocket, context: Dict[str, Any]):
    await websocket.send_json(HealthCheck().model_dump())


manager.handler(health_check, "health_check")
