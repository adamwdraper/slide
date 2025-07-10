import logging
from tyler import Agent
import weave

# Set up logging
logger = logging.getLogger(__name__)

@weave.op()
def initialize_my_hr_bot_agent(thread_store=None, file_store=None, model_name="gpt-4.1", purpose_prompt=None, bot_user_id=None):
    """
    Initialize and return a my-hr-bot Agent configured with store instances
    
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
# No sub-agents specified

    # Create the my-hr-bot agent
    my_hr_bot_agent = Agent(
        name="my-hr-bot",
        model_name=model_name,
        version="1.0.0",
        purpose=purpose_prompt.format(bot_user_id=bot_user_id) if bot_user_id else purpose_prompt,
        notes=f"""
- Advanced HR assistant with Notion integration
- Specialized for Slack bot interactions
- Bot user ID: {bot_user_id}
""",
        # Tools configuration
# No tools specified
        thread_store=thread_store,
        file_store=file_store,
        # Sub-agents: []
    )

    logger.info("my-hr-bot agent initialized with tools: []")
    
    return my_hr_bot_agent 