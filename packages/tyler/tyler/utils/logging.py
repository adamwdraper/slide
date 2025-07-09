"""Logging configuration for tyler package."""
import os
import logging
from typing import Optional

_is_configured = False

def _ensure_logging_configured():
    """Internal function to configure logging if not already configured."""
    global _is_configured
    if _is_configured:
        return

    # Get log level from environment and convert to uppercase
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Convert string to logging level constant
    try:
        log_level = getattr(logging, log_level_str)
    except AttributeError:
        print(f"Invalid LOG_LEVEL: {log_level_str}. Defaulting to INFO.")
        log_level = logging.INFO
    
    # Configure the root logger with our format
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        force=True  # Ensure we override any existing configuration
    )
    
    # Get the root logger and set its level
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    _is_configured = True

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a configured logger.
    
    This function ensures logging is configured with the appropriate level from
    the LOG_LEVEL environment variable before returning a logger. Configuration
    happens automatically the first time this function is called.
    
    Args:
        name: The name for the logger. If None, uses the caller's module name.
        
    Returns:
        A configured logger instance.
        
    Usage:
        # In any file:
        from tyler.utils.logging import get_logger
        logger = get_logger(__name__)  # Automatically configures logging
        logger.debug("Debug message")  # Will respect LOG_LEVEL from .env
    """
    _ensure_logging_configured()
    return logging.getLogger(name or '__name__') 