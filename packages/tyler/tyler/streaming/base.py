"""Base protocol and utilities for streaming modes.

This module defines the common interface that all streaming modes implement,
along with shared utilities for stream processing.
"""
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Protocol,
)

if TYPE_CHECKING:
    from tyler.models.agent import Agent
    from tyler.models.thread import Thread


class StreamMode(Protocol):
    """Protocol defining the interface for streaming modes.
    
    Each streaming mode must implement a stream method that takes an agent
    and thread, and yields mode-specific output.
    """
    
    @property
    def name(self) -> str:
        """The mode name (e.g., 'events', 'openai', 'vercel')."""
        ...
    
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[Any, None]:
        """Stream execution output in this mode's format.
        
        Args:
            agent: The Agent instance to use for execution
            thread: The Thread to process
            
        Yields:
            Mode-specific output (ExecutionEvent, raw chunks, SSE strings, etc.)
        """
        ...


class BaseStreamMode(ABC):
    """Abstract base class for streaming modes.
    
    Provides common functionality and ensures consistent interface across modes.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The mode name (e.g., 'events', 'openai', 'vercel')."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        agent: "Agent",
        thread: "Thread",
    ) -> AsyncGenerator[Any, None]:
        """Stream execution output in this mode's format."""
        pass


class ChunkAccumulator:
    """Utility class for accumulating streaming chunks.
    
    Handles the common pattern of collecting content, tool calls,
    and thinking tokens from streaming chunks.
    """
    
    def __init__(self):
        self.content: List[str] = []
        self.thinking: List[str] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.current_tool_call: Optional[Dict[str, Any]] = None
        self.tool_args: Dict[str, str] = {}
        self.metrics: Dict[str, Any] = {}
    
    def add_content(self, chunk: str) -> None:
        """Add a content chunk."""
        if chunk:
            self.content.append(chunk)
    
    def add_thinking(self, chunk: str) -> None:
        """Add a thinking/reasoning chunk."""
        if chunk:
            self.thinking.append(chunk)
    
    def get_content(self) -> str:
        """Get accumulated content as a string."""
        return "".join(self.content)
    
    def get_thinking(self) -> Optional[str]:
        """Get accumulated thinking as a string, or None if empty."""
        return "".join(self.thinking) if self.thinking else None
    
    def has_tool_calls(self) -> bool:
        """Check if there are any tool calls."""
        return bool(self.tool_calls)
    
    def _init_tool_arg_buffer(self, tool_call_id: str, initial_value: Optional[str]) -> None:
        """Initialize a tool argument buffer if not already present."""
        if tool_call_id not in self.tool_args:
            self.tool_args[tool_call_id] = initial_value or ""
    
    def process_tool_call_delta(self, tool_call: Any) -> None:
        """Process a tool call delta from a streaming chunk.
        
        Handles both dict and object formats from different LLM providers.
        """
        if isinstance(tool_call, dict):
            self._process_dict_tool_call(tool_call)
        else:
            self._process_object_tool_call(tool_call)
    
    def _process_dict_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Process a tool call in dict format."""
        if "id" in tool_call and tool_call["id"]:
            self.current_tool_call = {
                "id": str(tool_call["id"]),
                "type": "function",
                "function": {
                    "name": tool_call.get("function", {}).get("name", ""),
                    "arguments": tool_call.get("function", {}).get("arguments", "") or "",
                },
            }
            self._init_tool_arg_buffer(
                self.current_tool_call["id"],
                self.current_tool_call["function"]["arguments"],
            )
            if self.current_tool_call not in self.tool_calls:
                self.tool_calls.append(self.current_tool_call)
        elif self.current_tool_call and "function" in tool_call:
            if "name" in tool_call["function"] and tool_call["function"]["name"]:
                self.current_tool_call["function"]["name"] = tool_call["function"]["name"]
            if "arguments" in tool_call["function"]:
                buf_id = self.current_tool_call["id"]
                self.tool_args.setdefault(buf_id, "")
                self.tool_args[buf_id] += tool_call["function"]["arguments"] or ""
                self.current_tool_call["function"]["arguments"] = self.tool_args[buf_id]
    
    def _process_object_tool_call(self, tool_call: Any) -> None:
        """Process a tool call in object format."""
        if hasattr(tool_call, "id") and tool_call.id:
            self.current_tool_call = {
                "id": str(tool_call.id),
                "type": "function",
                "function": {
                    "name": getattr(tool_call.function, "name", ""),
                    "arguments": getattr(tool_call.function, "arguments", "") or "",
                },
            }
            self._init_tool_arg_buffer(
                self.current_tool_call["id"],
                self.current_tool_call["function"]["arguments"],
            )
            if self.current_tool_call not in self.tool_calls:
                self.tool_calls.append(self.current_tool_call)
        elif self.current_tool_call and hasattr(tool_call, "function"):
            if hasattr(tool_call.function, "name") and tool_call.function.name:
                self.current_tool_call["function"]["name"] = tool_call.function.name
            if hasattr(tool_call.function, "arguments"):
                buf_id = self.current_tool_call["id"]
                self.tool_args.setdefault(buf_id, "")
                self.tool_args[buf_id] += getattr(tool_call.function, "arguments", "") or ""
                self.current_tool_call["function"]["arguments"] = self.tool_args[buf_id]
    
    def process_usage(self, chunk: Any) -> None:
        """Extract usage information from a chunk if present."""
        if hasattr(chunk, "usage") and chunk.usage:
            self.metrics["usage"] = {
                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                "total_tokens": getattr(chunk.usage, "total_tokens", 0),
            }
    
    def reset(self) -> None:
        """Reset the accumulator for a new step."""
        self.content.clear()
        self.thinking.clear()
        self.tool_calls.clear()
        self.current_tool_call = None
        self.tool_args.clear()
        self.metrics.clear()


def extract_thinking_content(delta: Any) -> tuple[Optional[str], Optional[str]]:
    """Extract thinking/reasoning content from a delta.
    
    Args:
        delta: The delta object from a streaming chunk
        
    Returns:
        Tuple of (thinking_content, thinking_type) or (None, None) if not present
    """
    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
        return str(delta.reasoning_content), "reasoning"
    elif hasattr(delta, "thinking") and delta.thinking is not None:
        return str(delta.thinking), "thinking"
    elif hasattr(delta, "extended_thinking") and delta.extended_thinking is not None:
        return str(delta.extended_thinking), "extended_thinking"
    return None, None
