import os
# Removed dummy environment variables to avoid interfering with examples tests
import pytest
from unittest.mock import patch, MagicMock, create_autospec, Mock, AsyncMock
from tyler import Agent, Thread, Message, ThreadStore
from tyler.models.agent import StreamUpdate
from tyler.utils.tool_runner import tool_runner, ToolRunner
from narrator.database.storage_backend import MemoryBackend
from narrator import FileStore
from openai import OpenAI
from litellm import ModelResponse
import base64
import os
import json
from types import SimpleNamespace
from weave import StringPrompt


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
        self.usage = usage


class MockToolCall:
    def __init__(self, id="test_id", function_name="test_tool", arguments="{}"):
        self.id = id
        self.type = "function"
        self.function = SimpleNamespace(name=function_name, arguments=arguments)

@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client to prevent real API calls"""
    with patch('openai.OpenAI', autospec=True) as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock()
        yield mock

@pytest.fixture(autouse=True)
def mock_litellm():
    """Mock litellm to prevent real API calls"""
    with patch('litellm.acompletion', autospec=True) as mock:
        yield mock

@pytest.fixture(autouse=True)
def mock_file_processor():
    """Mock tool_runner to prevent real API calls for file processing"""
    with patch.object(tool_runner, 'run_tool_async') as mock_run_tool:
        mock_run_tool.return_value = {"content": "processed content"}
        yield mock_run_tool

@pytest.fixture
def mock_tool_runner():
    mock = MagicMock(spec=ToolRunner)
    mock.execute_tool_call = AsyncMock()
    mock.get_tool_attributes = MagicMock(return_value=None)
    return mock

@pytest.fixture
def mock_thread_store():
    """Create a mock thread store for testing and register it in the registry."""
    class MockThreadStore(ThreadStore):
        def __init__(self):
            super().__init__()  # Initialize with memory backend
            self.get = AsyncMock()
            self.save = AsyncMock()
            self.delete = AsyncMock()
            self.list = AsyncMock()
            self.find_by_attributes = AsyncMock()
            self.find_by_source = AsyncMock()
            self.initialized = False

        async def initialize(self):
            if not self.initialized:
                await super().initialize()
                self.initialized = True

    store = MockThreadStore()
    # Set default return values
    store.get.return_value = None
    store.save.return_value = None
    store.delete.return_value = True
    store.list.return_value = []
    store.find_by_attributes.return_value = []
    store.find_by_source.return_value = []
    
    return store

@pytest.fixture
def mock_file_store():
    """Create a mock file store for testing."""
    from narrator import FileStore
    
    # Create a proper FileStore mock
    class MockFileStore(FileStore):
        def __init__(self):
            # Don't call super().__init__() to avoid creating real directories
            self.base_path = "/tmp/test"
            self.max_file_size = 50 * 1024 * 1024
            self.allowed_mime_types = {"text/plain"}
            self.max_storage_size = 5 * 1024 * 1024 * 1024
            
        async def save(self, content, filename, mime_type=None):
            return {"id": "test-file-id", "filename": filename}
            
        async def get(self, file_id, storage_path=None):
            return b"test content"
            
        async def delete(self, file_id, storage_path=None):
            pass
    
    return MockFileStore()

@pytest.fixture
def mock_wandb():
    return MagicMock()

@pytest.fixture
def mock_prompt():
    return MagicMock()

@pytest.fixture
def mock_env_vars():
    return {
        "OPENAI_API_KEY": "test_key",
        "OPENAI_ORG_ID": "test_org"
    }

@pytest.fixture
def thread():
    """Create a thread fixture for testing"""
    return Thread(
        id="test_thread",
        messages=[],
        metadata={}
    )

@pytest.fixture
def agent(mock_tool_runner, mock_thread_store, mock_file_store, mock_openai, mock_wandb, mock_litellm, mock_prompt, mock_file_processor, mock_env_vars):
    """Create a test agent that uses mock stores"""
    agent = Agent(
        name="Tyler",
        model_name="gpt-4",
        temperature=0.5,
        purpose="test purpose",
        notes="test notes",
        thread_store=mock_thread_store,
        file_store=mock_file_store
    )
    
    return agent

def test_init(agent):
    """Test Agent initialization"""
    assert agent.model_name == "gpt-4"
    assert agent.temperature == 0.5
    assert agent.purpose == "test purpose"
    assert agent.notes == "test notes"
    assert len(agent.tools) == 0
    assert agent.max_tool_iterations == 10

@pytest.mark.asyncio
async def test_go_thread_not_found(agent, mock_thread_store):
    """Test go() with non-existent thread"""
    mock_thread_store.get.return_value = None
    
    with pytest.raises(ValueError, match="Thread with ID test-conv not found"):
        await agent.go("test-conv")

@pytest.mark.asyncio
async def test_go_max_recursion(agent, mock_thread_store):
    """Test go() with maximum iteration count reached"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_thread_store.get.return_value = thread
    
    # Instead of setting iteration count directly, mock the step method to simulate
    # reaching max iterations and force a call to _handle_max_iterations
    with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
        # Create a side effect that will increment the iteration count past the max
        def side_effect(*args, **kwargs):
            agent._iteration_count = agent.max_tool_iterations
            # Return an empty response with no message content to avoid adding extra messages
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            # Set content to None so no message is added from the step response
            mock_response.choices[0].message.content = None
            mock_response.choices[0].message.tool_calls = None
            return mock_response, {}
        
        mock_step.side_effect = side_effect
        
        # No need to patch _get_thread_store since we already set it in the fixture
        with patch.object(agent, '_get_thread', return_value=thread):
            result_thread, new_messages = await agent.go("test-conv")
            
            assert len(new_messages) == 1
            assert new_messages[0].role == "assistant"
            assert new_messages[0].content == "Maximum tool iteration count reached. Stopping further tool calls."
            mock_thread_store.save.assert_called_with(result_thread)

@pytest.mark.asyncio
async def test_go_no_tool_calls(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with a response that doesn't include tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0

    # Create a mock response
    mock_response = MagicMock()
    mock_response.id = "test-id"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].index = 0
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.role = "assistant"
    mock_response.model = "gpt-4"
    mock_response.usage.completion_tokens = 10
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.total_tokens = 30

    # Mock the weave operation by patching _get_completion with a dummy object
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"

    class DummyCompletion:
        async def call(self, s, **kwargs):
            return (mock_response, mock_weave_call)

    agent._get_completion = DummyCompletion()

    # No need to patch _get_thread_store since we already set it in the fixture
    with patch.object(agent, '_get_thread', return_value=thread):
        result_thread, new_messages = await agent.go("test-conv")

        # Since system messages are ephemeral, we only expect the assistant message
        assert len(result_thread.messages) == 1  
        assert result_thread.messages[0].role == "assistant"
        assert result_thread.messages[0].content == "Test response"
        assert len(new_messages) == 1
        assert new_messages[0].role == "assistant"
        assert "metrics" in new_messages[0].model_dump()
        assert "timing" in new_messages[0].metrics
        assert "usage" in new_messages[0].metrics
        mock_thread_store.save.assert_called_with(result_thread)
        assert agent._iteration_count == 0

@pytest.mark.asyncio
async def test_go_with_tool_calls(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0

    # Create a mock response with tool calls
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me help you with that",
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "test-tool",
                        "arguments": '{"arg": "value"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    tool_response.choices[0].message = SimpleNamespace(**vars(tool_response.choices[0].message))

    # Create a mock response for after tool execution
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 25,
            "total_tokens": 30
        }
    })

    # Patch the _get_completion method
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"
    with patch.object(agent, '_get_completion', new_callable=AsyncMock) as mocked_get_completion:
        mocked_get_completion.call.side_effect = [(tool_response, mock_weave_call), (final_response, mock_weave_call)]
        
        with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
            patched_tool_runner.execute_tool_call = AsyncMock(return_value={
                "name": "test-tool",
                "content": "Tool result"
            })
            patched_tool_runner.get_tool_attributes.return_value = None

            # No need to patch _get_thread_store since we already set it in the fixture
            with patch.object(agent, '_get_thread', return_value=thread):
                result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages (without system message)
    messages = result_thread.messages
    assert len(messages) == 3  # assistant with tool call, tool result, final assistant
    assert messages[0].role == "assistant"
    assert messages[0].tool_calls is not None
    assert messages[1].role == "tool"
    assert messages[1].tool_call_id == "test-call-id"
    assert messages[1].content == "{'name': 'test-tool', 'content': 'Tool result'}"
    assert messages[2].role == "assistant"
    assert messages[2].content == "Here's what I found"

@pytest.mark.asyncio
async def test_init_with_tools(mock_thread_store, mock_file_store, mock_prompt, mock_litellm, mock_file_processor, mock_openai):
    """Test Agent initialization with both string and dict tools"""
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock the tool module loading
        mock_tool_runner.load_tool_module.return_value = [
            {"type": "function", "function": {"name": "module_tool", "parameters": {}}}
        ]
        
        # Create a custom tool
        custom_tool = {
            'definition': {
                'function': {
                    'name': 'custom_tool',
                    'parameters': {}
                }
            },
            'implementation': lambda: None,
            'attributes': {'type': 'custom'}
        }
        
        agent = Agent(
            tools=['web', custom_tool],  # Mix of string module and custom tool
            thread_store=mock_thread_store,
            file_store=mock_file_store
        )
        
        # Verify tool loading
        mock_tool_runner.load_tool_module.assert_called_once_with('web')
        mock_tool_runner.register_tool.assert_called_once()
        mock_tool_runner.register_tool_attributes.assert_called_once_with('custom_tool', {'type': 'custom'})
        
        # Verify processed tools
        assert len(agent._processed_tools) == 2

@pytest.mark.asyncio
async def test_init_invalid_custom_tool():
    """Test Agent initialization with invalid custom tool"""
    invalid_tool = {
        'implementation': lambda: None  # Missing definition
    }

    with pytest.raises(ValueError, match="Custom tools must have 'definition' and 'implementation' keys"):
        Agent(tools=[invalid_tool])

@pytest.mark.asyncio
async def test_step_with_metrics(agent, mock_thread_store):
    """Test getting completion with metrics tracking"""
    thread = Thread(id="test-thread")
    thread.messages = []

    # Add a test message
    thread.add_message(Message(role="user", content="test message"))

    # Create a mock response
    mock_response = MagicMock()
    mock_response.id = "test-id"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].index = 0
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.role = "assistant"
    mock_response.model = "gpt-4"
    mock_response.usage.completion_tokens = 10
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.total_tokens = 30

    # Mock the weave operation
    mock_weave_call = MagicMock()
    mock_weave_call.id = "test-weave-id"
    mock_weave_call.ui_url = "https://weave.ui/test"

    # Override _get_completion to prevent real API calls
    class DummyCompletion:
        async def call(self, s, **kwargs):
            return (mock_response, mock_weave_call)

    with patch.object(agent, '_get_completion', new=DummyCompletion()):
        response, metrics = await agent.step(thread)

    # Compare relevant attributes instead of the entire response object
    assert response.id == mock_response.id
    assert response.choices[0].message.content == mock_response.choices[0].message.content
    assert response.choices[0].message.role == mock_response.choices[0].message.role
    assert response.model == mock_response.model
    assert response.usage.completion_tokens == mock_response.usage.completion_tokens
    assert response.usage.prompt_tokens == mock_response.usage.prompt_tokens
    assert response.usage.total_tokens == mock_response.usage.total_tokens

    # Verify metrics
    assert metrics["model"] == "gpt-4"
    assert "timing" in metrics
    assert "started_at" in metrics["timing"]
    assert "ended_at" in metrics["timing"]
    assert "latency" in metrics["timing"]
    assert metrics["usage"]["completion_tokens"] == 10
    assert metrics["usage"]["prompt_tokens"] == 20
    assert metrics["usage"]["total_tokens"] == 30
    assert metrics["weave_call"]["id"] == "test-weave-id"
    assert metrics["weave_call"]["ui_url"] == "https://weave.ui/test"

@pytest.mark.asyncio
async def test_step_error(agent):
    """Test error handling in step"""
    thread = Thread(id="test-thread")
    thread.messages = []
    
    # Create a mock error that will be raised
    api_error = Exception("API Error")
    
    # Override _get_completion with a dummy object whose async call method raises the error
    class DummyFail:
        async def call(self, s, **kwargs):
            raise api_error

    agent._get_completion = DummyFail()
    
    result_thread, new_messages = await agent.step(thread)
    # The error should be captured in a message appended to the thread
    error_message = result_thread.messages[-1].content
    error_metrics = result_thread.messages[-1].metrics.get("error", "")
    assert "I encountered an error:" in error_message
    assert "API Error" in error_metrics

@pytest.mark.asyncio
async def test_step_no_weave(agent):
    """Test step metrics when weave call info is not available"""
    thread = Thread(id="test-thread")
    thread.messages = [Message(role="system", content="Test system prompt")]  # Add system message

    # Create a mock response without weave call info
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })

    # Explicitly patch _get_completion with an AsyncMock and set up the return value for call()
    agent._get_completion = AsyncMock()
    agent._get_completion.call.return_value = (mock_response, None)

    response, metrics = await agent.step(thread)

    assert response.choices[0].message.content == "Test response"
    assert metrics["model"] == "gpt-4"
    assert metrics["usage"]["total_tokens"] == 30

@pytest.mark.asyncio
async def test_handle_max_iterations(agent, mock_thread_store):
    """Test handling of max iterations reached"""
    thread = Thread(id="test-thread")
    new_messages = [Message(role="user", content="test")]
    
    # The _handle_max_iterations method uses _get_thread_store which is already patched in the fixture
    result_thread, filtered_messages = await agent._handle_max_iterations(thread, new_messages)
    
    assert len(filtered_messages) == 1
    assert filtered_messages[0].role == "assistant"
    assert filtered_messages[0].content == "Maximum tool iteration count reached. Stopping further tool calls."
    mock_thread_store.save.assert_called_once_with(result_thread)

@pytest.mark.asyncio
async def test_get_thread_direct(agent):
    """Test getting thread directly without thread store"""
    thread = Thread(id="test-thread")
    result = await agent._get_thread(thread)
    assert result == thread

@pytest.mark.asyncio
async def test_get_thread_missing_store(agent):
    """Test getting thread by ID without thread store"""
    # Set thread store to None
    agent.thread_store = None
    
    with pytest.raises(ValueError, match="Thread store is required when passing thread ID"):
        await agent._get_thread("test-thread-id")

@pytest.mark.asyncio
async def test_tool_execution_error(agent):
    """Test handling of tool execution errors"""
    thread = Thread(id="test-thread")
    new_messages = []
    tool_call = {
        "id": "test-id",
        "type": "function",
        "function": {
            "name": "test-tool",
            "arguments": "{}"
        }
    }

    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(side_effect=Exception("Tool error"))
        mock_tool_runner.get_tool_attributes.return_value = None

        # Should not raise exception but handle it gracefully
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)

        assert not should_break
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert new_messages[0].name == "test-tool"
        # Just check that the error message contains the error text
        assert "Tool error" in new_messages[0].content

@pytest.mark.asyncio
async def test_process_tool_call_with_interrupt(agent):
    """Test processing a tool call that is marked as an interrupt"""
    tool_call = MagicMock()
    tool_call.id = "test-call-id"
    tool_call.function.name = "interrupt_tool"
    tool_call.function.arguments = "{}"
    
    thread = Thread(id="test-thread")
    new_messages = []
    
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        # Mock tool attributes to indicate it's an interrupt tool
        mock_tool_runner.get_tool_attributes.return_value = {'type': 'interrupt'}
        
        # Mock tool execution
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "interrupt_tool",
            "content": "Interrupting execution"
        })
        
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)
        
        assert should_break is True
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        assert new_messages[0].name == "interrupt_tool"
        assert new_messages[0].tool_call_id == "test-call-id"
        assert "metrics" in new_messages[0].model_dump()

@pytest.mark.asyncio
async def test_serialize_tool_calls():
    """Test serialization of tool calls"""
    agent = Agent()
    
    # Create a mock tool call
    tool_call = MagicMock()
    tool_call.id = "test-id"
    tool_call.type = "function"
    tool_call.function.name = "test_function"
    tool_call.function.arguments = '{"arg": "value"}'
    
    serialized = agent._serialize_tool_calls([tool_call])
    
    assert len(serialized) == 1
    assert serialized[0]["id"] == "test-id"
    assert serialized[0]["type"] == "function"
    assert serialized[0]["function"]["name"] == "test_function"
    assert serialized[0]["function"]["arguments"] == '{"arg": "value"}'
    
    # Test with None
    assert agent._serialize_tool_calls(None) is None

@pytest.mark.asyncio
async def test_go_with_weave_metrics(agent, mock_thread_store, mock_prompt):
    """Test go() with weave metrics tracking"""
    thread = Thread(id="test-conv", title="Test Thread")
    thread.messages = []
    mock_thread_store.get.return_value = thread
    
    # Create a mock weave call with metrics
    mock_weave_call = MagicMock()
    mock_weave_call.id = "weave-call-id"
    mock_weave_call.ui_url = "https://weave.ui/call-id"
    
    # Create the mock response
    mock_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Test response",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",
        "usage": {"completion_tokens": 10, "prompt_tokens": 20, "total_tokens": 30}
    })
    
    # Create a mock for step
    async def mock_step_metrics(*args, **kwargs):
        return mock_response, {
            'model': 'gpt-4',
            'timing': {
                'started_at': '2024-03-20T00:00:00+00:00',
                'ended_at': '2024-03-20T00:00:01+00:00',
                'latency': 1000
            },
            'usage': {
                'completion_tokens': 10,
                'prompt_tokens': 20,
                'total_tokens': 30
            },
            'weave_call': {
                'id': mock_weave_call.id,
                'ui_url': mock_weave_call.ui_url
            }
        }
    
    # Patch the method that actually generates the metrics
    with patch.object(agent, 'step', side_effect=mock_step_metrics):
        # No need to patch _get_thread_store since we already set it in the fixture
        with patch.object(agent, '_get_thread', return_value=thread):
            result_thread, new_messages = await agent.go(thread)
            
            assert len(new_messages) == 1
            message = new_messages[0]
            assert 'model' in message.metrics
            assert 'timing' in message.metrics
            assert 'usage' in message.metrics
            assert message.metrics['usage'] == {
                'completion_tokens': 10,
                'prompt_tokens': 20,
                'total_tokens': 30
            }
            assert message.metrics['weave_call']['id'] == "weave-call-id"
            assert message.metrics['weave_call']['ui_url'] == "https://weave.ui/call-id"

@pytest.mark.asyncio
async def test_get_thread_no_store():
    """Test get_thread with no thread store"""
    agent = Agent()  # Create without thread store - will create defaults
    thread = Thread(id="test-thread")
    
    # Should work with direct thread object
    result = await agent._get_thread(thread)
    assert result == thread
    
    # Set thread store to None to test the error case
    agent.thread_store = None
    
    with pytest.raises(ValueError) as exc_info:
        await agent._get_thread("test-thread-id")
    assert str(exc_info.value) == "Thread store is required when passing thread ID"

@pytest.mark.asyncio
async def test_go_with_multiple_tool_call_iterations(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with multiple iterations of tool calls"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0

    # First response with tool call
    first_response = ModelResponse(**{
        "id": "test-id-1",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me help you with that",
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "tool_one",
                        "arguments": '{"arg": "first"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    # Convert message dict to SimpleNamespace
    message_dict = first_response.choices[0].message
    first_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Second response with another tool call
    second_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me try another tool",
                "role": "assistant",
                "tool_calls": [{
                    "id": "call-2",
                    "type": "function",
                    "function": {
                        "name": "tool_two",
                        "arguments": '{"arg": "second"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 8,
            "prompt_tokens": 25,
            "total_tokens": 33
        }
    })
    # Convert message dict to SimpleNamespace
    message_dict = second_response.choices[0].message
    second_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Final response without tool calls
    final_response = ModelResponse(**{
        "id": "test-id-3",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 30,
            "total_tokens": 35
        }
    })
    # Convert message dict to SimpleNamespace
    message_dict = final_response.choices[0].message
    final_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=None
    )

    # Mock the completion call
    mock_completion = AsyncMock()
    mock_completion.call.side_effect = [
        (first_response, None),
        (second_response, None),
        (final_response, None)
    ]
    agent._get_completion = mock_completion

    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        # Mock tool executions with different results
        patched_tool_runner.execute_tool_call = AsyncMock(side_effect=[
            {"name": "tool_one", "content": "First tool result"},
            {"name": "tool_two", "content": "Second tool result"}
        ])
        patched_tool_runner.get_tool_attributes.return_value = None

        # No need to patch _get_thread_store since we already set it in the fixture
        with patch.object(agent, '_get_thread', return_value=thread):
            result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages (without system message)
    messages = result_thread.messages
    assert len(messages) == 5  # 2 pairs of assistant+tool, final assistant
    assert messages[0].role == "assistant"
    assert messages[0].content == "Let me help you with that"
    assert messages[0].tool_calls is not None
    assert messages[1].role == "tool"
    assert messages[1].tool_call_id == "call-1"
    assert messages[1].content == "{'name': 'tool_one', 'content': 'First tool result'}"
    assert messages[2].role == "assistant"
    assert messages[2].content == "Let me try another tool"
    assert messages[2].tool_calls is not None
    assert messages[3].role == "tool"
    assert messages[3].tool_call_id == "call-2"
    assert messages[3].content == "{'name': 'tool_two', 'content': 'Second tool result'}"
    assert messages[4].role == "assistant"
    assert messages[4].content == "Here's what I found"

@pytest.mark.asyncio
async def test_go_with_tool_calls_no_content(agent, mock_thread_store, mock_prompt, mock_litellm):
    """Test go() with tool calls but no content in the assistant message"""
    thread = Thread(id="test-conv", title="Test Thread")
    mock_prompt.system_prompt.return_value = "Test system prompt"
    thread.messages = []
    mock_thread_store.get.return_value = thread
    agent._iteration_count = 0

    # Response with only tool call, no content
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": None,  # No content
                "role": "assistant",
                "tool_calls": [{
                    "id": "test-call-id",
                    "type": "function",
                    "function": {
                        "name": "test-tool",
                        "arguments": '{"arg": "value"}'
                    }
                }]
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })
    # Convert message dict to SimpleNamespace
    message_dict = tool_response.choices[0].message
    tool_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=[
            SimpleNamespace(
                id=tc["id"],
                type=tc["type"],
                function=SimpleNamespace(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                )
            ) for tc in message_dict["tool_calls"]
        ]
    )

    # Final response after tool call
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's what I found",
                "role": "assistant",
                "tool_calls": None
            }
        }],
        "model": "gpt-4",
        "usage": {
            "completion_tokens": 5,
            "prompt_tokens": 25,
            "total_tokens": 30
        }
    })
    # Convert message dict to SimpleNamespace
    message_dict = final_response.choices[0].message
    final_response.choices[0].message = SimpleNamespace(
        content=message_dict["content"],
        role=message_dict["role"],
        tool_calls=None
    )

    # Mock the completion call
    mock_completion = AsyncMock()
    mock_completion.call.side_effect = [
        (tool_response, None),
        (final_response, None)
    ]
    agent._get_completion = mock_completion

    with patch('tyler.models.agent.tool_runner') as patched_tool_runner:
        patched_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test-tool",
            "content": "Tool result"
        })
        patched_tool_runner.get_tool_attributes.return_value = None

        # No need to patch _get_thread_store since we already set it in the fixture
        with patch.object(agent, '_get_thread', return_value=thread):
            result_thread, new_messages = await agent.go("test-conv")

    # Verify the sequence of messages (without system message)
    messages = result_thread.messages
    assert len(messages) == 3  # assistant with tool call, tool result, final assistant
    assert messages[0].role == "assistant"
    assert messages[0].content == ""  # Empty content
    assert messages[0].tool_calls is not None
    assert messages[1].role == "tool"
    assert messages[1].tool_call_id == "test-call-id"
    assert messages[1].content == "{'name': 'test-tool', 'content': 'Tool result'}"
    assert messages[2].role == "assistant"
    assert messages[2].content == "Here's what I found"

@pytest.mark.asyncio
async def test_process_tool_call_with_files(agent, thread):
    """Test processing a tool call that returns files"""
    # Mock the tool execution result
    mock_result = (
        json.dumps({"success": True, "message": "File generated"}),
        [{
            "filename": "test.txt",
            "content": b"test content",
            "mime_type": "text/plain",
            "description": "A test file"
        }]
    )

    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result

        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }

        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)

        # Check that attachments were created
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 1
        assert message.attachments[0].filename == "test.txt"
        assert message.attachments[0].content == b"test content"
        assert message.attachments[0].mime_type == "text/plain"

@pytest.mark.asyncio
async def test_process_tool_call_without_files(agent, thread):
    """Test processing a tool call that doesn't return files"""
    # Mock the tool execution result
    mock_result = "Simple result"  # Just return a string

    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result

        # Create a tool call
        tool_call = {
            'id': 'test_id',
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }

        new_messages = []
        result = await agent._process_tool_call(tool_call, thread, new_messages)

        # Check that message was created without attachments
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 0
        assert message.content == "Simple result"

@pytest.mark.asyncio
async def test_process_tool_call_with_image_attachment():
    """Test processing a tool call that returns an image attachment."""
    agent = Agent()
    thread = Thread(id="test-thread")
    new_messages = []

    # Create a tool call
    tool_call = {
        'id': 'test_id',
        'type': 'function',
        'function': {
            'name': 'test_tool',
            'arguments': '{}'
        }
    }

    # Create base64 encoded content
    test_image_bytes = b"test image content"
    encoded_content = base64.b64encode(test_image_bytes).decode('utf-8')

    # Mock the tool execution result with an image attachment
    mock_result = (
        "Image generated successfully",
        [{
            "filename": "test.png",
            "content": encoded_content,  # Already base64 encoded
            "mime_type": "image/png",
            "description": "A test image"
        }]
    )

    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_result
        await agent._process_tool_call(tool_call, thread, new_messages)

        # Check that attachments were created
        assert len(new_messages) == 1
        message = new_messages[0]
        assert len(message.attachments) == 1
        attachment = message.attachments[0]
        assert attachment.filename == "test.png"
        assert attachment.content == encoded_content  # Compare with encoded content
        assert attachment.mime_type == "image/png"

@pytest.mark.asyncio
async def test_go_with_tool_returning_image(mock_thread_store, mock_file_store):
    """Test the go() method when a tool returns an image attachment."""
    # Set up mock thread store to return a test thread
    mock_thread_store.get.return_value = Thread(id="test-thread")
    
    # Create agent with mock stores
    agent = Agent(thread_store=mock_thread_store, file_store=mock_file_store)
    
    # Create base64 encoded content
    test_image_bytes = b"test image content"
    encoded_content = base64.b64encode(test_image_bytes).decode('utf-8')

    # First response with tool call
    tool_response = ModelResponse(**{
        "id": "test-id",
        "choices": [{
            "finish_reason": "tool_calls",
            "index": 0,
            "message": {
                "content": "Let me generate that image for you",
                "role": "assistant",
                "tool_calls": [{
                    "id": "test_id",
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "arguments": "{}"
                    }
                }]
            }
        }],
        "model": "gpt-4",  # Match expected model name
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })

    # Final response after tool execution
    final_response = ModelResponse(**{
        "id": "test-id-2",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "Here's your generated image",
                "role": "assistant"
            }
        }],
        "model": "gpt-4",  # Match expected model name
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 20,
            "total_tokens": 30
        }
    })

    # Mock _get_completion to return our responses in sequence
    mock_completion = AsyncMock()
    mock_completion.call.side_effect = [
        (tool_response, None),
        (final_response, None)
    ]
    agent._get_completion = mock_completion

    # Mock tool execution result with an image attachment
    with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = ("Image generated successfully", [{
            "filename": "test.png",
            "content": encoded_content,
            "mime_type": "image/png"
        }])
        
        # Also mock _get_thread directly to return the thread
        with patch.object(agent, '_get_thread', return_value=Thread(id="test-thread")):
            # Execute go method
            result_thread, new_messages = await agent.go("test-thread")

            # Verify messages
            assert len(new_messages) == 3
            assert new_messages[0].role == "assistant"  # Initial message with tool call
            assert new_messages[0].content == "Let me generate that image for you"
            assert new_messages[1].role == "tool"  # Tool response with image
            assert len(new_messages[1].attachments) == 1
            assert new_messages[1].attachments[0].content == encoded_content
            assert new_messages[2].role == "assistant"  # Final message
            assert new_messages[2].content == "Here's your generated image"

@pytest.mark.asyncio
async def test_normalize_tool_call():
    """Test the _normalize_tool_call method with different input formats"""
    agent = Agent()
    
    # Test with dict format
    dict_tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "test_tool",
            "arguments": '{"param": "value"}'
        }
    }
    normalized = agent._normalize_tool_call(dict_tool_call)
    assert normalized.id == "call_123"
    assert normalized.type == "function"
    assert normalized.function.name == "test_tool"
    assert normalized.function.arguments == '{"param": "value"}'
    
    # Test with object that's already normalized
    from types import SimpleNamespace
    obj_tool_call = SimpleNamespace(
        id="call_456",
        type="function",
        function=SimpleNamespace(
            name="another_tool",
            arguments='{"another": "param"}'
        )
    )
    normalized_obj = agent._normalize_tool_call(obj_tool_call)
    assert normalized_obj is obj_tool_call  # Should return the same object

@pytest.mark.asyncio
async def test_handle_tool_execution_empty_arguments():
    """Test _handle_tool_execution with empty arguments"""
    agent = Agent()
    
    # Create a tool call with empty arguments
    from types import SimpleNamespace
    tool_call = SimpleNamespace(
        id="call_123",
        type="function",
        function=SimpleNamespace(
            name="test_tool",
            arguments=""  # Empty arguments
        )
    )
    
    # Mock tool_runner.execute_tool_call
    with patch('tyler.models.agent.tool_runner') as mock_tool_runner:
        mock_tool_runner.execute_tool_call = AsyncMock(return_value={
            "name": "test_tool",
            "content": "Tool executed with empty args"
        })
        
        result = await agent._handle_tool_execution(tool_call)
        
        # Verify tool_runner was called with normalized arguments
        args = mock_tool_runner.execute_tool_call.call_args[0][0]
        assert args.function.arguments == "{}"  # Empty string should be converted to empty JSON object
        assert result["content"] == "Tool executed with empty args"

@pytest.mark.asyncio
async def test_go_with_completion_error(agent, mock_thread_store):
    """Test go method with error during completion"""
    thread = Thread()
    thread.add_message(Message(role="user", content="Test completion error"))

    # Mock step to raise an exception
    with patch.object(agent, 'step') as mock_step:
        mock_step.side_effect = Exception("Completion API error")
        
        # No need to patch _get_thread_store since we already set it in the fixture
        result_thread, new_messages = await agent.go(thread)

        # Verify error was handled and added to thread
        assert len(new_messages) == 1
        # Check that the error is reflected in the message content
        assert "error" in new_messages[0].content.lower() or "Completion API error" in new_messages[0].content

        # Verify thread was saved
        assert mock_thread_store.save.call_count > 0  # Allow multiple saves

@pytest.mark.asyncio
async def test_go_with_invalid_response(agent, mock_thread_store):
    """Test go method with invalid response from completion"""
    thread = Thread()
    thread.add_message(Message(role="user", content="Test invalid response"))

    # Mock step to return None for response
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (None, {})
        
        # No need to patch _get_thread_store since we already set it in the fixture
        result_thread, new_messages = await agent.go(thread)

        # Verify error was handled and added to thread
        assert len(new_messages) == 1
        # Check for presence of error message without requiring exact format
        assert "error" in new_messages[0].content.lower() or "response" in new_messages[0].content.lower()

        # Verify thread was saved
        assert mock_thread_store.save.call_count > 0  # Allow multiple saves

@pytest.mark.asyncio
async def test_get_thread_with_missing_thread(agent):
    """Test _get_thread with missing thread ID"""
    # Set up the existing thread store to return None for the missing thread
    agent.thread_store.get.return_value = None
    
    # Call _get_thread with non-existent ID
    with pytest.raises(ValueError, match="Thread with ID missing-id not found"):
        await agent._get_thread("missing-id")
        
    # Verify thread_store.get was called
    agent.thread_store.get.assert_called_once_with("missing-id")

@pytest.mark.asyncio
async def test_serialize_tool_calls_with_invalid_calls():
    """Test _serialize_tool_calls with invalid tool calls"""
    agent = Agent()
    
    # Test with None
    assert agent._serialize_tool_calls(None) is None
    
    # Test with empty list
    assert agent._serialize_tool_calls([]) is None
    
    # Test with invalid tool calls (missing ID)
    from types import SimpleNamespace
    invalid_calls = [
        {},  # Empty dict
        {"function": {"name": "test", "arguments": "{}"}},  # Missing ID
        SimpleNamespace(function=SimpleNamespace(name="test", arguments="{}")),  # Missing ID in object
    ]
    
    serialized = agent._serialize_tool_calls(invalid_calls)
    assert serialized is None

@pytest.mark.asyncio
async def test_process_tool_call_with_execution_error(agent, thread):
    """Test _process_tool_call with tool execution error"""
    # Create a tool call
    tool_call = {
        "id": "call_123",
        "function": {
            "name": "test_tool",
            "arguments": "{}"
        }
    }

    # Mock _handle_tool_execution to raise an exception
    with patch.object(agent, '_handle_tool_execution') as mock_handle:
        mock_handle.side_effect = Exception("Tool execution failed")

        new_messages = []
        should_break = await agent._process_tool_call(tool_call, thread, new_messages)

        # Verify error message was added
        assert len(new_messages) == 1
        assert new_messages[0].role == "tool"
        # Check for presence of error message without requiring exact format
        assert "Tool execution failed" in new_messages[0].content
        
        # Should not break iteration
        assert should_break is False

@pytest.mark.asyncio
async def test_get_completion_with_weave_call():
    """Test _get_completion with weave call tracking"""
    agent = Agent(model_name="gpt-4")  # Set model to match test expectations
    
    # Mock acompletion
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_acompletion.return_value = mock_response
        
        # Call _get_completion directly
        response = await agent._get_completion(model="gpt-4", messages=[])
        
        # Verify acompletion was called
        mock_acompletion.assert_called_once_with(model="gpt-4", messages=[])
        
        # Verify response is returned
        assert response is mock_response

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

@pytest.mark.asyncio
async def test_init_with_api_base_and_extra_headers():
    """Test Agent initialization with api_base and extra_headers"""
    api_base = "https://api.inference.wandb.ai/v1"
    extra_headers = {"OpenAI-Project": "team/project"}
    
    agent = Agent(
        name="Tyler",
        model_name="deepseek-ai/DeepSeek-R1-0528",
        api_base=api_base,
        extra_headers=extra_headers
    )
    
    assert agent.api_base == api_base
    assert agent.extra_headers == extra_headers
    assert agent.model_name == "deepseek-ai/DeepSeek-R1-0528"

@pytest.mark.asyncio
async def test_init_without_api_base_and_extra_headers():
    """Test Agent initialization without api_base and extra_headers (defaults)"""
    agent = Agent(name="Tyler", model_name="gpt-4")
    
    assert agent.api_base is None
    assert agent.extra_headers is None

@pytest.mark.asyncio
async def test_step_with_api_base_and_extra_headers(mock_thread_store):
    """Test step method includes api_base and extra_headers in completion params"""
    api_base = "https://api.inference.wandb.ai/v1"
    extra_headers = {"OpenAI-Project": "team/project", "Custom-Header": "value"}
    
    agent = Agent(
        name="Tyler",
        model_name="deepseek-ai/DeepSeek-R1-0528",
        api_base=api_base,
        extra_headers=extra_headers
    )
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="test message"))
    
    # Mock acompletion to capture the parameters passed to it
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_response.id = "test-id"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "deepseek-ai/DeepSeek-R1-0528"
        mock_response.usage.completion_tokens = 10
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response
        
        # Call step
        response, metrics = await agent.step(thread)
        
        # Verify acompletion was called with our custom parameters
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        completion_params = call_args[1] if call_args[1] else call_args[0][0] if call_args[0] else {}
        
        # Check that api_base and extra_headers were included
        assert completion_params.get("api_base") == api_base
        assert completion_params.get("extra_headers") == extra_headers
        assert completion_params.get("model") == "deepseek-ai/DeepSeek-R1-0528"

@pytest.mark.asyncio
async def test_step_without_custom_params(mock_thread_store):
    """Test step method without api_base and extra_headers (should not include them)"""
    agent = Agent(name="Tyler", model_name="gpt-4")
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="test message"))
    
    # Mock acompletion to capture the parameters passed to it
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_response.id = "test-id"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "gpt-4"
        mock_response.usage.completion_tokens = 10
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response
        
        # Call step
        response, metrics = await agent.step(thread)
        
        # Verify acompletion was called without custom parameters
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        completion_params = call_args[1] if call_args[1] else call_args[0][0] if call_args[0] else {}
        
        # Check that api_base and extra_headers were NOT included
        assert "api_base" not in completion_params
        assert "extra_headers" not in completion_params
        assert completion_params.get("model") == "gpt-4"

@pytest.mark.asyncio
async def test_go_with_custom_api_params(mock_thread_store):
    """Test go method with custom API parameters"""
    api_base = "https://api.inference.wandb.ai/v1"
    extra_headers = {"OpenAI-Project": "team/project"}
    
    agent = Agent(
        name="Tyler",
        model_name="deepseek-ai/DeepSeek-R1-0528",
        api_base=api_base,
        extra_headers=extra_headers
    )
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-conv", title="Test Thread")
    thread.messages = []
    mock_thread_store.get.return_value = thread
    
    # Mock acompletion
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_response.id = "test-id"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "deepseek-ai/DeepSeek-R1-0528"
        mock_response.usage.completion_tokens = 10
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response
        
        # Mock weave call
        mock_weave_call = MagicMock()
        mock_weave_call.id = "test-weave-id"
        mock_weave_call.ui_url = "https://weave.ui/test"
        
        # Override _get_completion to prevent real API calls but capture params
        class DummyCompletion:
            async def call(self, s, **kwargs):
                # Verify that the kwargs contain our custom parameters
                assert kwargs.get("api_base") == api_base
                assert kwargs.get("extra_headers") == extra_headers
                return (mock_response, mock_weave_call)
        
        agent._get_completion = DummyCompletion()
        
        # No need to patch _get_thread_store since we already set it in the fixture
        with patch.object(agent, '_get_thread', return_value=thread):
            result_thread, new_messages = await agent.go("test-conv")
            
            # Verify basic functionality still works
            assert len(new_messages) == 1
            assert new_messages[0].role == "assistant"
            assert new_messages[0].content == "Test response"

@pytest.mark.asyncio
async def test_step_with_streaming_and_custom_params(mock_thread_store):
    """Test step method with streaming enabled and custom API parameters"""
    api_base = "https://api.inference.wandb.ai/v1"
    extra_headers = {"OpenAI-Project": "team/project"}
    
    agent = Agent(
        name="Tyler",
        model_name="deepseek-ai/DeepSeek-R1-0528",
        api_base=api_base,
        extra_headers=extra_headers
    )
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="test message"))
    
    # Mock acompletion for streaming
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        # Create a mock async generator for streaming response
        async def mock_stream():
            yield MagicMock()
        
        mock_acompletion.return_value = mock_stream()
        
        # Call step with streaming
        response, metrics = await agent.step(thread, stream=True)
        
        # Verify acompletion was called with streaming and custom parameters
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        completion_params = call_args[1] if call_args[1] else call_args[0][0] if call_args[0] else {}
        
        assert completion_params.get("api_base") == api_base
        assert completion_params.get("extra_headers") == extra_headers
        assert completion_params.get("stream") is True

@pytest.mark.asyncio
async def test_init_with_empty_extra_headers():
    """Test Agent initialization with empty extra_headers dict"""
    agent = Agent(
        name="Tyler",
        model_name="gpt-4",
        extra_headers={}
    )
    
    assert agent.extra_headers == {}

@pytest.mark.asyncio
async def test_step_with_empty_api_base():
    """Test step method with empty string api_base (should not be included)"""
    agent = Agent(
        name="Tyler",
        model_name="gpt-4",
        api_base=""  # Empty string
    )
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="test message"))
    
    # Mock acompletion
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_response.id = "test-id"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "gpt-4"
        mock_response.usage.completion_tokens = 10
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_acompletion.return_value = mock_response
        
        # Call step
        response, metrics = await agent.step(thread)
        
        # Verify acompletion was called without api_base (empty string is falsy)
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        completion_params = call_args[1] if call_args[1] else call_args[0][0] if call_args[0] else {}
        
        # Empty string should not be included (it's falsy)
        assert "api_base" not in completion_params

@pytest.mark.asyncio
async def test_weave_inference_service_example():
    """Test a realistic example using weave inference service"""
    # This test simulates the actual usage pattern for weave inference
    agent = Agent(
        name="Tyler",
        model_name="deepseek-ai/DeepSeek-R1-0528",
        api_base="https://api.inference.wandb.ai/v1",
        extra_headers={"OpenAI-Project": "my-team/my-project"}
    )
    
    # No need to mock file store - it's created automatically in init
    
    thread = Thread(id="test-thread")
    thread.add_message(Message(role="user", content="Tell me a joke"))
    
    # Mock a successful response
    with patch('tyler.models.agent.acompletion') as mock_acompletion:
        mock_response = MagicMock()
        mock_response.id = "deepseek-response-id"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Why don't scientists trust atoms? Because they make up everything!"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "deepseek-ai/DeepSeek-R1-0528"
        mock_response.usage.completion_tokens = 15
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.total_tokens = 25
        mock_acompletion.return_value = mock_response
        
        # Call step
        response, metrics = await agent.step(thread)
        
        # Verify the completion was called with correct weave inference parameters
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        completion_params = call_args[1] if call_args[1] else call_args[0][0] if call_args[0] else {}
        
        assert completion_params["model"] == "deepseek-ai/DeepSeek-R1-0528"
        assert completion_params["api_base"] == "https://api.inference.wandb.ai/v1"
        assert completion_params["extra_headers"] == {"OpenAI-Project": "my-team/my-project"}
        assert completion_params["temperature"] == 0.7  # Default temperature
        
        # Verify response
        assert response.choices[0].message.content == "Why don't scientists trust atoms? Because they make up everything!"
        assert metrics["model"] == "deepseek-ai/DeepSeek-R1-0528" 


@pytest.mark.asyncio
async def test_base_url_alias():
    """Test that base_url is properly aliased to api_base"""
    # Test 1: Using base_url should set api_base
    agent1 = Agent(name="TestAgent1", base_url="https://custom-api.example.com/v1")
    assert agent1.api_base == "https://custom-api.example.com/v1", "base_url should be aliased to api_base"
    
    # Test 2: Using api_base directly should still work
    agent2 = Agent(name="TestAgent2", api_base="https://another-api.example.com/v1")
    assert agent2.api_base == "https://another-api.example.com/v1", "api_base should work directly"
    
    # Test 3: Neither base_url nor api_base provided
    agent3 = Agent(name="TestAgent3")
    assert agent3.api_base is None, "api_base should be None when neither is provided"


@pytest.mark.asyncio
async def test_go_general_exception_handling(mock_thread_store):
    """Test general exception handling in go method"""
    agent = Agent(
        name="TestAgent",
        thread_store=mock_thread_store
    )
    
    # Create a thread to pass
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock step to raise a general exception (not ValueError)
    with patch.object(agent, 'step') as mock_step:
        mock_step.side_effect = RuntimeError("Unexpected error")
        
        result_thread, messages = await agent.go(thread)
        
        # Should have an error message
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert "I encountered an error:" in messages[0].content
        assert "Unexpected error" in messages[0].content
        
        # Thread should be saved even on error
        mock_thread_store.save.assert_called()


@pytest.mark.asyncio
async def test_go_with_thread_id(mock_thread_store):
    """Test go method with thread ID instead of thread object"""
    thread = Thread(id="test_thread_id")
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock thread store to return our thread
    mock_thread_store.get.return_value = thread
    
    agent = Agent(
        name="TestAgent",
        thread_store=mock_thread_store
    )
    
    # Mock step
    with patch.object(agent, 'step') as mock_step:
        mock_step.return_value = (
            MockResponse([MockChoice(MockMessage("Response"))]),
            {"model": "gpt-4"}
        )
        
        # Call with thread ID
        result_thread, messages = await agent.go("test_thread_id")
        
        # Verify thread was fetched
        mock_thread_store.get.assert_called_with("test_thread_id")


@pytest.mark.asyncio
async def test_go_missing_thread_store():
    """Test go method when thread store is missing"""
    # Agent creates a default thread store if None is provided
    # So we need to test by setting it to None after creation
    agent = Agent(name="TestAgent")
    agent.thread_store = None
    
    with pytest.raises(ValueError, match="Thread store is required"):
        await agent.go("thread_id")


@pytest.mark.asyncio
async def test_go_thread_not_found_in_store(mock_thread_store):
    """Test go method when thread not found in store"""
    mock_thread_store.get.return_value = None
    
    agent = Agent(
        name="TestAgent",
        thread_store=mock_thread_store
    )
    
    with pytest.raises(ValueError, match="Thread with ID missing_id not found"):
        await agent.go("missing_id")


@pytest.mark.asyncio
async def test_gemini_tool_handling(mock_thread_store, mock_file_store):
    """Test special handling for Gemini models"""
    # Create a custom tool with additionalProperties
    custom_tool = {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'description': 'Test tool',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'context': {
                            'type': 'object',
                            'description': 'Additional context',
                            'additionalProperties': True  # This should be removed for Gemini
                        }
                    }
                }
            }
        },
        'implementation': lambda context: "Result"
    }
    
    agent = Agent(
        model_name="gemini-pro",  # Gemini model
        tools=[custom_tool],
        thread_store=mock_thread_store,
        file_store=mock_file_store
    )
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Mock the acompletion to check the tools passed
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_completion.return_value = MockResponse([
            MockChoice(MockMessage("Response"))
        ])
        
        response, metrics = await agent.step(thread)
        
        # Check that tools were passed to completion
        call_args = mock_completion.call_args[1]
        assert 'tools' in call_args
        
        # Verify additionalProperties was removed for Gemini
        tools = call_args['tools']
        for tool in tools:
            if 'function' in tool and 'parameters' in tool['function']:
                params = tool['function']['parameters']
                if 'properties' in params:
                    for prop_name, prop in params['properties'].items():
                        if isinstance(prop, dict):
                            assert 'additionalProperties' not in prop


@pytest.mark.asyncio
async def test_process_tool_result_with_metrics():
    """Test _process_tool_result helper with different scenarios"""
    agent = Agent(name="TestAgent")
    
    # Test with exception result
    tool_call = {"id": "123", "function": {"name": "test_tool"}}
    exception = Exception("Tool failed")
    
    message, should_break = agent._process_tool_result(
        exception, tool_call, "test_tool"
    )
    
    assert message.role == "tool"
    assert "Tool execution failed" in message.content
    assert not should_break
    
    # Test with interrupt tool
    with patch.object(tool_runner, 'get_tool_attributes', return_value={'type': 'interrupt'}):
        agent._tool_attributes_cache.clear()  # Clear cache
        message, should_break = agent._process_tool_result(
            "Success", tool_call, "interrupt_tool"
        )
        
        assert should_break


@pytest.mark.asyncio
async def test_create_error_message():
    """Test error message creation helper"""
    agent = Agent(name="TestAgent")
    
    # Test basic error message
    error_msg = agent._create_error_message("Test error")
    
    assert error_msg.role == "assistant"
    assert "I encountered an error: Test error" in error_msg.content
    assert error_msg.metrics["timing"]["started_at"] == error_msg.metrics["timing"]["ended_at"]
    assert error_msg.metrics["timing"]["latency"] == 0
    
    # Test with custom source
    custom_source = {"id": "custom", "name": "Custom Source"}
    error_msg = agent._create_error_message("Test error", custom_source)
    assert error_msg.source == custom_source


@pytest.mark.asyncio
async def test_normalize_tool_call_edge_cases():
    """Test _normalize_tool_call with various edge cases"""
    agent = Agent(name="TestAgent")
    
    # Test with dict having whitespace arguments - should preserve
    tool_dict = {
        "id": "123",
        "function": {
            "name": "test_tool",
            "arguments": "  "  # Whitespace only
        }
    }
    
    normalized = agent._normalize_tool_call(tool_dict)
    assert normalized.function.arguments == "  "  # Preserves whitespace
    
    # Test with dict missing arguments
    tool_dict2 = {
        "id": "456",
        "function": {
            "name": "test_tool"
            # No arguments key
        }
    }
    
    normalized2 = agent._normalize_tool_call(tool_dict2)
    assert normalized2.function.arguments == "{}"
    
    # Test with object having empty string arguments
    tool_obj = MockToolCall(arguments='')
    normalized3 = agent._normalize_tool_call(tool_obj)
    assert normalized3.function.arguments == "{}"  # Empty string is converted
    
    # Test with object having valid arguments
    tool_obj2 = MockToolCall(arguments='{"key": "value"}')
    normalized4 = agent._normalize_tool_call(tool_obj2)
    assert normalized4 is tool_obj2  # Should return original if valid


@pytest.mark.asyncio
async def test_step_error_handling():
    """Test error handling in step method"""
    agent = Agent(name="TestAgent")
    
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Test when acompletion raises an exception
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_completion.side_effect = Exception("API Error")
        
        # Use go() method to see error handling (step() returns response and metrics)
        result_thread, messages = await agent.go(thread)
        
        # Should have error message
        assert len(messages) > 0
        assert any("encountered an error" in m.content for m in messages if m.role == "assistant")


def test_stream_update_slots():
    """Test that StreamUpdate uses __slots__ correctly"""
    update = StreamUpdate(StreamUpdate.Type.CONTENT_CHUNK, "test data")
    
    # Should have type and data attributes
    assert update.type == StreamUpdate.Type.CONTENT_CHUNK
    assert update.data == "test data"
    
    # Should not have __dict__ due to __slots__
    assert not hasattr(update, '__dict__')
    
    # Should not be able to add new attributes
    with pytest.raises(AttributeError):
        update.new_attr = "value"


@pytest.mark.asyncio
async def test_agent_with_child_agents():
    """Test that agent properly registers delegation tools for child agents"""
    child1 = Agent(name="Child1", purpose="Help with task 1")
    child2 = Agent(name="Child2", purpose="Help with task 2")
    
    parent = Agent(
        name="Parent",
        purpose="Coordinate tasks",
        agents=[child1, child2]
    )
    
    # Check that delegation tools were created
    tool_names = [tool['function']['name'] for tool in parent._processed_tools if 'function' in tool]
    assert "delegate_to_Child1" in tool_names
    assert "delegate_to_Child2" in tool_names
    
    # Check tool descriptions
    for tool in parent._processed_tools:
        if tool.get('function', {}).get('name') == 'delegate_to_Child1':
            assert "Help with task 1" in tool['function']['description']


@pytest.mark.asyncio
async def test_tool_attributes_caching():
    """Test that tool attributes are cached properly"""
    agent = Agent(name="TestAgent")
    
    # Mock tool_runner.get_tool_attributes
    with patch.object(tool_runner, 'get_tool_attributes') as mock_get_attrs:
        mock_get_attrs.return_value = {"type": "normal"}
        
        # First call should hit tool_runner
        attrs1 = agent._get_tool_attributes("tool1")
        assert attrs1 == {"type": "normal"}
        mock_get_attrs.assert_called_once_with("tool1")
        
        # Second call should use cache
        attrs2 = agent._get_tool_attributes("tool1")
        assert attrs2 == {"type": "normal"}
        mock_get_attrs.assert_called_once()  # Still only once
        
        # Different tool should hit tool_runner again
        attrs3 = agent._get_tool_attributes("tool2")
        assert mock_get_attrs.call_count == 2


@pytest.mark.asyncio
async def test_system_prompt_generation():
    """Test system prompt generation with various configurations"""
    # Test with string values and custom tool
    custom_tool = {
        'definition': {
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'description': 'A test tool for testing',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'param': {'type': 'string'}
                    }
                }
            }
        },
        'implementation': lambda param: f"Processed: {param}"
    }
    
    agent = Agent(
        name="TestAgent",
        purpose="Help users with testing",
        notes="Important test notes",
        model_name="gpt-4",
        tools=[custom_tool]
    )
    
    # Access the generated system prompt
    system_prompt = agent._system_prompt
    
    # Should contain agent name and model
    assert "TestAgent" in system_prompt
    assert "gpt-4" in system_prompt
    
    # Should have the purpose and notes
    assert "Help users with testing" in system_prompt
    assert "Important test notes" in system_prompt
    
    # Should include tool description
    assert "test_tool" in system_prompt
    assert "A test tool for testing" in system_prompt


@pytest.mark.asyncio
async def test_get_timestamp():
    """Test timestamp helper method"""
    agent = Agent(name="TestAgent")
    
    # Get two timestamps
    ts1 = agent._get_timestamp()
    ts2 = agent._get_timestamp()
    
    # Should be valid ISO format timestamps
    from datetime import datetime
    dt1 = datetime.fromisoformat(ts1.replace('Z', '+00:00'))
    dt2 = datetime.fromisoformat(ts2.replace('Z', '+00:00'))
    
    # Should be very close in time (within 1 second)
    assert (dt2 - dt1).total_seconds() < 1.0 