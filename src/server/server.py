from __future__ import annotations

import selectors
import socket
import sys
from utils.logging import get_logger
from utils.types import ConnectionState
from server.connection import WebSocketConnection

logger = get_logger(__name__)

def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    sel = selectors.DefaultSelector()

    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind((host, port))
    lsock.listen(1)
    lsock.setblocking(False)
    sel.register(lsock, selectors.EVENT_READ, data="listener")

    logger.info(f"Listening on ws://{host}:{port}")
    conn: WebSocketConnection | None = None

    try:
        while True:
            # Simple select loop; you can tune timeout later for heartbeats
            events = sel.select(timeout=1.0)
            for key, mask in events:
                if key.data == "listener":
                    if conn is not None:
                        # One-connection demo: refuse extra clients
                        try:
                            cs, addr = lsock.accept()
                            cs.close()
                            logger.info("Refused extra connection from %s", addr)
                        except Exception:
                            pass
                        continue

                    cs, addr = lsock.accept()
                    cs.setblocking(False)
                    conn = WebSocketConnection(cs, addr)

                    # Wire minimal callbacks
                    conn.on_open = lambda: logger.info("WebSocket OPEN")
                    conn.on_text = lambda msg, c=conn: c.send_text(f"Echo: {msg}")
                    conn.on_binary = lambda data, c=conn: c.send_binary(data)
                    conn.on_pong = lambda payload: logger.debug("PONG %r", payload)
                    conn.on_close = lambda: logger.info("WebSocket CLOSED")

                    sel.register(cs, selectors.EVENT_READ, data=conn)
                    logger.info("Accepted connection from %s", addr)

                else:
                    c: WebSocketConnection = key.data
                    if mask & selectors.EVENT_READ:
                        c.on_readable()
                    if mask & selectors.EVENT_WRITE:
                        c.on_writable()

                    # Update interest in WRITE based on queue
                    newmask = selectors.EVENT_READ | (selectors.EVENT_WRITE if c.want_write else 0)
                    if newmask != mask:
                        sel.modify(c.socket, newmask, data=c)

                    if c.state == ConnectionState.CLOSED:
                        try:
                            sel.unregister(c.socket)
                        except Exception:
                            pass
                        conn = None
                        logger.info("Connection closed; still listening.")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        try:
            sel.unregister(lsock)
        except Exception:
            pass
        lsock.close()