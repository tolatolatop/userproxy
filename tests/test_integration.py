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
            assert "timestamp" in client_id_msg
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

            # 发送命令给不存在的接收者
            command_data = {
                "type": "command",
                "client_id": client_id,
                "receiver": "nonexistent_server",
                "command": "echo 'Hello World'",
                "data": {"env": "test"},
                "request_id": "test_req_001",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(command_data))

            # 接收错误响应（接收者不存在）
            result_response = websocket.receive_json()
            assert result_response["type"] == "command"
            assert result_response["success"] is False
            assert "接收者" in result_response["error"]
            assert "nonexistent_server" in result_response["error"]

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

            # 发送多个命令给不存在的接收者
            commands = [
                {"command": "pwd", "request_id": "req_001"},
                {"command": "ls", "request_id": "req_002"},
                {"command": "echo 'test'", "request_id": "req_003"}
            ]

            for cmd in commands:
                command_data = {
                    "type": "command",
                    "client_id": client_id,
                    "receiver": "nonexistent_server",
                    "command": cmd["command"],
                    "request_id": cmd["request_id"],
                    "timestamp": datetime.now().isoformat()
                }
                websocket.send_text(json.dumps(command_data))

                # 接收每个命令的错误响应（接收者不存在）
                result_response = websocket.receive_json()
                assert result_response["type"] == "command"
                assert result_response["request_id"] == cmd["request_id"]
                assert result_response["success"] is False
                assert "接收者" in result_response["error"]
                assert "nonexistent_server" in result_response["error"]

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

            # 发送命令给不存在的接收者
            command_data = {
                "type": "command",
                "client_id": client_id,
                "receiver": "nonexistent_server",
                "command": "date",
                "request_id": "mixed_test",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_text(json.dumps(command_data))
            result_response = websocket.receive_json()
            assert result_response["type"] == "command"
            assert result_response["success"] is False
            assert "接收者" in result_response["error"]

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

    def test_command_forwarding_between_clients(self, client):
        """测试客户端之间的命令转发"""
        # 创建两个客户端连接
        with client.websocket_connect("/ws") as websocket1:
            client1_msg = websocket1.receive_json()
            client1_id = client1_msg["client_id"]

            with client.websocket_connect("/ws") as websocket2:
                client2_msg = websocket2.receive_json()
                client2_id = client2_msg["client_id"]

                # client1 发送命令给 client2
                command_data = {
                    "type": "command",
                    "client_id": client1_id,
                    "receiver": client2_id,
                    "command": "echo 'Hello from client1'",
                    "request_id": "forward_test",
                    "timestamp": datetime.now().isoformat()
                }
                websocket1.send_text(json.dumps(command_data))

                # client2 应该收到转发的命令
                forwarded_command = websocket2.receive_json()
                assert forwarded_command["type"] == "command"
                assert forwarded_command["client_id"] == client1_id
                assert forwarded_command["receiver"] == client2_id
                assert forwarded_command["command"] == "echo 'Hello from client1'"
                assert forwarded_command["request_id"] == "forward_test"

                # client2 发送命令结果给 client1
                result_data = {
                    "type": "command",
                    "client_id": client2_id,
                    "receiver": client1_id,
                    "request_id": "forward_test",
                    "success": True,
                    "result": {"output": "Hello from client1"},
                    "timestamp": datetime.now().isoformat()
                }
                websocket2.send_text(json.dumps(result_data))

                # client1 应该收到命令结果
                result_response = websocket1.receive_json()
                assert result_response["type"] == "command"
                assert result_response["client_id"] == client2_id
                assert result_response["receiver"] == client1_id
                assert result_response["request_id"] == "forward_test"
                assert result_response["success"] is True
                assert "result" in result_response

    def test_command_with_real_receiver(self, client):
        """测试有真实接收者的命令执行"""
        # 创建两个客户端连接，模拟真实的命令转发
        with client.websocket_connect("/ws") as websocket1:
            client1_msg = websocket1.receive_json()
            client1_id = client1_msg["client_id"]

            with client.websocket_connect("/ws") as websocket2:
                client2_msg = websocket2.receive_json()
                client2_id = client2_msg["client_id"]

                # client1 发送命令给 client2
                command_data = {
                    "type": "command",
                    "client_id": client1_id,
                    "receiver": client2_id,
                    "command": "echo 'test command'",
                    "request_id": "real_test",
                    "timestamp": datetime.now().isoformat()
                }
                websocket1.send_text(json.dumps(command_data))

                # client2 应该收到转发的命令
                forwarded_command = websocket2.receive_json()
                assert forwarded_command["type"] == "command"
                assert forwarded_command["client_id"] == client1_id
                assert forwarded_command["receiver"] == client2_id
                assert forwarded_command["command"] == "echo 'test command'"
                assert forwarded_command["request_id"] == "real_test"

                # client2 模拟执行命令并返回结果
                result_data = {
                    "type": "command",
                    "client_id": client2_id,
                    "receiver": client1_id,
                    "request_id": "real_test",
                    "success": True,
                    "result": {"output": "test command", "exit_code": 0},
                    "timestamp": datetime.now().isoformat()
                }
                websocket2.send_text(json.dumps(result_data))

                # client1 应该收到命令执行结果
                result_response = websocket1.receive_json()
                assert result_response["type"] == "command"
                assert result_response["client_id"] == client2_id
                assert result_response["receiver"] == client1_id
                assert result_response["request_id"] == "real_test"
                assert result_response["success"] is True
                assert "result" in result_response
                assert result_response["result"]["output"] == "test command"

    def test_websocket_reconnect_functionality(self, client):
        """测试WebSocket重连功能"""
        test_client_id = "integration_reconnect_test"

        # 第一次连接
        with client.websocket_connect(f"/ws/{test_client_id}") as websocket1:
            client_id_msg1 = websocket1.receive_json()
            assert client_id_msg1["type"] == "client_id"
            assert client_id_msg1["client_id"] == test_client_id

            # 发送ping消息
            ping_data = {"type": "ping",
                         "timestamp": datetime.now().isoformat()}
            websocket1.send_text(json.dumps(ping_data))
            pong_response1 = websocket1.receive_json()
            assert pong_response1["type"] == "pong"

        # 重连（使用相同的client_id）
        with client.websocket_connect(f"/ws/{test_client_id}") as websocket2:
            client_id_msg2 = websocket2.receive_json()
            assert client_id_msg2["type"] == "client_id"
            assert client_id_msg2["client_id"] == test_client_id

            # 重连后仍然可以正常通信
            ping_data = {"type": "ping",
                         "timestamp": datetime.now().isoformat()}
            websocket2.send_text(json.dumps(ping_data))
            pong_response2 = websocket2.receive_json()
            assert pong_response2["type"] == "pong"

    def test_reconnect_command_forwarding(self, client):
        """测试重连后的命令转发功能"""
        test_client_id = "reconnect_command_test"

        # 创建两个客户端，其中一个使用重连
        with client.websocket_connect("/ws") as websocket1:
            client1_msg = websocket1.receive_json()
            client1_id = client1_msg["client_id"]

            # 第二个客户端使用重连端点
            with client.websocket_connect(f"/ws/{test_client_id}") as websocket2:
                client2_msg = websocket2.receive_json()
                client2_id = client2_msg["client_id"]
                assert client2_id == test_client_id

                # client1 发送命令给重连的client2
                command_data = {
                    "type": "command",
                    "client_id": client1_id,
                    "receiver": test_client_id,
                    "command": "echo 'reconnect test'",
                    "request_id": "reconnect_cmd",
                    "timestamp": datetime.now().isoformat()
                }
                websocket1.send_text(json.dumps(command_data))

                # client2 应该收到转发的命令
                forwarded_command = websocket2.receive_json()
                assert forwarded_command["type"] == "command"
                assert forwarded_command["client_id"] == client1_id
                assert forwarded_command["receiver"] == test_client_id
                assert forwarded_command["command"] == "echo 'reconnect test'"

                # client2 返回命令结果
                result_data = {
                    "type": "command",
                    "client_id": test_client_id,
                    "receiver": client1_id,
                    "request_id": "reconnect_cmd",
                    "success": True,
                    "result": {"output": "reconnect test"},
                    "timestamp": datetime.now().isoformat()
                }
                websocket2.send_text(json.dumps(result_data))

                # client1 应该收到命令结果
                result_response = websocket1.receive_json()
                assert result_response["type"] == "command"
                assert result_response["success"] is True
                assert result_response["result"]["output"] == "reconnect test"
