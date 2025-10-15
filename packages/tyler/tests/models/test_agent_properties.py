"""
Tests to ensure Agent model properties are not accidentally removed during refactoring.

This test suite validates that all expected Agent properties exist and function correctly.
"""
import pytest
from tyler import Agent


class TestAgentProperties:
    """Test that all expected Agent properties exist and work correctly."""
    
    def test_agent_has_all_expected_fields(self):
        """Test that Agent model has all expected fields defined."""
        expected_fields = [
            'model_name',
            'api_base',
            'api_key',
            'extra_headers',
            'temperature',
            'drop_params',
            'reasoning',
            'name',
            'purpose',
            'notes',
            'version',
            'tools',
            'max_tool_iterations',
            'agents',
            'thread_store',
            'file_store',
            'step_errors_raise'
        ]
        
        # Check that all fields are defined in the model
        model_fields = Agent.model_fields
        for field_name in expected_fields:
            assert field_name in model_fields, f"Expected field '{field_name}' not found in Agent model"
    
    def test_agent_initialization_with_all_properties(self):
        """Test that Agent can be initialized with all properties."""
        agent = Agent(
            model_name="gpt-4o",
            api_base="https://custom.api.com/v1",
            api_key="test-api-key",
            extra_headers={"X-Custom": "header"},
            temperature=0.8,
            drop_params=False,
            reasoning="low",
            name="TestAgent",
            purpose="Test purpose",
            notes="Test notes",
            version="2.0.0",
            tools=[],
            max_tool_iterations=5,
            agents=[],
            step_errors_raise=True
        )
        
        # Verify all properties were set correctly
        assert agent.model_name == "gpt-4o"
        assert agent.api_base == "https://custom.api.com/v1"
        assert agent.api_key == "test-api-key"
        assert agent.extra_headers == {"X-Custom": "header"}
        assert agent.temperature == 0.8
        assert agent.drop_params is False
        assert agent.reasoning == "low"
        assert agent.name == "TestAgent"
        assert str(agent.purpose) == "Test purpose"
        assert str(agent.notes) == "Test notes"
        assert agent.version == "2.0.0"
        assert agent.tools == []
        assert agent.max_tool_iterations == 5
        assert agent.agents == []
        assert agent.step_errors_raise is True
    
    def test_api_key_passed_to_completion_handler(self):
        """Test that api_key is passed to CompletionHandler."""
        agent = Agent(
            model_name="gpt-4o",
            api_key="test-key-123"
        )
        
        assert agent.completion_handler.api_key == "test-key-123"
    
    def test_api_base_passed_to_completion_handler(self):
        """Test that api_base is passed to CompletionHandler."""
        agent = Agent(
            model_name="gpt-4o",
            api_base="https://custom.api.com/v1"
        )
        
        assert agent.completion_handler.api_base == "https://custom.api.com/v1"
    
    def test_base_url_alias_for_api_base(self):
        """Test that base_url is properly aliased to api_base."""
        agent = Agent(
            model_name="gpt-4o",
            base_url="https://custom.api.com/v1"
        )
        
        assert agent.api_base == "https://custom.api.com/v1"
        assert agent.completion_handler.api_base == "https://custom.api.com/v1"
    
    def test_wandb_inference_configuration(self):
        """Test typical W&B Inference configuration."""
        agent = Agent(
            model_name="openai/deepseek-ai/DeepSeek-R1-0528",
            base_url="https://api.inference.wandb.ai/v1",
            api_key="wandb-test-key",
            extra_headers={
                "HTTP-Referer": "https://wandb.ai/test/project",
                "X-Project-Name": "test/project"
            },
            reasoning="low",
            temperature=0.7
        )
        
        assert agent.model_name == "openai/deepseek-ai/DeepSeek-R1-0528"
        assert agent.api_base == "https://api.inference.wandb.ai/v1"
        assert agent.api_key == "wandb-test-key"
        assert agent.extra_headers["HTTP-Referer"] == "https://wandb.ai/test/project"
        assert agent.reasoning == "low"
        
        # Verify passed to completion handler
        assert agent.completion_handler.api_base == "https://api.inference.wandb.ai/v1"
        assert agent.completion_handler.api_key == "wandb-test-key"
        assert agent.completion_handler.extra_headers["HTTP-Referer"] == "https://wandb.ai/test/project"
    
    def test_extra_allow_config(self):
        """Test that Agent allows extra fields via pydantic config."""
        # This should not raise an error thanks to "extra": "allow"
        agent = Agent(
            model_name="gpt-4o",
            custom_field="custom_value",
            another_field=123
        )
        
        # Extra fields are stored but not validated
        assert hasattr(agent, 'custom_field')
        assert agent.custom_field == "custom_value"
        assert hasattr(agent, 'another_field')
        assert agent.another_field == 123
    
    def test_property_defaults(self):
        """Test that all properties have reasonable defaults."""
        agent = Agent()
        
        # Test defaults
        assert agent.model_name == "gpt-4.1"
        assert agent.api_base is None
        assert agent.api_key is None
        assert agent.extra_headers is None
        assert agent.temperature == 0.7
        assert agent.drop_params is True
        assert agent.reasoning is None
        assert agent.name == "Tyler"
        assert agent.version == "1.0.0"
        assert agent.tools == []
        assert agent.max_tool_iterations == 10
        assert agent.agents == []
        assert agent.thread_store is not None  # Created by default
        assert agent.file_store is not None  # Created by default
        assert agent.step_errors_raise is False

