from fastapi import WebSocket as FastAPIWebSocket
from pydantic import BaseModel


class WebSocket:

    def __init__(self, ws: FastAPIWebSocket):
        self._ws = ws

    async def accept(self):
        await self._ws.accept()

    async def close(self):
        await self._ws.close()

    async def receive_text(self):
        return await self._ws.receive_text()

    async def send_text(self, message: str):
        await self._ws.send_text(message)

    async def send_message(self, model: BaseModel):
        await self.send_json(model.model_dump(mode='json'))

    async def receive_json(self):
        return await self._ws.receive_json()

    async def send_json(self, message):
        await self._ws.send_json(message)

    def client(self):
        return self._ws.client
