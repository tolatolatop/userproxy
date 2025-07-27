import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from src.userproxy import app


@pytest.fixture
def client():
    """提供测试客户端"""
    return TestClient(app)


@pytest.fixture
def websocket_mock():
    """提供WebSocket模拟对象"""
    return AsyncMock()


@pytest.fixture
def context():
    """提供测试上下文"""
    return {"client_id": "test_client"}


@pytest.fixture(scope="session")
def event_loop():
    """提供事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_ping_data():
    """提供示例ping数据"""
    from datetime import datetime
    return {
        "type": "ping",
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def sample_command_data():
    """提供示例命令数据"""
    from datetime import datetime
    return {
        "type": "command",
        "client_id": "client1",
        "receiver": "server",
        "command": "ls -la",
        "data": {"path": "/tmp"},
        "request_id": "req_123",
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def sample_data_message():
    """提供示例数据消息"""
    from datetime import datetime
    return {
        "type": "data",
        "client_id": "client1",
        "receiver": "server",
        "data": "Hello, World!",
        "chunk_index": 0,
        "total_chunks": 1,
        "is_final": True,
        "timestamp": datetime.now().isoformat()
    }
