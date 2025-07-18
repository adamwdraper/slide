#!/usr/bin/env python3
"""
Space Monkey example with multiple tool capabilities
This bot can generate images using DALL-E 3 and handle audio (text-to-speech and speech-to-text)
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
    """Space Monkey bot with image generation and audio processing capabilities"""
    
    # Check for required environment variables
    required_vars = {
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_APP_TOKEN": "xapp-...",
        "OPENAI_API_KEY": "sk-..."  # Required for image generation and audio processing
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
    
    # Create an agent with multiple tool capabilities
    agent = Agent(
        name="ToolsBot",
        model_name="gpt-4.1",
        purpose="""You are a versatile AI assistant that helps users with various tasks in Slack.
        
        Your capabilities include:
        
        **Image Generation:**
        When users ask you to create, generate, or make an image:
        1. Use the image generation tool to create the image
        2. Describe what you're creating
        3. Share any tips for better prompts
        
        **Audio Processing:**
        When users ask you to convert text to speech:
        1. Use the text-to-speech tool with appropriate voice selection
        2. Generate clear, natural-sounding audio
        
        When users share audio files for transcription:
        1. Use the speech-to-text tool to transcribe the content
        2. Provide accurate text transcription
        
        You're friendly, helpful, and love assisting people with creative and practical tasks!""",
        temperature=0.7,
        thread_store=thread_store,
        file_store=file_store,
        tools=["image", "audio"]  # Enable both image and audio tools
    )
    logger.info(f"Created agent: {agent.name} with image and audio capabilities")
    
    # Create and configure the Slack app
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        response_topics="image generation, audio processing, text-to-speech, speech-to-text, creating visuals, DALL-E requests, art creation, voice synthesis, transcription"
    )
    
    print("🚀 Starting Space Monkey Tools Bot...")
    print("🎨 Bot can generate images using DALL-E 3!")
    print("🔊 Bot can convert text to speech and transcribe audio!")
    print("📡 Bot is ready to receive messages!")
    print("💬 Try asking your bot to:")
    print("   • 'generate an image of...' or 'create a picture of...'")
    print("   • 'convert this text to speech: [your text]'")
    print("   • Share an audio file and ask 'transcribe this audio'")
    print("🛑 Press Ctrl+C to stop")
    
    # Start the app
    await app.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!") 