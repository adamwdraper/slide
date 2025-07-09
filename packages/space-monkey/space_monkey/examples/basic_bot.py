"""
Basic example bot using Space Monkey framework

This example demonstrates how to create a simple bot with custom agents.
"""

import logging
from typing import Dict, Any, Optional

from space_monkey import SpaceMonkey, SlackAgent, Config
from narrator import Thread, Message

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EchoAgent(SlackAgent):
    """
    A simple echo agent that responds to messages containing "echo:"
    """
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        """Handle messages that start with 'echo:'"""
        text = event.get("text", "").strip()
        return text.lower().startswith("echo:")
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """Echo back the message after 'echo:'"""
        text = event.get("text", "")
        if text.lower().startswith("echo:"):
            echo_text = text[5:].strip()  # Remove "echo:" prefix
            return f"🔊 Echo: {echo_text}"
        return None

class HelpAgent(SlackAgent):
    """
    A help agent that responds to help requests
    """
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        """Handle messages containing 'help'"""
        text = event.get("text", "").lower()
        return "help" in text
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """Provide help information"""
        return """
🤖 **Space Monkey Bot Help**

Here's what I can do:

• **Echo**: Type `echo: your message` and I'll echo it back
• **Help**: Type `help` to see this message
• **Greeting**: Say `hello` or `hi` and I'll greet you

*This is a basic example bot built with Space Monkey framework.*
        """

class GreetingAgent(SlackAgent):
    """
    A greeting agent that responds to greetings
    """
    
    def should_handle(self, event: Dict[str, Any], thread: Thread) -> bool:
        """Handle greeting messages"""
        text = event.get("text", "").lower().strip()
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        return any(greeting in text for greeting in greetings)
    
    async def process_message(self, thread: Thread, event: Dict[str, Any]) -> Optional[str]:
        """Respond with a greeting"""
        user_id = event.get("user", "friend")
        return f"👋 Hello <@{user_id}>! Nice to meet you. I'm Space Monkey, your friendly bot assistant!"

def create_basic_bot() -> SpaceMonkey:
    """
    Create a basic bot with example agents
    
    Returns:
        SpaceMonkey: Configured bot instance
    """
    # Create bot from environment variables
    bot = SpaceMonkey.from_env()
    
    # Add agents
    bot.add_agent("echo", EchoAgent, {"version": "1.0.0"})
    bot.add_agent("help", HelpAgent, {"version": "1.0.0"})
    bot.add_agent("greeting", GreetingAgent, {"version": "1.0.0"})
    
    return bot

def main():
    """Main function to run the basic bot"""
    logger.info("Starting basic Space Monkey bot...")
    
    # Create and run the bot
    bot = create_basic_bot()
    bot.run()

if __name__ == "__main__":
    main() 