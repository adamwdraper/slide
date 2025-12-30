"""Tests for structured output feature.

Tests the response_type parameter for Agent.run() that enables
Pydantic-validated structured outputs from LLM responses.
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
        """Test that structured output returns validated model."""
        # Mock the LLM response with valid JSON
        valid_response = {
            "invoice_id": "INV-001",
            "total": 100.00,
            "items": ["Widget A", "Widget B"],
            "paid": False
        }
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(valid_response)
        
        # Patch acompletion in the agent module where it's imported
        with patch('tyler.models.agent.acompletion', new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            result = await agent.run(thread, response_type=Invoice)
            
            # Verify structured_data is populated
            assert result.structured_data is not None
            assert isinstance(result.structured_data, Invoice)
            assert result.structured_data.invoice_id == "INV-001"
            assert result.structured_data.total == 100.00
            assert result.structured_data.items == ["Widget A", "Widget B"]
            assert result.structured_data.paid is False
            
            # Verify content is also available
            assert result.content == json.dumps(valid_response)
            
            # Verify no retries were needed
            assert result.validation_retries == 0
    
    @pytest.mark.asyncio
    async def test_structured_output_disabled_by_default(self, agent, thread):
        """Test that structured_data is None when response_type is not provided."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Here's an invoice for you..."
        mock_response.choices[0].message.tool_calls = None
        
        with patch.object(agent, 'step', new_callable=AsyncMock) as mock_step:
            mock_step.return_value = (mock_response, {"usage": {}})
            
            result = await agent.run(thread)
            
            # structured_data should be None when not using response_type
            assert result.structured_data is None
    
    @pytest.mark.asyncio
    async def test_validation_failure_raises_without_retry(self, agent, thread):
        """Test that validation failure raises StructuredOutputError when no retry config."""
        # Invalid response - missing required fields
        invalid_response = {
            "invoice_id": "INV-001"
            # Missing: total, items
        }
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(invalid_response)
        
        with patch('tyler.models.agent.acompletion', new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response
            
            with pytest.raises(StructuredOutputError) as exc_info:
                await agent.run(thread, response_type=Invoice)
            
            # Verify error details
            assert "Validation failed" in str(exc_info.value)
            assert exc_info.value.validation_errors is not None
            assert len(exc_info.value.validation_errors) > 0
            assert exc_info.value.last_response == invalid_response


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
        invalid_response = {"priority": "invalid_priority"}  # Not in Literal
        valid_response = {
            "priority": "high",
            "category": "billing",
            "summary": "Payment issue",
            "requires_escalation": True
        }
        
        mock_response_1 = MagicMock()
        mock_response_1.choices = [MagicMock()]
        mock_response_1.choices[0].message.content = json.dumps(invalid_response)
        
        mock_response_2 = MagicMock()
        mock_response_2.choices = [MagicMock()]
        mock_response_2.choices[0].message.content = json.dumps(valid_response)
        
        with patch('tyler.models.agent.acompletion', new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = [mock_response_1, mock_response_2]
            
            result = await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should succeed after retry
            assert result.structured_data is not None
            assert isinstance(result.structured_data, SupportTicket)
            assert result.structured_data.priority == "high"
            
            # Should have taken 1 retry
            assert result.validation_retries == 1
            
            # Should have called completion twice
            assert mock_completion.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, agent_with_retry, thread):
        """Test that error is raised after max retries exceeded."""
        # All responses are invalid
        invalid_response = {"priority": "invalid"}
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(invalid_response)
        
        with patch('tyler.models.agent.acompletion', new_callable=AsyncMock) as mock_completion:
            # Return invalid response for all attempts (initial + 2 retries = 3)
            mock_completion.return_value = mock_response
            
            with pytest.raises(StructuredOutputError) as exc_info:
                await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should have tried 3 times (initial + 2 retries)
            assert mock_completion.call_count == 3
            assert "after 3 attempts" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_json_parse_error_triggers_retry(self, agent_with_retry, thread):
        """Test that JSON parse errors also trigger retry."""
        invalid_json = "This is not valid JSON {"
        valid_response = {
            "priority": "low",
            "category": "general",
            "summary": "Test ticket",
            "requires_escalation": False
        }
        
        mock_response_1 = MagicMock()
        mock_response_1.choices = [MagicMock()]
        mock_response_1.choices[0].message.content = invalid_json
        
        mock_response_2 = MagicMock()
        mock_response_2.choices = [MagicMock()]
        mock_response_2.choices[0].message.content = json.dumps(valid_response)
        
        with patch('tyler.models.agent.acompletion', new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = [mock_response_1, mock_response_2]
            
            result = await agent_with_retry.run(thread, response_type=SupportTicket)
            
            # Should succeed after retry
            assert result.structured_data is not None
            assert result.validation_retries == 1


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

