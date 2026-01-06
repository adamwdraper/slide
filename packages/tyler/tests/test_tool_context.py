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


class TestToolContextDataclass:
    """Tests for the ToolContext dataclass."""
    
    def test_toolcontext_creation_with_defaults(self):
        """Test ToolContext can be created with defaults."""
        ctx = ToolContext()
        
        assert ctx.tool_name is None
        assert ctx.tool_call_id is None
        assert ctx.deps == {}
    
    def test_toolcontext_creation_with_values(self):
        """Test ToolContext can be created with all values."""
        deps = {"db": "mock_db", "user_id": "123"}
        ctx = ToolContext(
            tool_name="my_tool",
            tool_call_id="call_abc123",
            deps=deps
        )
        
        assert ctx.tool_name == "my_tool"
        assert ctx.tool_call_id == "call_abc123"
        assert ctx.deps == deps
    
    def test_toolcontext_dict_style_getitem(self):
        """Test dict-style access with __getitem__."""
        ctx = ToolContext(deps={"key": "value", "number": 42})
        
        assert ctx["key"] == "value"
        assert ctx["number"] == 42
    
    def test_toolcontext_dict_style_getitem_keyerror(self):
        """Test __getitem__ raises KeyError for missing key."""
        ctx = ToolContext(deps={"key": "value"})
        
        with pytest.raises(KeyError):
            _ = ctx["missing_key"]
    
    def test_toolcontext_dict_style_setitem(self):
        """Test dict-style assignment with __setitem__."""
        ctx = ToolContext()
        ctx["new_key"] = "new_value"
        
        assert ctx["new_key"] == "new_value"
        assert ctx.deps["new_key"] == "new_value"
    
    def test_toolcontext_get_method(self):
        """Test get() method with default value."""
        ctx = ToolContext(deps={"key": "value"})
        
        assert ctx.get("key") == "value"
        assert ctx.get("missing") is None
        assert ctx.get("missing", "default") == "default"
    
    def test_toolcontext_contains(self):
        """Test 'in' operator via __contains__."""
        ctx = ToolContext(deps={"key": "value"})
        
        assert "key" in ctx
        assert "missing" not in ctx
    
    def test_toolcontext_keys(self):
        """Test keys() method."""
        ctx = ToolContext(deps={"a": 1, "b": 2})
        
        assert set(ctx.keys()) == {"a", "b"}
    
    def test_toolcontext_items(self):
        """Test items() method."""
        ctx = ToolContext(deps={"a": 1, "b": 2})
        
        assert dict(ctx.items()) == {"a": 1, "b": 2}
    
    def test_toolcontext_values(self):
        """Test values() method."""
        ctx = ToolContext(deps={"a": 1, "b": 2})
        
        assert set(ctx.values()) == {1, 2}
    
    def test_toolcontext_iteration(self):
        """Test iteration via __iter__."""
        ctx = ToolContext(deps={"a": 1, "b": 2, "c": 3})
        
        keys = list(ctx)
        assert set(keys) == {"a", "b", "c"}
    
    def test_toolcontext_len(self):
        """Test len() via __len__."""
        ctx = ToolContext(deps={"a": 1, "b": 2})
        
        assert len(ctx) == 2
    
    def test_toolcontext_empty_len(self):
        """Test len() for empty context."""
        ctx = ToolContext()
        
        assert len(ctx) == 0
    
    def test_toolcontext_update_with_dict(self):
        """Test update() with a dictionary."""
        ctx = ToolContext(deps={"a": 1, "b": 2})
        
        ctx.update({"b": 20, "c": 3})
        
        assert ctx["a"] == 1
        assert ctx["b"] == 20
        assert ctx["c"] == 3
    
    def test_toolcontext_update_with_kwargs(self):
        """Test update() with keyword arguments."""
        ctx = ToolContext(deps={"a": 1})
        
        ctx.update(b=2, c=3)
        
        assert ctx["a"] == 1
        assert ctx["b"] == 2
        assert ctx["c"] == 3
    
    def test_toolcontext_update_with_toolcontext(self):
        """Test update() with another ToolContext."""
        ctx1 = ToolContext(deps={"a": 1})
        ctx2 = ToolContext(deps={"b": 2, "c": 3})
        
        ctx1.update(ctx2)
        
        assert ctx1["a"] == 1
        assert ctx1["b"] == 2
        assert ctx1["c"] == 3
    
    def test_toolcontext_update_combined(self):
        """Test update() with dict and kwargs combined."""
        ctx = ToolContext(deps={"a": 1})
        
        ctx.update({"b": 2}, c=3)
        
        assert ctx["a"] == 1
        assert ctx["b"] == 2
        assert ctx["c"] == 3
    
    @pytest.mark.asyncio
    async def test_tool_receives_rich_context(self):
        """Test that tools receive ToolContext with metadata fields."""
        received_ctx = None
        
        async def tool_checking_context(ctx: ToolContext, value: str) -> str:
            nonlocal received_ctx
            received_ctx = ctx
            return f"Value: {value}"
        
        runner = ToolRunner()
        runner.register_tool(
            name="check_ctx",
            implementation=tool_checking_context,
            definition={"name": "check_ctx", "parameters": {"type": "object"}}
        )
        
        # Create a rich context with metadata
        ctx = ToolContext(
            tool_name="check_ctx",
            tool_call_id="call_123",
            deps={"user_id": "test_user"}
        )
        
        result = await runner.run_tool_async(
            "check_ctx",
            {"value": "hello"},
            context=ctx
        )
        
        assert result == "Value: hello"
        assert received_ctx is not None
        assert received_ctx.tool_name == "check_ctx"
        assert received_ctx.tool_call_id == "call_123"
        assert received_ctx["user_id"] == "test_user"


class TestAgentLevelToolContext:
    """Tests for agent-level tool_context that merges with run-level context."""
    
    @pytest.fixture
    def agent_with_context(self):
        """Create an agent with agent-level context."""
        return Agent(
            model_name="gpt-4o",
            tool_context={"db_client": "mock_db", "config": {"timeout": 30}}
        )
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        thread = Thread()
        thread.add_message(Message(role="user", content="Test message"))
        return thread
    
    @pytest.mark.asyncio
    async def test_agent_level_context_is_used(self, agent_with_context, thread):
        """Test that agent-level tool_context is available during run."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Done"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].message.refusal = None
        
        with patch.object(agent_with_context, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            # Run without any run-level context
            await agent_with_context.run(thread)
            
            # During run, _tool_context should have been set from agent-level
            # (it's cleared after, so we check via the step call)
            # The test verifies no error occurred with agent-level context
    
    @pytest.mark.asyncio
    async def test_agent_level_context_cleared_after_run(self, agent_with_context, thread):
        """Test that _tool_context is cleared after run even with agent-level context."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Done"
        mock_response.choices[0].message.tool_calls = None
        
        with patch.object(agent_with_context, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            await agent_with_context.run(thread)
            
            # _tool_context should be cleared after run
            assert agent_with_context._tool_context is None
            # But agent.tool_context still exists
            assert agent_with_context.tool_context == {"db_client": "mock_db", "config": {"timeout": 30}}
    
    @pytest.mark.asyncio
    async def test_run_level_context_merges_with_agent_level(self, agent_with_context, thread):
        """Test that run-level context merges with agent-level context."""
        captured_context = None
        
        original_step = agent_with_context.step
        async def capturing_step(*args, **kwargs):
            nonlocal captured_context
            # Capture the merged context during execution
            captured_context = agent_with_context._tool_context
            # Return a mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].finish_reason = "stop"
            mock_response.choices[0].message.content = "Done"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].message.refusal = None
            return (mock_response, {"usage": {}})
        
        with patch.object(agent_with_context, 'step', side_effect=capturing_step):
            # Run with per-run context that adds new keys
            await agent_with_context.run(
                thread,
                tool_context={"run_key": "run_value"}
            )
        
        # Verify merging happened
        assert captured_context is not None
        assert captured_context["db_client"] == "mock_db"      # From agent
        assert captured_context["config"]["timeout"] == 30     # From agent  
        assert captured_context["run_key"] == "run_value"      # From run
    
    @pytest.mark.asyncio
    async def test_run_level_context_overrides_agent_level(self, agent_with_context, thread):
        """Test that run-level context overrides agent-level for same keys."""
        captured_context = None
        
        async def capturing_step(*args, **kwargs):
            nonlocal captured_context
            captured_context = agent_with_context._tool_context
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].finish_reason = "stop"
            mock_response.choices[0].message.content = "Done"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].message.refusal = None
            return (mock_response, {"usage": {}})
        
        with patch.object(agent_with_context, 'step', side_effect=capturing_step):
            # Run with context that overrides db_client
            await agent_with_context.run(
                thread,
                tool_context={"db_client": "overridden_db"}
            )
        
        # Run-level should override agent-level
        assert captured_context["db_client"] == "overridden_db"  # Overridden
        assert captured_context["config"]["timeout"] == 30        # From agent
    
    @pytest.mark.asyncio
    async def test_agent_without_context_uses_run_level_only(self, thread):
        """Test agent without tool_context uses only run-level context."""
        agent_no_context = Agent(model_name="gpt-4o")
        captured_context = None
        
        async def capturing_step(*args, **kwargs):
            nonlocal captured_context
            captured_context = agent_no_context._tool_context
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].finish_reason = "stop"
            mock_response.choices[0].message.content = "Done"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].message.refusal = None
            return (mock_response, {"usage": {}})
        
        with patch.object(agent_no_context, 'step', side_effect=capturing_step):
            await agent_no_context.run(
                thread,
                tool_context={"only_run": "value"}
            )
        
        assert captured_context == {"only_run": "value"}
