"""Tests for tyler.config module - Config loading functionality.

Following TDD: These tests are written BEFORE implementation.
Tests map to spec acceptance criteria AC-1 through AC-15.
"""
import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from tyler.config import load_config, load_custom_tool


class TestLoadConfigBasic:
    """Test basic config loading scenarios (AC-1, AC-2)"""
    
    def test_load_config_from_current_directory(self, tmp_path, monkeypatch):
        """AC-1: Load config from ./tyler-chat-config.yaml in current directory"""
        # Create config in "current directory"
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "tyler-chat-config.yaml"
        config_data = {
            "name": "TestAgent",
            "model_name": "gpt-4o",
            "temperature": 0.8
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Load without explicit path (should auto-discover)
        result = load_config()
        
        assert result["name"] == "TestAgent"
        assert result["model_name"] == "gpt-4o"
        assert result["temperature"] == 0.8
    
    def test_load_config_from_explicit_path(self, tmp_path):
        """AC-2: Load config from explicit path"""
        config_file = tmp_path / "my-config.yaml"
        config_data = {
            "name": "ExplicitAgent",
            "model_name": "gpt-4.1"
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert result["name"] == "ExplicitAgent"
        assert result["model_name"] == "gpt-4.1"


class TestEnvVarSubstitution:
    """Test environment variable substitution (AC-3, AC-9)"""
    
    def test_load_config_substitutes_env_vars(self, tmp_path):
        """AC-3: ${API_KEY} should be replaced with env var value"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "Agent",
            "api_key": "${TEST_API_KEY}",
            "notes": "Using ${TEST_MODEL} model"
        }
        config_file.write_text(yaml.dump(config_data))
        
        # Set environment variables
        with patch.dict(os.environ, {"TEST_API_KEY": "secret-123", "TEST_MODEL": "gpt-4o"}):
            result = load_config(str(config_file))
        
        assert result["api_key"] == "secret-123"
        assert result["notes"] == "Using gpt-4o model"
    
    def test_load_config_missing_env_var_preserved(self, tmp_path):
        """AC-9: ${MISSING} should stay as literal if env var doesn't exist"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "api_key": "${NONEXISTENT_VAR}"
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert result["api_key"] == "${NONEXISTENT_VAR}"


class TestCustomToolLoading:
    """Test custom tool file loading (AC-4, AC-10, AC-11, AC-12, AC-13)"""
    
    def test_load_config_loads_custom_tools(self, tmp_path):
        """AC-4: Load custom tools from Python files"""
        # Create a custom tool file
        tool_file = tmp_path / "my_tools.py"
        tool_file.write_text('''
TOOLS = [
    {
        "definition": {
            "type": "function",
            "function": {
                "name": "custom_tool",
                "description": "A custom tool",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "implementation": lambda: "result"
    }
]
''')
        
        # Create config that references the tool
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "Agent",
            "tools": [f"./{tool_file.name}"]
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        # Should have loaded the tool
        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["definition"]["function"]["name"] == "custom_tool"
    
    def test_load_custom_tool_relative_path(self, tmp_path):
        """AC-10: Relative paths resolved relative to config file"""
        # Create subdirectory with tool
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        tool_file = tools_dir / "custom.py"
        tool_file.write_text('''
TOOLS = [{"definition": {"type": "function", "function": {"name": "test_tool", "description": "test", "parameters": {}}}, "implementation": lambda: "ok"}]
''')
        
        # Config in parent directory with relative reference
        config_file = tmp_path / "config.yaml"
        config_data = {"tools": ["./tools/custom.py"]}
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert len(result["tools"]) == 1
        assert result["tools"][0]["definition"]["function"]["name"] == "test_tool"
    
    def test_load_custom_tool_absolute_path(self, tmp_path):
        """AC-11: Handle absolute paths"""
        tool_file = tmp_path / "tool.py"
        tool_file.write_text('''
TOOLS = [{"definition": {"type": "function", "function": {"name": "abs_tool", "description": "test", "parameters": {}}}, "implementation": lambda: "ok"}]
''')
        
        config_file = tmp_path / "config.yaml"
        config_data = {"tools": [str(tool_file)]}  # Absolute path
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert len(result["tools"]) == 1
        assert result["tools"][0]["definition"]["function"]["name"] == "abs_tool"
    
    def test_load_custom_tool_home_path(self, tmp_path):
        """AC-12: Expand ~/tools/custom.py paths"""
        # Create tool in temp location (simulating home)
        tool_file = tmp_path / "custom.py"
        tool_file.write_text('''
TOOLS = [{"definition": {"type": "function", "function": {"name": "home_tool", "description": "test", "parameters": {}}}, "implementation": lambda: "ok"}]
''')
        
        config_file = tmp_path / "config.yaml"
        config_data = {"tools": [f"~/{tool_file.name}"]}
        config_file.write_text(yaml.dump(config_data))
        
        # Mock home directory expansion
        with patch('pathlib.Path.expanduser', return_value=tool_file):
            result = load_config(str(config_file))
        
        assert len(result["tools"]) == 1
    
    def test_load_custom_tool_missing_file(self, tmp_path, caplog):
        """AC-13: Log warning and skip tool if file missing"""
        import logging
        caplog.set_level(logging.WARNING)
        
        config_file = tmp_path / "config.yaml"
        config_data = {
            "tools": ["./nonexistent_tool.py", "web"]  # One missing, one valid
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        # Should skip missing tool, keep valid one
        assert "tools" in result
        assert "web" in result["tools"]
        # Should not include the missing tool
        assert not any("nonexistent_tool" in str(tool) for tool in result["tools"])


class TestMCPConfig:
    """Test MCP configuration preservation (AC-5)"""
    
    def test_load_config_preserves_mcp_config(self, tmp_path):
        """AC-5: MCP config should be in returned dict"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "name": "Agent",
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
        
        result = load_config(str(config_file))
        
        assert "mcp" in result
        assert result["mcp"]["servers"][0]["name"] == "docs"
        assert result["mcp"]["servers"][0]["url"] == "https://example.com/mcp"


class TestErrorCases:
    """Test error handling (AC-6, AC-7, AC-8, AC-14)"""
    
    def test_load_config_missing_file_explicit_path(self):
        """AC-6: FileNotFoundError when explicit path doesn't exist"""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")
    
    def test_load_config_missing_file_auto_discover(self, tmp_path, monkeypatch):
        """AC-7: ValueError with searched paths when auto-discovery fails"""
        # Change to empty directory
        monkeypatch.chdir(tmp_path)
        
        with pytest.raises(ValueError, match="No config file found"):
            load_config()  # No path - should search and fail
    
    def test_load_config_invalid_yaml(self, tmp_path):
        """AC-8: yaml.YAMLError on syntax error"""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("name: Agent\n  bad: indentation:\n  - broken")
        
        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))
    
    def test_load_config_invalid_extension(self, tmp_path):
        """AC-14: ValueError for non-YAML extensions"""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"name": "Agent"}')
        
        with pytest.raises(ValueError, match="must be .yaml or .yml"):
            load_config(str(json_file))
        
        # Also test .txt
        txt_file = tmp_path / "config.txt"
        txt_file.write_text("name: Agent")
        
        with pytest.raises(ValueError, match="must be .yaml or .yml"):
            load_config(str(txt_file))


class TestSearchOrder:
    """Test standard location search order (AC-15)"""
    
    def test_load_config_search_order(self, tmp_path, monkeypatch):
        """AC-15: Try cwd → ~/.tyler → /etc/tyler in order"""
        # We'll test that it finds the first existing config
        
        # Create config in "home" location
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        tyler_dir = home_dir / ".tyler"
        tyler_dir.mkdir()
        home_config = tyler_dir / "chat-config.yaml"
        home_config.write_text(yaml.dump({"name": "HomeAgent"}))
        
        # Create config in "cwd"
        cwd_dir = tmp_path / "cwd"
        cwd_dir.mkdir()
        cwd_config = cwd_dir / "tyler-chat-config.yaml"
        cwd_config.write_text(yaml.dump({"name": "CwdAgent"}))
        
        # Change to cwd and mock home
        monkeypatch.chdir(cwd_dir)
        with patch('pathlib.Path.home', return_value=home_dir):
            result = load_config()
        
        # Should find CWD config first
        assert result["name"] == "CwdAgent"
        
        # Now remove cwd config and try again
        cwd_config.unlink()
        with patch('pathlib.Path.home', return_value=home_dir):
            result = load_config()
        
        # Should fall back to home config
        assert result["name"] == "HomeAgent"


class TestBuiltInTools:
    """Test that built-in tool names pass through unchanged"""
    
    def test_builtin_tools_unchanged(self, tmp_path):
        """Built-in tool module names should pass through"""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "tools": ["web", "slack", "notion"]
        }
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert result["tools"] == ["web", "slack", "notion"]


class TestEmptyAndEdgeCases:
    """Test empty configs and edge cases"""
    
    def test_empty_config_file(self, tmp_path):
        """Empty YAML should return empty dict or defaults"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        
        result = load_config(str(config_file))
        
        # Empty YAML returns None, which we should handle
        assert result is not None or result == {}
    
    def test_config_with_yml_extension(self, tmp_path):
        """Should accept .yml extension too"""
        config_file = tmp_path / "config.yml"
        config_data = {"name": "YmlAgent"}
        config_file.write_text(yaml.dump(config_data))
        
        result = load_config(str(config_file))
        
        assert result["name"] == "YmlAgent"

