"""Logging configuration for narrator package."""
import os
import logging
from typing import Optional

class _NarratorNullHandler(logging.Handler):
    def emit(self, record):
        pass

_is_configured = False

def _ensure_logging_configured():
    """Attach a NullHandler and optionally set level based on env without overriding app config."""
    global _is_configured
    if _is_configured:
        return

    logger = logging.getLogger('narrator')
    # Avoid duplicate handlers
    if not any(isinstance(h, _NarratorNullHandler) for h in logger.handlers):
        logger.addHandler(_NarratorNullHandler())

    # Respect env level but do not call basicConfig or force reconfigure
    log_level_str = os.getenv('NARRATOR_LOG_LEVEL', os.getenv('LOG_LEVEL', '')).upper()
    if log_level_str:
        level = getattr(logging, log_level_str, None)
        if isinstance(level, int):
            logger.setLevel(level)

    _is_configured = True

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger.
    
    This function ensures logging is configured with the appropriate level from
    the NARRATOR_LOG_LEVEL (or LOG_LEVEL) environment variable before returning a logger. 
    Configuration happens automatically the first time this function is called.
    
    Args:
        name: The name for the logger. If None, uses the caller's module name.
        
    Returns:
        A configured logger instance.
        
    Usage:
        # In any file:
        from narrator.utils.logging import get_logger
        logger = get_logger(__name__)  # Automatically configures logging
        logger.debug("Debug message")  # Will respect NARRATOR_LOG_LEVEL from .env
    """
    _ensure_logging_configured()
    return logging.getLogger(name or 'narrator.unknown')