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
        websocket.send_text("ping")
        # 由于有health_check handler，应该收到健康检查响应
        data = websocket.receive_json()
        assert data == HealthCheck().model_dump()
        # 还会收到广播消息
        msg = websocket.receive_text()
        assert "用户说: ping" in msg
