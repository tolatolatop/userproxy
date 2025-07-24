from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Callable, Awaitable, Dict, Any
import logging
from pydantic import BaseModel
import uuid

app = FastAPI()

access_logger = logging.getLogger("access")

Handler = Callable[[str, WebSocket, Dict[str, Any]], Awaitable[None]]


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.handlers: Dict[str, Handler] = {}
        self.client_map: Dict[str, WebSocket] = {}
        self.ws_to_id: Dict[WebSocket, str] = {}

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
    await websocket.send_json(HealthCheck().model_dump())
