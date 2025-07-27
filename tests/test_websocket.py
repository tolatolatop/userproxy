import pytest
import asyncio
import json
from datetime import datetime
from src.userproxy.websocket_manager import manager, ping_handler, pong_handler, command_handler, data_handler, client_id_handler
from src.userproxy.schemas import ClientIdMessage, PingPongMessage, CommandMessage, CommandResultMessage, DataMessage, MessageType
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.userproxy import app


# 测试client_id消息处理
@pytest.mark.asyncio
async def test_client_id_handler():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试客户端ID消息
    client_id_data = {
        "type": "client_id",
        "client_id": "new_client_123",
        "timestamp": datetime.now().isoformat()
    }

    await client_id_handler(client_id_data, websocket, context)

    # client_id处理器不应该发送响应
    websocket.send_json.assert_not_called()


# 测试基础连接和消息处理
def test_websocket_endpoint():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # 先收到client_id
        client_id_msg = websocket.receive_json()
        assert client_id_msg["type"] == "client_id"
        assert "client_id" in client_id_msg


# 测试ping/pong消息处理
@pytest.mark.asyncio
async def test_ping_handler():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试ping消息
    ping_data = {
        "type": "ping",
        "timestamp": datetime.now().isoformat()
    }

    await ping_handler(ping_data, websocket, context)

    # 验证发送了pong响应
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "pong"
    assert sent_data["client_id"] == "test_client"


@pytest.mark.asyncio
async def test_pong_handler():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试pong消息
    pong_data = {
        "type": "pong",
        "timestamp": datetime.now().isoformat(),
        "client_id": "test_client"
    }

    await pong_handler(pong_data, websocket, context)

    # pong处理器不应该发送任何响应
    websocket.send_json.assert_not_called()


# 测试命令消息处理
@pytest.mark.asyncio
async def test_command_handler():
    websocket = AsyncMock()
    context = {"client_id": "server"}

    # 测试命令消息 - 接收者存在的情况
    command_data = {
        "type": "command",
        "client_id": "client1",
        "receiver": "server",
        "command": "ls -la",
        "data": {"path": "/tmp"},
        "request_id": "req_123",
        "timestamp": datetime.now().isoformat()
    }

    # 模拟接收者存在
    with patch.object(manager, 'client_map', {'server': websocket}):
        await command_handler(command_data, websocket, context)

        # 验证命令被转发给接收者
        websocket.send_json.assert_called_once()
        sent_data = websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "command"
        assert sent_data["client_id"] == "client1"
        assert sent_data["receiver"] == "server"
        assert sent_data["command"] == "ls -la"
        assert sent_data["request_id"] == "req_123"


@pytest.mark.asyncio
async def test_command_handler_receiver_not_found():
    websocket = AsyncMock()
    context = {"client_id": "client1"}

    # 测试命令消息 - 接收者不存在的情况
    command_data = {
        "type": "command",
        "client_id": "client1",
        "receiver": "nonexistent_server",
        "command": "ls -la",
        "data": {"path": "/tmp"},
        "request_id": "req_123",
        "timestamp": datetime.now().isoformat()
    }

    # 模拟接收者不存在
    with patch.object(manager, 'client_map', {}):
        await command_handler(command_data, websocket, context)

        # 验证发送了错误响应
        websocket.send_json.assert_called_once()
        sent_data = websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "command"
        assert sent_data["success"] is False
        assert "接收者" in sent_data["error"]
        assert "nonexistent_server" in sent_data["error"]


@pytest.mark.asyncio
async def test_command_result_handler():
    websocket = AsyncMock()
    context = {"client_id": "client1"}

    # 测试命令结果消息
    result_data = {
        "type": "command",
        "client_id": "server",
        "receiver": "client1",
        "request_id": "req_123",
        "success": True,
        "result": {"output": "file1.txt file2.txt"},
        "timestamp": datetime.now().isoformat()
    }

    # 模拟目标接收者存在
    target_websocket = AsyncMock()
    with patch.object(manager, 'client_map', {'client1': target_websocket}):
        await command_handler(result_data, websocket, context)

        # 验证命令结果被转发给目标接收者
        target_websocket.send_json.assert_called_once()
        sent_data = target_websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "command"
        assert sent_data["success"] is True
        assert sent_data["receiver"] == "client1"


@pytest.mark.asyncio
async def test_command_result_handler_target_not_found():
    websocket = AsyncMock()
    context = {"client_id": "client1"}

    # 测试命令结果消息 - 目标接收者不存在
    result_data = {
        "type": "command",
        "client_id": "server",
        "receiver": "nonexistent_client",
        "request_id": "req_123",
        "success": True,
        "result": {"output": "file1.txt file2.txt"},
        "timestamp": datetime.now().isoformat()
    }

    # 模拟目标接收者不存在
    with patch.object(manager, 'client_map', {}):
        await command_handler(result_data, websocket, context)

        # 命令结果处理器不应该发送响应（因为目标不存在）
        websocket.send_json.assert_not_called()


# 测试数据消息处理
@pytest.mark.asyncio
async def test_data_handler():
    websocket = AsyncMock()
    context = {"client_id": "client1"}

    # 测试数据消息
    data_message = {
        "type": "data",
        "client_id": "client1",
        "receiver": "server",
        "data": "Hello, World!",
        "chunk_index": 0,
        "total_chunks": 1,
        "is_final": True,
        "timestamp": datetime.now().isoformat()
    }

    await data_handler(data_message, websocket, context)

    # 数据处理器不应该发送响应
    websocket.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_data_handler_with_chunks():
    websocket = AsyncMock()
    context = {"client_id": "client1"}

    # 测试分片数据消息
    data_message = {
        "type": "data",
        "client_id": "client1",
        "receiver": "server",
        "data": "chunk_data",
        "chunk_index": 2,
        "total_chunks": 5,
        "is_final": False,
        "timestamp": datetime.now().isoformat()
    }

    await data_handler(data_message, websocket, context)

    # 数据处理器不应该发送响应
    websocket.send_json.assert_not_called()


# 测试错误处理
@pytest.mark.asyncio
async def test_ping_handler_invalid_data():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试无效的ping消息 - 使用无效的type值
    invalid_ping_data = {
        "type": "invalid_type",  # 无效的消息类型
        "timestamp": datetime.now().isoformat()
    }

    await ping_handler(invalid_ping_data, websocket, context)

    # 验证发送了错误响应
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "error", sent_data
    assert "消息格式错误" in sent_data["detail"]


@pytest.mark.asyncio
async def test_command_handler_invalid_data():
    websocket = AsyncMock()
    context = {"client_id": "server"}

    # 测试无效的命令消息 - 缺少必需字段
    invalid_command_data = {
        "type": "command",
        "client_id": "client1",
        # 缺少receiver和command字段
    }

    await command_handler(invalid_command_data, websocket, context)

    # 验证发送了错误响应
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "error"
    assert "消息格式错误" in sent_data["detail"]


# 测试未定义消息类型
@pytest.mark.asyncio
async def test_undefined_message_type():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试未定义的消息类型
    undefined_data = {
        "type": "unknown_type",
        "data": "some_data"
    }

    await manager._handle_undefined_message(undefined_data, websocket, context)

    # 验证发送了错误响应
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "error"
    assert "未定义的消息类型" in sent_data["detail"]
    assert "unknown_type" in sent_data["detail"]
    assert "supported_types" in sent_data


# 测试连接管理器
@pytest.mark.asyncio
async def test_connection_manager():
    websocket = AsyncMock()

    # 测试连接
    await manager.connect(websocket)
    assert websocket in manager.active_connections
    assert len(manager.active_connections) > 0

    # 获取client_id
    client_id = manager.ws_to_id.get(websocket)
    assert client_id is not None
    assert client_id in manager.client_map

    # 测试断开连接
    manager.disconnect(websocket)
    assert websocket not in manager.active_connections
    assert client_id not in manager.client_map


# 测试消息处理流程
@pytest.mark.asyncio
async def test_message_handling_flow():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试完整的消息处理流程
    test_message = json.dumps({
        "type": "ping",
        "timestamp": datetime.now().isoformat()
    })

    await manager.handle_message(test_message, websocket)

    # 验证ping处理器被调用并发送了pong
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "pong"


# 测试非JSON消息处理
@pytest.mark.asyncio
async def test_non_json_message():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 测试非JSON格式的消息
    non_json_message = "This is not JSON"

    await manager.handle_message(non_json_message, websocket)

    # 验证发送了错误响应
    websocket.send_json.assert_called_once()
    sent_data = websocket.send_json.call_args[0][0]
    assert sent_data["type"] == "error"
    assert "未定义的消息类型" in sent_data["detail"]


# 测试处理器异常处理
@pytest.mark.asyncio
async def test_handler_exception():
    websocket = AsyncMock()
    context = {"client_id": "test_client"}

    # 模拟处理器抛出异常 - 直接patch manager.handlers中的处理器
    original_ping_handler = manager.handlers["ping"]

    async def mock_ping_handler(data, websocket, context):
        raise Exception("Test error")

    manager.handlers["ping"] = mock_ping_handler

    try:
        test_message = json.dumps({
            "type": "ping",
            "timestamp": datetime.now().isoformat()
        })

        await manager.handle_message(test_message, websocket)

        # 验证发送了错误响应
        websocket.send_json.assert_called_once()
        sent_data = websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "error", sent_data
        assert "Test error" in sent_data["detail"]
    finally:
        # 恢复原始处理器
        manager.handlers["ping"] = original_ping_handler


# 测试Pydantic模型验证
def test_client_id_message_validation():
    """测试客户端ID消息验证"""
    # 测试有效的客户端ID消息
    valid_client_id = ClientIdMessage(
        client_id="test_client_123"
    )
    assert valid_client_id.type == MessageType.CLIENT_ID
    assert valid_client_id.client_id == "test_client_123"
    assert valid_client_id.timestamp is not None


def test_ping_pong_message_validation():
    # 测试有效的ping消息
    valid_ping = PingPongMessage(
        type=MessageType.PING,
        timestamp=datetime.now()
    )
    assert valid_ping.type == MessageType.PING

    # 测试有效的pong消息
    valid_pong = PingPongMessage(
        type=MessageType.PONG,
        client_id="test_client",
        timestamp=datetime.now()
    )
    assert valid_pong.type == MessageType.PONG
    assert valid_pong.client_id == "test_client"


def test_command_message_validation():
    # 测试有效的命令消息
    valid_command = CommandMessage(
        client_id="client1",
        receiver="server",
        command="ls",
        data={"path": "/tmp"},
        request_id="req_123"
    )
    assert valid_command.command == "ls"
    assert valid_command.receiver == "server"
    assert valid_command.data == {"path": "/tmp"}


def test_data_message_validation():
    # 测试有效的数据消息
    valid_data = DataMessage(
        client_id="client1",
        receiver="server",
        data="Hello, World!",
        chunk_index=0,
        total_chunks=1,
        is_final=True
    )
    assert valid_data.data == "Hello, World!"
    assert valid_data.chunk_index == 0
    assert valid_data.is_final is True
