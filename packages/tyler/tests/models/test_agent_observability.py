"""Tests for the new agent execution observability features."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tyler import Agent, Thread, Message, AgentResult, ExecutionEvent, EventType
from litellm import ModelResponse
from types import SimpleNamespace
from typing import AsyncGenerator
import asyncio


class MockChoice:
    def __init__(self, message=None, delta=None):
        self.message = message
        self.delta = delta


class MockMessage:
    def __init__(self, content="Test response", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class MockResponse:
    def __init__(self, choices=None, usage=None):
        self.choices = choices or []
        self.usage = usage or SimpleNamespace(
            completion_tokens=10,
            prompt_tokens=20,
            total_tokens=30
        )


@pytest.fixture
def mock_completion():
    """Mock the acompletion function"""
    with patch('tyler.models.agent.acompletion') as mock:
        # Default to returning a simple response
        mock.return_value = MockResponse([
            MockChoice(MockMessage("Test response"))
        ])
        yield mock


@pytest.mark.asyncio
async def test_go_non_streaming_returns_agent_result(mock_completion):
    """Test that go() without streaming returns an AgentResult."""
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="Test agent"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Run agent
    result = await agent.run(thread)
    
    # Verify result type and structure
    assert isinstance(result, AgentResult)
    assert result.thread == thread
    assert len(result.new_messages) > 0
    assert result.content == "Test response"
    # AgentResult no longer has execution or success attributes


@pytest.mark.asyncio
async def test_go_streaming_yields_execution_events(mock_completion):
    """Test that go() with streaming yields ExecutionEvent objects."""
    # Mock streaming response
    async def mock_stream(*args, **kwargs):
        # Simulate streaming chunks
        chunks = [
            MockResponse([MockChoice(delta=SimpleNamespace(content="Hello"))]),
            MockResponse([MockChoice(delta=SimpleNamespace(content=" world"))]),
            MockResponse([MockChoice(delta=SimpleNamespace(content=None))],
                        usage=SimpleNamespace(completion_tokens=5, prompt_tokens=10, total_tokens=15))
        ]
        for chunk in chunks:
            yield chunk
    
    mock_completion.return_value = mock_stream()
    
    agent = Agent(
        model_name="gpt-4o-mini",
        purpose="Test agent"
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Collect all events
    events = []
    async for event in agent.stream(thread):
        assert isinstance(event, ExecutionEvent)
        events.append(event)
    
    # Verify we got the expected events
    event_types = [e.type for e in events]
    assert EventType.ITERATION_START in event_types
    assert EventType.LLM_REQUEST in event_types
    assert EventType.LLM_STREAM_CHUNK in event_types
    assert EventType.LLM_RESPONSE in event_types
    assert EventType.MESSAGE_CREATED in event_types
    assert EventType.EXECUTION_COMPLETE in event_types
    
    # Check stream chunks
    stream_chunks = [e for e in events if e.type == EventType.LLM_STREAM_CHUNK]
    assert len(stream_chunks) == 2
    assert stream_chunks[0].data["content_chunk"] == "Hello"
    assert stream_chunks[1].data["content_chunk"] == " world"


@pytest.mark.asyncio
async def test_execution_with_tool_calls(mock_completion):
    """Test execution details capture tool calls correctly."""
    # Mock response with tool call
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="calculate",
            arguments='{"x": 5, "y": 3}'
        )
    )
    
    mock_completion.side_effect = [
        # First call - assistant wants to use tool
        MockResponse([
            MockChoice(MockMessage("Let me calculate that", tool_calls=[tool_call]))
        ]),
        # Second call - after tool execution
        MockResponse([
            MockChoice(MockMessage("The result is 8"))
        ])
    ]
    
    # Mock tool execution
    with patch('tyler.utils.tool_runner.tool_runner.execute_tool_call') as mock_tool:
        mock_tool.return_value = "8"
        
        agent = Agent(
            model_name="gpt-4o-mini",
            purpose="Test agent",
            tools=[{
                "definition": {
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "description": "Calculate",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                "implementation": lambda x, y: x + y
            }]
        )
        
        thread = Thread()
        thread.add_message(Message(role="user", content="What is 5 + 3?"))
        
        result = await agent.run(thread)
        
        # Verify the result contains the expected content
        assert result.content == "The result is 8"
        assert len(result.new_messages) > 0


@pytest.mark.asyncio
async def test_execution_error_handling(mock_completion):
    """Test that execution errors are captured in the result."""
    # Make completion fail
    mock_completion.side_effect = Exception("API Error")
    
    agent = Agent(model_name="gpt-4o-mini")
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    result = await agent.run(thread)
    
    # Should still get a result, but with error
    assert isinstance(result, AgentResult)
    # Error message is set as output
    assert result.content is not None
    assert "error" in result.content.lower()


@pytest.mark.asyncio
async def test_tool_duration_tracking_non_streaming(mock_completion):
    """Test that tool execution duration is tracked in non-streaming mode.
    
    Note: Currently the duration tracking is implemented via ExecutionEvent
    recording, but the actual tool message metrics may have placeholder values.
    This test verifies the core timing infrastructure is in place.
    """
    import asyncio
    
    # Create a tool that takes measurable time
    async def slow_tool():
        await asyncio.sleep(0.05)  # 50ms
        return "Tool completed"
    
    agent = Agent(
        model_name="gpt-4o-mini",
        tools=[{
            "definition": {
                "type": "function",
                "function": {
                    "name": "slow_tool",
                    "description": "A slow tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            "implementation": slow_tool
        }]
    )
    
    # Mock tool call
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="slow_tool",
            arguments="{}"
        )
    )
    
    # Mock responses
    mock_completion.side_effect = [
        # First call - assistant wants to use tool
        MockResponse([
            MockChoice(MockMessage("Let me use the slow tool", tool_calls=[tool_call]))
        ]),
        # Second call - after tool execution
        MockResponse([
            MockChoice(MockMessage("The tool completed successfully"))
        ])
    ]
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Please use the slow tool"))
    
    # Execute
    result = await agent.run(thread)
    
    # Verify tool was executed by checking messages
    tool_executed = False
    for msg in result.new_messages:
        if msg.role == "tool":
            tool_executed = True
            # Tool messages should have metrics with timing info
            assert msg.metrics is not None
            assert "timing" in msg.metrics
            assert "latency" in msg.metrics["timing"]
            # Note: The actual duration tracking is in ExecutionEvent data,
            # not in the message metrics currently
    
    assert tool_executed, "Tool should have been executed"
    

@pytest.mark.asyncio
async def test_tool_duration_tracking_streaming(mock_completion):
    """Test that tool execution duration is tracked in streaming mode.
    
    This test specifically checks that ExecutionEvent objects include
    duration tracking for tool calls in streaming mode.
    """
    import asyncio
    
    # Create a tool that takes measurable time
    async def slow_tool():
        await asyncio.sleep(0.05)  # 50ms
        return "Tool completed"
    
    agent = Agent(
        model_name="gpt-4o-mini",
        tools=[{
            "definition": {
                "type": "function",
                "function": {
                    "name": "slow_tool",
                    "description": "A slow tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            "implementation": slow_tool
        }]
    )
    
    # Mock tool call
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="slow_tool",
            arguments="{}"
        )
    )
    
    # Create mock streaming response
    async def mock_stream(*args, **kwargs):
        # First chunks - content and tool call
        yield MockResponse([MockChoice(delta=SimpleNamespace(content="Let me use "))])
        yield MockResponse([MockChoice(delta=SimpleNamespace(content="the slow tool"))])
        yield MockResponse([MockChoice(delta=SimpleNamespace(tool_calls=[tool_call]))])
        # Final chunk with usage info
        yield MockResponse([MockChoice(delta=SimpleNamespace(content=None))], 
                          usage=SimpleNamespace(
                              completion_tokens=10,
                              prompt_tokens=20,
                              total_tokens=30
                          ))
    
    # Create second streaming response
    async def mock_stream_final(*args, **kwargs):
        yield MockResponse([MockChoice(delta=SimpleNamespace(content="The tool completed successfully"))])
        yield MockResponse([MockChoice(delta=SimpleNamespace(content=None))], 
                          usage=SimpleNamespace(
                              completion_tokens=5,
                              prompt_tokens=10,
                              total_tokens=15
                          ))
    
    # Mock responses
    mock_completion.side_effect = [
        mock_stream(),  # First streaming response
        # Second call after tool - simple response
        mock_stream_final()
    ]
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Please use the slow tool"))
    
    # Collect events
    tool_result_events = []
    async for event in agent.stream(thread):
        if event.type == EventType.TOOL_RESULT:
            tool_result_events.append(event)
    
    # Verify we got tool result event with duration
    assert len(tool_result_events) == 1
    tool_event = tool_result_events[0]
    
    # Verify duration was tracked and is reasonable
    duration_ms = tool_event.data.get("duration_ms", 0)
    assert duration_ms > 40  # Should be at least 40ms (allowing some margin)
    assert duration_ms < 200  # Should not be more than 200ms


@pytest.mark.asyncio
async def test_json_parsing_error_handling(mock_completion):
    """Test that JSON parsing errors are handled with specific exceptions."""
    agent = Agent(
        model_name="gpt-4o-mini",
        tools=[{
            "definition": {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "Test tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            "implementation": lambda: "success"
        }]
    )
    
    # Create tool call with invalid JSON arguments
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="test_tool",
            arguments="{invalid json"  # Invalid JSON
        )
    )
    
    # Mock response with tool call
    mock_completion.side_effect = [
        MockResponse([
            MockChoice(MockMessage("Using tool", tool_calls=[tool_call]))
        ]),
        MockResponse([
            MockChoice(MockMessage("Done"))
        ])
    ]
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Should handle gracefully without bare except
    result = await agent.run(thread)
    
    # Verify tool was still executed (JSON parse errors should be handled gracefully)
    tool_messages = [msg for msg in result.new_messages if msg.role == "tool"]
    assert len(tool_messages) == 1
    # Tool should have been called even with invalid JSON (empty args due to parse error)


@pytest.mark.asyncio
async def test_type_hints_with_overloads():
    """Test that type hints work correctly with go() method overloads."""
    agent = Agent(model_name="gpt-4o-mini")
    thread = Thread()
    
    # These type annotations should work without errors
    # (actual execution is not important for this test)
    
    # Non-streaming returns AgentResult
    async def test_non_streaming():
        result: AgentResult = await agent.run(thread)
        return result
    
    # Streaming returns AsyncGenerator[ExecutionEvent, None]
    async def test_streaming():
        events: AsyncGenerator[ExecutionEvent, None] = agent.stream(thread)
        return events
    
    # Just verify the functions can be defined without type errors
    assert callable(test_non_streaming)
    assert callable(test_streaming)


@pytest.mark.asyncio
async def test_streaming_with_error(mock_completion):
    """Test streaming handles errors gracefully."""
    # Make streaming fail partway through
    async def mock_stream_error(*args, **kwargs):
        yield MockResponse([MockChoice(delta=SimpleNamespace(content="Hello"))])
        raise Exception("Stream error")
    
    mock_completion.return_value = mock_stream_error()
    
    agent = Agent(model_name="gpt-4o-mini")
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    events = []
    async for event in agent.stream(thread):
        events.append(event)
    
    # Should have error event
    error_events = [e for e in events if e.type == EventType.EXECUTION_ERROR]
    assert len(error_events) > 0
    assert "Stream error" in error_events[0].data["message"]
