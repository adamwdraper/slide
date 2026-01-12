"""Streaming module for Tyler agent execution.

This module provides different streaming modes for agent execution:

- **events**: Yields ExecutionEvent objects with detailed telemetry (default)
- **openai**: Yields raw LiteLLM chunks in OpenAI-compatible format
- **vercel**: Yields SSE strings for Vercel AI SDK Data Stream Protocol
- **vercel_objects**: Yields chunk dicts for Vercel AI SDK (for marimo, etc.)

Usage:
    from tyler.streaming import get_stream_mode, STREAM_MODES
    
    # Get a streaming mode by name
    mode = get_stream_mode("vercel")
    async for chunk in mode.stream(agent, thread):
        yield chunk
"""
from typing import Dict, Literal, Union

# Base classes and utilities
from tyler.streaming.base import (
    BaseStreamMode,
    ChunkAccumulator,
    StreamMode,
    extract_thinking_content,
)

# Streaming mode implementations
from tyler.streaming.events import EventsStreamMode, events_stream_mode
from tyler.streaming.openai import OpenAIStreamMode, openai_stream_mode
from tyler.streaming.vercel import VercelStreamMode, vercel_stream_mode
from tyler.streaming.vercel_objects import VercelObjectsStreamMode, vercel_objects_stream_mode

# Vercel protocol utilities (for direct use in endpoints)
from tyler.streaming.vercel_protocol import (
    FinishReason,
    VercelStreamFormatter,
    VERCEL_STREAM_HEADERS,
    to_sse,
    done_sse,
)

# Type alias for mode names
StreamModeName = Literal["events", "openai", "vercel", "vercel_objects"]

# Registry of available streaming modes
STREAM_MODES: Dict[str, BaseStreamMode] = {
    "events": events_stream_mode,
    "openai": openai_stream_mode,
    "vercel": vercel_stream_mode,
    "vercel_objects": vercel_objects_stream_mode,
}


def get_stream_mode(mode: Union[StreamModeName, str]) -> BaseStreamMode:
    """Get a streaming mode by name.
    
    Args:
        mode: The name of the streaming mode ('events', 'openai', or 'vercel')
        
    Returns:
        The corresponding StreamMode instance
        
    Raises:
        ValueError: If the mode name is not recognized
    """
    if mode not in STREAM_MODES:
        valid_modes = ", ".join(f"'{m}'" for m in STREAM_MODES.keys())
        raise ValueError(f"Invalid streaming mode: '{mode}'. Must be one of: {valid_modes}")
    return STREAM_MODES[mode]


__all__ = [
    # Base classes
    "BaseStreamMode",
    "StreamMode",
    "ChunkAccumulator",
    "extract_thinking_content",
    # Mode classes
    "EventsStreamMode",
    "OpenAIStreamMode",
    "VercelStreamMode",
    "VercelObjectsStreamMode",
    # Singleton instances
    "events_stream_mode",
    "openai_stream_mode",
    "vercel_stream_mode",
    "vercel_objects_stream_mode",
    # Vercel protocol
    "VercelStreamFormatter",
    "FinishReason",
    "VERCEL_STREAM_HEADERS",
    "to_sse",
    "done_sse",
    # Registry and dispatcher
    "STREAM_MODES",
    "get_stream_mode",
    "StreamModeName",
]
