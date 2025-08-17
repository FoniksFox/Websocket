"""
WebSocket connection handling module for one TCP socket.
Handles the socket's lifecycle and state machine.
"""

from __future__ import annotations

from socket import socket, SHUT_RDWR
from collections import deque
import errno
import time
from typing import Callable

from utils.logging import get_logger
from utils.types import ConnectionState, Role, Opcode, ProtocolError, MessageTooBigError
from utils.protocol import encode_frame, decode_frames, make_close, make_ping, make_pong
from server.handshake import parse_http_upgrade_request, create_upgrade_response, format_http_response

MAX_HANDSHAKE_BYTES = 32 * 1024  # 32 KiB cap for HTTP upgrade request

class WebSocketConnection:
    """
    Manages a single WebSocket connection over an accepted TCP socket.
    Lifecycle: NEW ->HANDSHAKING -> OPEN -> CLOSING -> CLOSED
    """

    def __init__(self, sock: socket, addr: tuple[str, int]) -> None:
        self.socket = sock
        self.socket.setblocking(False)  # non-blocking
        self.addr = addr
        self.role = Role.SERVER
        self.logger = get_logger(f"server.connection[{addr[0]}:{addr[1]}]")
        self.read_buffer = bytearray()
        self.write_queue: deque[bytes] = deque()
        self.state = ConnectionState.NEW
        self.handshake_deadline = time.monotonic() + 10.0  # 10s timeout
        self._handshake_reply_enqueued = False
        self._close_enqueued = False
        # Keepalive timers
        self.ping_interval: float = 30.0  # seconds between pings when idle (0 to disable)
        self.pong_timeout: float = 10.0   # seconds to wait for pong after ping
        self.last_rx_at: float = time.monotonic()
        self.last_tx_at: float = self.last_rx_at
        self._awaiting_pong: bool = False
        self._last_ping_at: float = 0.0
        self._last_ping_payload: bytes = b""
        # Close info (peer-initiated)
        self.close_code: int | None = None
        # Optional callbacks (set these from server/higher layer)
        self.on_open: Callable[[], None] | None = None
        self.on_close: Callable[[], None] | None = None
        self.on_text: Callable[[str], None] | None = None
        self.on_binary: Callable[[bytes], None] | None = None
        self.on_pong: Callable[[bytes], None] | None = None
        self.logger.info("Connection created")

    def open(self) -> None:
        """
        Non-blocking handshake step: attempt to read headers; if complete, send 101.
        Call this when the socket is readable; it may need multiple calls.
        """
        if self.state == ConnectionState.NEW:
            self.state = ConnectionState.HANDSHAKING
            self.logger.info(f"Starting WebSocket handshake with {self.addr} (HANDSHAKING)")
        if self.state != ConnectionState.HANDSHAKING:
            self.logger.debug(f"Ignoring handshake in state={self.state}: {self.addr}")
            return

        # Timeout
        if time.monotonic() > self.handshake_deadline:
            self.logger.error("Handshake timeout")
            self.close()
            return

        # Read what’s available (non-blocking)
        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    self.logger.error("Peer closed before handshake")
                    self.close()
                    return
                self.read_buffer.extend(chunk)
                # Keep looping to drain until EAGAIN/EWOULDBLOCK
            except BlockingIOError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break  # Nothing more to read now; proceed to parse
                self.logger.error("Recv error during handshake: %s", e)
                self.close()
                return

        # Not enough yet
        header_end = self.read_buffer.find(b"\r\n\r\n")
        if header_end == -1:
            # Guard against unbounded header growth
            if len(self.read_buffer) > MAX_HANDSHAKE_BYTES:
                self.logger.error("Handshake header too large; closing")
                self.close()
            return

        headers_bytes = bytes(self.read_buffer[:header_end + 4])
        # Keep any data after headers in the buffer for later processing
        self.read_buffer = self.read_buffer[header_end + 4:]

        # Parse and enqueue response
        try:
            req = parse_http_upgrade_request(headers_bytes)
            result = create_upgrade_response(req)
            response = result["response"]
            self.write_queue.append(format_http_response(response))
            self._handshake_reply_enqueued = True
        except Exception as e:
            self.logger.error("Handshake failed: %s", e)
            self.close()
            return

        self.logger.info("Handshake response enqueued; waiting to flush")

    def flush_writes(self) -> None:
        """
        Non-blocking writer: send queued bytes; call when socket is writable.
        """
        while self.write_queue:
            buf = self.write_queue[0]
            try:
                sent = self.socket.send(buf)
                if sent == 0:
                    self.logger.error("Socket write returned 0")
                    self.close()
                    return
                if sent < len(buf):
                    # Keep the unsent tail
                    self.write_queue[0] = buf[sent:]
                    self.last_tx_at = time.monotonic()
                    return
                else:
                    self.write_queue.popleft()
                    self.last_tx_at = time.monotonic()
            except BlockingIOError:
                # Nothing to write now; wait for next writable event
                self.logger.debug("Socket not writable; waiting...")
                return
            except OSError as e:
                self.logger.error("Send error: %s", e)
                self.close()
                return

        # If handshake response has been sent, transition to OPEN
        if self.state == ConnectionState.HANDSHAKING and self._handshake_reply_enqueued:
            self._handshake_reply_enqueued = False
            self.state = ConnectionState.OPEN
            self.logger.info("Handshake sent; state=OPEN")
            # Notify application
            if callable(self.on_open):
                try:
                    self.on_open()
                except Exception as e:
                    self.logger.error("on_open callback error: %s", e)

        # If a CLOSE was enqueued and queue is now empty, close the socket
        if self._close_enqueued and not self.write_queue:
            self._close_enqueued = False
            self.close()

    @property
    def want_write(self) -> bool:
        """Return True if there's data enqueued to send (register for EVENT_WRITE)."""
        return bool(self.write_queue)

    def close(self) -> None:
        """
        Close the underlying socket and transition to CLOSED.
        """
        self.logger.info(f"Closing WebSocket connection: {self.addr}")
        if self.state == ConnectionState.CLOSED:
            self.logger.warning(f"WebSocket connection already closed: {self.addr}")
            return
        try:
            try:
                self.socket.shutdown(SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        finally:
            self.state = ConnectionState.CLOSED
            self.logger.info("Connection closed")
            # Notify application
            if callable(self.on_close):
                try:
                    self.on_close()
                except Exception as e:
                    self.logger.error("on_close callback error: %s", e)

    def on_readable(self) -> None:
        """
        Handle a READ-ready event: handshake or read frames.
        """
        if self.state in (ConnectionState.NEW, ConnectionState.HANDSHAKING):
            self.open()
            # After enqueuing 101, any leftover bytes remain in read_buffer; we start processing after OPEN
            return
        if self.state != ConnectionState.OPEN:
            return

        # Drain socket
        while True:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    # Peer closed TCP; begin close
                    self.close()
                    return
                self.read_buffer.extend(chunk)
                self.last_rx_at = time.monotonic()
            except BlockingIOError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                self.logger.error("Recv error: %s", e)
                self.close()
                return

        # Process any complete frames
        self.process_incoming()

    def process_incoming(self) -> None:
        """
        Process incoming WebSocket frames.
        """
        sender_role = Role.CLIENT
        try:
            frames, remainder = decode_frames(self.read_buffer, sender_role)
        except MessageTooBigError:
            # 1009: Message too big
            self.write_queue.append(make_close(self.role, 1009, "Message too big"))
            self._close_enqueued = True
            self.state = ConnectionState.CLOSING
            return
        except ProtocolError as e:
            # 1002: Protocol error
            self.logger.debug("Protocol error: %s", e)
            self.write_queue.append(make_close(self.role, 1002, "Protocol error"))
            self._close_enqueued = True
            self.state = ConnectionState.CLOSING
            return
        self.read_buffer = bytearray(remainder)
        for frame in frames:
            match frame.opcode:
                case Opcode.TEXT:
                    if callable(self.on_text):
                        try:
                            self.on_text(frame.payload.decode('utf-8'))
                        except Exception as e:
                            self.logger.error("on_text callback error: %s", e)
                    else:
                        self.logger.debug("TEXT received (no on_text handler set)")
                case Opcode.BINARY:
                    if callable(self.on_binary):
                        try:
                            self.on_binary(frame.payload)
                        except Exception as e:
                            self.logger.error("on_binary callback error: %s", e)
                    else:
                        self.logger.debug("BINARY received (no on_binary handler set)")
                case Opcode.CLOSE:
                    # Record peer close info
                    if len(frame.payload) >= 2:
                        self.close_code = int.from_bytes(frame.payload[:2], "big")
                        try:
                            self.close_reason = frame.payload[2:].decode("utf-8") if len(frame.payload) > 2 else ""
                        except UnicodeDecodeError:
                            self.close_reason = None
                    # Echo CLOSE payload back unmasked as server (only once)
                    if not self._close_enqueued:
                        self.write_queue.append(encode_frame(self.role, Opcode.CLOSE, frame.payload, fin=True))
                        self._close_enqueued = True
                        self.state = ConnectionState.CLOSING
                case Opcode.PING:
                    pong = make_pong(self.role, frame.payload)
                    self.write_queue.append(pong)
                case Opcode.PONG:
                    # If we were waiting for a specific PONG, clear the timer when it matches
                    if self._awaiting_pong:
                        if not self._last_ping_payload or frame.payload == self._last_ping_payload:
                            self._awaiting_pong = False
                            self._last_ping_payload = b""
                    if callable(self.on_pong):
                        try:
                            self.on_pong(frame.payload)
                        except Exception as e:
                            self.logger.error("on_pong callback error: %s", e)
                case _:
                    self.logger.warning(f"Unknown frame opcode: {frame.opcode}")
                    self.write_queue.append(make_close(self.role, 1002, "Protocol error"))
                    self._close_enqueued = True
                    self.state = ConnectionState.CLOSING
                    pass

    def on_writable(self) -> None:
        """
        Handle a WRITE-ready event: flush queued writes.
        """
        if self.state in (ConnectionState.HANDSHAKING, ConnectionState.OPEN, ConnectionState.CLOSING):
            self.flush_writes()

    # Send helpers
    def send_text(self, message: str) -> None:
        """
        Send a text message.
        """
        if self.state != ConnectionState.OPEN:
            self.logger.warning("Attempted to send text message while not open")
            return
        frame = encode_frame(self.role, Opcode.TEXT, message.encode('utf-8'))
        self.write_queue.append(frame)
        self.last_tx_at = time.monotonic()

    def send_binary(self, data: bytes) -> None:
        """
        Send a binary message.
        """
        if self.state != ConnectionState.OPEN:
            self.logger.warning("Attempted to send binary message while not open")
            return
        frame = encode_frame(self.role, Opcode.BINARY, data)
        self.write_queue.append(frame)
        self.last_tx_at = time.monotonic()

    def send_ping(self, payload: bytes = b"") -> None:
        """
        Send a PING frame.
        """
        if self.state != ConnectionState.OPEN:
            self.logger.warning("Attempted to send PING while not open")
            return
        frame = make_ping(self.role, payload)
        self.write_queue.append(frame)
        self.last_tx_at = time.monotonic()

    def initiate_close(self, code: int = 1000, reason: str = "") -> None:
        """
        Initiate a close handshake (server side).
        """
        if self.state == ConnectionState.CLOSED:
            return
        if not self._close_enqueued:
            self.write_queue.append(make_close(self.role, code, reason))
            self._close_enqueued = True
            self.state = ConnectionState.CLOSING
            self.last_tx_at = time.monotonic()

    # Keepalive driver: call periodically from the server loop (e.g., once per second)
    def heartbeat(self) -> None:
        """Send PINGs on idle and close on PONG timeout."""
        if self.state != ConnectionState.OPEN:
            return
        now = time.monotonic()
        # If we are awaiting a PONG and it took too long, initiate close
        if self._awaiting_pong and (now - self._last_ping_at) > self.pong_timeout:
            self.logger.warning("PONG timeout; closing connection")
            self.initiate_close(1001, "Ping timeout")
            return
        # If idle long enough and not already awaiting a PONG, send a PING
        if self.ping_interval > 0 and not self._awaiting_pong and (now - self.last_rx_at) >= self.ping_interval:
            # 8-byte token based on monotonic clock; echoed back by peer
            token = time.monotonic_ns().to_bytes(8, 'big', signed=False)
            self._last_ping_payload = token
            self._awaiting_pong = True
            self._last_ping_at = now
            self.send_ping(token)

    @property
    def next_heartbeat_at(self) -> float:
        """
        When this connection would like a heartbeat tick next.
        Use in server loop to set selector timeout.
        """
        if self.state != ConnectionState.OPEN or self.ping_interval <= 0:
            return float("inf")
        if self._awaiting_pong:
            # We’re waiting for a pong; next deadline is the timeout
            return self._last_ping_at + self.pong_timeout
        # Idle ping due at last_rx_at + ping_interval
        return self.last_rx_at + self.ping_interval