import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set environment variables for testing"""
    with patch.dict(os.environ, {
        'SLACK_BOT_TOKEN': 'test-bot-token',
        'SLACK_SIGNING_SECRET': 'test-signing-secret',
        'OPENAI_API_KEY': 'test-openai-key',
        'NOTION_TOKEN': 'test-notion-token',
        'WANDB_API_KEY': 'test-wandb-key'
    }):
        yield

@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI/litellm calls for testing (both sync and async)
    
    We patch at multiple locations because modules use different import styles:
    - litellm.completion / litellm.acompletion (direct module access)
    - tyler.models.agent.acompletion (from litellm import acompletion)
    
    The mock detects:
    1. If an output tool (e.g., __MovieReview_output__) is in tools, return a tool call
    2. If response_format is requested, return valid JSON
    3. Otherwise return plain text
    """
    from unittest.mock import AsyncMock
    import json
    
    def create_mock_response(content, tool_calls=None):
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=content, tool_calls=tool_calls))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )
    
    def create_tool_call_response(tool_name, arguments):
        """Create a response with a tool call."""
        tool_call = MagicMock()
        tool_call.id = "call_test123"
        tool_call.type = "function"
        tool_call.function = MagicMock()
        tool_call.function.name = tool_name
        tool_call.function.arguments = json.dumps(arguments)
        return create_mock_response(None, tool_calls=[tool_call])
    
    # Generic structured output data that matches common test schemas
    structured_data = {
        "title": "Test Movie",
        "rating": 8.5,
        "genre": "drama",
        "pros": ["Great acting", "Good plot"],
        "cons": ["Too long"],
        "recommended": True,
        "priority": "medium",
        "category": "general",
        "summary": "Test summary",
        "requires_escalation": False,
        "suggested_actions": ["Review", "Follow up"]
    }
    
    # Default response for non-structured output
    default_response = create_mock_response("Test response")
    
    # JSON response for simple JSON mode (response_format="json")
    json_response = create_mock_response(json.dumps(structured_data))
    
    def smart_response(*args, **kwargs):
        """Return appropriate response based on request type."""
        tools = kwargs.get('tools', [])
        
        # Check for output tool pattern (structured output via tool calls)
        for tool in tools:
            if tool.get('type') == 'function':
                func = tool.get('function', {})
                name = func.get('name', '')
                if name.startswith('__') and name.endswith('_output__'):
                    # Return a tool call to the output tool with valid data
                    return create_tool_call_response(name, structured_data)
        
        # Check for simple JSON mode
        if kwargs.get('response_format'):
            return json_response
        
        return default_response
    
    async def async_smart_response(*args, **kwargs):
        """Async version of smart_response."""
        return smart_response(*args, **kwargs)
    
    async_mock = AsyncMock(side_effect=async_smart_response)
    
    with patch('litellm.completion', side_effect=smart_response) as mock_sync, \
         patch('litellm.acompletion', async_mock), \
         patch('tyler.models.agent.acompletion', async_mock):
        yield mock_sync, async_mock

@pytest.fixture(autouse=True)
def mock_wandb():
    """Mock wandb calls for testing"""
    with patch('wandb.init') as mock_init, \
         patch('wandb.log') as mock_log:
        mock_init.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        yield mock_init, mock_log 