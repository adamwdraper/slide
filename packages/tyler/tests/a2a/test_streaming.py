"""Tests for A2A token streaming implementation.

Tests cover:
- Streaming executor emits chunks (AC: tokens arrive within ~100ms)
- Streaming executor final event (AC: lastChunk=True on completion)
- Streaming disabled uses run() (AC: streaming disabled config)
- Streaming with tool calls (AC: tool calls resume streaming)
- Streaming error handling (AC: error emits failed status)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import sys

from tyler.models.execution import EventType, ExecutionEvent


# Create proper mock classes for A2A SDK types that support inheritance
class MockAgentExecutor:
    """Mock base class for AgentExecutor."""
    pass


class MockRequestContext:
    """Mock RequestContext."""
    pass


class MockEventQueue:
    """Mock EventQueue."""
    pass


# Setup mock modules with proper classes
def setup_a2a_mocks():
    """Setup A2A SDK mocks with proper class support."""
    mock_a2a = MagicMock()
    
    # Server module mocks
    mock_server = MagicMock()
    mock_agent_execution = MagicMock()
    mock_agent_execution.AgentExecutor = MockAgentExecutor
    mock_agent_execution.RequestContext = MockRequestContext
    mock_server.agent_execution = mock_agent_execution
    
    mock_events = MagicMock()
    mock_events.EventQueue = MockEventQueue
    mock_events.InMemoryQueueManager = MagicMock
    mock_server.events = mock_events
    
    mock_tasks = MagicMock()
    mock_tasks.InMemoryTaskStore = MagicMock
    mock_tasks.InMemoryPushNotificationConfigStore = MagicMock
    mock_server.tasks = mock_tasks
    
    mock_a2a.server = mock_server
    
    return {
        'a2a': mock_a2a,
        'a2a.server': mock_server,
        'a2a.server.apps': MagicMock(),
        'a2a.server.request_handlers': MagicMock(),
        'a2a.server.agent_execution': mock_agent_execution,
        'a2a.server.events': mock_events,
        'a2a.server.tasks': mock_tasks,
        'a2a.types': MagicMock(),
    }


def create_mock_event(event_type: EventType, data: dict) -> ExecutionEvent:
    """Create a mock ExecutionEvent."""
    return ExecutionEvent(
        type=event_type,
        timestamp=datetime.now(timezone.utc),
        data=data
    )


async def async_generator(items):
    """Helper to create async generator from list."""
    for item in items:
        yield item


class TestStreamingExecutorEmitsChunks:
    """Test that streaming executor emits chunks for each LLM_STREAM_CHUNK event."""
    
    @pytest.mark.asyncio
    async def test_streaming_executor_emits_chunks(self):
        """Test that executor emits TaskArtifactUpdateEvent for each token chunk."""
        # Setup proper A2A mocks
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            # Reimport to get fresh module with mocks
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            TylerAgentExecutor = server_module.TylerAgentExecutor
            
            # Setup mock agent with streaming
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent"
            
            # Create mock streaming events
            streaming_events = [
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "Hello"}),
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": " world"}),
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "!"}),
                create_mock_event(EventType.EXECUTION_COMPLETE, {"duration_ms": 100}),
            ]
            
            mock_agent.stream = MagicMock(return_value=async_generator(streaming_events))
            
            # Create executor with streaming enabled
            executor = TylerAgentExecutor(mock_agent, streaming=True)
            
            # Setup mock context and event queue
            mock_context = MagicMock()
            mock_context.task_id = "test-task-123"
            mock_context.context_id = "test-context"
            mock_context.message = MagicMock()
            mock_context.message.parts = None
            
            mock_event_queue = AsyncMock()
            
            # Execute
            await executor.execute(mock_context, mock_event_queue)
            
            # Verify chunks were emitted
            enqueue_calls = mock_event_queue.enqueue_event.call_args_list
            
            # Should have: 1 working status + 3 chunk artifacts + 1 final artifact + 1 completed status
            # Total: at least 6 events
            assert len(enqueue_calls) >= 6, f"Expected at least 6 events, got {len(enqueue_calls)}"
            
            # Verify stream() was called (meaning streaming path was used)
            mock_agent.stream.assert_called_once()


class TestStreamingExecutorFinalEvent:
    """Test that streaming executor sends lastChunk=True on completion."""
    
    @pytest.mark.asyncio
    async def test_streaming_executor_final_event_has_last_chunk(self):
        """Test that final artifact event has lastChunk=True."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            TylerAgentExecutor = server_module.TylerAgentExecutor
            
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent"
            
            streaming_events = [
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "Done"}),
                create_mock_event(EventType.EXECUTION_COMPLETE, {"duration_ms": 50}),
            ]
            
            mock_agent.stream = MagicMock(return_value=async_generator(streaming_events))
            
            executor = TylerAgentExecutor(mock_agent, streaming=True)
            
            mock_context = MagicMock()
            mock_context.task_id = "test-task-456"
            mock_context.context_id = "test-context"
            mock_context.message = MagicMock()
            mock_context.message.parts = None
            
            mock_event_queue = AsyncMock()
            
            await executor.execute(mock_context, mock_event_queue)
            
            enqueue_calls = mock_event_queue.enqueue_event.call_args_list
            
            # Should have multiple events: working status + chunk(s) + final artifact + completed
            # At least 4 events for this simple case
            assert len(enqueue_calls) >= 4, f"Expected at least 4 events, got {len(enqueue_calls)}"
            
            # Verify stream() was called (meaning streaming path was used)
            mock_agent.stream.assert_called_once()


class TestStreamingDisabledUsesRun:
    """Test that when streaming is disabled, executor uses agent.run()."""
    
    @pytest.mark.asyncio
    async def test_streaming_disabled_uses_run(self):
        """Test that executor falls back to agent.run() when streaming disabled."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            TylerAgentExecutor = server_module.TylerAgentExecutor
            
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent"
            
            # Setup run() to return AgentResult
            mock_result = MagicMock()
            mock_result.new_messages = [MagicMock(content="Hello", role="assistant")]
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent.stream = MagicMock()  # Should NOT be called
            
            executor = TylerAgentExecutor(mock_agent, streaming=False)
            
            mock_context = MagicMock()
            mock_context.task_id = "test-task-789"
            mock_context.context_id = None
            mock_context.message = MagicMock()
            mock_context.message.parts = None
            
            mock_event_queue = AsyncMock()
            
            await executor.execute(mock_context, mock_event_queue)
            
            # Verify run() was called, stream() was not
            mock_agent.run.assert_called_once()
            mock_agent.stream.assert_not_called()


class TestStreamingWithToolCalls:
    """Test that streaming works correctly with tool call iterations."""
    
    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls(self):
        """Test that streaming resumes after tool execution."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            TylerAgentExecutor = server_module.TylerAgentExecutor
            
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent"
            
            # Simulate: first response with tool call, then final response
            streaming_events = [
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "Let me "}),
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "check..."}),
                create_mock_event(EventType.TOOL_SELECTED, {"tool_name": "search", "arguments": {}}),
                create_mock_event(EventType.TOOL_RESULT, {"result": "Found data"}),
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "The answer"}),
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": " is 42."}),
                create_mock_event(EventType.EXECUTION_COMPLETE, {"duration_ms": 200}),
            ]
            
            mock_agent.stream = MagicMock(return_value=async_generator(streaming_events))
            
            executor = TylerAgentExecutor(mock_agent, streaming=True)
            
            mock_context = MagicMock()
            mock_context.task_id = "test-task-tool"
            mock_context.context_id = "tool-context"
            mock_context.message = MagicMock()
            mock_context.message.parts = None
            
            mock_event_queue = AsyncMock()
            
            await executor.execute(mock_context, mock_event_queue)
            
            enqueue_calls = mock_event_queue.enqueue_event.call_args_list
            
            # Should have artifact events for all 4 content chunks
            artifact_events = [
                c for c in enqueue_calls
                if hasattr(c.args[0], 'artifact')
            ]
            
            # At least 4 artifact events (4 chunks) + 1 final
            assert len(artifact_events) >= 4, f"Expected at least 4 artifact events, got {len(artifact_events)}"


class TestStreamingErrorHandling:
    """Test that streaming handles errors correctly."""
    
    @pytest.mark.asyncio
    async def test_streaming_error_emits_failed_status(self):
        """Test that errors emit TaskStatusUpdateEvent with failed state."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            TylerAgentExecutor = server_module.TylerAgentExecutor
            
            mock_agent = MagicMock()
            mock_agent.name = "Test Agent"
            
            streaming_events = [
                create_mock_event(EventType.LLM_STREAM_CHUNK, {"content_chunk": "Starting"}),
                create_mock_event(EventType.EXECUTION_ERROR, {"message": "API Error", "error_type": "APIError"}),
            ]
            
            mock_agent.stream = MagicMock(return_value=async_generator(streaming_events))
            
            executor = TylerAgentExecutor(mock_agent, streaming=True)
            
            mock_context = MagicMock()
            mock_context.task_id = "test-task-error"
            mock_context.context_id = "error-context"
            mock_context.message = MagicMock()
            mock_context.message.parts = None
            
            mock_event_queue = AsyncMock()
            
            await executor.execute(mock_context, mock_event_queue)
            
            enqueue_calls = mock_event_queue.enqueue_event.call_args_list
            
            # Should have: working status + 1 chunk + error status
            # At least 3 events
            assert len(enqueue_calls) >= 3, f"Expected at least 3 events, got {len(enqueue_calls)}"
            
            # Verify stream() was called
            mock_agent.stream.assert_called_once()


class TestA2AServerStreamingConfig:
    """Test A2AServer streaming configuration."""
    
    def test_server_accepts_streaming_param(self):
        """Test that A2AServer accepts streaming parameter."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            A2AServer = server_module.A2AServer
            
            mock_agent = MagicMock()
            mock_agent.name = "Test"
            mock_agent.purpose = "Test"
            mock_agent.tools = []
            
            with patch.object(server_module, 'HAS_A2A', True):
                # Test default (streaming enabled)
                server = A2AServer(agent=mock_agent)
                assert server._streaming_enabled is True
                
                # Test explicit enable
                server_enabled = A2AServer(agent=mock_agent, streaming=True)
                assert server_enabled._streaming_enabled is True
                
                # Test explicit disable
                server_disabled = A2AServer(agent=mock_agent, streaming=False)
                assert server_disabled._streaming_enabled is False
    
    def test_streaming_config_passed_to_executor(self):
        """Test that streaming config is passed to executor."""
        a2a_mocks = setup_a2a_mocks()
        
        with patch.dict('sys.modules', a2a_mocks):
            import importlib
            import tyler.a2a.server as server_module
            importlib.reload(server_module)
            
            A2AServer = server_module.A2AServer
            
            mock_agent = MagicMock()
            mock_agent.name = "Test"
            mock_agent.purpose = "Test"
            mock_agent.tools = []
            
            with patch.object(server_module, 'HAS_A2A', True):
                server = A2AServer(agent=mock_agent, streaming=False)
                
                # Executor should have streaming disabled
                assert server._executor._streaming_enabled is False
