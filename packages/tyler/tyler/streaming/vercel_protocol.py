"""Vercel AI SDK Data Stream Protocol support.

Implements the SSE-based protocol described at:
https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol

This allows Tyler agents to stream responses directly to frontends using
@ai-sdk/react's useChat hook.
"""
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, TypedDict, Union
from enum import Enum


# Headers required for the Vercel AI SDK Data Stream Protocol
VERCEL_STREAM_HEADERS = {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",  # disable nginx buffering
}


class FinishReason(str, Enum):
    """Finish reasons for message completion."""
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content-filter"
    TOOL_CALLS = "tool-calls"
    ERROR = "error"
    OTHER = "other"


# Type definitions for UI Message Chunks
# Based on https://github.com/vercel/ai - packages/ai/src/ui-message-stream/ui-message-chunks.ts

class TextStartChunk(TypedDict):
    type: Literal["text-start"]
    id: str


class TextDeltaChunk(TypedDict):
    type: Literal["text-delta"]
    id: str
    delta: str


class TextEndChunk(TypedDict):
    type: Literal["text-end"]
    id: str


class ReasoningStartChunk(TypedDict):
    type: Literal["reasoning-start"]
    id: str


class ReasoningDeltaChunk(TypedDict):
    type: Literal["reasoning-delta"]
    id: str
    delta: str


class ReasoningEndChunk(TypedDict):
    type: Literal["reasoning-end"]
    id: str


class ToolInputStartChunk(TypedDict):
    type: Literal["tool-input-start"]
    toolCallId: str
    toolName: str


class ToolInputDeltaChunk(TypedDict):
    type: Literal["tool-input-delta"]
    toolCallId: str
    inputTextDelta: str


class ToolInputAvailableChunk(TypedDict):
    type: Literal["tool-input-available"]
    toolCallId: str
    toolName: str
    input: Any


class ToolOutputAvailableChunk(TypedDict):
    type: Literal["tool-output-available"]
    toolCallId: str
    output: Any


class ToolOutputErrorChunk(TypedDict):
    type: Literal["tool-output-error"]
    toolCallId: str
    errorText: str


class ErrorChunk(TypedDict):
    type: Literal["error"]
    errorText: str


class StartStepChunk(TypedDict):
    type: Literal["start-step"]


class FinishStepChunk(TypedDict):
    type: Literal["finish-step"]


class StartChunk(TypedDict, total=False):
    type: Literal["start"]
    messageId: str
    messageMetadata: Any


class FinishChunk(TypedDict, total=False):
    type: Literal["finish"]
    finishReason: str
    messageMetadata: Any


class AbortChunk(TypedDict, total=False):
    type: Literal["abort"]
    reason: str


# Union type for all possible chunks
UIMessageChunk = Union[
    TextStartChunk,
    TextDeltaChunk,
    TextEndChunk,
    ReasoningStartChunk,
    ReasoningDeltaChunk,
    ReasoningEndChunk,
    ToolInputStartChunk,
    ToolInputDeltaChunk,
    ToolInputAvailableChunk,
    ToolOutputAvailableChunk,
    ToolOutputErrorChunk,
    ErrorChunk,
    StartStepChunk,
    FinishStepChunk,
    StartChunk,
    FinishChunk,
    AbortChunk,
]


def to_sse(chunk: UIMessageChunk) -> str:
    """Format a chunk as a Server-Sent Event line.
    
    Args:
        chunk: The UI message chunk to format
        
    Returns:
        SSE-formatted string ready to send to the client
    """
    return f"data: {json.dumps(chunk)}\n\n"


def done_sse() -> str:
    """Return the SSE stream termination marker.
    
    Returns:
        The [DONE] marker in SSE format
    """
    return "data: [DONE]\n\n"


@dataclass
class VercelStreamFormatter:
    """Converts Tyler ExecutionEvents to Vercel AI SDK Data Stream Protocol.
    
    This formatter maintains state to properly track text and reasoning
    block boundaries and generate unique IDs for each block.
    
    Example:
        formatter = VercelStreamFormatter()
        
        # Start the message
        yield formatter.format_message_start()
        
        # Stream text content
        yield formatter.format_text_start()
        yield formatter.format_text_delta("Hello, ")
        yield formatter.format_text_delta("world!")
        yield formatter.format_text_end()
        
        # Finish the message
        yield formatter.format_finish()
        yield formatter.format_done()
    """
    
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex}")
    
    # Internal state
    _text_id: Optional[str] = field(default=None, repr=False)
    _reasoning_id: Optional[str] = field(default=None, repr=False)
    _text_started: bool = field(default=False, repr=False)
    _reasoning_started: bool = field(default=False, repr=False)
    
    def format_message_start(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Emit start event.
        
        Args:
            metadata: Optional metadata to include in the start event
            
        Returns:
            SSE-formatted start event
        """
        chunk: StartChunk = {"type": "start", "messageId": self.message_id}
        if metadata is not None:
            chunk["messageMetadata"] = metadata
        return to_sse(chunk)
    
    def format_text_start(self) -> str:
        """Emit text-start event.
        
        Returns:
            SSE-formatted text-start event
        """
        self._text_id = f"text_{uuid.uuid4().hex[:24]}"
        self._text_started = True
        chunk: TextStartChunk = {"type": "text-start", "id": self._text_id}
        return to_sse(chunk)
    
    def format_text_delta(self, content: str) -> str:
        """Emit text-delta event.
        
        Args:
            content: The text content to stream
            
        Returns:
            SSE-formatted text-delta event
        """
        if self._text_id is None:
            raise ValueError("format_text_start() must be called before format_text_delta()")
        chunk: TextDeltaChunk = {
            "type": "text-delta",
            "id": self._text_id,
            "delta": content,
        }
        return to_sse(chunk)
    
    def format_text_end(self) -> str:
        """Emit text-end event.
        
        Returns:
            SSE-formatted text-end event
        """
        if self._text_id is None:
            raise ValueError("format_text_start() must be called before format_text_end()")
        chunk: TextEndChunk = {"type": "text-end", "id": self._text_id}
        self._text_started = False
        return to_sse(chunk)
    
    def format_reasoning_start(self) -> str:
        """Emit reasoning-start event.
        
        Returns:
            SSE-formatted reasoning-start event
        """
        self._reasoning_id = f"reasoning_{uuid.uuid4().hex[:16]}"
        self._reasoning_started = True
        chunk: ReasoningStartChunk = {"type": "reasoning-start", "id": self._reasoning_id}
        return to_sse(chunk)
    
    def format_reasoning_delta(self, content: str) -> str:
        """Emit reasoning-delta event.
        
        Args:
            content: The reasoning content to stream
            
        Returns:
            SSE-formatted reasoning-delta event
        """
        if self._reasoning_id is None:
            raise ValueError("format_reasoning_start() must be called before format_reasoning_delta()")
        chunk: ReasoningDeltaChunk = {
            "type": "reasoning-delta",
            "id": self._reasoning_id,
            "delta": content,
        }
        return to_sse(chunk)
    
    def format_reasoning_end(self) -> str:
        """Emit reasoning-end event.
        
        Returns:
            SSE-formatted reasoning-end event
        """
        if self._reasoning_id is None:
            raise ValueError("format_reasoning_start() must be called before format_reasoning_end()")
        chunk: ReasoningEndChunk = {"type": "reasoning-end", "id": self._reasoning_id}
        self._reasoning_started = False
        return to_sse(chunk)
    
    def format_tool_input_start(self, tool_call_id: str, tool_name: str) -> str:
        """Emit tool-input-start event.
        
        Args:
            tool_call_id: The ID of the tool call
            tool_name: The name of the tool being called
            
        Returns:
            SSE-formatted tool-input-start event
        """
        chunk: ToolInputStartChunk = {
            "type": "tool-input-start",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
        }
        return to_sse(chunk)
    
    def format_tool_input_delta(self, tool_call_id: str, input_delta: str) -> str:
        """Emit tool-input-delta event for streaming tool arguments.
        
        Args:
            tool_call_id: The ID of the tool call
            input_delta: The delta of tool input arguments
            
        Returns:
            SSE-formatted tool-input-delta event
        """
        chunk: ToolInputDeltaChunk = {
            "type": "tool-input-delta",
            "toolCallId": tool_call_id,
            "inputTextDelta": input_delta,
        }
        return to_sse(chunk)
    
    def format_tool_input_available(
        self,
        tool_call_id: str,
        tool_name: str,
        input_args: Dict[str, Any],
    ) -> str:
        """Emit tool-input-available event when tool input is complete.
        
        Args:
            tool_call_id: The ID of the tool call
            tool_name: The name of the tool being called
            input_args: The complete tool arguments
            
        Returns:
            SSE-formatted tool-input-available event
        """
        chunk: ToolInputAvailableChunk = {
            "type": "tool-input-available",
            "toolCallId": tool_call_id,
            "toolName": tool_name,
            "input": input_args,
        }
        return to_sse(chunk)
    
    def format_tool_output_available(
        self,
        tool_call_id: str,
        output: Any,
    ) -> str:
        """Emit tool-output-available event when tool execution completes.
        
        Args:
            tool_call_id: The ID of the tool call
            output: The tool output (will be wrapped in {"result": ...} if not a dict)
            
        Returns:
            SSE-formatted tool-output-available event
        """
        # Ensure output is a dict for consistency
        if not isinstance(output, dict):
            output = {"result": str(output)}
        chunk: ToolOutputAvailableChunk = {
            "type": "tool-output-available",
            "toolCallId": tool_call_id,
            "output": output,
        }
        return to_sse(chunk)
    
    def format_tool_output_error(self, tool_call_id: str, error_text: str) -> str:
        """Emit tool-output-error event when tool execution fails.
        
        Args:
            tool_call_id: The ID of the tool call
            error_text: The error message
            
        Returns:
            SSE-formatted tool-output-error event
        """
        chunk: ToolOutputErrorChunk = {
            "type": "tool-output-error",
            "toolCallId": tool_call_id,
            "errorText": error_text,
        }
        return to_sse(chunk)
    
    def format_step_start(self) -> str:
        """Emit start-step event.
        
        Returns:
            SSE-formatted start-step event
        """
        chunk: StartStepChunk = {"type": "start-step"}
        return to_sse(chunk)
    
    def format_step_finish(self) -> str:
        """Emit finish-step event.
        
        Returns:
            SSE-formatted finish-step event
        """
        chunk: FinishStepChunk = {"type": "finish-step"}
        return to_sse(chunk)
    
    def format_error(self, error_text: str) -> str:
        """Emit error event.
        
        Args:
            error_text: The error message
            
        Returns:
            SSE-formatted error event
        """
        chunk: ErrorChunk = {"type": "error", "errorText": error_text}
        return to_sse(chunk)
    
    def format_finish(
        self,
        finish_reason: Optional[FinishReason] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Emit finish event.
        
        Args:
            finish_reason: Optional reason for finishing
            metadata: Optional metadata to include
            
        Returns:
            SSE-formatted finish event
        """
        chunk: FinishChunk = {"type": "finish"}
        if finish_reason is not None:
            chunk["finishReason"] = finish_reason.value
        if metadata is not None:
            chunk["messageMetadata"] = metadata
        return to_sse(chunk)
    
    def format_abort(self, reason: Optional[str] = None) -> str:
        """Emit abort event.
        
        Args:
            reason: Optional reason for aborting
            
        Returns:
            SSE-formatted abort event
        """
        chunk: AbortChunk = {"type": "abort"}
        if reason is not None:
            chunk["reason"] = reason
        return to_sse(chunk)
    
    @staticmethod
    def format_done() -> str:
        """Emit stream termination marker.
        
        Returns:
            The [DONE] marker in SSE format
        """
        return done_sse()
    
    # Convenience properties
    @property
    def text_started(self) -> bool:
        """Whether a text block is currently open."""
        return self._text_started
    
    @property
    def reasoning_started(self) -> bool:
        """Whether a reasoning block is currently open."""
        return self._reasoning_started
