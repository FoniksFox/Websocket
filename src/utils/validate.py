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

    # Optional masking enforcement based on who sent the frame
    if sender_role is not None:
        if sender_role == Role.CLIENT and frame.masking_key is None:
            logger.debug("Client frames must be masked")
            raise ProtocolError("Client frames must be masked")
        if sender_role == Role.SERVER and frame.masking_key is not None:
            logger.debug("Server frames must not be masked")
            raise ProtocolError("Server frames must not be masked")