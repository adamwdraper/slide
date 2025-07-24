"""Integration test for tool imports - namespace and direct approaches"""
import os
# Removed dummy environment variables to avoid interfering with examples tests

import pytest
from unittest.mock import patch, MagicMock
from tyler import Agent, Thread, Message
from lye import web, files, command_line, WEB_TOOLS


@pytest.mark.asyncio
async def test_tool_group_integration():
    """Test using tool groups"""
    
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(
            content="I have access to multiple web tools.",
            tool_calls=None
        )
        mock_response.usage = MagicMock(
            completion_tokens=10, prompt_tokens=20, total_tokens=30
        )
        mock_completion.return_value = mock_response
        
        # Create agent with tool group
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=[*WEB_TOOLS]  # Unpack all web tools
        )
        
        # Check tools were loaded
        tool_names = [t['function']['name'] for t in agent._processed_tools]
        assert len(tool_names) >= 2  # Should have multiple web tools
        assert any('fetch' in name for name in tool_names)
        assert any('download' in name for name in tool_names)


@pytest.mark.asyncio 
async def test_mixed_tools_integration():
    """Test mixing namespace imports, groups, and strings"""
    
    with patch('tyler.models.agent.acompletion') as mock_completion:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(
            content="I have tools from multiple sources.",
            tool_calls=None
        )
        mock_response.usage = MagicMock(
            completion_tokens=10, prompt_tokens=20, total_tokens=30
        )
        mock_completion.return_value = mock_response
        
        # Create agent with mixed tools
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent",  # Add explicit string
            tools=[
                web.fetch_page,       # Namespace function
                files.write_file,     # Namespace function
                *WEB_TOOLS,          # Tool group
                "command_line"       # String (legacy)
            ]
        )
        
        # Verify all tools loaded
        tool_names = [t['function']['name'] for t in agent._processed_tools]
        
        # Should have tools from all sources
        assert any('fetch_page' in name for name in tool_names)
        assert any('write' in name for name in tool_names)
        assert any('command' in name for name in tool_names)
        assert len(tool_names) > 4  # Multiple tools loaded 