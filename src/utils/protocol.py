"""WebSocket protocol handling module"""

from __future__ import annotations
from utils.types import Opcode, Role, MaskingKey, ProtocolError, Frame, BytesLike
from utils.logging import get_logger
from utils.validate import validate_frame

logger = get_logger(__name__)

def encode_frame(role: Role, op: Opcode, payload: bytes, fin: bool = True, masking_key: MaskingKey | None = None, rsv1: bool = False, rsv2: bool = False, rsv3: bool = False) -> bytes:
    """
    Encodes a WebSocket frame.

    Args:
        role: The role of the WebSocket (client or server).
        op: The opcode of the WebSocket frame.
        payload: The payload data to include in the frame.
        fin: Whether this is the final fragment in a message.
        masking_key: The masking key to use (must be 4 bytes).
        rsv1: The value of the RSV1 bit.
        rsv2: The value of the RSV2 bit.
        rsv3: The value of the RSV3 bit.

    Returns:
        The encoded frame as bytes.
    """
    # Validate inputs
    frame = Frame(
        fin=fin,
        rsv1=rsv1,
        rsv2=rsv2,
        rsv3=rsv3,
        opcode=op,
        payload=payload,
        masking_key=masking_key
    )
    validate_frame(frame, role)

    # Construct header
    message = bytearray()
    message.append(fin << 7 | rsv1 << 6 | rsv2 << 5 | rsv3 << 4 | op.value)
    message.append((role == Role.CLIENT) << 7)
    if len(payload) <= 125:
        message[-1] |= len(payload)
    elif len(payload) <= 65535:
        message[-1] |= 126
        message.extend(len(payload).to_bytes(2, byteorder='big'))
    else:
        message[-1] |= 127
        message.extend(len(payload).to_bytes(8, byteorder='big'))
    if role == Role.CLIENT and masking_key is not None:
        message.extend(masking_key)

    message.extend(apply_mask(payload, masking_key) if masking_key and role == Role.CLIENT else payload)
    return bytes(message)


def decode_frame(frame: BytesLike, sender_role: Role) -> Frame:
    """
    Decodes a WebSocket frame.

    Args:
        frame: The raw frame bytes.
        sender_role: The role of the WebSocket that produced this frame (client or server).

    Returns:
        A Frame object with the decoded values.
    """
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise ProtocolError("Frame must be bytes, bytearray, or memoryview")

    if isinstance(frame, memoryview):
        frame = frame.tobytes()

    if len(frame) < 2:
        raise ProtocolError("Frame too short")

    first_byte = frame[0]
    fin = (first_byte & 0x80) != 0
    rsv1 = (first_byte & 0x40) != 0
    rsv2 = (first_byte & 0x20) != 0
    rsv3 = (first_byte & 0x10) != 0
    try:
        opcode = Opcode(first_byte & 0x0F)
    except ValueError:
        raise ProtocolError("Invalid opcode")

    second_byte = frame[1]
    masked = (second_byte & 0x80) != 0
    payload_length = second_byte & 0x7F

    if payload_length == 126:
        if len(frame) < 4:
            raise ProtocolError("Frame too short for extended payload length")
        payload_length = int.from_bytes(frame[2:4], byteorder='big')
        header_length = 4
    elif payload_length == 127:
        if len(frame) < 10:
            raise ProtocolError("Frame too short for extended payload length")
        # RFC 6455: 64-bit length must fit in 63 bits (MSB must be 0)
        if (frame[2] & 0x80) != 0:
            raise ProtocolError("Invalid 64-bit payload length (MSB must be 0)")
        payload_length = int.from_bytes(frame[2:10], byteorder='big')
        header_length = 10
    else:
        header_length = 2

    if len(frame) < header_length + payload_length + (4 if masked else 0):
        raise ProtocolError("Frame too short for specified payload length")

    masking_key: MaskingKey | None = None
    if masked:
        masking_key = frame[header_length:header_length + 4]
        if len(masking_key) != 4:
            raise ProtocolError("Invalid masking key length")
        header_length += 4

    payload_start = header_length
    payload_end = payload_start + payload_length
    payload = frame[payload_start:payload_end]

    if masked and masking_key is not None:
        payload = apply_mask(payload, masking_key)

    res = Frame(
        fin=fin,
        rsv1=rsv1,
        rsv2=rsv2,
        rsv3=rsv3,
        opcode=opcode,
        masking_key=masking_key,
        payload=payload
    )
    validate_frame(res, sender_role)
    return res


def peek_frame_header(data: BytesLike) -> tuple[int, bool] | None:
    """
    Return (total_frame_length_in_bytes, masked) if header is complete,
    or None if not enough bytes to decide yet. Does not validate RSV/opcode.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ProtocolError("Data must be bytes, bytearray, or memoryview")

    if isinstance(data, memoryview):
        data = data.tobytes()

    if len(data) < 2:
        return None

    second_byte = data[1]
    masked = (second_byte & 0x80) != 0
    payload_length = second_byte & 0x7F

    if payload_length == 126:
        if len(data) < 4:
            return None
        payload_length = int.from_bytes(data[2:4], byteorder='big')
        header_length = 4
    elif payload_length == 127:
        if len(data) < 10:
            return None
        # 64-bit length must fit in 63 bits
        if (data[2] & 0x80) != 0:
            raise ProtocolError("Invalid 64-bit payload length (MSB must be 0)")
        payload_length = int.from_bytes(data[2:10], byteorder='big')
        header_length = 10
    else:
        header_length = 2

    total_length = header_length + payload_length + (4 if masked else 0)
    if len(data) < total_length:
        return None

    return total_length, masked


def decode_frames(buffer: bytes | bytearray | memoryview, sender_role: Role) -> tuple[list[Frame], bytes]:
    """
    Incrementally decode zero or more complete frames from buffer.
    Return (frames, remainder). Uses validate_frame for each decoded frame.
    """
    if not isinstance(buffer, (bytes, bytearray, memoryview)):
        raise ProtocolError("Buffer must be bytes, bytearray, or memoryview")

    if isinstance(buffer, memoryview):
        buffer = buffer.tobytes()

    frames = []
    while len(buffer) > 0:
        result = peek_frame_header(buffer)
        if result is None:
            break
        frame_length, _ = result
        if len(buffer) < frame_length:
            break
        frame = decode_frame(buffer[:frame_length], sender_role)
        frames.append(frame)
        buffer = buffer[frame_length:]

    return frames, buffer


# Convenience builders (enforce control-frame rules)
def make_ping(role: Role, payload: bytes = b"") -> bytes:
    """Create a Ping frame (opcode 0x9)."""
    return encode_frame(role, Opcode.PING, payload, fin=True, masking_key=None)


def make_pong(role: Role, payload: bytes = b"") -> bytes:
    """Create a Pong frame (opcode 0xA)."""
    return encode_frame(role, Opcode.PONG, payload, fin=True, masking_key=None)


def make_close(role: Role, code: int = 1000, reason: str = "") -> bytes:
    """
    Create a Close frame (opcode 0x8).

    Args:
        code: The close status code (default: 1000).
        reason: The close reason (default: empty).

    Returns:
        The encoded Close frame as bytes.
    """
    payload = code.to_bytes(2, byteorder='big') + reason.encode('utf-8')
    return encode_frame(role, Opcode.CLOSE, payload, fin=True, masking_key=None)


def apply_mask(payload: bytes, masking_key: MaskingKey) -> bytes:
    """
    Masks / Unmasks the payload using the provided masking key.

    Args:
        payload: The payload to mask.
        masking_key: The masking key to use (must be 4 bytes).

    Returns:
        The masked payload.
    """
    if len(masking_key) != 4:
        raise ProtocolError("Invalid masking key length")
    return bytes(b ^ masking_key[i % 4] for i, b in enumerate(payload))