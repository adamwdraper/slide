"""Tests for Agent vercel_objects streaming mode."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from tyler import Agent, Thread, Message
from types import SimpleNamespace
from litellm import ModelResponse


class MockDelta:
    def __init__(self, content=None, tool_calls=None, reasoning_content=None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning_content = reasoning_content


class MockChoiceDelta:
    def __init__(self, delta):
        self.delta = delta


class MockChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


def create_streaming_chunk(content=None, tool_calls=None, role="assistant", usage=None, reasoning_content=None):
    """Helper function to create streaming chunks with proper structure"""
    delta = {"role": role}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    if reasoning_content is not None:
        delta["reasoning_content"] = reasoning_content
    delta_obj = SimpleNamespace(**delta)
    chunk = {
        "id": "chunk-id",
        "choices": [{
            "index": 0,
            "delta": delta_obj
        }]
    }
    if usage:
        chunk["usage"] = usage
    return ModelResponse(**chunk)


@pytest.mark.asyncio
async def async_generator(chunks):
    for chunk in chunks:
        yield chunk


@pytest.mark.asyncio
async def test_vercel_objects_stream_basic_response():
    """Test vercel_objects streaming mode with basic text response."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" there!"),
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        chunk_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            chunk_events.append(chunk)
        
        # Should have dict objects, not SSE strings
        assert all(isinstance(c, dict) for c in chunk_events)
        
        # Should start with message start event
        assert chunk_events[0]["type"] == "start"
        assert "messageId" in chunk_events[0]
        
        # Should have text events
        all_types = [c["type"] for c in chunk_events]
        
        assert "text-start" in all_types
        assert "text-delta" in all_types
        assert "text-end" in all_types
        assert "finish" in all_types
        
        # Should NOT have [DONE] marker (that's only for SSE mode)
        assert "data: [DONE]\n\n" not in chunk_events


@pytest.mark.asyncio
async def test_vercel_objects_stream_text_content():
    """Test that vercel_objects stream includes text content in deltas."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" world!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        text_deltas = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if chunk["type"] == "text-delta":
                text_deltas.append(chunk["delta"])
        
        assert text_deltas == ["Hello", " world!"]


@pytest.mark.asyncio
async def test_vercel_objects_step_stream_basic_response():
    """step_stream(mode='vercel_objects') yields step-local chunks without message-level markers."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))

    chunks = [
        create_streaming_chunk(content="Hi"),
        create_streaming_chunk(content="!"),
    ]

    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"

    with patch.object(agent, "_get_completion") as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)

        chunk_events = []
        async for chunk in agent.step_stream(thread, mode="vercel_objects"):
            chunk_events.append(chunk)

        assert all(isinstance(c, dict) for c in chunk_events)

        # First event should be step start
        assert chunk_events[0]["type"] == "start-step"

        # Should include text events and finish-step
        event_types = [c["type"] for c in chunk_events]

        assert "text-start" in event_types
        assert "text-delta" in event_types
        assert "text-end" in event_types
        assert "finish-step" in event_types

        # step_stream should not emit message-level start/finish
        assert "start" not in event_types
        assert "finish" not in event_types


@pytest.mark.asyncio
async def test_vercel_objects_stream_with_reasoning():
    """Test vercel_objects streaming with reasoning/thinking tokens."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Think about this"))
    
    # Create chunks with reasoning content
    chunks = [
        create_streaming_chunk(reasoning_content="Let me think..."),
        create_streaming_chunk(reasoning_content=" about this."),
        create_streaming_chunk(content="The answer is 42."),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        event_types = []
        reasoning_deltas = []
        text_deltas = []
        
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            event_types.append(chunk["type"])
            
            if chunk["type"] == "reasoning-delta":
                reasoning_deltas.append(chunk["delta"])
            elif chunk["type"] == "text-delta":
                text_deltas.append(chunk["delta"])
        
        # Should have reasoning events
        assert "reasoning-start" in event_types
        assert "reasoning-delta" in event_types
        assert "reasoning-end" in event_types
        
        # Should have text events after reasoning
        assert "text-start" in event_types
        assert "text-delta" in event_types
        assert "text-end" in event_types
        
        # Check content
        assert reasoning_deltas == ["Let me think...", " about this."]
        assert text_deltas == ["The answer is 42."]


@pytest.mark.asyncio
async def test_vercel_objects_stream_with_tool_calls():
    """Test vercel_objects streaming with tool calls."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Get the weather"))
    
    chunks = [
        create_streaming_chunk(content="Let me check."),
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "San Francisco"}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "temperature": 72,
            "condition": "sunny"
        })
        
        event_types = []
        tool_events = []
        
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            event_types.append(chunk["type"])
            
            if chunk["type"].startswith("tool-"):
                tool_events.append(chunk)
        
        # Should have tool events
        assert "tool-input-start" in event_types
        assert "tool-input-available" in event_types
        assert "tool-output-available" in event_types
        
        # Verify tool input event content
        tool_input_start = next(e for e in tool_events if e["type"] == "tool-input-start")
        assert tool_input_start["toolCallId"] == "call_123"
        assert tool_input_start["toolName"] == "get_weather"
        
        tool_input_avail = next(e for e in tool_events if e["type"] == "tool-input-available")
        assert tool_input_avail["input"] == {"city": "San Francisco"}
        
        tool_output = next(e for e in tool_events if e["type"] == "tool-output-available")
        assert "result" in tool_output["output"]


@pytest.mark.asyncio
async def test_vercel_objects_stream_error_handling():
    """Test vercel_objects streaming error handling."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test error"))
    
    error = Exception("Test error occurred")
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.side_effect = error
        
        error_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if chunk["type"] == "error":
                error_events.append(chunk)
        
        # Should have an error event
        assert len(error_events) >= 1
        assert "errorText" in error_events[0]


@pytest.mark.asyncio
async def test_vercel_objects_stream_tool_error():
    """Test vercel_objects streaming with tool execution error."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Use a tool"))
    
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_456",
            "type": "function",
            "function": {
                "name": "failing_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool failed"))
        
        tool_error_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if chunk["type"] == "tool-output-error":
                tool_error_events.append(chunk)
        
        # Should have tool error event
        assert len(tool_error_events) >= 1
        assert tool_error_events[0]["toolCallId"] == "call_456"


@pytest.mark.asyncio
async def test_vercel_objects_stream_finish_event():
    """Test vercel_objects streaming finish event has correct finish reason."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi there!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        finish_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if chunk["type"] == "finish":
                finish_events.append(chunk)
        
        assert len(finish_events) == 1
        assert finish_events[0]["finishReason"] == "stop"


@pytest.mark.asyncio
async def test_vercel_objects_stream_no_sse_wrapping():
    """Test that vercel_objects mode yields dicts, not SSE strings."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Response"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        chunk_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            chunk_events.append(chunk)
        
        # All chunks should be dicts
        for chunk in chunk_events:
            assert isinstance(chunk, dict)
            assert "type" in chunk
            # Should NOT be SSE format
            assert not isinstance(chunk, str)


@pytest.mark.asyncio
async def test_vercel_objects_stream_message_id_consistency():
    """Test that message ID is consistent in start event."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        message_ids = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if "messageId" in chunk:
                message_ids.append(chunk["messageId"])
        
        # Should have at least one message ID in start event
        assert len(message_ids) >= 1
        # Message ID should start with msg_
        assert message_ids[0].startswith("msg_")


@pytest.mark.asyncio
async def test_vercel_objects_mode_string_literal():
    """Test that mode='vercel_objects' is a valid option."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        # Should not raise ValueError
        chunk_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            chunk_events.append(chunk)
        
        # Should have yielded dict chunks
        assert len(chunk_events) > 0
        assert all(isinstance(c, dict) for c in chunk_events)


@pytest.mark.asyncio
async def test_vercel_objects_chunk_format_matches_marimo():
    """Test that chunk format is compatible with marimo's expectations."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = [
        create_streaming_chunk(content="Hi!"),
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        chunk_events = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            chunk_events.append(chunk)
        
        # Verify chunk format matches marimo's expected format
        # marimo expects: {"type": "text-delta", "id": "...", "delta": "..."}
        text_deltas = [c for c in chunk_events if c["type"] == "text-delta"]
        assert len(text_deltas) > 0
        
        for td in text_deltas:
            assert "type" in td
            assert "id" in td
            assert "delta" in td
            assert td["type"] == "text-delta"


@pytest.mark.asyncio
async def test_vercel_objects_camel_case_keys():
    """Test that chunk keys use camelCase as required by Vercel SDK."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Get weather"))
    
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_789",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "NYC"}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value="sunny")
        
        tool_chunks = []
        async for chunk in agent.stream(thread, mode="vercel_objects"):
            if chunk["type"].startswith("tool-"):
                tool_chunks.append(chunk)
        
        # Verify camelCase keys (not snake_case)
        tool_input = next((c for c in tool_chunks if c["type"] == "tool-input-start"), None)
        assert tool_input is not None
        assert "toolCallId" in tool_input  # camelCase
        assert "toolName" in tool_input    # camelCase
        assert "tool_call_id" not in tool_input  # NOT snake_case
        assert "tool_name" not in tool_input     # NOT snake_case
