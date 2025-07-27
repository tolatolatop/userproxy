import pytest
import json
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient
from src.userproxy import app
from src.userproxy.schemas import MessageType


class TestWebSocketIntegration:
    """WebSocket集成测试类"""

    def test_websocket_connection_and_client_id(self, client):
        """测试WebSocket连接和客户端ID分配"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            assert client_id_msg["type"] == "client_id"
            assert "client_id" in client_id_msg
            assert len(client_id_msg["client_id"]) > 0

    def test_ping_pong_communication(self, client):
        """测试ping/pong通信"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送ping消息
            ping_data = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(ping_data))

            # 接收pong响应
            pong_response = websocket.receive_json()
            assert pong_response["type"] == "pong", pong_response
            assert pong_response["client_id"] == client_id

    def test_command_execution_flow(self, client):
        """测试命令执行流程"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送命令
            command_data = {
                "type": "command",
                "client_id": client_id,
                "receiver": "server",
                "command": "echo 'Hello World'",
                "data": {"env": "test"},
                "request_id": "test_req_001",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(command_data))

            # 接收命令结果
            result_response = websocket.receive_json()
            assert result_response["type"] == "command"
            assert result_response["client_id"] == client_id
            assert result_response["receiver"] == client_id
            assert result_response["request_id"] == "test_req_001"
            assert result_response["success"] is True
            assert "result" in result_response

    def test_data_transmission(self, client):
        """测试数据传输"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送数据消息
            data_message = {
                "type": "data",
                "client_id": client_id,
                "receiver": "server",
                "data": "Test data content",
                "chunk_index": 0,
                "total_chunks": 1,
                "is_final": True,
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(data_message))

            # 数据消息不应该有响应，所以不会收到消息
            # 这里只是验证消息被正确处理（没有抛出异常）

    def test_chunked_data_transmission(self, client):
        """测试分片数据传输"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送多个数据分片
            for i in range(3):
                data_message = {
                    "type": "data",
                    "client_id": client_id,
                    "receiver": "server",
                    "data": f"chunk_{i}_data",
                    "chunk_index": i,
                    "total_chunks": 3,
                    "is_final": (i == 2),  # 最后一个分片
                    "timestamp": datetime.now().isoformat()
                }
                websocket.send_text(json.dumps(data_message))

    def test_undefined_message_type(self, client):
        """测试未定义消息类型处理"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            websocket.receive_json()

            # 发送未定义的消息类型
            undefined_message = {
                "type": "unknown_type",
                "data": "some_data"
            }
            websocket.send_text(json.dumps(undefined_message))

            # 接收错误响应
            error_response = websocket.receive_json()
            assert error_response["type"] == "error"
            assert "未定义的消息类型" in error_response["detail"]
            assert "unknown_type" in error_response["detail"]
            assert "supported_types" in error_response

    def test_invalid_json_message(self, client):
        """测试无效JSON消息处理"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            websocket.receive_json()

            # 发送无效的JSON
            websocket.send_text("This is not JSON")

            # 接收错误响应
            error_response = websocket.receive_json()
            assert error_response["type"] == "error"
            assert "未定义的消息类型" in error_response["detail"]

    def test_invalid_message_format(self, client):
        """测试无效消息格式处理"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            websocket.receive_json()

            # 发送格式无效的ping消息（缺少必要字段）
            invalid_ping = {
                "type": "invalid_type"
            }
            websocket.send_text(json.dumps(invalid_ping))

            # 接收错误响应
            error_response = websocket.receive_json()
            assert error_response["type"] == "error"
            assert "未定义的消息类型" in error_response["detail"]

    def test_multiple_commands_sequence(self, client):
        """测试多个命令的序列执行"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送多个命令
            commands = [
                {"command": "pwd", "request_id": "req_001"},
                {"command": "ls", "request_id": "req_002"},
                {"command": "echo 'test'", "request_id": "req_003"}
            ]

            for cmd in commands:
                command_data = {
                    "type": "command",
                    "client_id": client_id,
                    "receiver": "server",
                    "command": cmd["command"],
                    "request_id": cmd["request_id"],
                    "timestamp": datetime.now().isoformat()
                }
                websocket.send_text(json.dumps(command_data))

                # 接收每个命令的结果
                result_response = websocket.receive_json()
                assert result_response["type"] == "command"
                assert result_response["request_id"] == cmd["request_id"]
                assert result_response["success"] is True

    def test_mixed_message_types(self, client):
        """测试混合消息类型处理"""
        with client.websocket_connect("/ws") as websocket:
            # 接收客户端ID
            client_id_msg = websocket.receive_json()
            client_id = client_id_msg["client_id"]

            # 发送ping
            ping_data = {"type": "ping",
                         "timestamp": datetime.now().isoformat()}
            websocket.send_text(json.dumps(ping_data))
            pong_response = websocket.receive_json()
            assert pong_response["type"] == "pong"

            # 发送命令
            command_data = {
                "type": "command",
                "client_id": client_id,
                "receiver": "server",
                "command": "date",
                "request_id": "mixed_test",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(command_data))
            result_response = websocket.receive_json()
            assert result_response["type"] == "command"
            assert result_response["success"] is True

            # 发送数据
            data_message = {
                "type": "data",
                "client_id": client_id,
                "receiver": "server",
                "data": "mixed test data",
                "chunk_index": 0,
                "total_chunks": 1,
                "is_final": True,
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(data_message))

            # 再次发送ping
            websocket.send_text(json.dumps(ping_data))
            pong_response2 = websocket.receive_json()
            assert pong_response2["type"] == "pong"
