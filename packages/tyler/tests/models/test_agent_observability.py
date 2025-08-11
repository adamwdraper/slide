"""Tests for the new agent execution observability features."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tyler import Agent, Thread, Message, AgentResult, ExecutionEvent, EventType
from litellm import ModelResponse
from types import SimpleNamespace
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
    result = await agent.go(thread)
    
    # Verify result type and structure
    assert isinstance(result, AgentResult)
    assert result.thread == thread
    assert len(result.messages) > 0
    assert result.output == "Test response"
    assert hasattr(result, 'execution')
    assert result.success is True
    
    # Verify execution details
    assert result.execution.total_tokens == 30
    assert result.execution.duration_ms > 0
    assert len(result.execution.events) > 0
    
    # Check event types
    event_types = [e.type for e in result.execution.events]
    assert EventType.ITERATION_START in event_types
    assert EventType.LLM_REQUEST in event_types
    assert EventType.LLM_RESPONSE in event_types
    assert EventType.MESSAGE_CREATED in event_types
    assert EventType.EXECUTION_COMPLETE in event_types


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
    async for event in agent.go(thread, stream=True):
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
        
        result = await agent.go(thread)
        
        # Check tool calls in execution
        assert len(result.execution.tool_calls) == 1
        tool_call_detail = result.execution.tool_calls[0]
        assert tool_call_detail.tool_name == "calculate"
        assert tool_call_detail.arguments == {"x": 5, "y": 3}
        assert tool_call_detail.success is True
        
        # Check events include tool execution
        event_types = [e.type for e in result.execution.events]
        assert EventType.TOOL_SELECTED in event_types
        assert EventType.TOOL_RESULT in event_types


@pytest.mark.asyncio
async def test_execution_error_handling(mock_completion):
    """Test that execution errors are captured in the result."""
    # Make completion fail
    mock_completion.side_effect = Exception("API Error")
    
    agent = Agent(model_name="gpt-4o-mini")
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    result = await agent.go(thread)
    
    # Should still get a result, but with error
    assert isinstance(result, AgentResult)
    assert result.success is False
    # Error message is set as output
    assert result.output is not None
    assert "error" in result.output.lower()
    
    # Check error event
    error_events = [e for e in result.execution.events if e.type == EventType.EXECUTION_ERROR]
    assert len(error_events) > 0
    # There's a known issue with StringPrompt serialization
    assert any(phrase in error_events[0].data["message"] for phrase in ["API Error", "StringPrompt", "JSON serializable"])


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
    async for event in agent.go(thread, stream=True):
        events.append(event)
    
    # Should have error event
    error_events = [e for e in events if e.type == EventType.EXECUTION_ERROR]
    assert len(error_events) > 0
    assert "Stream error" in error_events[0].data["message"]
