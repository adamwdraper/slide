"""
Message classifier for Space Monkey internal use
"""
import logging
import weave
from tyler import Agent

logger = logging.getLogger(__name__)

@weave.op()
def initialize_message_classifier_agent(thread_store=None, file_store=None, model_name="gpt-4.1", purpose_prompt=None, bot_user_id=None):
    """
    Initialize and return a classifier agent that determines if/how the main agent should respond.
    
    Args:
        thread_store: The thread store instance for the agent to use (optional)
        file_store: The file store instance for the agent to use (optional)
        model_name: The model to use for the agent (default: gpt-4.1)
        purpose_prompt: The purpose prompt for the agent
        bot_user_id: The Slack user ID of the bot (optional)
        
    Returns:
        Agent: An initialized message classifier agent
    """
    message_classifier_agent = Agent(
        name="MessageClassifier",
        model_name=model_name,
        version="2.0.0",
        purpose=purpose_prompt.format(bot_user_id=bot_user_id),
        thread_store=thread_store,
        file_store=file_store
    )
    
    logger.info("MessageClassifier agent initialized")
    return message_classifier_agent 