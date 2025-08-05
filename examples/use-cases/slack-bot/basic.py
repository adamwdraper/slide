#!/usr/bin/env python3
"""
Slack Bot Example - Basic

Demonstrates how to create a Slack bot using Space Monkey (which integrates
Tyler, Lye, and Narrator) for a complete AI agent experience.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os

# Import Space Monkey (which uses Tyler, Lye, and Narrator internally)
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_research_bot():
    """Create a research-focused Slack bot."""
    
    # Set up persistent storage
    thread_store = await ThreadStore.create("sqlite+aiosqlite:///slack_bot.db")
    file_store = await FileStore.create(base_path="./slack_files")
    
    # Create research-focused agent
    agent = Agent(
        name="ResearchBot",
        model_name="gpt-4o",
        purpose="""I'm a research assistant bot for Slack. I can:
        - Search the web for information
        - Analyze and summarize findings
        - Save research reports as files
        - Answer questions with sources
        - Help with fact-checking
        
        I maintain conversation context and can work on multi-part research tasks.
        """,
        tools=["web", "files", "image"],  # Use tool groups for simplicity
        temperature=0.3,  # Lower temperature for more focused responses
        thread_store=thread_store,
        file_store=file_store
    )
    
    return agent, thread_store, file_store


async def create_general_assistant():
    """Create a general-purpose assistant bot."""
    
    # Set up storage
    thread_store = await ThreadStore.create("sqlite+aiosqlite:///assistant_bot.db")  
    file_store = await FileStore.create(base_path="./assistant_files")
    
    # Create general assistant agent
    agent = Agent(
        name="AssistantBot",
        model_name="gpt-4o",
        purpose="""I'm a helpful assistant bot for your Slack workspace. I can:
        - Answer questions and provide explanations
        - Help with writing and editing
        - Search for information online
        - Work with files and documents
        - Analyze images and media
        - Execute simple automation tasks
        
        I'm friendly, helpful, and maintain context across our conversations.
        """,
        tools=["web", "files", "image", "audio"],  # Full tool suite
        temperature=0.7,  # Higher temperature for more creative responses
        thread_store=thread_store,
        file_store=file_store
    )
    
    return agent, thread_store, file_store


async def create_support_bot():
    """Create a customer support focused bot."""
    
    # Set up storage with longer retention for support tickets
    thread_store = await ThreadStore.create("sqlite+aiosqlite:///support_bot.db")
    file_store = await FileStore.create(base_path="./support_files")
    
    # Create support-focused agent
    agent = Agent(
        name="SupportBot", 
        model_name="gpt-4o",
        purpose="""I'm a customer support assistant. I can:
        - Help troubleshoot technical issues
        - Search for solutions and documentation
        - Create support tickets and reports
        - Escalate complex issues appropriately
        - Maintain detailed conversation history
        
        I'm patient, thorough, and focused on solving problems.
        """,
        tools=["web", "files"],  # Focused toolset for support
        temperature=0.2,  # Very focused responses for support
        thread_store=thread_store,
        file_store=file_store
    )
    
    return agent, thread_store, file_store


async def main():
    """Main function to set up and run the Slack bot."""
    
    # Load environment variables
    load_dotenv()
    
    # Check required environment variables
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("\nPlease set them in your .env file:")
        print("SLACK_BOT_TOKEN=xoxb-your-bot-token")
        print("SLACK_APP_TOKEN=xapp-your-app-token")
        print("\nSee Slack documentation for how to get these tokens:")
        print("https://api.slack.com/authentication/token-types")
        return
    
    # Choose which bot to create (you can change this)
    bot_type = os.getenv("BOT_TYPE", "research")  # research, assistant, or support
    
    try:
        if bot_type == "research":
            print("🔬 Creating Research Bot...")
            agent, thread_store, file_store = await create_research_bot()
        elif bot_type == "assistant":
            print("🤖 Creating General Assistant Bot...")
            agent, thread_store, file_store = await create_general_assistant()
        elif bot_type == "support":
            print("🎧 Creating Support Bot...")
            agent, thread_store, file_store = await create_support_bot()
        else:
            raise ValueError(f"Unknown bot type: {bot_type}")
        
        logger.info(f"Created {agent.name} with persistent storage")
        
        # Create and configure Slack app
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store,
            # Optional: Enable Weave tracing
            weave_project=f"slack-{bot_type}-bot" if os.getenv("WANDB_API_KEY") else None
        )
        
        logger.info("Slack app configured successfully")
        logger.info(f"Starting {agent.name} on http://0.0.0.0:8000")
        logger.info("Bot is ready to receive Slack messages! 🚀")
        logger.info(f"Bot type: {bot_type} (set BOT_TYPE env var to change)")
        
        # Start the app
        await app.start()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping bot...")
    except Exception as e:
        logger.error(f"Error running Slack bot: {e}")
        raise


def setup_example():
    """Print setup instructions for the Slack bot."""
    print("🤖 Slack Bot Setup Instructions")
    print("=" * 50)
    print()
    print("1. Create a Slack app at https://api.slack.com/apps")
    print("2. Enable Socket Mode in your app settings")
    print("3. Add the following OAuth scopes:")
    print("   - app_mentions:read")
    print("   - channels:history") 
    print("   - chat:write")
    print("   - files:write")
    print("   - im:history")
    print("   - im:write")
    print()
    print("4. Create a .env file with your tokens:")
    print("   SLACK_BOT_TOKEN=xoxb-your-bot-token")
    print("   SLACK_APP_TOKEN=xapp-your-app-token")
    print("   OPENAI_API_KEY=sk-your-openai-key")
    print("   BOT_TYPE=research  # or 'assistant' or 'support'")
    print()
    print("5. Install your app to your workspace")
    print("6. Run this script: python examples/use-cases/slack-bot/basic.py")
    print()
    print("Bot Types:")
    print("- research: Focused on research and information gathering")
    print("- assistant: General-purpose helpful assistant")  
    print("- support: Customer support focused bot")
    print()


if __name__ == "__main__":
    # Show setup instructions if tokens are missing
    if not (os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_APP_TOKEN")):
        setup_example()
        exit(1)
    
    
    print(f"🚀 Starting Slide Slack Bot")
    print(f"Bot type: {os.getenv('BOT_TYPE', 'research')}")
    print("Press Ctrl+C to stop\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped. Goodbye! 👋")