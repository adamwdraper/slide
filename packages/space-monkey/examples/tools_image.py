#!/usr/bin/env python3
"""
Space Monkey example with image generation capabilities
This bot can generate images using DALL-E 3 when asked
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
    """Space Monkey bot with image generation capabilities"""
    
    # Check for required environment variables
    required_vars = {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_APP_TOKEN": "xapp-...",
        "OPENAI_API_KEY": "sk-..."  # Required for image generation
    }
    
    missing_vars = []
    for var, example in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  {var}={example}")
    
    if missing_vars:
        logger.error("Missing required environment variables!")
        print("❌ Missing required environment variables!")
        print("Please set in your .env file:")
        for var in missing_vars:
            print(var)
        return
    
    # Create in-memory stores
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    logger.info("Created in-memory thread and file stores")
    
    # Create an agent with image generation capabilities
    agent = Agent(
        name="ImageBot",
        model_name="gpt-4o",
        purpose="""You are a creative AI assistant that helps users generate images in Slack.
        
        When users ask you to create, generate, or make an image:
        1. Use the image generation tool to create the image
        2. Describe what you're creating
        3. Share any tips for better prompts
        
        You're friendly, creative, and love helping people bring their visual ideas to life!""",
        temperature=0.7,
        thread_store=thread_store,
        file_store=file_store,
        tools=["image"]  # Enable image generation tools
    )
    logger.info(f"Created agent: {agent.name} with image generation capabilities")
    
    # Create and configure the Slack app
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        response_topics="image generation, creating visuals, DALL-E requests, art creation"
    )
    
    print("🚀 Starting Space Monkey Image Bot...")
    print("🎨 Bot can generate images using DALL-E 3!")
    print("📡 Bot is ready to receive messages!")
    print("💬 Try asking your bot to 'generate an image of...' or 'create a picture of...'")
    print("🛑 Press Ctrl+C to stop")
    
    # Start the app
    await app.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!") 