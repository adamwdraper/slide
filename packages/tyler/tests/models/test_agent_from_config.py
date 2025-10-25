"""Tests for Agent.from_config() class method.

Following TDD: These tests are written BEFORE implementation.
Tests map to spec acceptance criteria AC-16 through AC-25.
"""
import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from tyler import Agent
from pydantic import ValidationError


class TestAgentFromConfigBasic:
    """Test basic Agent.from_config() usage (AC-16, AC-17, AC-18)"""
    
    def test_agent_from_config_basic(self, tmp_path):
        """AC-16: Create agent from config file"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "ConfigAgent",
            "model_name": "gpt-4o",
            "temperature": 0.9,
            "purpose": "Test agent from config",
            "notes": "Testing config loading"
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        assert agent.name == "ConfigAgent"
        assert agent.model_name == "gpt-4o"
        assert agent.temperature == 0.9
        assert str(agent.purpose) == "Test agent from config"
        assert str(agent.notes) == "Testing config loading"
    
    def test_agent_from_config_auto_discover(self, tmp_path, monkeypatch):
        """AC-17: Auto-discover config when no path provided"""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "tyler-chat-config.yaml"
        config_data = {
            "name": "AutoDiscoverAgent",
            "model_name": "gpt-4.1"
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config()  # No path - should auto-discover
        
        assert agent.name == "AutoDiscoverAgent"
        assert agent.model_name == "gpt-4.1"
    
    def test_agent_from_config_explicit_path(self, tmp_path):
        """AC-18: Load from explicit config path"""
        config_file = tmp_path / "my-specific-config.yaml"
        config_data = {
            "name": "ExplicitAgent",
            "model_name": "gpt-4o-mini"
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        assert agent.name == "ExplicitAgent"
        assert agent.model_name == "gpt-4o-mini"


class TestAgentFromConfigOverrides:
    """Test parameter overrides (AC-19, AC-20)"""
    
    def test_agent_from_config_with_overrides(self, tmp_path):
        """AC-19: Override config values with kwargs"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "BaseAgent",
            "model_name": "gpt-4o",
            "temperature": 0.7,
            "max_tool_iterations": 5
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Override temperature and model_name
        agent = Agent.from_config(
            str(config_file),
            temperature=0.9,
            model_name="gpt-4.1"
        )
        
        # Overridden values
        assert agent.temperature == 0.9
        assert agent.model_name == "gpt-4.1"
        
        # Non-overridden values from config
        assert agent.name == "BaseAgent"
        assert agent.max_tool_iterations == 5
    
    def test_agent_from_config_tools_replaced_not_merged(self, tmp_path):
        """AC-20: Tools in kwargs replace (don't merge with) config tools"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "Agent",
            "tools": ["web", "slack"]
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Override tools completely
        agent = Agent.from_config(
            str(config_file),
            tools=["notion"]  # Should replace, not merge
        )
        
        # Only notion tool (from override), not web/slack from config
        assert agent.tools == ["notion"]


class TestAgentFromConfigMCP:
    """Test MCP configuration handling (AC-21)"""
    
    def test_agent_from_config_mcp_preserved_not_connected(self, tmp_path):
        """AC-21: MCP config set but not auto-connected"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "MCPAgent",
            "mcp": {
                "servers": [
                    {
                        "name": "docs",
                        "transport": "streamablehttp",
                        "url": "https://example.com/mcp"
                    }
                ]
            }
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        # MCP config should be set
        assert agent.mcp is not None
        assert agent.mcp["servers"][0]["name"] == "docs"
        
        # But not connected (no tools loaded from MCP)
        assert agent._mcp_connected is False


class TestAgentFromConfigAllParams:
    """Test that all config parameters are applied (AC-22)"""
    
    def test_agent_from_config_all_params_applied(self, tmp_path):
        """AC-22: All config params (name, purpose, notes, etc.) applied"""
        config_file = tmp_path / "full-config.yaml"
        config_data = {
            "name": "FullAgent",
            "model_name": "gpt-4o",
            "temperature": 0.85,
            "max_tool_iterations": 15,
            "purpose": "Full config test",
            "notes": "All parameters included",
            "version": "2.0.0",
            "tools": [],
            "reasoning": "medium",
            "drop_params": False
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        # Verify all parameters applied
        assert agent.name == "FullAgent"
        assert agent.model_name == "gpt-4o"
        assert agent.temperature == 0.85
        assert agent.max_tool_iterations == 15
        assert str(agent.purpose) == "Full config test"
        assert str(agent.notes) == "All parameters included"
        assert agent.version == "2.0.0"
        assert agent.tools == []
        assert agent.reasoning == "medium"
        assert agent.drop_params is False


class TestAgentFromConfigCustomTools:
    """Test custom tool loading (AC-23)"""
    
    def test_agent_from_config_custom_tools_loaded(self, tmp_path):
        """AC-23: Custom tools from config are loaded into agent"""
        # Create custom tool file
        tool_file = tmp_path / "custom_tool.py"
        tool_file.write_text('''
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "my_custom_tool",
                "description": "A custom tool from config",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "implementation": lambda: "custom result"
    }
]
''')
        
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "CustomToolAgent",
            "tools": [f"./{tool_file.name}"]
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        # Verify custom tool is in processed tools
        # Note: We test _processed_tools (private) to verify the full loading pipeline
        # worked correctly (file loaded, parsed, and registered), not just that the
        # raw tool string was stored. This is appropriate for integration testing.
        tool_names = [t['function']['name'] for t in agent._processed_tools]
        assert 'my_custom_tool' in tool_names


class TestAgentFromConfigEnvVars:
    """Test environment variable substitution (AC-24)"""
    
    def test_agent_from_config_env_vars_substituted(self, tmp_path):
        """AC-24: ${VAR} in config should be replaced with env var value"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "EnvAgent",
            "api_key": "${TEST_CONFIG_API_KEY}",
            "notes": "Using ${TEST_CONFIG_MODEL}"
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Set environment variables
        with patch.dict(os.environ, {
            "TEST_CONFIG_API_KEY": "secret-key-123",
            "TEST_CONFIG_MODEL": "gpt-4o"
        }):
            agent = Agent.from_config(str(config_file))
        
        # Env vars should be substituted
        assert agent.api_key == "secret-key-123"
        assert str(agent.notes) == "Using gpt-4o"


class TestAgentFromConfigErrors:
    """Test error handling (AC-25)"""
    
    def test_agent_from_config_invalid_params(self, tmp_path):
        """AC-25: Pydantic ValidationError for invalid config values"""
        config_file = tmp_path / "bad-config.yaml"
        config_data = {
            "name": "BadAgent",
            "temperature": "not-a-number",  # Should be float
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Should raise ValidationError from Agent's Pydantic validation
        with pytest.raises((ValidationError, ValueError)):
            agent = Agent.from_config(str(config_file))
    
    def test_agent_from_config_missing_file(self):
        """Config file not found should raise FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            agent = Agent.from_config("/nonexistent/config.yaml")
    
    def test_agent_from_config_invalid_yaml(self, tmp_path):
        """Invalid YAML syntax should raise yaml.YAMLError"""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("name: Agent\n  bad indentation:\n  - broken")
        
        with pytest.raises(yaml.YAMLError):
            agent = Agent.from_config(str(config_file))
    
    def test_agent_from_config_wrong_extension(self, tmp_path):
        """Non-YAML extension should raise ValueError"""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Agent"}')
        
        with pytest.raises(ValueError, match="must be .yaml or .yml"):
            agent = Agent.from_config(str(json_file))


class TestAgentFromConfigWithBuiltinTools:
    """Test built-in tool loading from config"""
    
    def test_agent_from_config_with_builtin_tools(self, tmp_path):
        """Built-in tool names should work from config"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "ToolAgent",
            "tools": ["web"]  # Built-in tool
        }
        config_file.write_text(yaml.dump(config_data))
        
        agent = Agent.from_config(str(config_file))
        
        # Should have loaded web tools
        assert len(agent._processed_tools) > 0
        # Web module has multiple tools
        tool_names = [t['function']['name'] for t in agent._processed_tools]
        assert any('web' in name.lower() or 'search' in name.lower() for name in tool_names)

