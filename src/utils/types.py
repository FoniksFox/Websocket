"""Module for all the types used throughout the WebSocket server"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import TypedDict, TypeAlias


# === HTTP / Handshake ===

# Header keys should be normalized to lowercase at parse time.
Headers: TypeAlias = dict[str, str]

class UpgradeRequest(TypedDict):
    host: str
    path: str
    headers: Headers
    # HTTP version string from the request line, e.g. "HTTP/1.1"
    version: str
    # WebSocket-specific headers
    sec_websocket_key: str
    sec_websocket_version: str  # typically "13"

class UpgradeResponse(TypedDict):
    status: int  # 101 for Switching Protocols
    accept: str  # Sec-WebSocket-Accept value
    headers: Headers
    # No subprotocol negotiation for MVP

class HandshakeResult(TypedDict):
    accept: str
    request: UpgradeRequest
    response: UpgradeResponse
    # No subprotocol negotiation for MVP


# === Protocol / Framing ===

class Opcode(IntEnum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA

class Role(Enum):
    CLIENT = "CLIENT"
    SERVER = "SERVER"

# 4-byte masking key for client->server frames
MaskingKey: TypeAlias = bytes 

@dataclass(slots=True)
class Frame:
    fin: bool
    rsv1: bool
    rsv2: bool
    rsv3: bool
    opcode: Opcode
    masking_key: MaskingKey | None
    payload: bytes


# === Messages ===

TextMessage: TypeAlias = str
BinaryMessage: TypeAlias = bytes

@dataclass(slots=True)
class CloseMessage:
    code: CloseCode
    reason: str | None = None

class CloseCode(IntEnum):
    NORMAL_CLOSURE = 1000
    PROTOCOL_ERROR = 1002
    UNSUPPORTED_DATA = 1003
    INVALID_PAYLOAD = 1007
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009
    INTERNAL_ERROR = 1011


# === Errors ===

class HandshakeError(Exception):
    """Raised when the HTTP Upgrade/WebSocket handshake fails."""

class ProtocolError(Exception):
    """Raised for RFC 6455 protocol violations."""

class MessageTooBigError(ProtocolError):
    """Raised when a frame or message exceeds allowed size."""

class MaskingError(ProtocolError):
    """Raised when client masking is missing/invalid or server masking is used."""

# Other aliases
BytesLike: TypeAlias = bytes | bytearray | memoryview


# === Connection ===

class ConnectionState(Enum):
    NEW = "NEW"
    HANDSHAKING = "HANDSHAKING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"