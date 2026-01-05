"""Tests for tool timeout feature.

Tests the timeout parameter for tool registration and execution.
"""
import pytest
import asyncio
import json
from unittest.mock import MagicMock

from tyler.utils.tool_runner import ToolRunner, ToolContext


class TestToolTimeout:
    """Tests for tool execution timeout."""
    
    @pytest.fixture
    def tool_runner(self):
        """Create a fresh ToolRunner for testing."""
        return ToolRunner()
    
    def test_register_tool_with_timeout(self, tool_runner):
        """Test that tools can be registered with a timeout."""
        async def fast_tool(query: str) -> str:
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="fast",
            implementation=fast_tool,
            definition={"name": "fast", "parameters": {"type": "object"}},
            timeout=5.0
        )
        
        assert tool_runner.tools["fast"]["timeout"] == 5.0
    
    def test_register_tool_without_timeout(self, tool_runner):
        """Test that tools registered without timeout have None."""
        async def regular_tool(query: str) -> str:
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="regular",
            implementation=regular_tool,
            definition={"name": "regular", "parameters": {"type": "object"}}
        )
        
        assert tool_runner.tools["regular"]["timeout"] is None
    
    def test_register_tool_with_negative_timeout_raises(self, tool_runner):
        """Test that registering a tool with negative timeout raises ValueError."""
        async def some_tool(query: str) -> str:
            return f"Result: {query}"
        
        with pytest.raises(ValueError, match="must be a positive number"):
            tool_runner.register_tool(
                name="invalid",
                implementation=some_tool,
                definition={"name": "invalid", "parameters": {"type": "object"}},
                timeout=-5.0
            )
    
    def test_register_tool_with_zero_timeout_raises(self, tool_runner):
        """Test that registering a tool with zero timeout raises ValueError."""
        async def some_tool(query: str) -> str:
            return f"Result: {query}"
        
        with pytest.raises(ValueError, match="must be a positive number"):
            tool_runner.register_tool(
                name="invalid",
                implementation=some_tool,
                definition={"name": "invalid", "parameters": {"type": "object"}},
                timeout=0
            )
    
    @pytest.mark.asyncio
    async def test_tool_completes_within_timeout(self, tool_runner):
        """Test that tools completing within timeout succeed."""
        async def fast_tool(query: str) -> str:
            await asyncio.sleep(0.01)  # 10ms
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="fast",
            implementation=fast_tool,
            definition={"name": "fast", "parameters": {"type": "object"}},
            timeout=1.0  # 1 second - plenty of time
        )
        
        result = await tool_runner.run_tool_async("fast", {"query": "test"})
        
        assert result == "Result: test"
    
    @pytest.mark.asyncio
    async def test_tool_exceeds_timeout(self, tool_runner):
        """Test that tools exceeding timeout raise TimeoutError."""
        async def slow_tool(query: str) -> str:
            await asyncio.sleep(5.0)  # 5 seconds
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="slow",
            implementation=slow_tool,
            definition={"name": "slow", "parameters": {"type": "object"}},
            timeout=0.1  # 100ms - will timeout
        )
        
        with pytest.raises(TimeoutError) as exc_info:
            await tool_runner.run_tool_async("slow", {"query": "test"})
        
        assert "slow" in str(exc_info.value)
        assert "timed out" in str(exc_info.value)
        assert "0.1" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_tool_without_timeout_no_limit(self, tool_runner):
        """Test that tools without timeout have no execution limit."""
        async def tool_no_timeout(query: str) -> str:
            await asyncio.sleep(0.05)  # 50ms
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="no_limit",
            implementation=tool_no_timeout,
            definition={"name": "no_limit", "parameters": {"type": "object"}}
            # No timeout specified
        )
        
        result = await tool_runner.run_tool_async("no_limit", {"query": "test"})
        
        assert result == "Result: test"
    
    @pytest.mark.asyncio
    async def test_execute_tool_call_with_timeout(self, tool_runner):
        """Test that execute_tool_call respects timeout."""
        async def slow_tool(query: str) -> str:
            await asyncio.sleep(5.0)
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="slow",
            implementation=slow_tool,
            definition={"name": "slow", "parameters": {"type": "object"}},
            timeout=0.1
        )
        
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "slow"
        mock_tool_call.function.arguments = json.dumps({"query": "test"})
        
        with pytest.raises(TimeoutError):
            await tool_runner.execute_tool_call(mock_tool_call)
    
    @pytest.mark.asyncio
    async def test_timeout_with_context_injection(self, tool_runner):
        """Test that timeout works with context-injected tools."""
        async def slow_ctx_tool(ctx: ToolContext, query: str) -> str:
            await asyncio.sleep(5.0)
            return f"User {ctx['user_id']} queried: {query}"
        
        tool_runner.register_tool(
            name="slow_ctx",
            implementation=slow_ctx_tool,
            definition={"name": "slow_ctx", "parameters": {"type": "object"}},
            timeout=0.1
        )
        
        context = ToolContext(deps={"user_id": "test_user"})
        
        with pytest.raises(TimeoutError) as exc_info:
            await tool_runner.run_tool_async(
                "slow_ctx",
                {"query": "test"},
                context=context
            )
        
        assert "slow_ctx" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_sync_tool_timeout(self, tool_runner):
        """Test that timeout works with synchronous tools."""
        import time
        
        def slow_sync_tool(query: str) -> str:
            time.sleep(5.0)  # Blocking sleep
            return f"Result: {query}"
        
        tool_runner.register_tool(
            name="slow_sync",
            implementation=slow_sync_tool,
            definition={"name": "slow_sync", "parameters": {"type": "object"}},
            timeout=0.1
        )
        
        with pytest.raises(TimeoutError) as exc_info:
            await tool_runner.run_tool_async("slow_sync", {"query": "test"})
        
        assert "slow_sync" in str(exc_info.value)


class TestExecuteWithTimeout:
    """Tests for the _execute_with_timeout helper method."""
    
    @pytest.fixture
    def tool_runner(self):
        """Create a fresh ToolRunner for testing."""
        return ToolRunner()
    
    @pytest.mark.asyncio
    async def test_execute_with_none_timeout(self, tool_runner):
        """Test that None timeout means no limit."""
        async def quick_coro():
            return "done"
        
        result = await tool_runner._execute_with_timeout(
            "test_tool",
            quick_coro(),
            timeout=None
        )
        
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_success(self, tool_runner):
        """Test successful execution within timeout."""
        async def quick_coro():
            await asyncio.sleep(0.01)
            return "completed"
        
        result = await tool_runner._execute_with_timeout(
            "test_tool",
            quick_coro(),
            timeout=1.0
        )
        
        assert result == "completed"
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_failure(self, tool_runner):
        """Test execution exceeding timeout."""
        async def slow_coro():
            await asyncio.sleep(10.0)
            return "never returned"
        
        with pytest.raises(TimeoutError) as exc_info:
            await tool_runner._execute_with_timeout(
                "slow_tool",
                slow_coro(),
                timeout=0.05
            )
        
        error_msg = str(exc_info.value)
        assert "slow_tool" in error_msg
        assert "timed out" in error_msg
        assert "0.05" in error_msg

