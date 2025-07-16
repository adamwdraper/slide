#!/usr/bin/env python3
"""
Simple Space Monkey example - minimal Slack bot setup
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Space Monkey components
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

async def main():
    """Simple Space Monkey bot example"""
    
    # Check for required environment variables
    if not os.getenv("SLACK_BOT_TOKEN") or not os.getenv("SLACK_APP_TOKEN"):
        print("❌ Missing required environment variables!")
        print("Please set in your .env file:")
        print("  SLACK_BOT_TOKEN=xoxb-...")
        print("  SLACK_APP_TOKEN=xapp-...")
        return
    
    # Create a simple agent
    agent = Agent(
        name="SimpleBot",
        model_name="gpt-4.1",
        purpose="To be a helpful assistant in Slack",
        temperature=0.7
    )
    
    # Create in-memory stores (simple for testing)
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    
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