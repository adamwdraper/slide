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
    
    The mock detects if response_format is requested (structured output) and
    returns valid JSON that can be parsed, otherwise returns plain text.
    """
    from unittest.mock import AsyncMock
    import json
    
    def create_mock_response(content):
        return MagicMock(
            choices=[MagicMock(message=MagicMock(content=content, tool_calls=None))],
            usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )
    
    # Default response for non-structured output
    default_response = create_mock_response("Test response")
    
    # JSON response for structured output - a generic object that can be parsed
    # Real validation will fail but at least JSON parsing succeeds
    json_response = create_mock_response(json.dumps({
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
    }))
    
    def smart_response(*args, **kwargs):
        """Return JSON for structured output requests, plain text otherwise."""
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