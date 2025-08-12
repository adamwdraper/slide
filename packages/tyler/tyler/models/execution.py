"""Execution observability models for agent execution tracking."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

# Direct imports to avoid circular dependency
from narrator import Thread, Message


class EventType(Enum):
    """All possible event types emitted during agent execution"""
    # LLM interactions
    LLM_REQUEST = "llm_request"          # {message_count, model, temperature}
    LLM_RESPONSE = "llm_response"        # {content, tool_calls, tokens, latency_ms}
    LLM_STREAM_CHUNK = "llm_stream_chunk" # {content_chunk}
    
    # Tool execution  
    TOOL_SELECTED = "tool_selected"      # {tool_name, arguments, tool_call_id}
    TOOL_EXECUTING = "tool_executing"    # {tool_name, tool_call_id}
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
    """Result from agent execution"""
    thread: Thread                    # Updated thread with new messages
    new_messages: List[Message]       # New messages added during execution
    content: Optional[str]            # Final assistant response content


