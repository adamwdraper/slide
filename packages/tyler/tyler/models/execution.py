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
class AgentResult:
    """Result from agent execution.
    
    Attributes:
        thread: Updated thread with new messages
        new_messages: New messages added during execution
        content: Final assistant response content (raw text)
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
    structured_data: Optional[Any] = None  # Optional[BaseModel] at runtime
    validation_retries: int = 0
    retry_history: Optional[List[Dict[str, Any]]] = None


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


