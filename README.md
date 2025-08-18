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

## Key Features Implemented

### Core Features

- [x] RFC 6455 HTTP Upgrade handshake (Sec-WebSocket-Accept)
- [x] Frame encode/decode (text, binary, control, masking rules)
- [x] Echo endpoint with one-connection server
- [ ] Basic broadcast hub
- [x] Ping/pong keepalive and idle timeout
- [x] Graceful close with close codes and reason
- [x] Logging and minimal metrics
- [x] Windows-friendly run script and instructions
- [x] Browser client for manual testing
- [x] Python CLI client (scaffolded in client.py, not implemented)

### Advanced Features (Not Implemented) ❌

- [ ] TLS (wss://) with Python `ssl`
- [ ] Fragmentation (continuation frames)
- [ ] Binary frames and large payload handling
- [ ] Origin checks and basic auth hooks
- [ ] Backpressure tuning and configurable buffers
- [ ] Simple chat rooms with channels
- [ ] CLI tooling (e.g., send, subscribe, benchmark)

## Project Structure

Current structure after implementation:

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
│   ├── utils/
│   │   ├── types.py               # Dataclasses, enums, type aliases
│   │   ├── protocol.py            # Frame encode/decode, masking, opcodes
│   │   ├── validate.py            # Validates websocket frames based on the protocol
│   │   └── logging.py             # Consistent logging config
│   └── demo/
│       └── index.html             # Ultra-simple native WebSocket app for testing
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

### Run the Server

```bat
rem From repository root
python src\demo.py
```

The server will listen on `ws://localhost:8765` by default.

### Try the Browser Client

1. Open `demo/index.html` in a modern browser.
2. The page will automatically connect to `ws://localhost:8765`.
3. Type a message and click "Send" - you should see "Echo: your message" returned.
4. Click "Ping" to test the ping/pong mechanism.

### Expected Behavior

- Server accepts one connection at a time (MVP limitation)
- Text messages are echoed back with "Echo: " prefix
- Browser logs show connection state and message flow
- Server logs show handshake, frame processing, and heartbeat activity

## Development URLs

- WebSocket: `ws://localhost:8765`
- Secure WebSocket (optional): `wss://localhost:8766` (when TLS is enabled)

## Success Criteria

### Achieved ✅

- [x] Real browser client can echo messages
- [x] Ping/pong and idle timeouts behave correctly
- [x] Clean close handshake with proper codes
- [x] No external dependencies for implementation
- [x] Clear logs and basic diagnostics
- [x] RFC 6455 compliance for implemented subset

### Not Achieved ❌

- [ ] Python client implementation (scaffolded only)
- [ ] Broadcast works across multiple concurrent connections (one connection limit)
- [ ] Comprehensive test suite (scaffolded only)

## Learning Outcomes

This project demonstrates:

- **Wire Protocol Implementation**: Successfully implemented RFC 6455 WebSocket protocol from specification, including HTTP Upgrade handshake, frame encoding/decoding, masking rules, and control frames.

- **Event-Driven Server Design**: Built a selector-based non-blocking server without frameworks, handling connection lifecycle, backpressure, and resource cleanup.

- **Protocol State Management**: Designed robust state machines for connection lifecycle and implemented proper error handling with WebSocket close codes.

- **Standards Compliance**: Enforced RFC 6455 requirements including UTF-8 validation, length constraints, masking rules, and control frame semantics.

- **Non-blocking I/O Patterns**: Implemented partial read/write handling, write queuing, and event-driven programming with Python's selectors module.

**Key Technical Skills Developed**:
- Binary protocol parsing and byte-level manipulation
- Network programming with sockets and event loops  
- State machine design for connection management
- Error handling and graceful degradation
- Module design and separation of concerns
- RFC interpretation and compliance testing

## Design Decisions

### Architecture Choices

**Selectors vs Asyncio**: Chose `selectors` for the event loop to maintain standard library compatibility and avoid async/await complexity. This provides good performance for moderate connection counts while keeping the codebase accessible.

**One Connection MVP**: Limited the server to accept only one concurrent connection to focus on protocol correctness rather than scaling. This simplified state management and debugging during development.

**Module Boundaries**: Separated concerns into distinct modules:
- `types.py`: Shared data structures and enums
- `protocol.py`: Stateless frame encoding/decoding 
- `handshake.py`: HTTP upgrade logic
- `connection.py`: Stateful connection management
- `validate.py`: RFC 6455 compliance checking

**Non-blocking I/O**: Implemented fully non-blocking socket operations with read/write buffers to handle partial sends and receives gracefully.

**Error Handling**: Mapped protocol violations to appropriate WebSocket close codes (1002 for protocol errors, 1009 for oversized messages) as per RFC 6455.

### Protocol Implementation Decisions

**Fragmentation**: Explicitly rejected fragmentation support in the MVP to reduce complexity. All frames must have FIN=1.

**Masking**: Enforced client-to-server masking and server-to-client unmasked frames as required by RFC 6455.

**Control Frames**: Implemented immediate PING→PONG responses and close frame echoing for proper connection lifecycle management.

**UTF-8 Validation**: Added strict UTF-8 validation for TEXT frames and CLOSE reason strings to maintain protocol compliance.

**Length Limits**: Enforced 63-bit payload length limit and 125-byte control frame payload limit as per RFC 6455.

### Utils Directory

Initially planned as shared utilities between client and server. Evolved to contain all protocol-level logic (types, validation, framing) that's independent of connection management. This separation proved valuable for testing and code reuse.

## Notes and Reflections

**August 16, 2025 - Protocol Setup**
Started by adding the types considered necessary for the project. Implemented the handshake logic and then the frame validation and protocol functions so that later development will be easier. Made the types, validate and protocol modules shared for both client and server to avoid code duplication.

**August 17-18, 2025 - Implementation Sprint & Final Comments**
Completed the core WebSocket implementation:

- *Connection State Machine*: Designed non-blocking handshake and frame processing with proper state transitions (NEW→HANDSHAKING→OPEN→CLOSING→CLOSED). Implemented write queuing, error mapping to close codes, and callback-based message handling.

- *Selector Event Loop*: Created a simple but effective selector-based server that handles accept, read, write events with proper interest mask management and connection cleanup, though the actual selector logic couldn't be implemented, it is only prepared.

- *Keepalive System*: Added ping/pong heartbeat logic with configurable intervals and timeout detection.

*Technical Challenges Overcome*:
- Non-blocking handshake with header parsing and remainder preservation
- Correct masking application and role-based validation
- 63-bit length constraint enforcement and endianness handling
- Graceful connection cleanup with close frame echoing
- Import path resolution and logging configuration

*What Worked Well*:
- Clear separation between stateless protocol logic and stateful connection management
- RFC 6455 compliance focus prevented many edge case bugs
- Browser WebSocket API provided excellent integration testing

*Time Constraints*:
- Limited to essential features only - no multi-connection support, comprehensive test suite, or Python client
- Focused on correctness over performance optimization
- Minimal error recovery and edge case handling

## Resources

- RFC 6455: The WebSocket Protocol — https://www.rfc-editor.org/rfc/rfc6455
- MDN WebSockets — https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
- WebSocket Frame Format (MDN) — https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers

---

**Started:** August 11, 2025
**Developer:** Boris Mladenov Beslimov
**Project:** Weekly-Projects — WebSocket