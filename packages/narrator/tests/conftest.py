import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock

# Add project root to PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set environment variables for testing"""
    with patch.dict(os.environ, {
            'NARRATOR_LOG_LEVEL': 'DEBUG',
    'NARRATOR_DB_ECHO': 'false',
    'NARRATOR_MAX_FILE_SIZE': str(50 * 1024 * 1024),  # 50MB
    'NARRATOR_MAX_STORAGE_SIZE': str(5 * 1024 * 1024 * 1024),  # 5GB
    }):
        yield

@pytest_asyncio.fixture
async def memory_thread_store():
    """Create an in-memory thread store for testing"""
    from narrator import ThreadStore
    store = await ThreadStore.create()  # No URL = memory backend
    return store

@pytest_asyncio.fixture
async def temp_file_store():
    """Create a temporary file store for testing"""
    import tempfile
    from narrator import FileStore
    
    with tempfile.TemporaryDirectory() as temp_dir:
        store = await FileStore.create(base_path=temp_dir)
        yield store

@pytest.fixture
def sample_thread():
    """Create a sample thread for testing"""
    from narrator import Thread, Message
    
    thread = Thread(title="Test Thread")
    thread.add_message(Message(role="user", content="Hello"))
    thread.add_message(Message(role="assistant", content="Hi there!"))
    return thread 