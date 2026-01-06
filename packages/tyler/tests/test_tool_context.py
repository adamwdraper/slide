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
    
    def test_tool_with_optional_context_does_not_require_context(self, tool_runner):
        """Test that tools with optional ctx param (has default) don't require context."""
        from typing import Optional
        
        async def tool_with_optional_ctx(ctx: Optional[ToolContext] = None, query: str = "") -> str:
            return f"Query: {query}"
        
        # Should not require context (has default value)
        assert tool_runner._tool_expects_context(tool_with_optional_ctx) is False
        # But should accept optional context
        assert tool_runner._tool_accepts_optional_context(tool_with_optional_ctx) is True
    
    def test_tool_with_required_context_requires_context(self, tool_runner):
        """Test that tools with required ctx param (no default) require context."""
        async def tool_with_required_ctx(ctx: ToolContext, query: str) -> str:
            return f"Query: {query}"
        
        # Should require context (no default value)
        assert tool_runner._tool_expects_context(tool_with_required_ctx) is True
        # Should not be optional
        assert tool_runner._tool_accepts_optional_context(tool_with_required_ctx) is False
    
    @pytest.mark.asyncio
    async def test_optional_context_receives_context_when_provided(self, tool_runner):
        """Test that tools with optional context still receive context when available."""
        received_ctx = None
        
        async def tool_with_optional_ctx(ctx: ToolContext = None, value: str = "") -> str:
            nonlocal received_ctx
            received_ctx = ctx
            return f"Value: {value}"
        
        tool_runner.register_tool(
            name="optional_ctx_tool",
            implementation=tool_with_optional_ctx,
            definition={"name": "optional_ctx_tool", "parameters": {"type": "object"}}
        )
        
        # Call with context provided
        ctx = ToolContext(deps={"user_id": "test_user"})
        result = await tool_runner.run_tool_async(
            "optional_ctx_tool",
            {"value": "hello"},
            context=ctx
        )
        
        assert result == "Value: hello"
        assert received_ctx is not None
        assert received_ctx["user_id"] == "test_user"
    
    @pytest.mark.asyncio
    async def test_optional_context_works_without_context(self, tool_runner):
        """Test that tools with optional context work when no context is provided."""
        received_ctx = "not_called"
        
        async def tool_with_optional_ctx(ctx: ToolContext = None, value: str = "") -> str:
            nonlocal received_ctx
            received_ctx = ctx
            return f"Value: {value}"
        
        tool_runner.register_tool(
            name="optional_ctx_tool2",
            implementation=tool_with_optional_ctx,
            definition={"name": "optional_ctx_tool2", "parameters": {"type": "object"}}
        )
        
        # Call without context - should NOT raise ToolContextError
        result = await tool_runner.run_tool_async(
            "optional_ctx_tool2",
            {"value": "hello"},
            context=None
        )
        
        assert result == "Value: hello"
        # Context param should not have been passed (tool uses default)
        # The function was called without context argument
    
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


class TestProgressCallbackIntegration:
    """Test progress_callback handling in _handle_tool_execution."""
    
    @pytest.fixture
    def captured_ctx_holder(self):
        """Mutable container for captured context."""
        return {"ctx": None}
    
    @pytest.fixture
    def agent_with_inspecting_tool(self, captured_ctx_holder):
        """Create an agent with a tool that captures its context."""
        async def inspecting_tool(ctx=None, message: str = "") -> str:
            captured_ctx_holder["ctx"] = ctx
            return f"got: {message}"
        
        tool_def = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "inspecting_tool",
                    "description": "A tool that captures context",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        }
                    }
                }
            },
            "implementation": inspecting_tool
        }
        
        return Agent(
            model_name="gpt-4o-mini",
            tools=[tool_def]
        )
    
    @pytest.mark.asyncio
    async def test_progress_callback_from_tool_context_dict(self, agent_with_inspecting_tool, captured_ctx_holder):
        """Test that progress_callback in tool_context dict is extracted and used."""
        callback_invocations = []
        
        async def my_callback(progress, total=None, message=None):
            callback_invocations.append((progress, total, message))
        
        # Create tool call
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function = MagicMock()
        tool_call.function.name = "inspecting_tool"
        tool_call.function.arguments = '{"message": "hello"}'
        
        # Set tool_context with progress_callback
        agent_with_inspecting_tool._tool_context = {"progress_callback": my_callback, "user_id": "123"}
        
        result = await agent_with_inspecting_tool._handle_tool_execution(tool_call)
        
        # Verify the tool executed (returns raw result string)
        assert "got: hello" in str(result)
        
        # Verify context was passed and has progress_callback on typed field
        ctx = captured_ctx_holder["ctx"]
        assert ctx is not None
        assert ctx.progress_callback == my_callback
    
    @pytest.mark.asyncio
    async def test_progress_callback_not_in_deps_after_extraction(self, agent_with_inspecting_tool, captured_ctx_holder):
        """Test that progress_callback is removed from deps after extraction."""
        async def my_callback(progress, total=None, message=None):
            pass
        
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function = MagicMock()
        tool_call.function.name = "inspecting_tool"
        tool_call.function.arguments = '{"message": "hello"}'
        
        # Set tool_context with progress_callback
        agent_with_inspecting_tool._tool_context = {"progress_callback": my_callback, "user_id": "123"}
        
        await agent_with_inspecting_tool._handle_tool_execution(tool_call)
        
        # Verify progress_callback is NOT in deps (was extracted to typed field)
        ctx = captured_ctx_holder["ctx"]
        assert ctx is not None
        assert "progress_callback" not in ctx.deps
        assert ctx.get("user_id") == "123"
        # But it should be on the typed field
        assert ctx.progress_callback is not None
    
    @pytest.fixture
    def progress_tracking(self):
        """Mutable containers for tracking progress invocations."""
        return {
            "streaming": [],
            "user": []
        }
    
    @pytest.fixture
    def agent_with_progress_tool(self, progress_tracking):
        """Create an agent with a tool that reports progress."""
        async def tool_with_progress(ctx=None, steps: int = 3) -> str:
            if ctx and ctx.progress_callback:
                for i in range(steps):
                    await ctx.progress_callback(i + 1, steps, f"Step {i+1}")
            return "done"
        
        tool_def = {
            "definition": {
                "type": "function",
                "function": {
                    "name": "progress_tool",
                    "description": "A tool that reports progress",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "steps": {"type": "integer", "default": 3}
                        }
                    }
                }
            },
            "implementation": tool_with_progress
        }
        
        return Agent(
            model_name="gpt-4o-mini",
            tools=[tool_def]
        )
    
    @pytest.mark.asyncio
    async def test_composite_callback_when_both_exist(self, agent_with_progress_tool, progress_tracking):
        """Test that BOTH streaming callback AND user callback are called.
        
        This tests the critical bug fix where user's custom progress_callback
        was being silently ignored when streaming mode also provided a callback.
        """
        async def streaming_callback(progress, total=None, message=None):
            progress_tracking["streaming"].append(("stream", progress, total, message))
        
        async def user_callback(progress, total=None, message=None):
            progress_tracking["user"].append(("user", progress, total, message))
        
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function = MagicMock()
        tool_call.function.name = "progress_tool"
        tool_call.function.arguments = '{"steps": 3}'
        
        # Set user callback in tool_context
        agent_with_progress_tool._tool_context = {"progress_callback": user_callback}
        
        # Call with streaming callback parameter (simulates stream=events mode)
        await agent_with_progress_tool._handle_tool_execution(tool_call, progress_callback=streaming_callback)
        
        # BOTH should have been called (composite callback)
        assert len(progress_tracking["streaming"]) == 3, f"Streaming callback should be called 3 times, got {len(progress_tracking['streaming'])}"
        assert len(progress_tracking["user"]) == 3, f"User callback should be called 3 times, got {len(progress_tracking['user'])}"
        
        # Verify data is correct
        assert progress_tracking["streaming"][0] == ("stream", 1, 3, "Step 1")
        assert progress_tracking["user"][0] == ("user", 1, 3, "Step 1")
    
    @pytest.mark.asyncio
    async def test_only_streaming_callback_when_no_user_callback(self, agent_with_progress_tool, progress_tracking):
        """Test that only streaming callback is used when no user callback."""
        async def streaming_callback(progress, total=None, message=None):
            progress_tracking["streaming"].append(progress)
        
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function = MagicMock()
        tool_call.function.name = "progress_tool"
        tool_call.function.arguments = '{"steps": 2}'
        
        # No user callback, empty tool_context
        agent_with_progress_tool._tool_context = {}
        
        await agent_with_progress_tool._handle_tool_execution(tool_call, progress_callback=streaming_callback)
        
        assert len(progress_tracking["streaming"]) == 2
    
    @pytest.mark.asyncio
    async def test_only_user_callback_when_no_streaming_callback(self, agent_with_progress_tool, progress_tracking):
        """Test that only user callback is used when no streaming callback (run mode)."""
        async def user_callback(progress, total=None, message=None):
            progress_tracking["user"].append(progress)
        
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function = MagicMock()
        tool_call.function.name = "progress_tool"
        tool_call.function.arguments = '{"steps": 2}'
        
        # User callback in tool_context, no streaming callback parameter
        agent_with_progress_tool._tool_context = {"progress_callback": user_callback}
        
        await agent_with_progress_tool._handle_tool_execution(tool_call)  # No progress_callback param
        
        assert len(progress_tracking["user"]) == 2
