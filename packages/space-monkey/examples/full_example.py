#!/usr/bin/env python3
"""
Space Monkey Example - Simple HR Agent

This example demonstrates how to create and run a Slack agent using Space Monkey
with the clean API described in the README.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

# Import everything from Space Monkey
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """
    Main function demonstrating the Space Monkey API.
    """
    logger.info("Starting Space Monkey example...")
    
    # Load environment variables
    load_dotenv()
    
    # Verify required environment variables
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set them in your .env file")
        return
    
    try:
        # Create stores - using in-memory for this example
        logger.info("Creating stores...")
        thread_store = await ThreadStore.create()  # In-memory by default
        file_store = await FileStore.create()      # Default file storage
        
        logger.info("Stores created successfully")
        
        # Create agent directly
        logger.info("Creating Tyler agent...")
        
        agent = Agent(
            name="ExampleBot",
            model_name="gpt-4.1",
            purpose="To be a helpful assistant in Slack",
            tools=["web", "files"],
            temperature=0.7
        )
        logger.info("Tyler agent created successfully")
        
        # Create and configure Slack app
        logger.info("Creating Slack app...")
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store
        )
        
        logger.info("Slack app created successfully")
        logger.info("Starting server on http://0.0.0.0:8000")
        logger.info("Bot is ready to receive Slack messages!")
        
        # Start the app
        await app.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error running Space Monkey: {e}")
        raise

def example_with_database():
    """
    Example showing how to use with a PostgreSQL database.
    
    Note: This is just for demonstration - you'd call this instead of main()
    """
    async def database_example():
        # Production setup with PostgreSQL
        thread_store = await ThreadStore.create(
            "postgresql+asyncpg://user:pass@localhost/db"
        )
        file_store = await FileStore.create(base_path="/data/files")
        
        # Custom agent
        agent = Agent(
            name="SupportBot",
            model_name="gpt-4.1",
            purpose="Help users with technical support questions",
            tools=["web", "files"],
            temperature=0.3
        )
        
        app = SlackApp(
            agent=agent,
            thread_store=thread_store,
            file_store=file_store,
            weave_project="support-bot"
        )
        
        await app.start(port=8080)
    
    return database_example

if __name__ == "__main__":
    print("🚀 Space Monkey - Tyler Slack Agent Example")
    print("==========================================")
    print()
    print("This example shows how to create a Slack agent with just a few lines of code.")
    print("Make sure you have set up your .env file with the required variables:")
    print("  - SLACK_BOT_TOKEN")
    print("  - SLACK_APP_TOKEN")
    print("  - PERCI_PROMPT_VERSION (optional)")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋") 