"""Tests for structured output feature.

Tests the response_type parameter for Agent.run() that enables
Pydantic-validated structured outputs from LLM responses.

The implementation uses an output-tool pattern where the structured
output schema is registered as a special tool that the model calls
when ready to provide its final answer.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from tyler import Agent, AgentResult, RetryConfig, StructuredOutputError
from narrator import Thread, Message


class Invoice(BaseModel):
    """Test model for structured output."""
    invoice_id: str
    total: float
    items: List[str]
    paid: bool = False


class SupportTicket(BaseModel):
    """More complex test model with validation."""
    priority: Literal["low", "medium", "high"]
    category: str
    summary: str = Field(max_length=500)
    requires_escalation: bool


def create_output_tool_response(model_name: str, data: dict, content: str = ""):
    """Helper to create a mock response with output tool call."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    
    # Create tool call for the output tool
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.type = "function"
    tool_call.function = MagicMock()
    tool_call.function.name = f"__{model_name}_output__"
    tool_call.function.arguments = json.dumps(data)
    
    mock_response.choices[0].message.tool_calls = [tool_call]
    
    return mock_response


def create_plain_response(content: str):
    """Helper to create a mock response with plain text (no tool calls)."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.choices[0].message.tool_calls = None
    return mock_response


class TestStructuredOutputBasic:
    """Basic structured output tests."""
    
    @pytest.fixture
    def agent(self):
        """Create a basic agent for testing."""
        return Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test structured output"
        )
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Create an invoice for $100"))
        return t
    
    @pytest.mark.asyncio
    async def test_structured_output_basic(self, agent, thread):
        """Test that structured output returns validated model via output tool."""
        valid_data = {
            "invoice_id": "INV-001",
            "total": 100.00,
            "items": ["Widget A", "Widget B"],
            "paid": False
        }
        
        mock_response = create_output_tool_response("Invoice", valid_data)
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            result = await agent.run(thread, response_type=Invoice)
            
            # Verify structured_data is populated
            assert result.structured_data is not None
            assert isinstance(result.structured_data, Invoice)
            assert result.structured_data.invoice_id == "INV-001"
            assert result.structured_data.total == 100.00
            assert result.structured_data.items == ["Widget A", "Widget B"]
            assert result.structured_data.paid is False
            
            # Verify content contains the JSON
            assert json.loads(result.content) == valid_data
            
            # Verify no retries were needed
            assert result.validation_retries == 0
    
    @pytest.mark.asyncio
    async def test_structured_output_disabled_by_default(self, agent, thread):
        """Test that structured_data is None when response_type is not provided."""
        mock_response = create_plain_response("Here's an invoice for you...")
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            result = await agent.run(thread)
            
            # structured_data should be None when not using response_type
            assert result.structured_data is None
    
    @pytest.mark.asyncio
    async def test_agent_level_response_type(self, thread):
        """Test that response_type on Agent is used as default for all runs."""
        agent_with_default = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test structured output",
            response_type=Invoice
        )
        
        valid_data = {
            "invoice_id": "INV-002",
            "total": 250.00,
            "items": ["Service A"],
            "paid": True
        }
        
        mock_response = create_output_tool_response("Invoice", valid_data)
        
        with patch.object(agent_with_default, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            result = await agent_with_default.run(thread)
            
            assert result.structured_data is not None
            assert isinstance(result.structured_data, Invoice)
            assert result.structured_data.invoice_id == "INV-002"
    
    @pytest.mark.asyncio
    async def test_per_run_response_type_overrides_agent_default(self, thread):
        """Test that per-run response_type overrides agent's default."""
        agent_with_default = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test structured output",
            response_type=Invoice
        )
        
        support_data = {
            "priority": "high",
            "category": "billing",
            "summary": "Payment issue",
            "requires_escalation": True
        }
        
        # Note: output tool name changes based on the response_type passed to run()
        mock_response = create_output_tool_response("SupportTicket", support_data)
        
        with patch.object(agent_with_default, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            result = await agent_with_default.run(thread, response_type=SupportTicket)
            
            assert result.structured_data is not None
            assert isinstance(result.structured_data, SupportTicket)
            assert result.structured_data.priority == "high"
    
    @pytest.mark.asyncio
    async def test_validation_failure_raises_without_retry(self, agent, thread):
        """Test that validation failure raises StructuredOutputError when no retry config."""
        # Invalid response - missing required fields
        invalid_data = {
            "invoice_id": "INV-001"
            # Missing: total, items
        }
        
        mock_response = create_output_tool_response("Invoice", invalid_data)
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            with pytest.raises(StructuredOutputError) as exc_info:
                await agent.run(thread, response_type=Invoice)
            
            # Verify error details
            assert "Validation failed" in str(exc_info.value)
            assert exc_info.value.validation_errors is not None
            assert len(exc_info.value.validation_errors) > 0
            assert exc_info.value.last_response == invalid_data


class TestStructuredOutputRetry:
    """Tests for retry logic on validation failure."""
    
    @pytest.fixture
    def agent_with_retry(self):
        """Create agent with retry config."""
        return Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test structured output with retry",
            retry_config=RetryConfig(max_retries=2, backoff_base_seconds=0.01)
        )
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Create a support ticket"))
        return t
    
    @pytest.mark.asyncio
    async def test_retry_on_validation_failure(self, agent_with_retry, thread):
        """Test that agent retries on validation failure and succeeds."""
        # First response is invalid, second is valid
        invalid_data = {"priority": "invalid_priority"}  # Not in Literal
        valid_data = {
            "priority": "high",
            "category": "billing",
            "summary": "Payment issue",
            "requires_escalation": True
        }
        
        mock_response_1 = create_output_tool_response("SupportTicket", invalid_data)
        mock_response_2 = create_output_tool_response("SupportTicket", valid_data)
        
        with patch.object(agent_with_retry, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.side_effect = [
                (mock_response_1, {"usage": {}}),
                (mock_response_2, {"usage": {}})
            ]
            
            result = await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should succeed after retry
            assert result.structured_data is not None
            assert isinstance(result.structured_data, SupportTicket)
            assert result.structured_data.priority == "high"
            
            # Should have taken 1 retry
            assert result.validation_retries == 1
            
            # Should have called step twice
            assert mock_step.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, agent_with_retry, thread):
        """Test that error is raised after max retries exceeded."""
        # All responses are invalid
        invalid_data = {"priority": "invalid"}
        
        mock_response = create_output_tool_response("SupportTicket", invalid_data)
        
        with patch.object(agent_with_retry, 'step', new_callable=AsyncMock) as mock_step:
            # Return invalid response for all attempts (initial + 2 retries = 3)
            mock_step.return_value = (mock_response, {"usage": {}})
            
            with pytest.raises(StructuredOutputError) as exc_info:
                await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should have tried 3 times (initial + 2 retries)
            assert mock_step.call_count == 3
            assert "after 3 attempts" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_json_parse_error_triggers_retry(self, agent_with_retry, thread):
        """Test that JSON parse errors also trigger retry."""
        # Create a response with invalid JSON in tool arguments
        mock_response_1 = MagicMock()
        mock_response_1.choices = [MagicMock()]
        mock_response_1.choices[0].message.content = ""
        tool_call_1 = MagicMock()
        tool_call_1.id = "call_123"
        tool_call_1.type = "function"
        tool_call_1.function = MagicMock()
        tool_call_1.function.name = "__SupportTicket_output__"
        tool_call_1.function.arguments = "This is not valid JSON {"
        mock_response_1.choices[0].message.tool_calls = [tool_call_1]
        
        valid_data = {
            "priority": "low",
            "category": "general",
            "summary": "Test ticket",
            "requires_escalation": False
        }
        mock_response_2 = create_output_tool_response("SupportTicket", valid_data)
        
        with patch.object(agent_with_retry, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.side_effect = [
                (mock_response_1, {"usage": {}}),
                (mock_response_2, {"usage": {}})
            ]
            
            result = await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should succeed after retry
            assert result.structured_data is not None
            assert result.validation_retries == 1


class TestResponseFormatJson:
    """Tests for response_format='json' simple JSON mode."""
    
    @pytest.fixture
    def agent(self):
        """Create a basic agent for testing."""
        return Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test JSON mode"
        )
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Give me some data"))
        return t
    
    @pytest.mark.asyncio
    async def test_response_format_json_passes_to_completion(self, agent, thread):
        """Test that response_format='json' adds json_object to completion params."""
        mock_response = create_plain_response('{"key": "value"}')
        
        captured_params = {}
        
        async def capture_step(thread_arg, stream=False):
            # Check that _response_format is set
            captured_params['response_format'] = agent._response_format
            return (mock_response, {"usage": {}})
        
        with patch.object(agent, 'step', side_effect=capture_step):
            result = await agent.run(thread, response_format="json")
            
            # Verify response_format was set during run
            assert captured_params.get('response_format') == "json"
            
            # Should return the JSON content
            assert result.content == '{"key": "value"}'
            
            # structured_data should be None (response_format doesn't validate)
            assert result.structured_data is None


class TestStructuredOutputWithTools:
    """Tests for structured output working with regular tools."""
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Search for invoices"))
        return t
    
    @pytest.mark.asyncio
    async def test_regular_tool_call_before_output_tool(self, thread):
        """Test that regular tools can be called before the output tool."""
        # Create agent without tools - we'll add a mock tool definition manually
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test with tools"
        )
        
        # Add a mock tool to processed_tools
        mock_tool_def = {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get current time",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        agent._processed_tools = [mock_tool_def]
        
        # First response: model calls a regular tool
        tool_call_response = MagicMock()
        tool_call_response.choices = [MagicMock()]
        tool_call_response.choices[0].message.content = "Let me check the time first"
        tool_call = MagicMock()
        tool_call.id = "call_time"
        tool_call.type = "function"
        tool_call.function = MagicMock()
        tool_call.function.name = "get_current_time"
        tool_call.function.arguments = "{}"
        tool_call_response.choices[0].message.tool_calls = [tool_call]
        
        # Second response: model calls the output tool
        valid_data = {
            "invoice_id": "INV-001",
            "total": 100.00,
            "items": ["Time-based billing"],
            "paid": False
        }
        output_response = create_output_tool_response("Invoice", valid_data)
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.side_effect = [
                (tool_call_response, {"usage": {}}),
                (output_response, {"usage": {}})
            ]
            
            # Mock tool execution
            with patch.object(agent, '_handle_tool_execution', new_callable=AsyncMock) as mock_tool:
                mock_tool.return_value = "Current time: 2024-01-15 10:30:00"
                
                result = await agent.run(thread, response_type=Invoice)
                
                # Should succeed with structured output
                assert result.structured_data is not None
                assert isinstance(result.structured_data, Invoice)
                assert result.structured_data.invoice_id == "INV-001"
                
                # Regular tool should have been called
                assert mock_tool.called
    
    @pytest.mark.asyncio
    async def test_output_tool_passed_to_step(self, thread):
        """Test that the output tool and tool_choice are passed to step()."""
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test output tool addition"
        )
        
        valid_data = {"invoice_id": "INV-001", "total": 50.0, "items": ["Test"], "paid": True}
        output_response = create_output_tool_response("Invoice", valid_data)
        
        captured_tools = []
        captured_system_prompt = []
        captured_tool_choice = []
        
        async def capture_step(thread_arg, stream=False, tools=None, system_prompt=None, tool_choice=None):
            # Capture the parameters passed to step
            if tools:
                captured_tools.extend(tools)
            if system_prompt:
                captured_system_prompt.append(system_prompt)
            if tool_choice:
                captured_tool_choice.append(tool_choice)
            return (output_response, {"usage": {}})
        
        with patch.object(agent, 'step', side_effect=capture_step):
            await agent.run(thread, response_type=Invoice)
            
            # Check that output tool was passed to step
            output_tool_names = [t.get('function', {}).get('name', '') for t in captured_tools]
            assert "__Invoice_output__" in output_tool_names
            
            # Check that system prompt includes output instruction
            assert len(captured_system_prompt) > 0
            assert "structured_output_instruction" in captured_system_prompt[0]
            
            # Check that tool_choice="required" was passed (like Pydantic AI)
            assert len(captured_tool_choice) > 0
            assert captured_tool_choice[0] == "required"


class TestStructuredOutputValidation:
    """Tests for validation and edge cases."""
    
    @pytest.fixture
    def thread(self):
        """Create a test thread."""
        t = Thread()
        t.add_message(Message(role="user", content="Test"))
        return t
    
    @pytest.mark.asyncio
    async def test_response_type_and_response_format_conflict(self, thread):
        """Test that using both response_type and response_format raises an error."""
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test validation"
        )
        
        with pytest.raises(ValueError) as exc_info:
            await agent.run(thread, response_type=Invoice, response_format="json")
        
        assert "Cannot specify both response_type and response_format" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_agent_level_response_type_and_response_format_conflict(self, thread):
        """Test that agent-level response_type conflicts with response_format."""
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test validation",
            response_type=Invoice  # Agent-level default
        )
        
        with pytest.raises(ValueError) as exc_info:
            await agent.run(thread, response_format="json")
        
        assert "Cannot specify both response_type and response_format" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_plain_text_response_triggers_reminder(self, thread):
        """Test that plain text response adds a reminder message.
        
        Note: With tool_choice="required", models should always call a tool.
        This test verifies fallback behavior if a model doesn't comply.
        """
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test reminder"
        )
        
        # First response: plain text (no tool calls) - edge case fallback
        plain_text_response = create_plain_response("Here is my answer...")
        
        # Second response: proper output tool call
        valid_data = {"invoice_id": "INV-001", "total": 50.0, "items": ["Test"], "paid": True}
        output_response = create_output_tool_response("Invoice", valid_data)
        
        call_count = [0]
        
        async def mock_step(thread_arg, stream=False, tools=None, system_prompt=None, tool_choice=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return (plain_text_response, {"usage": {}})
            return (output_response, {"usage": {}})
        
        with patch.object(agent, 'step', side_effect=mock_step):
            result = await agent.run(thread, response_type=Invoice)
            
            # Should succeed on second attempt
            assert result.structured_data is not None
            
            # Check that a system reminder message was added
            reminder_messages = [m for m in thread.messages if m.role == "system" and "must provide your response" in m.content]
            assert len(reminder_messages) == 1
            assert "__Invoice_output__" in reminder_messages[0].content
            # Verify the source identifies it as an agent-generated reminder
            assert reminder_messages[0].source["type"] == "agent"
            assert reminder_messages[0].source["name"] == "structured_output_reminder"
            assert reminder_messages[0].source["id"] == "test-agent"
    
    @pytest.mark.asyncio
    async def test_regular_tools_processed_before_output_tool(self, thread):
        """Test that regular tool calls are processed before the output tool."""
        agent = Agent(
            name="test-agent",
            model_name="gpt-4.1",
            purpose="Test tool ordering"
        )
        
        # Add a mock tool definition
        mock_tool_def = {
            "type": "function",
            "function": {
                "name": "fetch_data",
                "description": "Fetch data",
                "parameters": {"type": "object", "properties": {}}
            }
        }
        agent._processed_tools = [mock_tool_def]
        
        # Response with both a regular tool call AND output tool call
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        
        # Regular tool call
        regular_tool_call = MagicMock()
        regular_tool_call.id = "call_regular"
        regular_tool_call.type = "function"
        regular_tool_call.function = MagicMock()
        regular_tool_call.function.name = "fetch_data"
        regular_tool_call.function.arguments = "{}"
        
        # Output tool call
        output_tool_call = MagicMock()
        output_tool_call.id = "call_output"
        output_tool_call.type = "function"
        output_tool_call.function = MagicMock()
        output_tool_call.function.name = "__Invoice_output__"
        output_tool_call.function.arguments = json.dumps({
            "invoice_id": "INV-001", "total": 50.0, "items": ["Test"], "paid": True
        })
        
        mock_response.choices[0].message.tool_calls = [regular_tool_call, output_tool_call]
        
        execution_order = []
        
        async def mock_handle_tool(tool_call):
            tool_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call['function']['name']
            execution_order.append(tool_name)
            return "Success"
        
        def mock_process_result(result, tool_call, tool_name):
            msg = Message(role="tool", name=tool_name, content=str(result), tool_call_id="test")
            return msg, False
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            with patch.object(agent, '_handle_tool_execution', side_effect=mock_handle_tool):
                with patch.object(agent, '_process_tool_result', side_effect=mock_process_result):
                    result = await agent.run(thread, response_type=Invoice)
                    
                    # Regular tool should be processed first
                    assert execution_order == ["fetch_data"]
                    
                    # Output should still be returned
                    assert result.structured_data is not None
                    assert result.structured_data.invoice_id == "INV-001"


class TestRetryConfig:
    """Tests for RetryConfig model."""
    
    def test_default_values(self):
        """Test RetryConfig default values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.retry_on_validation_error is True
        assert config.backoff_base_seconds == 0.5
    
    def test_custom_values(self):
        """Test RetryConfig with custom values."""
        config = RetryConfig(
            max_retries=5,
            retry_on_validation_error=False,
            backoff_base_seconds=1.0
        )
        assert config.max_retries == 5
        assert config.retry_on_validation_error is False
        assert config.backoff_base_seconds == 1.0
    
    def test_max_retries_bounds(self):
        """Test that max_retries is bounded."""
        from pydantic import ValidationError
        
        # Valid bounds
        assert RetryConfig(max_retries=0).max_retries == 0
        assert RetryConfig(max_retries=10).max_retries == 10
        
        # Invalid - too high
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=11)
        
        # Invalid - negative
        with pytest.raises(ValidationError):
            RetryConfig(max_retries=-1)
    
    def test_immutable(self):
        """Test that RetryConfig is immutable (frozen)."""
        from pydantic import ValidationError
        
        config = RetryConfig()
        with pytest.raises(ValidationError):
            config.max_retries = 5

