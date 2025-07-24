import pytest
import asyncio
from src.userproxy.websocket_manager import health_check, HealthCheck
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from src.userproxy import app


@pytest.mark.asyncio
async def test_health_check():
    websocket = AsyncMock()
    message = "test"
    context = {}
    await health_check(message, websocket, context)
    websocket.send_json.assert_awaited_once_with(HealthCheck().model_dump())


def test_websocket_endpoint():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # 先收到client_id
        client_id_msg = websocket.receive_json()
        assert client_id_msg["type"] == "client_id"
        assert "client_id" in client_id_msg
        # 发送ping，收到健康检查响应
        websocket.send_text("ping")
        data = websocket.receive_json()
        assert data == HealthCheck().model_dump()
