# WebSocket

A week-long solo project to implement the WebSocket protocol (RFC 6455) from the ground up using only the Python standard library.

## Project Overview

This project is part of the Weekly-Projects series. The goal is to build a minimal-yet-correct WebSocket stack by hand, starting from the HTTP Upgrade handshake through frame parsing, masking, ping/pong, and graceful close. It's a proof of concept with clean code and good docs over feature breadth.

## Learning Objectives

- Web networking fundamentals with Python sockets and selectors
- HTTP/1.1 Upgrade handshake and RFC 6455 compliance basics
- Frame encoding/decoding, masking/unmasking, and close semantics
- Event loop design: non-blocking I/O, backpressure, and connection lifecycle
- Clean protocol boundaries and testable modules (unittest from stdlib)
- Optional TLS (wss) using `ssl` from the standard library

## Design Philosophy

- Correctness first: follow RFC 6455 for the subset implemented
- Minimal moving parts: no external libraries, standard library only
- Transparency: explicit state machines and clear boundaries between layers
- Readability: small, single-purpose modules with docstrings and type hints
- Testability: pure functions for framing; deterministic tests without network

## Technical Approach

### Protocol Surface (MVP)

- HTTP Upgrade handshake (Sec-WebSocket-Key -> Sec-WebSocket-Accept)
- Text frames (UTF-8) end-to-end
- Client masking enforced (client->server masked, server->client unmasked)
- Control frames: ping, pong, close (including close codes)
- Simple message boundaries (no fragmentation in MVP)
- Broadcast and echo handlers

### Server Architecture (Python stdlib)

- `socket` + `selectors` for a tiny non-blocking event loop (no third-party)
- Connection state machine: Handshaking -> Open -> Closing -> Closed
- Per-connection read buffer and frame parser
- Backpressure-aware send queue (avoid blocking on large writes)
- Clean shutdown with FIN/close handshake and resource cleanup
- Optional TLS via `ssl.SSLContext`. WSS is a stretch-goal, not MVP.

### Client Options

- Minimal Python client (stdlib only) for handshake and frames
- Simple browser client (native `WebSocket` API) for quick manual testing

## Key Features to Implement

### Core Features

- [ ] RFC 6455 HTTP Upgrade handshake (Sec-WebSocket-Accept)
- [ ] Frame encode/decode (text, control, masking rules)
- [ ] Echo endpoint and basic broadcast hub
- [ ] Ping/pong keepalive and idle timeout
- [ ] Graceful close with close codes and reason
- [ ] Logging and minimal metrics
- [ ] Windows-friendly run script and instructions

### Advanced Features (If time permits)

- [ ] TLS (wss://) with Python `ssl`
- [ ] Fragmentation (continuation frames)
- [ ] Binary frames and large payload handling
- [ ] Origin checks and basic auth hooks
- [ ] Backpressure tuning and configurable buffers
- [ ] Simple chat rooms with channels
- [ ] CLI tooling (e.g., send, subscribe, benchmark)

## Project Structure

Planned structure (subject to small changes during implementation):

```
Websocket/
├── src/
│   ├── server/
│   │   ├── server.py              # Entry point; event loop + selector
│   │   ├── handshake.py           # HTTP upgrade and headers
│   │   ├── connection.py          # Per-connection state machine
│   │   └── hub.py                 # Broadcast/rooms routing (MVP: global)
│   ├── client/
│   │   ├── client.py              # Minimal stdlib Python client
│   │   └── browser/
│   │       └── index.html         # Simple page using native WebSocket
│   └── utils/
│       ├── types.py               # Dataclasses, enums, type aliases
│       ├── protocol.py            # Frame encode/decode, masking, opcodes
│       ├── validate.py            # Validates websocket frames based on the protocol
│       └── logging.py             # Consistent logging config
├── tests/
│   ├── test_protocol.py           # Unit tests for frame parsing
│   ├── test_handshake.py          # Unit tests for accept key calc
│   └── test_integration.py        # Socket-level happy-path tests
├── LICENSE
└── README.md                      # This file
```

## Technology Stack

- Language: Python 3.11+
- Standard library only for implementation:
	- `socket`, `selectors`, `ssl`, `base64`, `hashlib`, `struct`, `enum`, `dataclasses`, `logging`, `time`, `signal`, `types`
- Testing: `unittest` (stdlib).
- Dev tools: Browser DevTools for protocol inspection (manual)

## Getting Started

### Prerequisites

- Python 3.11+ on Windows
- A terminal (cmd.exe or PowerShell)

### Run the Server (after implementation)

```bat
rem From repository root
py -3 src\server\server.py
```

The server will listen on `ws://localhost:8765` by default.

### Try the Browser Client (after implementation)

1. Open `src\client\browser\index.html` in a modern browser.
2. Connect to `ws://localhost:8765` and send a test message.

### Try the Python Client (after implementation)

```bat
py -3 src\client\client.py --url ws://localhost:8765
```

## Development URLs

- WebSocket: `ws://localhost:8765`
- Secure WebSocket (optional): `wss://localhost:8766` (when TLS is enabled)

## Success Criteria

- [ ] Real clients (browser + Python) can echo messages
- [ ] Broadcast works across multiple concurrent connections
- [ ] Ping/pong and idle timeouts behave correctly
- [ ] Clean close handshake with proper codes
- [ ] No external dependencies for implementation
- [ ] Clear logs and basic diagnostics

## Learning Outcomes

This project demonstrates:

- Implementing a wire protocol directly from an RFC
- Designing a small event-driven server without frameworks
- Handling byte-level parsing and stateful connections robustly
- Balancing correctness, simplicity, and performance constraints

## Design Decisions

### Utils

Actually used as a directory to put all shared code between client and server logic. May change that in the future with a proper "shared" directory if it becomes too chaotic, but there are not that many modules right now, so there's no need yet.

## Notes and Reflections

**August 16, 2025 - Protocol Setup**
Started by adding the types considered necessary for the project. Implemented the handshake logic and then the frame validation and protocol functions so that later development will be easier. Made the types, validate and protocol modules shared for both client and server to avoid code duplication.

## Resources

- RFC 6455: The WebSocket Protocol — https://www.rfc-editor.org/rfc/rfc6455
- MDN WebSockets — https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
- WebSocket Frame Format (MDN) — https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers

---

**Started:** August 11, 2025
**Developer:** Boris Mladenov Beslimov
**Project:** Weekly-Projects — WebSocket