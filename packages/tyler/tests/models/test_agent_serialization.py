"""Tests for Agent serialization and deserialization.

This module tests that Agent instances can be properly serialized and deserialized
with Weave, ensuring that helper objects like message_factory and completion_handler
are correctly excluded from serialization and recreated on deserialization.
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from tyler import Agent
from tyler.models.message_factory import MessageFactory
from tyler.models.completion_handler import CompletionHandler
from narrator import Thread, Message


class TestAgentSerialization:
    """Test Agent serialization and deserialization."""
    
    def test_agent_helper_objects_excluded_from_dict(self):
        """Test that helper objects are excluded from model_dump()."""
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            temperature=0.8
        )
        
        # Get serialized dict
        agent_dict = agent.model_dump()
        
        # Helper objects should not be in the serialized dict
        assert "message_factory" not in agent_dict
        assert "completion_handler" not in agent_dict
        
        # But they should exist as instance attributes
        assert agent.message_factory is not None
        assert agent.completion_handler is not None
        assert isinstance(agent.message_factory, MessageFactory)
        assert isinstance(agent.completion_handler, CompletionHandler)
    
    def test_agent_helper_objects_excluded_from_json(self):
        """Test that helper objects are excluded from JSON serialization."""
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            temperature=0.8
        )
        
        # Get JSON serialization
        agent_json = agent.model_dump_json()
        agent_dict = json.loads(agent_json)
        
        # Helper objects should not be in the JSON
        assert "message_factory" not in agent_dict
        assert "completion_handler" not in agent_dict
        
        # But they should exist as instance attributes
        assert agent.message_factory is not None
        assert agent.completion_handler is not None
    
    def test_agent_deserialization_recreates_helpers(self):
        """Test that helper objects are recreated after deserialization."""
        # Create an agent
        original_agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            temperature=0.8,
            api_base="https://api.example.com",
            extra_headers={"X-Custom": "header"}
        )
        
        # Serialize and deserialize (simulating Weave round-trip)
        agent_dict = original_agent.model_dump()
        deserialized_agent = Agent(**agent_dict)
        
        # Helper objects should be recreated
        assert deserialized_agent.message_factory is not None
        assert deserialized_agent.completion_handler is not None
        assert isinstance(deserialized_agent.message_factory, MessageFactory)
        assert isinstance(deserialized_agent.completion_handler, CompletionHandler)
        
        # Verify they're properly configured
        assert deserialized_agent.message_factory.agent_name == "TestAgent"
        assert deserialized_agent.message_factory.model_name == "gpt-4.1"
        assert deserialized_agent.completion_handler.model_name == "gpt-4.1"
        assert deserialized_agent.completion_handler.temperature == 0.8
        assert deserialized_agent.completion_handler.api_base == "https://api.example.com"
        assert deserialized_agent.completion_handler.extra_headers == {"X-Custom": "header"}
    
    @pytest.mark.asyncio
    async def test_deserialized_agent_can_run(self):
        """Test that a deserialized agent can successfully run."""
        # Create an agent
        original_agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1"
        )
        
        # Serialize and deserialize
        agent_dict = original_agent.model_dump()
        deserialized_agent = Agent(**agent_dict)
        
        # Create a thread
        thread = Thread()
        thread.add_message(Message(role="user", content="Hello!"))
        
        # Mock the completion
        with patch('tyler.models.agent.acompletion') as mock_acompletion:
            mock_response = MagicMock()
            mock_response.id = "test-response-id"
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].finish_reason = "stop"
            mock_response.choices[0].message.content = "Hello! How can I help you?"
            mock_response.choices[0].message.role = "assistant"
            mock_response.choices[0].message.tool_calls = None
            mock_response.model = "gpt-4.1"
            mock_response.usage.completion_tokens = 10
            mock_response.usage.prompt_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_acompletion.return_value = mock_response
            
            # Run should work without errors
            result = await deserialized_agent.run(thread)
            
            # Verify result
            assert result is not None
            assert result.content is not None
            assert "Hello! How can I help you?" in result.content
    
    def test_agent_stores_excluded_from_serialization(self):
        """Test that thread_store and file_store remain excluded."""
        agent = Agent(name="TestAgent")
        
        # Get serialized dict
        agent_dict = agent.model_dump()
        
        # Stores should not be in the serialized dict
        assert "thread_store" not in agent_dict
        assert "file_store" not in agent_dict
        
        # But they should exist as instance attributes
        assert agent.thread_store is not None
        assert agent.file_store is not None
    
    def test_multiple_serialization_cycles(self):
        """Test that multiple serialization/deserialization cycles work."""
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            temperature=0.7
        )
        
        # First cycle
        agent_dict_1 = agent.model_dump()
        agent_2 = Agent(**agent_dict_1)
        
        # Second cycle
        agent_dict_2 = agent_2.model_dump()
        agent_3 = Agent(**agent_dict_2)
        
        # All should have properly initialized helpers
        assert agent.message_factory is not None
        assert agent_2.message_factory is not None
        assert agent_3.message_factory is not None
        assert agent.completion_handler is not None
        assert agent_2.completion_handler is not None
        assert agent_3.completion_handler is not None
        
        # Configuration should be preserved
        assert agent_3.name == "TestAgent"
        assert agent_3.model_name == "gpt-4.1"
        assert agent_3.temperature == 0.7


class TestAgentHelperReinitializationEdgeCases:
    """Test edge cases in helper object reinitialization."""
    
    def test_agent_with_custom_message_factory(self):
        """Test that custom message_factory is preserved."""
        # Create a custom message factory
        custom_factory = MessageFactory("CustomAgent", "custom-model")
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            message_factory=custom_factory
        )
        
        # Custom factory should be preserved
        assert agent.message_factory is custom_factory
        assert agent.message_factory.agent_name == "CustomAgent"
        assert agent.message_factory.model_name == "custom-model"
        
        # Completion handler should still be auto-created
        assert agent.completion_handler is not None
        assert agent.completion_handler.model_name == "gpt-4.1"
    
    def test_agent_with_custom_completion_handler(self):
        """Test that custom completion_handler is preserved."""
        # Create a custom completion handler
        custom_handler = CompletionHandler(
            model_name="custom-model",
            temperature=0.95,
            api_base="https://custom.api"
        )
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            completion_handler=custom_handler
        )
        
        # Custom handler should be preserved
        assert agent.completion_handler is custom_handler
        assert agent.completion_handler.model_name == "custom-model"
        assert agent.completion_handler.temperature == 0.95
        assert agent.completion_handler.api_base == "https://custom.api"
        
        # Message factory should still be auto-created
        assert agent.message_factory is not None
        assert agent.message_factory.agent_name == "TestAgent"
    
    def test_agent_with_both_custom_helpers(self):
        """Test that both custom helpers are preserved."""
        custom_factory = MessageFactory("CustomAgent", "custom-model-1")
        custom_handler = CompletionHandler(
            model_name="custom-model-2",
            temperature=0.99
        )
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4.1",
            message_factory=custom_factory,
            completion_handler=custom_handler
        )
        
        # Both custom helpers should be preserved
        assert agent.message_factory is custom_factory
        assert agent.completion_handler is custom_handler
        assert agent.message_factory.model_name == "custom-model-1"
        assert agent.completion_handler.model_name == "custom-model-2"
    
    def test_agent_with_custom_reasoning_config(self):
        """Test serialization with reasoning config."""
        agent = Agent(
            name="TestAgent",
            reasoning={"type": "enabled", "budget_tokens": 1024}
        )
        
        # Serialize and deserialize
        agent_dict = agent.model_dump()
        deserialized = Agent(**agent_dict)
        
        # Reasoning should be preserved
        assert deserialized.reasoning == {"type": "enabled", "budget_tokens": 1024}
        assert deserialized.completion_handler.reasoning == {"type": "enabled", "budget_tokens": 1024}
    
    def test_agent_with_tools(self):
        """Test serialization with tools."""
        agent = Agent(
            name="TestAgent",
            tools=["web"]
        )
        
        # Serialize and deserialize
        agent_dict = agent.model_dump()
        deserialized = Agent(**agent_dict)
        
        # Tools should be preserved and processed
        assert deserialized.tools == ["web"]
        assert len(deserialized._processed_tools) > 0
    
    def test_agent_with_mcp_config(self):
        """Test serialization with MCP config (without connection)."""
        mcp_config = {
            "servers": [
                {
                    "name": "test-server",
                    "transport": "stdio",
                    "command": "echo",
                    "args": ["test"]
                }
            ]
        }
        
        agent = Agent(
            name="TestAgent",
            mcp=mcp_config
        )
        
        # Serialize and deserialize
        agent_dict = agent.model_dump()
        deserialized = Agent(**agent_dict)
        
        # MCP config should be preserved
        assert deserialized.mcp == mcp_config
        assert deserialized._mcp_connected == False


class TestWeaveCompatibility:
    """Test compatibility with Weave-specific serialization patterns."""
    
    def test_simulated_weave_roundtrip(self):
        """Simulate a Weave-style serialization roundtrip."""
        # Create an agent
        agent = Agent(
            name="WeaveAgent",
            model_name="gpt-4.1",
            temperature=0.9
        )
        
        # Simulate Weave serialization: model_dump() followed by reconstruction
        # Weave typically uses model_dump() or similar to get a dict representation
        serialized = agent.model_dump()
        
        # Simulate deserialization (what Weave would do)
        # Helper objects will be None/missing from serialized dict
        assert "message_factory" not in serialized
        assert "completion_handler" not in serialized
        
        # Reconstruct from dict (simulating Weave deserialization)
        reconstructed = Agent(**serialized)
        
        # Helper objects should be properly initialized
        assert reconstructed.message_factory is not None
        assert reconstructed.completion_handler is not None
        assert isinstance(reconstructed.message_factory, MessageFactory)
        assert isinstance(reconstructed.completion_handler, CompletionHandler)
        
        # Verify they're functional
        assert reconstructed.message_factory.agent_name == "WeaveAgent"
        assert reconstructed.completion_handler.model_name == "gpt-4.1"
        assert reconstructed.completion_handler.temperature == 0.9
    
    @pytest.mark.asyncio
    async def test_logger_not_serialized(self):
        """Verify that module-level logger doesn't cause issues."""
        # This test verifies the original bug doesn't occur:
        # The module-level logger should never become a string attribute
        agent = Agent(name="TestAgent")
        
        # Serialize and deserialize
        agent_dict = agent.model_dump()
        deserialized = Agent(**agent_dict)
        
        # Create a thread
        thread = Thread()
        thread.add_message(Message(role="user", content="Test"))
        
        # Mock the completion
        with patch('tyler.models.agent.acompletion') as mock_acompletion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.choices[0].message.tool_calls = None
            mock_response.usage.completion_tokens = 5
            mock_response.usage.prompt_tokens = 5
            mock_response.usage.total_tokens = 10
            mock_acompletion.return_value = mock_response
            
            # This should not raise AttributeError: 'str' object has no attribute 'debug'
            # The bug would occur if logger was serialized as a string
            try:
                result = await deserialized.run(thread)
                # If we get here, logger works correctly
                assert True
            except AttributeError as e:
                if "'str' object has no attribute 'debug'" in str(e):
                    pytest.fail("Logger was serialized as string - the bug still exists!")
                raise

