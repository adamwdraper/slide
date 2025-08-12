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
class ToolCall:
    """Structured tool call information"""
    tool_name: str
    tool_call_id: str
    arguments: Dict[str, Any]
    result: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class ExecutionDetails:
    """Complete execution telemetry"""
    events: List[ExecutionEvent]
    start_time: datetime
    end_time: datetime
    total_iterations: int
    
    @property
    def duration_ms(self) -> float:
        """Total execution time in milliseconds"""
        return (self.end_time - self.start_time).total_seconds() * 1000
        
    @property
    def total_tokens(self) -> int:
        """Sum of all tokens used across all LLM calls"""
        total = 0
        for event in self.events:
            if event.type == EventType.LLM_RESPONSE:
                total += event.data.get("tokens", {}).get("total_tokens", 0)
        return total
        
    @property
    def tool_calls(self) -> List[ToolCall]:
        """All tool calls made during execution"""
        calls = []
        tool_executions = {}
        
        # First collect tool selections
        for event in self.events:
            if event.type == EventType.TOOL_SELECTED:
                tool_executions[event.data["tool_call_id"]] = {
                    "tool_name": event.data["tool_name"],
                    "arguments": event.data["arguments"],
                    "start_time": event.timestamp
                }
        
        # Then match with results
        for event in self.events:
            if event.type in (EventType.TOOL_RESULT, EventType.TOOL_ERROR):
                tool_call_id = event.data["tool_call_id"]
                if tool_call_id in tool_executions:
                    exec_data = tool_executions[tool_call_id]
                    duration_ms = (event.timestamp - exec_data["start_time"]).total_seconds() * 1000
                    
                    calls.append(ToolCall(
                        tool_name=exec_data["tool_name"],
                        tool_call_id=tool_call_id,
                        arguments=exec_data["arguments"],
                        result=event.data.get("result"),
                        duration_ms=duration_ms,
                        success=event.type == EventType.TOOL_RESULT,
                        error=event.data.get("error") if event.type == EventType.TOOL_ERROR else None
                    ))
        
        return calls


@dataclass
class AgentResult:
    """Result from agent execution"""
    thread: Thread                    # Updated thread with new messages
    new_messages: List[Message]       # New messages added during execution
    content: Optional[str]            # Final assistant response content
    execution: ExecutionDetails       # Full execution telemetry
    
    @property
    def success(self) -> bool:
        """Whether execution completed without errors"""
        return not any(e.type == EventType.EXECUTION_ERROR for e in self.execution.events)


