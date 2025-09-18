from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """消息类型枚举"""
    PING = "ping"
    PONG = "pong"
    COMMAND = "command"
    DATA = "data"
    CLIENT_ID = "client_id"
    ERROR = "error"


class ClientIdMessage(BaseModel):
    """客户端ID分配消息"""
    type: MessageType = Field(MessageType.CLIENT_ID, description="消息类型")
    client_id: str = Field(..., description="分配的客户端ID")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")


class PingPongMessage(BaseModel):
    """简单的生命检查ping和pong消息"""
    type: MessageType = Field(..., description="消息类型：ping或pong")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")
    client_id: Optional[str] = Field(None, description="客户端ID（可选）")


class CommandMessage(BaseModel):
    """适用于执行远程命令的消息"""
    type: MessageType = Field(MessageType.COMMAND, description="消息类型")
    client_id: str = Field(..., description="客户端ID")
    receiver: str = Field(..., description="接收命令的目标对象")
    command: str = Field(..., description="要执行的命令")
    data: Optional[Dict] = Field(None, description="命令相关的数据")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")
    request_id: Optional[str] = Field(None, description="请求ID，用于追踪")


class CommandResultMessage(BaseModel):
    """命令执行结果回传消息"""
    type: MessageType = Field(MessageType.COMMAND, description="消息类型")
    client_id: str = Field(..., description="客户端ID")
    receiver: str = Field(..., description="接收结果的目标对象")
    request_id: str = Field(..., description="对应的请求ID")
    success: bool = Field(..., description="命令执行是否成功")
    result: Optional[Dict] = Field(None, description="命令执行结果")
    error: Optional[str] = Field(None, description="错误信息（如果执行失败）")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")


class DataMessage(BaseModel):
    """适用于大数据传输的消息"""
    type: MessageType = Field(MessageType.DATA, description="消息类型")
    client_id: str = Field(..., description="客户端ID")
    receiver: str = Field(..., description="接收数据的目标对象")
    data: str = Field(..., description="传输的数据")
    chunk_index: int = Field(0, description="分片索引，从0开始")
    total_chunks: int = Field(1, description="总分片数")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")
    is_final: bool = Field(False, description="是否为最后一个分片")


class ErrorMessage(BaseModel):
    """错误消息"""
    type: MessageType = Field(MessageType.ERROR, description="消息类型")
    client_id: Optional[str] = Field(None, description="客户端ID（可选）")
    receiver: Optional[str] = Field(None, description="接收错误消息的目标对象（可选）")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    request_id: Optional[str] = Field(None, description="关联的请求ID（如果有）")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="时间戳")
    original_message: Optional[Dict] = Field(None, description="原始消息（如果错误来自消息处理）")


# 联合类型，用于处理所有类型的WebSocket消息
WebSocketMessage = ClientIdMessage | PingPongMessage | CommandMessage | CommandResultMessage | DataMessage | ErrorMessage
