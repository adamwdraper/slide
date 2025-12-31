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
    """Mock OpenAI/litellm calls for testing (both sync and async)"""
    from unittest.mock import AsyncMock
    
    mock_response = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response", tool_calls=None))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    )
    
    with patch('litellm.completion') as mock_sync, \
         patch('litellm.acompletion', new_callable=AsyncMock) as mock_async:
        mock_sync.return_value = mock_response
        mock_async.return_value = mock_response
        yield mock_sync, mock_async

@pytest.fixture(autouse=True)
def mock_wandb():
    """Mock wandb calls for testing"""
    with patch('wandb.init') as mock_init, \
         patch('wandb.log') as mock_log:
        mock_init.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        yield mock_init, mock_log 