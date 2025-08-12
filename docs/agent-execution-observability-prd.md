# Agent Execution Observability PRD

## Executive Summary

This PRD outlines a redesign of the Tyler Agent's execution API to provide comprehensive observability while maintaining a developer-friendly interface. The new design introduces a result object pattern and unified streaming/non-streaming execution model that exposes rich telemetry data for all agent operations.

## Problem Statement

Currently, the agent's `.go()` method returns minimal information `(thread, new_messages)`, making it difficult for developers to:
- Understand what tools were used during execution
- Track token usage and costs
- Debug complex multi-step agent workflows
- Build rich UIs that show agent thinking/processing
- Monitor performance and identify bottlenecks

## Goals

1. **Complete Observability**: Expose all agent execution details including LLM calls, tool usage, timing, and errors
2. **Developer-Friendly**: Simple things should be simple, complex things should be possible
3. **Unified Interface**: Consistent API for both streaming and non-streaming modes
4. **Industry Standards**: Align with patterns from OpenAI Agents SDK and Pydantic AI
5. **Thread-Centric**: Maintain threads as the primary abstraction for conversations

## Design

### Core Data Structures

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from enum import Enum

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
                total += event.data.get("tokens", {}).get("total", 0)
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
```

### API Design

```python
class Agent:
    async def go(
        self, 
        thread: Union[Thread, str],
        stream: bool = False
    ) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None]]:
        """
        Process the thread with the agent.
        
        This method executes the agent on the given thread, handling tool calls,
        managing conversation flow, and providing detailed execution telemetry.
        
        Args:
            thread: Thread object or thread ID to process. The thread will be
                   modified in-place with new messages.
            stream: If True, returns an async generator yielding ExecutionEvents
                   as they occur. If False, collects all events and returns an
                   AgentResult after completion.
            
        Returns:
            If stream=False:
                AgentResult containing the updated thread, new messages,
                final output, and complete execution details.
                
            If stream=True:
                Async generator yielding ExecutionEvent objects in real-time.
                Events include message creation, tool execution, and all
                intermediate steps.
            
        Raises:
            ValueError: If thread_id is provided but thread is not found
            Exception: Re-raises any unhandled exceptions during execution,
                      but execution details are still available in the result
                      
        Example:
            # Non-streaming usage
            result = await agent.go(thread)
            print(f"Response: {result.content}")
            print(f"Tokens used: {result.execution.total_tokens}")
            
            # Streaming usage
            async for event in agent.go(thread, stream=True):
                if event.type == EventType.MESSAGE_CREATED:
                    print(f"New message: {event.data['message'].content}")
        """
        if stream:
            return self._go_stream(thread)
        else:
            return await self._go_complete(thread)
```

## Implementation Details

### Non-Streaming Mode

The non-streaming implementation collects all events during execution and returns them in the AgentResult:

```python
async def _go_complete(self, thread: Union[Thread, str]) -> AgentResult:
    # Initialize execution tracking
    events = []
    start_time = datetime.now(UTC)
    new_messages = []
    
    # Record event helper
    def record_event(event_type: EventType, data: Dict[str, Any], metadata=None):
        events.append(ExecutionEvent(
            type=event_type,
            timestamp=datetime.now(UTC),
            data=data,
            metadata=metadata
        ))
    
    # Main execution loop
    # ... (implementation details)
    
    # Build result
    execution = ExecutionDetails(
        events=events,
        start_time=start_time,
        end_time=datetime.now(UTC),
        total_iterations=self._iteration_count
    )
    
    # Extract final output
    output = None
    for msg in reversed(new_messages):
        if msg.role == "assistant" and msg.content:
            output = msg.content
            break
    
    return AgentResult(
        thread=thread,
        messages=new_messages,
        output=output,
        execution=execution
    )
```

### Streaming Mode

The streaming implementation yields events as they happen:

```python
async def _go_stream(self, thread: Union[Thread, str]) -> AsyncGenerator[ExecutionEvent, None]:
    # Yield events in real-time
    yield ExecutionEvent(
        type=EventType.ITERATION_START,
        timestamp=datetime.now(UTC),
        data={"iteration_number": 1, "max_iterations": self.max_tool_iterations}
    )
    
    # Process and yield events as they occur
    # ... (implementation details)
    
    # Final completion event
    yield ExecutionEvent(
        type=EventType.EXECUTION_COMPLETE,
        timestamp=datetime.now(UTC),
        data={
            "duration_ms": total_duration,
            "total_tokens": total_tokens
        }
    )
```

## Usage Examples

### Basic Chat Application

```python
# Simple usage - developers can ignore execution details
result = await agent.go(thread)
print(result.content)
```

### Advanced Monitoring

```python
# Rich telemetry for production monitoring
result = await agent.go(thread)

# Log execution metrics
logger.info(f"Execution took {result.execution.duration_ms}ms")
logger.info(f"Used {result.execution.total_tokens} tokens")

# Track tool usage
for tool_call in result.execution.tool_calls:
    metrics.increment(f"tool_usage.{tool_call.tool_name}")
    if not tool_call.success:
        logger.error(f"Tool {tool_call.tool_name} failed: {tool_call.error}")

# Cost tracking
estimated_cost = calculate_cost(result.execution.total_tokens, model="gpt-4")
metrics.gauge("agent_cost", estimated_cost)
```

### Real-Time UI

```python
# Stream events for responsive UI
async for event in agent.go(thread, stream=True):
    match event.type:
        case EventType.LLM_STREAM_CHUNK:
            # Show typing indicator and content
            ui.append_content(event.data["content_chunk"])
            
        case EventType.TOOL_SELECTED:
            # Show tool badge
            ui.show_tool_indicator(
                name=event.data["tool_name"],
                args=event.data["arguments"]
            )
            
        case EventType.TOOL_RESULT:
            # Update tool status
            ui.update_tool_status(
                tool_call_id=event.data["tool_call_id"],
                status="complete"
            )
            
        case EventType.MESSAGE_CREATED:
            # Add message to chat
            message = event.data["message"]
            if message.role == "assistant":
                ui.add_assistant_message(message)
                
        case EventType.EXECUTION_COMPLETE:
            # Show summary
            ui.show_metrics({
                "duration": event.data["duration_ms"],
                "tokens": event.data["total_tokens"]
            })
```

### Debugging and Development

```python
# Detailed debugging during development
result = await agent.go(thread)

if not result.success:
    # Find what went wrong
    for event in result.execution.events:
        if event.type == EventType.EXECUTION_ERROR:
            print(f"Error at {event.timestamp}: {event.data['message']}")
            print(f"Traceback: {event.data.get('traceback')}")

# Analyze performance
slow_tools = [
    tc for tc in result.execution.tool_calls 
    if tc.duration_ms > 1000
]
if slow_tools:
    print("Slow tool calls detected:")
    for tc in slow_tools:
        print(f"  {tc.tool_name}: {tc.duration_ms}ms")
```

## Migration Path

Since backward compatibility is not required, the migration is straightforward:

```python
# Old API
thread, messages = await agent.go(thread)
async for update in agent.go_stream(thread):
    if update.type == StreamUpdate.Type.CONTENT_CHUNK:
        print(update.data)

# New API
result = await agent.go(thread)
messages = result.new_messages  # Same messages as before

async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data["content_chunk"])
```

## Conclusion

This design provides Tyler with a best-in-class agent execution API that balances simplicity with power. By always including execution details and using a result object pattern, we give developers the tools they need to build production-ready applications with comprehensive observability built in from day one.
