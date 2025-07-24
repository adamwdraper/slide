"""Test tool imports for Tyler agents - namespace and direct approaches"""
import os
# Removed dummy environment variables to avoid interfering with examples tests

import pytest
from tyler import Agent
from lye import web, files, WEB_TOOLS, FILES_TOOLS
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def mock_completion():
    """Mock LiteLLM completion to prevent API calls"""
    with patch('litellm.acompletion') as mock:
        # Create a more complete mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(
            content="Test response", 
            tool_calls=None
        )
        # Add usage info to prevent errors
        mock_response.usage = MagicMock(
            completion_tokens=10,
            prompt_tokens=20,
            total_tokens=30
        )
        mock.return_value = mock_response
        yield mock


@pytest.fixture
def mock_lye_tools():
    """Mock Lye tool implementations"""
    # Mock fetch_page
    fetch_mock = AsyncMock(return_value={
        "success": True,
        "status_code": 200,
        "content": "Mocked content"
    })
    
    # Mock Files class
    files_mock = MagicMock()
    files_mock.write_file = AsyncMock(return_value={
        "success": True,
        "file_url": "test.txt",
        "size": 100
    })
    files_mock.read_file = AsyncMock(return_value={
        "success": True,
        "content": "File content"
    })
    
    return fetch_mock, files_mock


class TestDirectToolImports:
    """Test direct tool imports functionality"""
    
    @pytest.mark.asyncio
    async def test_agent_with_direct_function_import(self, mock_completion):
        """Test agent can accept directly imported functions"""
        # Create agent with direct function reference
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=[web.fetch_page]  # Direct function reference
        )
        
        # Check tool is processed correctly
        assert len(agent._processed_tools) == 1
        tool_def = agent._processed_tools[0]
        assert tool_def['type'] == 'function'
        assert 'web-fetch_page' in tool_def['function']['name']
    
    @pytest.mark.asyncio
    async def test_agent_with_tool_groups(self, mock_completion):
        """Test agent can accept tool groups like WEB_TOOLS"""
        # Create agent with tool groups
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=[
                *WEB_TOOLS,      # Unpack web tools
                *FILES_TOOLS     # Unpack file tools
            ]
        )
        
        # Check all tools are processed
        assert len(agent._processed_tools) > 2  # Should have multiple tools
        
        # Check tool names
        tool_names = [tool['function']['name'] for tool in agent._processed_tools]
        assert any('fetch_page' in name for name in tool_names)
        assert any('download' in name for name in tool_names)
    
    @pytest.mark.asyncio
    async def test_mixed_tools(self, mock_completion):
        """Test mixing direct imports, tool groups, and strings"""
        # Create agent with mixed tool types
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",
            tools=[
                web.fetch_page,         # Direct function
                files.write_file,         # Direct function (was instance method)
                *WEB_TOOLS,        # Tool group unpacked
                "command_line",    # String reference
                {"definition": {"type": "function", "function": {"name": "custom", "description": "Custom tool", "parameters": {"type": "object", "properties": {}, "required": []}}}, "implementation": lambda: "custom"}  # Custom tool
            ]
        )
        
        # Should have tools from all sources
        assert len(agent._processed_tools) > 3
        
        # Check we have tools from different sources
        tool_names = [tool['function']['name'] for tool in agent._processed_tools]
        assert any('fetch_page' in name for name in tool_names)
        assert any('command' in name for name in tool_names)
    
    @pytest.mark.asyncio
    async def test_custom_tool_with_direct_import(self, mock_completion):
        """Test custom tools can be passed as callables"""
        # Define custom tool
        async def custom_tool(param: str) -> str:
            """Custom tool for testing"""
            return f"Processed: {param}"
        
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=[custom_tool]
        )
        
        # Check custom tool is registered
        assert len(agent._processed_tools) == 1
        tool_def = agent._processed_tools[0]
        assert tool_def['function']['name'] == 'custom_tool'
        assert 'Custom tool for testing' in tool_def['function']['description']
    
    @pytest.mark.asyncio
    async def test_invalid_tool_type_raises_error(self, mock_completion):
        """Test that invalid tool types raise appropriate errors"""
        with pytest.raises(Exception) as exc_info:
            Agent(
                name="test_agent",
                model_name="gpt-4",
                purpose="Test agent",  # Add explicit string
                tools=[123]  # Invalid type
            )
        
        # Should raise either ValueError or Pydantic ValidationError
        assert "validation error" in str(exc_info.value).lower() or "invalid tool type" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_tool_groups_filtering(self, mock_completion):
        """Test filtering tools from groups"""
        # Filter only download tools from web
        download_tools = [
            tool for tool in WEB_TOOLS 
            if 'download' in tool['definition']['function']['name']
        ]
        
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=download_tools
        )
        
        # Should only have download-related tools
        tool_names = [tool['function']['name'] for tool in agent._processed_tools]
        assert all('download' in name for name in tool_names)
        assert len(tool_names) > 0  # Should have at least one download tool 