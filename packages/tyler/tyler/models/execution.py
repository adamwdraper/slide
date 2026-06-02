"""Execution observability models for agent execution tracking."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from enum import Enum

# Direct imports to avoid circular dependency
from narrator import Thread, Message

if TYPE_CHECKING:
    from pydantic import BaseModel


class EventType(Enum):
    """All possible event types emitted during agent execution"""
    # LLM interactions
    LLM_REQUEST = "llm_request"          # {message_count, model, temperature}
    LLM_RESPONSE = "llm_response"        # {content, tool_calls, tokens, latency_ms}
    LLM_STREAM_CHUNK = "llm_stream_chunk" # {content_chunk}
    LLM_THINKING_CHUNK = "llm_thinking_chunk" # {thinking_chunk, thinking_type}
    
    # Tool execution  
    TOOL_SELECTED = "tool_selected"      # {tool_name, arguments, tool_call_id}
    TOOL_EXECUTING = "tool_executing"    # {tool_name, tool_call_id}
    TOOL_PROGRESS = "tool_progress"      # {tool_name, progress, total, message, tool_call_id}
    TOOL_RESULT = "tool_result"          # {tool_name, result, duration_ms, tool_call_id}
    TOOL_ERROR = "tool_error"            # {tool_name, error, tool_call_id}
    
    # Message management
    MESSAGE_CREATED = "message_created"  # {message: Message}
    
    # Control flow
    ITERATION_START = "iteration_start"  # {iteration_number, max_iterations}
    ITERATION_LIMIT = "iteration_limit"  # {iterations_used}
    EXECUTION_ERROR = "execution_error"  # {error_type, message, traceback}
    EXECUTION_COMPLETE = "execution_complete" # {duration_ms, total_tokens}


@dataclass
class ExecutionEvent:
    """Atomic unit of execution information"""
    type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    attributes: Optional[Dict[str, Any]] = None


@dataclass
class ToolCallSummary:
    """Structured summary of one tool call during agent execution."""
    tool_name: str
    tool_call_id: Optional[str]
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    success: bool = False


@dataclass
class ExecutionDetails:
    """Summary and event history for an agent execution."""
    events: List[ExecutionEvent] = field(default_factory=list)
    duration_ms: float = 0.0
    total_tokens: int = 0
    tool_calls: List[ToolCallSummary] = field(default_factory=list)

    @classmethod
    def from_events(cls, events: List[ExecutionEvent]) -> "ExecutionDetails":
        """Build execution details from ordered execution events."""
        duration_ms = 0.0
        complete_tokens: Optional[int] = None
        summed_tokens = 0
        tool_calls_by_id: Dict[str, ToolCallSummary] = {}
        anonymous_tool_calls: List[ToolCallSummary] = []

        def _tool_key(tool_name: str, tool_call_id: Optional[str]) -> str:
            if tool_call_id:
                return str(tool_call_id)
            return f"{tool_name}:{len(tool_calls_by_id)}"

        for event in events:
            data = event.data or {}

            if event.type == EventType.LLM_RESPONSE:
                tokens = data.get("tokens") or {}
                if isinstance(tokens, dict):
                    summed_tokens += int(tokens.get("total_tokens", 0) or 0)

            elif event.type == EventType.TOOL_SELECTED:
                tool_name = str(data.get("tool_name") or "")
                tool_call_id = data.get("tool_call_id")
                arguments = data.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {"value": arguments}
                summary = ToolCallSummary(
                    tool_name=tool_name,
                    tool_call_id=str(tool_call_id) if tool_call_id is not None else None,
                    arguments=arguments,
                )
                if tool_call_id is None:
                    anonymous_tool_calls.append(summary)
                else:
                    tool_calls_by_id[_tool_key(tool_name, str(tool_call_id))] = summary

            elif event.type in (EventType.TOOL_RESULT, EventType.TOOL_ERROR):
                tool_name = str(data.get("tool_name") or "")
                tool_call_id = data.get("tool_call_id")
                key = _tool_key(tool_name, str(tool_call_id) if tool_call_id is not None else None)
                summary = tool_calls_by_id.get(key)
                if summary is None:
                    summary = ToolCallSummary(
                        tool_name=tool_name,
                        tool_call_id=str(tool_call_id) if tool_call_id is not None else None,
                    )
                    if tool_call_id is None:
                        anonymous_tool_calls.append(summary)
                    else:
                        tool_calls_by_id[key] = summary

                summary.duration_ms = data.get("duration_ms")
                if event.type == EventType.TOOL_RESULT:
                    summary.result = data.get("result")
                    summary.success = True
                else:
                    summary.error = data.get("error")
                    summary.success = False

            elif event.type == EventType.EXECUTION_COMPLETE:
                duration_ms = float(data.get("duration_ms", 0.0) or 0.0)
                if "total_tokens" in data:
                    complete_tokens = int(data.get("total_tokens") or 0)

        return cls(
            events=list(events),
            duration_ms=duration_ms,
            total_tokens=complete_tokens if complete_tokens is not None else summed_tokens,
            tool_calls=list(tool_calls_by_id.values()) + anonymous_tool_calls,
        )


@dataclass
class AgentResult:
    """Result from agent execution.
    
    Attributes:
        thread: Updated thread with new messages
        new_messages: New messages added during execution
        content: Final assistant response content (raw text)
        execution: Execution details, event history, and tool summaries.
        structured_data: Validated Pydantic model when using response_type.
            Only populated when agent.run() is called with a response_type parameter.
        validation_retries: Number of validation retry attempts needed.
            Only relevant when using structured output with retry_config.
        retry_history: Detailed history of validation retry attempts.
            Each entry contains: attempt number, validation errors, and response preview.
            Only populated when validation retries occur during structured output.
    """
    thread: Thread
    new_messages: List[Message]
    content: Optional[str]
    execution: ExecutionDetails = field(default_factory=ExecutionDetails)
    structured_data: Optional[Any] = None  # Optional[BaseModel] at runtime
    validation_retries: int = 0
    retry_history: Optional[List[Dict[str, Any]]] = None

    @property
    def success(self) -> bool:
        """Whether execution completed without execution error events."""
        return not any(event.type == EventType.EXECUTION_ERROR for event in self.execution.events)


class StructuredOutputError(Exception):
    """Raised when structured output validation fails after all retry attempts.
    
    This exception is raised when:
    1. A response_type is specified for agent.run()
    2. The LLM response doesn't match the Pydantic schema
    3. All retry attempts (if configured) have been exhausted
    
    Attributes:
        validation_errors: List of Pydantic validation error details
        last_response: The raw JSON response from the last attempt
    
    Example:
        ```python
        try:
            result = await agent.run(thread, response_type=Invoice)
        except StructuredOutputError as e:
            print(f"Validation failed: {e.validation_errors}")
            print(f"Last response was: {e.last_response}")
        ```
    """
    def __init__(
        self, 
        message: str, 
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        last_response: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.validation_errors = validation_errors or []
        self.last_response = last_response


class ToolContextError(Exception):
    """Raised when a tool requires context but none was provided.
    
    This exception is raised when:
    1. A tool's function signature includes a 'ctx' or 'context' parameter
    2. The agent.run() was called without providing tool_context
    
    Example:
        ```python
        @tool
        async def get_user_data(ctx: ToolContext, field: str) -> str:
            return ctx["db"].get_user(ctx["user_id"], field)
        
        # This will raise ToolContextError:
        result = await agent.run(thread)  # Missing tool_context!
        
        # This works:
        result = await agent.run(thread, tool_context={"db": db, "user_id": "123"})
        ```
    """
    pass

