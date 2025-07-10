import logging
from tyler import Agent
import weave

# Set up logging
logger = logging.getLogger(__name__)

@weave.op()
def initialize_example_bot_agent(thread_store=None, file_store=None, model_name="gpt-4.1", purpose_prompt=None, bot_user_id=None):
    """
    Initialize and return a example-bot Agent configured with store instances
    
    Args:
        thread_store: The thread store instance for the agent to use (optional)
        file_store: The file store instance for the agent to use (optional)
        model_name: The model to use for the agent (default: gpt-4.1)
        purpose_prompt: The purpose prompt for the agent
        bot_user_id: The Slack user ID of the bot (optional)
        
    Returns:
        Agent: An initialized Tyler Agent
    """
    
    # Initialize sub-agents if any
    # Sub-agent: helper

    # Create the example-bot agent
    example_bot_agent = Agent(
        name="example-bot",
        model_name=model_name,
        version="1.0.0",
        purpose=purpose_prompt.format(bot_user_id=bot_user_id) if bot_user_id else purpose_prompt,
        notes=f"""
- An example Slack bot for testing
- Specialized for Slack bot interactions
- Bot user ID: {bot_user_id}
""",
        # Tools configuration
    # Notion: notion-search
    # Slack: send-message
        thread_store=thread_store,
        file_store=file_store,
        # Sub-agents: ['helper']
    )

    logger.info("example-bot agent initialized with tools: ['notion:notion-search', 'slack:send-message']")
    
    return example_bot_agent 