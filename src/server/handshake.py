"""Module for handling WebSocket handshakes"""

from __future__ import annotations
from utils.types import UpgradeRequest, UpgradeResponse, HandshakeResult, HandshakeError
from utils.logging import get_logger
from hashlib import sha1
import base64
import binascii

logger = get_logger(__name__)

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def parse_http_upgrade_request(raw: bytes) -> UpgradeRequest:
    """
    Parses a raw HTTP request into an UpgradeRequest object.
    
    Args:
        raw: The raw HTTP request bytes.
    
    Returns:
        An UpgradeRequest object with parsed headers and values.
    """
    parts = raw.decode('latin-1').split('\r\n\r\n', 1)
    lines = parts[0].split('\r\n')
    request_line = lines[0].split()
    if len(request_line) != 3:
        logger.error("Invalid HTTP request line: %s", lines[0])
        raise HandshakeError("Invalid HTTP request line")
    method, path, version = request_line[0], request_line[1], request_line[2]
    
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if line:
            key, value = line.split(":", 1)
            headers[key.lower()] = value.strip()
    
    # Validation
    if method != "GET":
        logger.error("Invalid HTTP method: %s", method)
        raise HandshakeError("Only GET method is supported for WebSocket upgrade")
    if version != "HTTP/1.1":
        logger.error("Invalid HTTP version: %s", version)
        raise HandshakeError("Only HTTP/1.1 is supported for WebSocket upgrade")
    host = headers.get("host")
    if host is None:
        logger.error("Host header is required")
        raise HandshakeError("Host header is required")
    if "upgrade" not in headers or headers["upgrade"].lower() != "websocket":
        logger.error("WebSocket upgrade required")
        raise HandshakeError("WebSocket upgrade required") # All requests are assumed to be WebSocket upgrades
    conn_header = headers.get("connection", "")
    conn_tokens = [t.strip().lower() for t in conn_header.split(",")]
    if "upgrade" not in conn_tokens:
        logger.error("Connection header must be 'Upgrade'")
        raise HandshakeError("Connection header must be 'Upgrade'")
    sec_websocket_key = headers.get("sec-websocket-key")
    if sec_websocket_key is None:
        logger.error("Missing Sec-WebSocket-Key header")
        raise HandshakeError("Missing Sec-WebSocket-Key header")
    if not validate_sec_websocket_key(sec_websocket_key):
        raise HandshakeError("Invalid Sec-WebSocket-Key header")

    sec_websocket_version = headers.get("sec-websocket-version")
    if sec_websocket_version is None:
        logger.error("Missing Sec-WebSocket-Version header")
        raise HandshakeError("Missing Sec-WebSocket-Version header")
    if sec_websocket_version != "13":
        logger.error("Invalid Sec-WebSocket-Version header")
        raise HandshakeError("Invalid Sec-WebSocket-Version header")

    upgrade_request: UpgradeRequest = {
        "host": host,
        "path": path,
        "headers": headers,
        "version": version,
        "sec_websocket_key": sec_websocket_key,
        "sec_websocket_version": sec_websocket_version
    }

    return upgrade_request


def format_http_response(response: UpgradeResponse) -> bytes:
    """
    Formats an UpgradeResponse object into raw HTTP response bytes.
    
    Args:
        response: The UpgradeResponse object to format.
    
    Returns:
        The raw HTTP response bytes.
    """
    status = response.get("status", 101)
    reason = "Switching Protocols" if status == 101 else "OK"
    status_line = f"HTTP/1.1 {status} {reason}\r\n"
    header_lines = "\r\n".join(f"{key}: {value}" for key, value in response.get("headers", {}).items())
    return (status_line + header_lines + "\r\n\r\n").encode("latin-1")


def create_upgrade_response(request: UpgradeRequest) -> HandshakeResult:
    """
    Creates an UpgradeResponse object based on the UpgradeRequest.
    
    Args:
        request: The UpgradeRequest object.
    
    Returns:
        An UpgradeResponse object with the status and headers set.
    """
    accept_value = compute_accept(request["sec_websocket_key"])
    response: UpgradeResponse = {
        "status": 101,
        "accept": accept_value,
        "headers": {
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Accept": accept_value
        }
    }
    
    res: HandshakeResult = {
        "accept": accept_value,
        "request": request,
        "response": response
    }
    return res


def compute_accept(sec_websocket_key: str) -> str:
    """
    Computes the Sec-WebSocket-Accept value from the Sec-WebSocket-Key.

    Args:
        sec_websocket_key: The Sec-WebSocket-Key from the client request.

    Returns:
        The computed Sec-WebSocket-Accept value.
    """
    # RFC 6455: Sec-WebSocket-Accept = base64( SHA1( key + GUID ) )
    sha = sha1((sec_websocket_key + GUID).encode("ascii")).digest()
    return base64.b64encode(sha).decode("ascii")

def validate_sec_websocket_key(key: str) -> bool:
    """
    Validates the Sec-WebSocket-Key.

    Args:
        key: The Sec-WebSocket-Key to validate.

    Returns:
        True if the key is valid, False otherwise.
    """
    try:
        raw = base64.b64decode(key, validate=True)
    except (binascii.Error, ValueError):
        return False
    return len(raw) == 16