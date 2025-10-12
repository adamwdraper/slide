import pytest
from unittest.mock import patch, MagicMock, AsyncMock, create_autospec
from tyler import Agent, Thread, ThreadStore, Message, ExecutionEvent, EventType
from tyler.utils.tool_runner import tool_runner
from litellm import ModelResponse
import json
from types import SimpleNamespace
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MockDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class MockChoiceDelta:
    def __init__(self, delta):
        self.delta = delta


class MockChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage

def create_streaming_chunk(content=None, tool_calls=None, role="assistant", usage=None):
    """Helper function to create streaming chunks with proper structure"""
    delta = {"role": role}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
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

@pytest.fixture
def mock_litellm():
    mock = AsyncMock()
    mock.return_value = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    
    with patch('litellm.acompletion', mock), \
         patch('tyler.models.agent.acompletion', mock):
        yield mock

@pytest.fixture
def agent(mock_litellm):
    with patch('tyler.models.agent.tool_runner', create_autospec(tool_runner)):
        agent = Agent(
            model_name="gpt-4.1",
            temperature=0.7,
            purpose="test purpose",
            stream=True
        )
        # Mock the weave operation
        mock_get_completion = AsyncMock()
        mock_get_completion.call = AsyncMock()
        agent._get_completion = mock_get_completion
        return agent

@pytest.mark.asyncio
async def async_generator(chunks):
    for chunk in chunks:
        yield chunk

@pytest.mark.asyncio
async def test_go_stream_basic_response():
    """Test streaming with basic response (no tool calls)"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Mock the completion response
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" there!")
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify the updates
        assert len(updates) >= 3  # At least content chunks and complete
        assert any(event.type == EventType.LLM_STREAM_CHUNK and event.data.get('content_chunk') == "Hello" for event in updates)
        assert any(event.type == EventType.LLM_STREAM_CHUNK and event.data.get('content_chunk') == " there!" for event in updates)
        assert any(event.type == EventType.MESSAGE_CREATED for event in updates)
        assert any(event.type == EventType.EXECUTION_COMPLETE for event in updates)

@pytest.mark.asyncio
async def test_go_stream_with_tool_calls():
    """Test streaming with tool calls"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Translate 'hello' to Spanish"))
    
    # Mock the completion response with tool calls
    chunks = [
        create_streaming_chunk(content="I'll help translate that."),
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "translate",
                "arguments": '{"text": "hello", "target_language": "Spanish"}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Return a dict that will be stringified
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "translate",
            "content": "Translation: hola"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify the updates
        assert len(updates) >= 4  # At least content chunk, tool message, and complete
        assert any(event.type == EventType.LLM_STREAM_CHUNK and 
                  event.data.get('content_chunk') == "I'll help translate that." for event in updates)
        # Tool message content should be the stringified dict
        assert any(event.type == EventType.MESSAGE_CREATED and 
                  event.data.get('message') and event.data['message'].content == "{'name': 'translate', 'content': 'Translation: hola'}" for event in updates)
        assert any(event.type == EventType.MESSAGE_CREATED for event in updates)
        assert any(event.type == EventType.EXECUTION_COMPLETE for event in updates)

@pytest.mark.asyncio
async def test_go_stream_error_handling():
    """Test error handling in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test error"))

    # Mock an error during completion
    error = Exception("Test error")

    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.side_effect = error

        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)

        # Verify error handling - just check for error type without verifying exact message
        assert any(event.type == EventType.EXECUTION_ERROR for event in updates)

@pytest.mark.asyncio
async def test_go_stream_max_iterations():
    """Test max iterations handling in streaming mode"""
    agent = Agent(stream=True, max_tool_iterations=0)  # Set to 0 to trigger immediately
    thread = Thread()
    thread.add_message(Message(role="user", content="Test max iterations"))
    
    # Mock chunks that will trigger tool calls repeatedly
    chunks_with_tools = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    # Create a counter to return different responses each time
    call_count = 0
    async def mock_completion(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Always return tool calls to force multiple iterations
        return (async_generator(chunks_with_tools), mock_weave_call)
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.side_effect = mock_completion
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify max iterations message or limit event
        assert any(event.type == EventType.ITERATION_LIMIT for event in updates) or \
               any(event.type == EventType.MESSAGE_CREATED and 
                  event.data.get('message') and "Maximum tool iteration count reached" in event.data['message'].content for event in updates)

@pytest.mark.asyncio
async def test_go_stream_invalid_json_handling():
    """Test handling of invalid JSON in tool arguments - should handle gracefully"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid JSON"))
    
    # Mock chunks with invalid JSON in tool arguments
    chunks = [
        create_streaming_chunk(content="I'll use the tool"),
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{"invalid": "json"'  # Missing closing brace
            }
        }])
    ]
    
    # Add a second completion response after tool execution
    chunks2 = [
        create_streaming_chunk(content="Done")
    ]
    
    mock_weave_call = MagicMock()
    
    # Mock tool execution to return success
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.side_effect = [
            (async_generator(chunks), mock_weave_call),
            (async_generator(chunks2), mock_weave_call)
        ]
        
        with patch('tyler.utils.tool_runner.tool_runner.execute_tool_call') as mock_tool_exec:
            mock_tool_exec.return_value = "Tool executed successfully"
            
            updates = []
            async for event in agent.go(thread, stream=True):
                updates.append(event)
            
            # Verify that tool was selected with empty args due to JSON parse error
            tool_selected_events = [e for e in updates if e.type == EventType.TOOL_SELECTED]
            assert len(tool_selected_events) > 0
            # The arguments should be empty dict due to parse error
            assert tool_selected_events[0].data['arguments'] == {}
            
            # Verify tool was executed (no error thrown)
            assert any(event.type == EventType.TOOL_RESULT for event in updates)
            
            # Verify no execution errors (graceful handling)
            assert not any(event.type == EventType.EXECUTION_ERROR for event in updates)

@pytest.mark.asyncio
async def test_go_stream_metrics_tracking():
    """Test that metrics are properly tracked in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4.1")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test metrics"))
    
    # Mock chunks with usage info
    chunks = [
        create_streaming_chunk(content="Hello"),
        create_streaming_chunk(content=" world", usage={
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the assistant message update
        assistant_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message')
        )
        
        # Verify metrics are present and correct
        assert "metrics" in assistant_message.model_dump()
        assert assistant_message.metrics["model"] == "gpt-4.1"
        assert "timing" in assistant_message.metrics
        assert "started_at" in assistant_message.metrics["timing"]
        assert "ended_at" in assistant_message.metrics["timing"]
        assert "latency" in assistant_message.metrics["timing"]
        assert assistant_message.metrics["usage"] == {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
        assert assistant_message.metrics["weave_call"]["id"] == "test-weave-id"
        assert assistant_message.metrics["weave_call"]["ui_url"] == "https://weave.ui/test"

@pytest.mark.asyncio
async def test_go_stream_tool_metrics():
    """Test that tool execution metrics are tracked in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4.1")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test tool metrics"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }], usage={
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the tool message update (not assistant message)
        tool_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].role == 'tool'
        )
        
        # Verify tool metrics are present and correct with actual values
        assert "metrics" in tool_message.model_dump()
        assert "timing" in tool_message.metrics
        assert tool_message.metrics["timing"]["started_at"] is not None
        assert tool_message.metrics["timing"]["ended_at"] is not None
        assert "latency" in tool_message.metrics["timing"]  # Just verify latency exists, don't check value
        # Tool message content should be stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"

@pytest.mark.asyncio
async def test_go_stream_multiple_messages_metrics():
    """Test metrics tracking across multiple messages in streaming mode"""
    agent = Agent(stream=True, model_name="gpt-4.1")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test multiple messages"))
    
    # First response with tool call
    first_chunks = [
        create_streaming_chunk(content="Let me help", tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    # Second response after tool execution
    second_chunks = [
        create_streaming_chunk(content="Here's the result", usage={
            "completion_tokens": 15,
            "prompt_tokens": 25,
            "total_tokens": 40
        })
    ]
    
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.side_effect = [
            (async_generator(first_chunks), mock_weave_call),
            (async_generator(second_chunks), mock_weave_call)
        ]
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Get all assistant and tool messages
        messages = [
            event.data['message'] for event in updates
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message')
        ]

        # Verify each message has proper metrics with actual values
        for message in messages:
            assert "metrics" in message.model_dump()
            # Only check model name for assistant messages
            if message.role == "assistant":
                assert message.metrics["model"] == "gpt-4.1"
            assert "timing" in message.metrics
            
            if message.role == "assistant":
                assert "usage" in message.metrics
                if hasattr(message, 'content') and message.content == "Here's the result":
                    # Check specific usage values for the second message
                    assert message.metrics["usage"] == {
                        "completion_tokens": 15,
                        "prompt_tokens": 25,
                        "total_tokens": 40
                    }
                assert "weave_call" in message.metrics
                assert message.metrics["weave_call"]["id"] == "test-weave-id"
                assert message.metrics["weave_call"]["ui_url"] == "https://weave.ui/test"
            
            if message.role == "tool":
                assert message.metrics["timing"]["started_at"] is not None
                assert message.metrics["timing"]["ended_at"] is not None
                assert "latency" in message.metrics["timing"]  # Just verify latency exists, don't check value

@pytest.mark.asyncio
async def test_go_stream_object_format_tool_calls():
    """Test streaming with tool calls in object format rather than dict format"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test object format tool calls"))

    # Create tool call in proper format
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param": "value"}'
        }
    }

    # Create a chunk with the tool call
    chunk = create_streaming_chunk(tool_calls=[tool_call])

    mock_weave_call = MagicMock()

    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })

        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)

        # Verify tool call was processed correctly - just check for tool message type
        assert any(event.type == EventType.MESSAGE_CREATED for event in updates)

@pytest.mark.asyncio
async def test_go_stream_object_format_tool_call_updates():
    """Test streaming with tool call updates in object format"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test object format tool call updates"))
    
    # First chunk with initial tool call
    initial_tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="test_tool",
            arguments='{"param": '
        )
    )
    
    # Second chunk with continuation of arguments (split JSON across deltas)
    continuation_tool_call = SimpleNamespace(
        function=SimpleNamespace(
            arguments='"value"}'
        )
    )
    
    chunks = [
        create_streaming_chunk(tool_calls=[initial_tool_call]),
        create_streaming_chunk(tool_calls=[continuation_tool_call])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the assistant message with tool calls
        assistant_message = next(
            (event.data['message'] for event in updates 
             if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].tool_calls),
            None
        )
        
        # Verify arguments were concatenated and parsed into {}
        assert assistant_message is not None
        assert assistant_message.tool_calls[0]["function"]["arguments"] == '{"param": "value"}'

@pytest.mark.asyncio
async def test_go_stream_dict_arguments_in_delta():
    """Streaming delta provides arguments as a dict; ensure selection uses dict but execution uses JSON string."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test dict args"))

    arg_dict = {"a": 1, "b": "x"}
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_dict",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": arg_dict  # dict, not string
            }
        }])
    ]

    mock_weave_call = MagicMock()

    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={"ok": True})

        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)

        # TOOL_SELECTED should carry dict arguments
        tool_selected = next(e for e in updates if e.type == EventType.TOOL_SELECTED)
        assert tool_selected.data["arguments"] == arg_dict

        # Execution should receive normalized wrapper with JSON string arguments
        called_arg = mock_tool_runner.execute_tool_call.call_args[0][0]
        assert isinstance(getattr(called_arg.function, 'arguments', None), str)
        assert json.loads(called_arg.function.arguments) == arg_dict

@pytest.mark.asyncio
async def test_go_stream_dict_format_tool_call_updates():
    """Split JSON arguments across multiple dict-format deltas should concatenate and parse."""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test dict format split"))

    first = {
        "id": "split1",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"x": '
        }
    }
    second = {
        # continuation without id
        "function": {
            "arguments": '1, "y": "z"}'
        }
    }

    chunks = [
        create_streaming_chunk(tool_calls=[first]),
        create_streaming_chunk(tool_calls=[second])
    ]

    mock_weave_call = MagicMock()

    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={"ok": True})

        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)

        # Assistant message should include reconstructed tool_calls
        assistant_msg = next(
            e.data['message'] for e in updates
            if e.type == EventType.MESSAGE_CREATED and e.data.get('message') and e.data['message'].role == 'assistant'
        )
        args_str = assistant_msg.tool_calls[0]['function']['arguments']
        assert args_str == '{"x": 1, "y": "z"}'
        # TOOL_SELECTED event should contain parsed dict
        tool_selected = next(e for e in updates if e.type == EventType.TOOL_SELECTED)
        assert tool_selected.data['arguments'] == {"x": 1, "y": "z"}

@pytest.mark.asyncio
async def test_go_stream_missing_tool_call_id():
    """Test handling of tool calls with missing ID"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test missing tool call ID"))
    
    # Create a tool call with missing ID
    invalid_tool_call = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{}'
        }
    }
    
    chunk = create_streaming_chunk(tool_calls=[invalid_tool_call])
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify no tool calls were processed (since ID was missing)
        assistant_messages = [
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message')
        ]
        
        # The assistant message should not have tool calls
        assert all(not getattr(msg, 'tool_calls', None) for msg in assistant_messages)

@pytest.mark.asyncio
async def test_go_stream_empty_arguments():
    """Test handling of empty arguments in tool calls"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test empty arguments"))
    
    # Mock chunks with empty arguments
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": ""  # Empty arguments
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the tool message
        tool_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].role == 'tool'
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"

@pytest.mark.asyncio
async def test_go_stream_thread_store_save():
    """Test that thread is saved during streaming"""
    # Create mock thread store
    mock_thread_store = MagicMock(spec=ThreadStore)
    mock_thread_store.save = AsyncMock(return_value=None)
    # Keep track of saved thread state
    saved_thread_data = {}
    
    async def mock_save(thread):
        # Simulate saving by storing messages using model_dump(mode='json')
        # to ensure datetime is stored as string, like a real DB would
        saved_thread_data[thread.id] = [
            msg.model_dump(mode='json') for msg in thread.messages
        ]
        
    async def mock_get(thread_id):
        if thread_id in saved_thread_data:
            # Reconstruct thread from saved data
            reconstructed_messages = []
            for msg_data in saved_thread_data[thread_id]:
                # --- Key Change: Parse timestamp string back to datetime ---
                if 'timestamp' in msg_data and isinstance(msg_data['timestamp'], str):
                    try:
                        # Ensure the string is parsed correctly into a datetime object
                        msg_data['timestamp'] = datetime.fromisoformat(msg_data['timestamp'])
                    except ValueError:
                        # Handle potential parsing errors, maybe log or use a default
                        logger.error(f"Failed to parse timestamp: {msg_data['timestamp']}")
                        # Optionally set a default or re-raise, depending on desired test behavior
                        # For now, let's remove it to avoid crashing the test if parsing fails
                        del msg_data['timestamp'] 
                # --- End Key Change ---
                
                # Recreate message, handling potential missing timestamp if parsing failed
                try:
                    reconstructed_messages.append(Message(**msg_data))
                except Exception as e:
                     logger.error(f"Failed to reconstruct message: {msg_data} with error {e}")
                     # Skip this message if reconstruction fails
                     continue
                     
            return Thread(
                id=thread_id, 
                messages=reconstructed_messages
            )
        return None
        
    mock_thread_store.save = mock_save
    mock_thread_store.get = mock_get
    
    # Create agent with the mock thread store directly
    agent = Agent(stream=True, thread_store=mock_thread_store)
    thread = Thread(id="test-thread")
    # Initial 'save' to put the empty thread in our mock store
    await mock_thread_store.save(thread)
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify thread was saved with messages
        saved_thread = await mock_thread_store.get(thread.id)
        assert saved_thread is not None
        # Check that messages were added before saving
        # We expect at least the assistant message and the tool message
        assert len(saved_thread.messages) >= 2, f"Expected >= 2 messages, found {len(saved_thread.messages)}"

@pytest.mark.asyncio
async def test_go_stream_reset_iteration_count():
    """Test that iteration count is reset after streaming"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test reset iteration count"))
    
    # Set iteration count to non-zero
    agent._iteration_count = 5
    
    # Simple response with no tool calls
    chunk = create_streaming_chunk(content="Simple response")
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion:
        mock_get_completion.call.return_value = (async_generator([chunk]), mock_weave_call)
        
        # Process all updates
        async for _ in agent.go(thread, stream=True):
            pass
        
        # Verify iteration count was reset
        assert agent._iteration_count == 0

@pytest.mark.asyncio
async def test_go_stream_invalid_response():
    """Test handling of invalid response from completion call"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid response"))
    
    # Mock step to return None instead of a valid response
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (None, {})
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Verify error was yielded
        assert any(event.type == EventType.EXECUTION_ERROR and 
                  "No response received" in str(event.data.get('message', '')) for event in updates)

@pytest.mark.asyncio
async def test_go_stream_tool_call_with_files():
    """Test handling of tool calls that return files in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test file handling"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    # Create test file data
    test_file = {
        "filename": "test.txt",
        "content": "test content",
        "mime_type": "text/plain"
    }
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Return tuple of content and files
        mock_tool_runner.execute_tool_call = AsyncMock(return_value=(
            {"name": "test_tool", "content": "File generated"},
            [test_file]
        ))
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the tool message
        tool_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].role == 'tool'
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'File generated'}"
        # Verify file attachment
        assert len(tool_message.attachments) == 1
        assert tool_message.attachments[0].filename == "test.txt"
        assert tool_message.attachments[0].content == "test content"
        assert tool_message.attachments[0].mime_type == "text/plain"

@pytest.mark.asyncio
async def test_go_stream_tool_call_with_attributes():
    """Test handling of tool calls with attributes"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test tool attributes"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Mock tool runner to return attributes
        mock_tool_runner.get_tool_attributes.return_value = {
            "type": "test",
            "category": "utility"
        }
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool result"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the tool message
        tool_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].role == 'tool'
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'test_tool', 'content': 'Tool result'}"
        # Verify tool attributes were used
        assert mock_tool_runner.get_tool_attributes.called

@pytest.mark.asyncio
async def test_go_stream_interrupt_tool():
    """Test handling of interrupt tools in streaming mode"""
    agent = Agent(stream=True)
    thread = Thread()
    thread.add_message(Message(role="user", content="Test interrupt tool"))
    
    # Mock chunks with tool call
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "interrupt_tool",
                "arguments": '{}'
            }
        }])
    ]
    
    mock_weave_call = MagicMock()
    
    with patch.object(agent, '_get_completion') as mock_get_completion, \
         patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_get_completion.call.return_value = (async_generator(chunks), mock_weave_call)
        # Mock tool runner to return interrupt type
        mock_tool_runner.get_tool_attributes.return_value = {
            "type": "interrupt"
        }
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "interrupt_tool",
            "content": "Interrupting execution"
        })
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Find the tool message
        tool_message = next(
            event.data['message'] for event in updates 
            if event.type == EventType.MESSAGE_CREATED and event.data.get('message') and event.data['message'].role == 'tool'
        )
        
        # Verify tool message content is stringified dict
        assert tool_message.content == "{'name': 'interrupt_tool', 'content': 'Interrupting execution'}"
        # Verify tool attributes were used
        assert mock_tool_runner.get_tool_attributes.called
        # Verify we got a complete update
        assert any(event.type == EventType.EXECUTION_COMPLETE for event in updates)


@pytest.mark.asyncio
async def test_go_stream_general_exception_handling():
    """Test general exception handling in go_stream"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock step to raise an exception
    with patch.object(agent, 'step') as mock_step:
        mock_step.side_effect = RuntimeError("Streaming failed")
        
        updates = []
        try:
            async for event in agent.go(thread, stream=True):
                updates.append(event)
        except Exception:
            pass  # go_stream may not raise, depending on implementation
        
        # Should have yielded an error update
        error_updates = [u for u in updates if u.type == EventType.EXECUTION_ERROR]
        assert len(error_updates) >= 1


@pytest.mark.asyncio
async def test_go_stream_tool_calls():
    """Test tool calls in streaming"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create mock streaming response with tool calls
    chunks = [
        create_streaming_chunk(tool_calls=[{
            "index": 0,
            "id": "1",
            "type": "function",
            "function": {"name": "test_tool", "arguments": '{"arg": "value"}'}
        }])
    ]
    
    # Add a final chunk to signal end
    chunks.append(create_streaming_chunk())
    
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_completion.return_value = async_generator(chunks)
        
        with patch.object(tool_runner, 'execute_tool_call') as mock_execute:
            mock_execute.return_value = "Tool result"
            
            updates = []
            async for event in agent.go(thread, stream=True):
                updates.append(event)
            
            # Should have tool-related updates
            tool_messages = [u for u in updates if u.type == EventType.MESSAGE_CREATED]
            assert len(tool_messages) >= 1


@pytest.mark.asyncio
async def test_go_stream_multiple_tool_calls():
    """Test handling of multiple tool calls in streaming"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create streaming response with multiple tool calls
    chunks = [
        create_streaming_chunk(tool_calls=[
            {"index": 0, "id": "1", "type": "function", "function": {"name": "tool1", "arguments": "{}"}},
            {"index": 1, "id": "2", "type": "function", "function": {"name": "tool2", "arguments": "{}"}}
        ])
    ]
    chunks.append(create_streaming_chunk())  # End chunk
    
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_completion.return_value = async_generator(chunks)
        
        # Mock tool execution
        call_count = 0
        async def mock_execute(tool_call):
            nonlocal call_count
            call_count += 1
            return f"Result {call_count}"
        
        with patch.object(tool_runner, 'execute_tool_call', side_effect=mock_execute):
            updates = []
            async for event in agent.go(thread, stream=True):
                updates.append(event)
            
            # Should have tool messages for both calls
            tool_messages = [u for u in updates if u.type == EventType.MESSAGE_CREATED]
            assert len(tool_messages) >= 2  # At least both tools should produce messages





@pytest.mark.asyncio
async def test_go_stream_cache_clearing():
    """Test that tool attributes cache is cleared at start of streaming"""
    agent = Agent(name="Tyler")
    
    # Pre-populate cache
    agent._tool_attributes_cache['existing_tool'] = {'type': 'old'}
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock step to return simple response
    chunks = [
        MockChunk([MockChoiceDelta(MockDelta(content="Response"))]),
        MockChunk([MockChoiceDelta(MockDelta())])
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        # Collect updates
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Cache should have been cleared
        assert 'existing_tool' not in agent._tool_attributes_cache


@pytest.mark.asyncio
async def test_go_stream_step_returns_none():
    """Test handling when step returns None for streaming response"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (None, {"model": "gpt-4"})
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Should have error update
        error_updates = [u for u in updates if u.type == EventType.EXECUTION_ERROR]
        assert len(error_updates) == 1
        assert "No response received" in error_updates[0].data.get('message', '')


@pytest.mark.asyncio
async def test_go_stream_chunk_without_choices():
    """Test handling chunks without choices"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create chunks, some without choices
    chunks = [
        MockChunk([]),  # No choices
        MockChunk([MockChoiceDelta(MockDelta(content="Hello"))]),
        MockChunk(None),  # None choices
        MockChunk([MockChoiceDelta(MockDelta(content=" world"))]),
        MockChunk([MockChoiceDelta(MockDelta())])  # End
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Should only have content from valid chunks
        content_chunks = [u.data.get('content_chunk') for u in updates if u.type == EventType.LLM_STREAM_CHUNK]
        assert content_chunks == ["Hello", " world"]


@pytest.mark.asyncio
async def test_go_stream_usage_metrics_from_final_chunk():
    """Test that usage metrics are extracted from the final chunk"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create chunks with usage in final chunk
    usage = SimpleNamespace(
        completion_tokens=10,
        prompt_tokens=5,
        total_tokens=15
    )
    
    chunks = [
        MockChunk([MockChoiceDelta(MockDelta(content="Response"))]),
        MockChunk([MockChoiceDelta(MockDelta())], usage=usage)  # Final chunk with usage
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
                # Get the assistant message
        assistant_msg = next(
            u.data['message'] for u in updates
            if u.type == EventType.MESSAGE_CREATED and u.data.get('message')
        )
        
        # Should have usage metrics from final chunk
        assert assistant_msg.metrics["usage"]["completion_tokens"] == 10
        assert assistant_msg.metrics["usage"]["prompt_tokens"] == 5
        assert assistant_msg.metrics["usage"]["total_tokens"] == 15


# ========== New Tests for Raw Streaming Mode ==========

@pytest.mark.asyncio
async def test_invalid_stream_value_raises_error():
    """Test that invalid stream parameter values raise ValueError"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Test with invalid string value
    with pytest.raises(ValueError, match="Invalid stream value"):
        async for _ in agent.go(thread, stream="invalid"):
            pass


@pytest.mark.asyncio
async def test_stream_events_explicit():
    """Test that stream='events' works the same as stream=True"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    chunks = [
        MockChunk([MockChoiceDelta(MockDelta(content="Hello"))]),
        MockChunk([MockChoiceDelta(MockDelta(content=" world"))]),
        MockChunk([MockChoiceDelta(MockDelta())], usage=SimpleNamespace(
            completion_tokens=5, prompt_tokens=10, total_tokens=15
        ))
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        updates = []
        async for event in agent.go(thread, stream="events"):
            updates.append(event)
        
        # Should yield ExecutionEvent objects
        assert all(isinstance(u, ExecutionEvent) for u in updates)
        
        # Should have LLM_STREAM_CHUNK events
        stream_chunks = [u for u in updates if u.type == EventType.LLM_STREAM_CHUNK]
        assert len(stream_chunks) == 2
        assert stream_chunks[0].data["content_chunk"] == "Hello"
        assert stream_chunks[1].data["content_chunk"] == " world"


@pytest.mark.asyncio
async def test_raw_mode_yields_chunks_with_openai_fields():
    """Test that stream='raw' yields raw LiteLLM chunks with OpenAI-compatible fields"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create chunks with OpenAI-compatible structure
    chunks = [
        {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {"content": "Hello"},
                "finish_reason": None
            }]
        },
        {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {"content": " world"},
                "finish_reason": None
            }]
        }
    ]
    
    async def mock_stream():
        for chunk_dict in chunks:
            yield ModelResponse(**chunk_dict)
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        raw_chunks = []
        async for chunk in agent.go(thread, stream="raw"):
            raw_chunks.append(chunk)
        
        # Should NOT be ExecutionEvent objects
        assert not any(isinstance(c, ExecutionEvent) for c in raw_chunks)
        
        # Should have OpenAI-compatible fields
        assert len(raw_chunks) == 2
        assert hasattr(raw_chunks[0], 'id')
        assert hasattr(raw_chunks[0], 'object')
        assert hasattr(raw_chunks[0], 'created')
        assert hasattr(raw_chunks[0], 'model')
        assert hasattr(raw_chunks[0], 'choices')
        assert raw_chunks[0].choices[0].delta.content == "Hello"
        assert raw_chunks[1].choices[0].delta.content == " world"


@pytest.mark.asyncio
async def test_raw_mode_includes_usage_in_final_chunk():
    """Test that stream='raw' includes usage information in the final chunk"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    usage = SimpleNamespace(
        completion_tokens=10,
        prompt_tokens=5,
        total_tokens=15
    )
    
    chunks = [
        MockChunk([MockChoiceDelta(MockDelta(content="Response"))]),
        MockChunk([MockChoiceDelta(MockDelta())], usage=usage)
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        raw_chunks = []
        async for chunk in agent.go(thread, stream="raw"):
            raw_chunks.append(chunk)
        
        # Final chunk should have usage
        assert hasattr(raw_chunks[-1], 'usage')
        assert raw_chunks[-1].usage.completion_tokens == 10
        assert raw_chunks[-1].usage.prompt_tokens == 5
        assert raw_chunks[-1].usage.total_tokens == 15


@pytest.mark.asyncio
async def test_raw_mode_tool_call_deltas():
    """Test that stream='raw' passes through tool call deltas unmodified"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Create chunks with tool call deltas
    chunks = [
        {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": ""}
                    }]
                },
                "finish_reason": None
            }]
        },
        {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "function": {"arguments": '{"location"'}
                    }]
                },
                "finish_reason": None
            }]
        },
        {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_calls": [{
                        "function": {"arguments": ': "Chicago"}'}
                    }]
                },
                "finish_reason": None
            }]
        }
    ]
    
    async def mock_stream():
        for chunk_dict in chunks:
            yield ModelResponse(**chunk_dict)
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        raw_chunks = []
        async for chunk in agent.go(thread, stream="raw"):
            raw_chunks.append(chunk)
        
        # Should have tool call deltas in raw format
        assert len(raw_chunks) == 3
        assert hasattr(raw_chunks[0].choices[0].delta, 'tool_calls')
        assert raw_chunks[0].choices[0].delta.tool_calls[0]["id"] == "call_123"
        assert raw_chunks[0].choices[0].delta.tool_calls[0]["function"]["name"] == "get_weather"


@pytest.mark.asyncio
async def test_stream_true_backward_compatibility():
    """Test that stream=True still works as before (backward compatibility)"""
    agent = Agent(name="Tyler")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    chunks = [
        MockChunk([MockChoiceDelta(MockDelta(content="Hello"))]),
        MockChunk([MockChoiceDelta(MockDelta(content=" world"))]),
    ]
    
    async def mock_stream():
        for chunk in chunks:
            yield chunk
    
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (mock_stream(), {"model": "gpt-4"})
        
        updates = []
        async for event in agent.go(thread, stream=True):
            updates.append(event)
        
        # Should still yield ExecutionEvent objects
        assert all(isinstance(u, ExecutionEvent) for u in updates)
        stream_chunks = [u for u in updates if u.type == EventType.LLM_STREAM_CHUNK]
        assert len(stream_chunks) == 2