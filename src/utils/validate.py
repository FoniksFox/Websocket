"""Module for all validation functions"""

from __future__ import annotations
from utils.types import Opcode, Role, ProtocolError, Frame, MessageTooBigError
from utils.logging import get_logger

MAX_PAYLOAD_SIZE = 2 ** 20  # 1MB, arbitrary limit

logger = get_logger(__name__)

def validate_frame(frame: Frame, sender_role: Role | None = None) -> None:
    """
    Validate a WebSocket frame (MVP).

    Common checks:
    - RSV bits must be 0 (no extensions)
    - Control frames: fin=True and payload <= 125
    - No fragmentation/continuation supported
    - Payload size <= MAX_PAYLOAD_SIZE

    Masking (optional):
    - If sender_role is provided, enforce:
      * CLIENT frames must be masked (masking_key length == 4)
      * SERVER frames must not be masked
    """
    if not isinstance(frame, Frame):
        logger.debug("Invalid frame type: %s", type(frame))
        raise ProtocolError("Invalid frame")

    if not isinstance(frame.opcode, Opcode):
        logger.debug("Invalid opcode type: %s", type(frame.opcode))
        raise ProtocolError("Invalid opcode")

    if frame.rsv1 or frame.rsv2 or frame.rsv3:
        logger.debug("RSV bits set; extensions not supported")
        raise ProtocolError("Invalid frame: RSV bits are not implemented yet")

    if frame.masking_key is not None and len(frame.masking_key) != 4:
        logger.debug("Invalid masking key length: %s", len(frame.masking_key))
        raise ProtocolError("Invalid masking key length")

    if len(frame.payload) > MAX_PAYLOAD_SIZE:
        logger.debug("Payload too large: %d", len(frame.payload))
        raise MessageTooBigError("Payload too large")

    if frame.opcode in (Opcode.PING, Opcode.PONG, Opcode.CLOSE):
        if not frame.fin:
            logger.debug("Control frames must be final (FIN must be True)")
            raise ProtocolError("Control frames must be final (FIN must be True)")
        if len(frame.payload) > 125:
            logger.debug("Control frames cannot have payloads larger than 125 bytes")
            raise ProtocolError("Control frames cannot have payloads larger than 125 bytes")

    if frame.opcode == Opcode.CONTINUATION:
        logger.debug("Continuation frames not supported in MVP")
        raise ProtocolError("Continuation frames not supported")
    if not frame.fin and frame.opcode in (Opcode.TEXT, Opcode.BINARY):
        logger.debug("Fragmentation not supported in MVP")
        raise ProtocolError("Fragmentation not supported")
    if frame.opcode == Opcode.TEXT:
        try:
            frame.payload.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Text frames must be valid UTF-8")
            raise ProtocolError("Text frames must be valid UTF-8")
    if frame.opcode == Opcode.CLOSE:
        if len(frame.payload) != 0 and len(frame.payload) < 2:
            logger.debug("Close frame payload too short")
            raise ProtocolError("Close frames must have a payload of at least 2 bytes, or no payload")
        if len(frame.payload) > 125:
            logger.debug("Close frame payload too large")
            raise ProtocolError("Close frames must not have a payload larger than 125 bytes")
        if len(frame.payload) >= 2:
            code = int.from_bytes(frame.payload[:2], byteorder='big')
            if not (1000 <= code <= 4999):
                logger.debug("Invalid close code: %d", code)
                raise ProtocolError("Invalid close code")
            if code in (1004, 1005, 1006, 1015):
                logger.debug("Reserved close code: %d", code)
                raise ProtocolError("Reserved close code")
            try:
                frame.payload[2:].decode('utf-8')
            except UnicodeDecodeError:
                logger.debug("Invalid close reason format: %s", frame.payload[2:])
                raise ProtocolError("Invalid close reason format")

    # Optional masking enforcement based on who sent the frame
    if sender_role is not None:
        if sender_role == Role.CLIENT and frame.masking_key is None:
            logger.debug("Client frames must be masked")
            raise ProtocolError("Client frames must be masked")
        if sender_role == Role.SERVER and frame.masking_key is not None:
            logger.debug("Server frames must not be masked")
            raise ProtocolError("Server frames must not be masked")