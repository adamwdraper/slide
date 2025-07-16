"""
Tests for Space Monkey API
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Test imports work correctly
def test_imports():
    """Test that all main classes can be imported."""
    try:
        from space_monkey import SlackApp, Agent, ThreadStore, FileStore
        assert SlackApp is not None
        assert Agent is not None
        assert ThreadStore is not None
        assert FileStore is not None
    except ImportError as e:
        pytest.fail(f"Failed to import Space Monkey components: {e}")

@pytest.mark.asyncio
async def test_stores_creation():
    """Test that stores can be created."""
    from space_monkey import ThreadStore, FileStore
    
    # Test ThreadStore creation (in-memory)
    thread_store = await ThreadStore.create()
    assert thread_store is not None
    
    # Test FileStore creation
    file_store = await FileStore.create()
    assert file_store is not None

def test_agent_creation():
    """Test that agents can be created."""
    from space_monkey import Agent
    
    # Test agent creation with required parameters
    agent = Agent(
        name="TestAgent",
        model_name="gpt-4.1",
        purpose="Test agent for unit testing",
        tools=["web"],
        temperature=0.7
    )
    
    assert agent.name == "TestAgent"
    assert agent.model_name == "gpt-4.1"
    assert "Test agent" in str(agent.purpose)

@pytest.mark.asyncio
async def test_slack_app_creation():
    """Test that SlackApp can be instantiated."""
    from space_monkey import SlackApp, Agent, ThreadStore, FileStore
    
    # Create mock components
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    agent = Agent(
        name="TestAgent",
        model_name="gpt-4.1", 
        purpose="Test purpose",
        tools=["web"],
        temperature=0.7
    )
    
    # Create SlackApp (don't start it)
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store
    )
    
    assert app.agent == agent
    assert app.thread_store == thread_store
    assert app.file_store == file_store

@pytest.mark.asyncio
async def test_slack_app_with_classifier_config():
    """Test that SlackApp accepts the new classifier configuration parameters."""
    from space_monkey import SlackApp, Agent, ThreadStore, FileStore
    
    # Create mock components
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    agent = Agent(
        name="TestAgent",
        model_name="gpt-4.1", 
        purpose="Test purpose",
        tools=["web"],
        temperature=0.7
    )
    
    # Create SlackApp with classifier config
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        response_topics="custom test topics"
    )
    
    assert app.agent == agent
    assert app.thread_store == thread_store
    assert app.file_store == file_store
    assert app.response_topics == "custom test topics"

def test_api_matches_readme():
    """Test that the API matches what's documented in the README."""
    # This test ensures the API we've implemented matches the README examples
    
    # Test 1: Simple import
    from space_monkey import SlackApp, Agent, ThreadStore, FileStore
    
    # Test 2: Agent constructor signature (Tyler Agent)
    import inspect
    agent_sig = inspect.signature(Agent.__init__)
    actual_params = list(agent_sig.parameters.keys())
    # Tyler Agent uses Pydantic model constructor pattern
    assert 'self' in actual_params, "Agent should have 'self' parameter"
    
    # Test that we can create an Agent instance (basic smoke test)
    agent = Agent(name="test", model_name="gpt-4.1", purpose="Test agent")
    assert agent.name == "test"
    assert agent.model_name == "gpt-4.1"
    
    # Test 3: SlackApp constructor signature
    slack_app_sig = inspect.signature(SlackApp.__init__)
    expected_slack_params = [
        'agent', 'thread_store', 'file_store', 'health_check_url', 'weave_project',
        'response_topics'
    ]
    actual_slack_params = list(slack_app_sig.parameters.keys())[1:]  # Skip 'self'
    
    for param in expected_slack_params:
        assert param in actual_slack_params, f"Missing parameter {param} in SlackApp.__init__()"

 