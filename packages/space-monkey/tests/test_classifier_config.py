"""
Tests for message classifier configuration features
"""
import pytest
import asyncio


def test_format_classifier_prompt_import():
    """Test that format_classifier_prompt can be imported."""
    from space_monkey import format_classifier_prompt
    assert format_classifier_prompt is not None


def test_format_classifier_prompt_default():
    """Test format_classifier_prompt with default values."""
    from space_monkey import format_classifier_prompt
    
    prompt = format_classifier_prompt()
    
    # Should contain default agent name
    assert "Assistant" in prompt
    # Should contain default response topics
    assert "general questions, requests for help, or inquiries" in prompt
    # Should have the proper prompt structure
    assert "Primary Directive" in prompt
    assert "Classification Criteria" in prompt
    assert "Response Rules" in prompt


def test_format_classifier_prompt_custom_agent_name():
    """Test format_classifier_prompt with custom agent name."""
    from space_monkey import format_classifier_prompt
    
    prompt = format_classifier_prompt(agent_name="CustomBot")
    
    # Should contain custom agent name throughout
    assert "CustomBot" in prompt
    assert prompt.count("CustomBot") > 5  # Should appear multiple times
    # Should not contain default name (except maybe in one place)
    assert prompt.count("Assistant") <= 1


def test_format_classifier_prompt_custom_bot_user_id():
    """Test format_classifier_prompt with custom bot user ID."""
    from space_monkey import format_classifier_prompt
    
    bot_id = "U123456789"
    prompt = format_classifier_prompt(bot_user_id=bot_id)
    
    # Should contain the bot user ID in mention format
    assert f"<@{bot_id}>" in prompt


def test_format_classifier_prompt_custom_topics():
    """Test format_classifier_prompt with custom response topics."""
    from space_monkey import format_classifier_prompt
    
    custom_topics = "technical support, bug reports, and product feedback"
    prompt = format_classifier_prompt(response_topics=custom_topics)
    
    # Should contain custom topics
    assert custom_topics in prompt
    # Should not contain default topics
    assert "general questions" not in prompt


@pytest.mark.asyncio
async def test_slack_app_default_classifier_config():
    """Test SlackApp with default classifier configuration."""
    from space_monkey import SlackApp, Agent, ThreadStore, FileStore
    
    # Create test components
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    agent = Agent(
        name="TestBot",
        model_name="gpt-4.1",
        purpose="Test agent",
        tools=["web"]
    )
    
    # Create SlackApp with defaults
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store
    )
    
    # Check that classifier configuration uses defaults
    assert app.response_topics is None  # Should be None to trigger default


@pytest.mark.asyncio
async def test_slack_app_custom_classifier_config():
    """Test SlackApp with custom classifier configuration."""
    from space_monkey import SlackApp, Agent, ThreadStore, FileStore
    
    # Create test components
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    agent = Agent(
        name="MainBot",
        model_name="gpt-4.1",
        purpose="Main agent",
        tools=["web"]
    )
    
    # Custom configuration
    custom_topics = "customer support and technical assistance"
    
    # Create SlackApp with custom config
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        response_topics=custom_topics
    )
    
    # Check that custom configuration is stored
    assert app.response_topics == custom_topics


def test_prompt_structure_integrity():
    """Test that the prompt maintains required structure elements."""
    from space_monkey import format_classifier_prompt
    
    prompt = format_classifier_prompt(
        agent_name="TestBot",
        bot_user_id="U123456",
        response_topics="test topics"
    )
    
    # Check for required sections (case insensitive)
    required_sections = [
        "primary_directive",
        "critical_check_mention",
        "classification_criteria", 
        "output_format_json",
        "emoji_guidelines",
        "agent_response_rules",
        "critical_analysis_last_message",
        "final_reminder"
    ]
    
    for section in required_sections:
        assert section in prompt.lower(), f"Missing required section: {section}"
    
    # Check for JSON structure
    assert '"response_type"' in prompt
    assert '"suggested_emoji"' in prompt
    assert '"confidence"' in prompt
    assert '"reasoning"' in prompt


def test_response_topics_examples():
    """Test common response topics examples work correctly."""
    from space_monkey import format_classifier_prompt
    
    examples = [
        "technical support, troubleshooting, or product questions",
        "people topics, HR, company culture, recognition, or employee experience", 
        "customer service, billing, and account management",
        "general questions, requests for help, or inquiries"
    ]
    
    for topics in examples:
        prompt = format_classifier_prompt(
            agent_name="ExampleBot",
            response_topics=topics
        )
        # Should contain the exact topics text
        assert topics in prompt
        # Should have proper structure
        assert "ExampleBot" in prompt
        assert "Primary Directive" in prompt
