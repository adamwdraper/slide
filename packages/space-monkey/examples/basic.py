#!/usr/bin/env python3
"""
Simple Space Monkey example - minimal Slack bot setup
"""
# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

# Import Space Monkey components and configure logging
from space_monkey import SlackApp, Agent, ThreadStore, FileStore
from space_monkey.utils import get_logger
logger = get_logger(__name__)

import asyncio
import os

async def main():
    """Simple Space Monkey bot example"""
    
    # Check for required environment variables
    if not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("SLACK_APP_TOKEN"):
        logger.error("Missing required environment variables!")
        print("❌ Missing required environment variables!")
        print("Please set in your .env file:")
        print("  SLACK_BOT_TOKEN=xoxb-...")
        print("  SLACK_APP_TOKEN=xapp-...")
        return
    
    # Create in-memory stores (simple for testing)
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    logger.info("Created in-memory thread and file stores")
    
    # Create a simple agent with stores
    agent = Agent(
        name="SimpleBot",
        model_name="gpt-4.1",
        purpose="To be a helpful assistant in Slack",
        temperature=0.7,
        thread_store=thread_store,
        file_store=file_store
    )
    logger.info(f"Created agent: {agent.name}")
    
    # Create and start the Slack app
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store
    )
    
    print("🚀 Starting Space Monkey bot...")
    print("📡 Bot is ready to receive messages!")
    print("💬 Mention your bot in Slack to interact")
    print("🛑 Press Ctrl+C to stop")
    
    # Start the app
    await app.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!") 