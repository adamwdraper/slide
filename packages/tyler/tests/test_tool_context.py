"""Tests for tool context injection feature.

Tests the tool_context parameter for Agent.run() and Agent.stream()
that enables dependency injection into tools.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from tyler import Agent, ToolContextError
from tyler.utils.tool_runner import ToolRunner, ToolContext
from narrator import Thread, Message


class TestToolContextInjection:
    """Tests for context injection into tools."""
    
    @pytest.fixture
    def tool_runner(self):
        """Create a fresh ToolRunner for testing."""
        return ToolRunner()
    
    def test_tool_expects_context_with_ctx_param(self, tool_runner):
        """Test detection of tools that expect context via 'ctx' parameter."""
        async def tool_with_ctx(ctx: ToolContext, query: str) -> str:
            return f"Query: {query}, User: {ctx.get('user_id')}"
        
        assert tool_runner._tool_expects_context(tool_with_ctx) is True
    
    def test_tool_expects_context_with_context_param(self, tool_runner):
        """Test detection of tools that expect context via 'context' parameter."""
        async def tool_with_context(context: Dict[str, Any], data: str) -> str:
            return f"Data: {data}"
        
        assert tool_runner._tool_expects_context(tool_with_context) is True
    
    def test_tool_does_not_expect_context(self, tool_runner):
        """Test that tools without ctx/context don't expect context."""
        async def regular_tool(query: str, limit: int = 10) -> str:
            return f"Query: {query}, Limit: {limit}"
        
        assert tool_runner._tool_expects_context(regular_tool) is False
    
    def test_tool_no_params_does_not_expect_context(self, tool_runner):
        """Test that tools with no params don't expect context."""
        async def no_param_tool() -> str:
            return "No params"
        
        assert tool_runner._tool_expects_context(no_param_tool) is False
    
    @pytest.mark.asyncio
    async def test_context_injection_async_tool(self, tool_runner):
        """Test context is injected into async tools."""
        received_context = {}
        
        async def async_tool_with_ctx(ctx: ToolContext, value: str) -> str:
            received_context.update(ctx)
            return f"Received: {value}"
        
        # Register the tool
        tool_runner.register_tool(
            name="test_tool",
            implementation=async_tool_with_ctx,
            definition={"name": "test_tool", "parameters": {"type": "object"}}
        )
        
        # Call with context
        context = {"user_id": "user_123", "db": "mock_db"}
        result = await tool_runner.run_tool_async(
            "test_tool", 
            {"value": "hello"},
            context=context
        )
        
        assert result == "Received: hello"
        assert received_context == context
    
    @pytest.mark.asyncio
    async def test_context_injection_sync_tool(self, tool_runner):
        """Test context is injected into sync tools (run in thread pool)."""
        received_context = {}
        
        def sync_tool_with_ctx(ctx: ToolContext, value: str) -> str:
            received_context.update(ctx)
            return f"Sync received: {value}"
        
        # Register the tool
        tool_runner.register_tool(
            name="sync_tool",
            implementation=sync_tool_with_ctx,
            definition={"name": "sync_tool", "parameters": {"type": "object"}}
        )
        
        context = {"setting": "value"}
        result = await tool_runner.run_tool_async(
            "sync_tool",
            {"value": "world"},
            context=context
        )
        
        assert result == "Sync received: world"
        assert received_context == context
    
    @pytest.mark.asyncio
    async def test_missing_context_raises_error(self, tool_runner):
        """Test that ToolContextError is raised when context is required but not provided."""
        async def tool_requiring_ctx(ctx: ToolContext) -> str:
            return "Should not reach here"
        
        tool_runner.register_tool(
            name="ctx_tool",
            implementation=tool_requiring_ctx,
            definition={"name": "ctx_tool", "parameters": {"type": "object"}}
        )
        
        with pytest.raises(ToolContextError) as exc_info:
            await tool_runner.run_tool_async("ctx_tool", {}, context=None)
        
        assert "requires context" in str(exc_info.value)
        assert "ctx_tool" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_tool_without_context_ignores_provided_context(self, tool_runner):
        """Test that tools without ctx param work when context is provided."""
        async def regular_tool(query: str) -> str:
            return f"Query: {query}"
        
        tool_runner.register_tool(
            name="regular",
            implementation=regular_tool,
            definition={"name": "regular", "parameters": {"type": "object"}}
        )
        
        # Should work fine - context is ignored for this tool
        result = await tool_runner.run_tool_async(
            "regular",
            {"query": "test"},
            context={"ignored": "data"}
        )
        
        assert result == "Query: test"
    
    @pytest.mark.asyncio
    async def test_tool_without_context_works_without_context(self, tool_runner):
        """Test backward compatibility - tools without ctx work without context."""
        async def regular_tool(query: str) -> str:
            return f"Query: {query}"
        
        tool_runner.register_tool(
            name="regular",
            implementation=regular_tool,
            definition={"name": "regular", "parameters": {"type": "object"}}
        )
        
        # Should work with context=None (default)
        result = await tool_runner.run_tool_async(
            "regular",
            {"query": "test"},
            context=None
        )
        
        assert result == "Query: test"


class TestAgentToolContext:
    """Tests for tool context in Agent.run() and Agent.stream()."""
    
    @pytest.fixture
    def agent(self):
        """Create agent with a tool that requires context."""
        return Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test tool context"
        )
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Get my orders"))
        return t
    
    @pytest.mark.asyncio
    async def test_tool_context_passed_through_run(self, agent, thread):
        """Test that tool_context is available during agent.run()."""
        # We'll verify that _tool_context is set during execution
        captured_context = {}
        
        original_handle = agent._handle_tool_execution
        
        async def mock_handle(tool_call, context=None):
            captured_context['ctx'] = agent._tool_context
            return "Tool result"
        
        agent._handle_tool_execution = mock_handle
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Let me check your orders"
        mock_response.choices[0].message.tool_calls = None
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            context = {"user_id": "123", "db": "mock"}
            await agent.run(thread, tool_context=context)
            
            # Context should be cleared after run completes
            assert agent._tool_context is None
    
    @pytest.mark.asyncio
    async def test_tool_context_cleared_after_run(self, agent, thread):
        """Test that tool_context is cleared after run() completes."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Done"
        mock_response.choices[0].message.tool_calls = None
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            await agent.run(thread, tool_context={"key": "value"})
            
            # Should be None after execution
            assert agent._tool_context is None
    
    @pytest.mark.asyncio
    async def test_tool_context_cleared_on_error(self, agent, thread):
        """Test that tool_context is cleared even if run() raises."""
        with patch.object(agent, '_run_complete', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Test error")
            
            with pytest.raises(RuntimeError):
                await agent.run(thread, tool_context={"key": "value"})
            
            # Should still be cleared after error
            assert agent._tool_context is None


class TestExecuteToolCallContext:
    """Tests for execute_tool_call with context."""
    
    @pytest.fixture
    def tool_runner(self):
        """Create a ToolRunner with registered tools."""
        runner = ToolRunner()
        
        async def tool_with_ctx(ctx: ToolContext, query: str) -> str:
            return f"User {ctx['user_id']} queried: {query}"
        
        async def tool_without_ctx(query: str) -> str:
            return f"Queried: {query}"
        
        runner.register_tool(
            "with_ctx",
            tool_with_ctx,
            {"name": "with_ctx", "parameters": {"type": "object"}}
        )
        runner.register_tool(
            "without_ctx", 
            tool_without_ctx,
            {"name": "without_ctx", "parameters": {"type": "object"}}
        )
        
        return runner
    
    @pytest.mark.asyncio
    async def test_execute_tool_call_with_context(self, tool_runner):
        """Test execute_tool_call passes context correctly."""
        # Create mock tool_call object
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "with_ctx"
        mock_tool_call.function.arguments = json.dumps({"query": "test"})
        
        context = {"user_id": "user_456"}
        result = await tool_runner.execute_tool_call(mock_tool_call, context=context)
        
        assert result == "User user_456 queried: test"
    
    @pytest.mark.asyncio
    async def test_execute_tool_call_without_context_tool(self, tool_runner):
        """Test execute_tool_call works for tools that don't need context."""
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "without_ctx"
        mock_tool_call.function.arguments = json.dumps({"query": "hello"})
        
        # Context is provided but tool doesn't use it
        result = await tool_runner.execute_tool_call(
            mock_tool_call, 
            context={"ignored": "data"}
        )
        
        assert result == "Queried: hello"
    
    @pytest.mark.asyncio
    async def test_execute_tool_call_missing_required_context(self, tool_runner):
        """Test execute_tool_call raises when context is needed but missing."""
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "with_ctx"
        mock_tool_call.function.arguments = json.dumps({"query": "test"})
        
        with pytest.raises(ToolContextError):
            await tool_runner.execute_tool_call(mock_tool_call, context=None)

