import pytest
import asyncio
from src.userproxy.websocket_manager import health_check, HealthCheck
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_health_check():
    websocket = AsyncMock()
    message = "test"
    context = {}
    await health_check(message, websocket, context)
    websocket.send_json.assert_awaited_once_with(HealthCheck().model_dump())
