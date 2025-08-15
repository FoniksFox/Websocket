"""Module for logging utilities"""

import logging

BASE_LOGGER = "ws"

def setup_logging(level:str | int = "INFO") -> None:
    """Set up a logger for the application"""
    logger = logging.getLogger(BASE_LOGGER)
    logger.propagate = False
    if isinstance(level, str):
        level = level.upper()
        level = getattr(logging, level, logging.INFO)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("[%(asctime)s %(name)s %(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.handlers.clear()
    logger.addHandler(handler)

def get_logger(child: str | None = None) -> logging.Logger:
    """Get a logger, optionally with a child name."""
    logger = logging.getLogger(BASE_LOGGER)
    if child:
        return logger.getChild(child)
    return logger


def set_logger_level(level: str | int, name: str = BASE_LOGGER) -> None:
    """Set the logging level for the specified logger."""
    logger = logging.getLogger(name)
    if isinstance(level, str):
        level = level.upper()
        level = getattr(logging, level, logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)