#!/usr/bin/env python3
"""
Cross-Package Integration Example

Demonstrates comprehensive integration of Tyler, Lye, and Narrator
showcasing different storage patterns, tool combinations, and agent capabilities.
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
from datetime import datetime

# Tyler - Agent framework
from tyler import Agent, Thread, Message, ThreadStore, FileStore

# Lye - Tools and capabilities  
from lye import WEB_TOOLS, FILES_TOOLS, IMAGE_TOOLS, AUDIO_TOOLS
from lye.web import search, fetch_page
from lye.files import write_file, read_file
from lye.image import analyze_image

# Narrator - Storage and persistence (imported through Tyler)
# ThreadStore and FileStore are re-exported from Tyler


async def example_basic_integration():
    """Basic example using all three packages together."""
    print("=== Basic Integration Example ===")
    
    # 1. Set up storage with Narrator
    thread_store = await ThreadStore.create()  # In-memory for demo
    file_store = await FileStore.create()      # Default file storage
    
    # 2. Create agent with Tyler using Lye tools
    agent = Agent(
        name="integration-demo",
        model_name="gpt-4o",
        purpose="Demonstrate integration of all Slide packages",
        tools=[
            *WEB_TOOLS,      # All web tools from Lye
            *FILES_TOOLS,    # All file tools from Lye  
            *IMAGE_TOOLS     # All image tools from Lye
        ],
        thread_store=thread_store,  # Narrator storage
        file_store=file_store       # Narrator storage
    )
    
    # 3. Create conversation thread
    thread = Thread(title="Cross-Package Demo")
    
    # 4. Add user message
    message = Message(
        role="user",
        content="Search for information about Python async/await, summarize it, and save it to a file called 'async_summary.md'"
    )
    thread.add_message(message)
    
    # 5. Process with agent
    print("🤖 Agent is working...")
    processed_thread, new_messages = await agent.run(thread)
    
    # 6. Show results
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"💬 Assistant: {msg.content[:200]}...")
        elif msg.role == "tool":
            print(f"🔧 Used tool: {msg.name}")
    
    print(f"✅ Thread saved with ID: {processed_thread.id}")
    return processed_thread


async def example_selective_tools():
    """Example using specific tools rather than tool groups."""
    print("\n=== Selective Tools Example ===")
    
    # Create agent with only specific tools we need
    agent = Agent(
        name="selective-agent",
        model_name="gpt-4o", 
        purpose="Focused agent with specific tools",
        tools=[
            search,         # Just web search
            fetch_page,     # Just page fetching
            write_file,     # Just file writing
            analyze_image   # Just image analysis
        ]
    )
    
    thread = Thread()
    message = Message(
        role="user",
        content="What tools do I have available? List them for me."
    )
    thread.add_message(message)
    
    processed_thread, new_messages = await agent.run(thread)
    
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"💬 Agent response: {msg.content}")
    
    return processed_thread


async def example_persistent_storage():
    """Example using persistent database storage."""
    print("\n=== Persistent Storage Example ===")
    
    # Use SQLite database for thread storage
    thread_store = await ThreadStore.create("sqlite+aiosqlite:///demo.db")
    file_store = await FileStore.create(base_path="./demo_files")
    
    agent = Agent(
        name="persistent-agent",
        model_name="gpt-4o",
        purpose="Agent with persistent storage",
        tools=["web", "files"],
        thread_store=thread_store,
        file_store=file_store
    )
    
    # Try to resume existing conversation
    existing_threads = await thread_store.list_recent(limit=1)
    
    if existing_threads:
        # Resume existing thread
        thread = existing_threads[0]
        print(f"📚 Resuming thread: {thread.title}")
        print(f"   Previous messages: {len(thread.messages)}")
    else:
        # Create new thread
        thread = Thread(title="Persistent Demo Session")
        print("🆕 Starting new persistent session")
    
    # Add new message
    message = Message(
        role="user",
        content="What did we discuss before? If this is our first conversation, introduce yourself."
    )
    thread.add_message(message)
    
    # Process and save
    processed_thread, new_messages = await agent.run(thread)
    await thread_store.save_thread(processed_thread)
    
    for msg in new_messages:
        if msg.role == "assistant":
            print(f"💬 Persistent agent: {msg.content[:200]}...")
    
    print(f"💾 Thread saved to database with {len(processed_thread.messages)} total messages")
    return processed_thread


async def example_mixed_storage():
    """Example showing different storage configurations."""
    print("\n=== Mixed Storage Example ===")
    
    # Create multiple agents with different storage configs
    agents_config = [
        {
            "name": "memory-agent",
            "thread_store": await ThreadStore.create(),  # In-memory
            "file_store": await FileStore.create(),      # In-memory files
            "description": "Everything in memory"
        },
        {
            "name": "hybrid-agent", 
            "thread_store": await ThreadStore.create("sqlite+aiosqlite:///hybrid.db"),  # DB threads
            "file_store": await FileStore.create(),                                    # Memory files
            "description": "DB threads, memory files"
        },
        {
            "name": "persistent-agent",
            "thread_store": await ThreadStore.create("sqlite+aiosqlite:///persistent.db"),  # DB threads
            "file_store": await FileStore.create(base_path="./persistent_files"),          # Disk files
            "description": "Everything persistent"
        }
    ]
    
    results = []
    for config in agents_config:
        agent = Agent(
            name=config["name"],
            model_name="gpt-4o",
            purpose=f"Agent with {config['description']}",
            tools=["web"],
            thread_store=config["thread_store"],
            file_store=config["file_store"]
        )
        
        thread = Thread(title=f"Test for {config['name']}")
        message = Message(role="user", content="Hello! What's your storage configuration?")
        thread.add_message(message)
        
        processed_thread, new_messages = await agent.run(thread)
        
        result = {
            "agent": config["name"],
            "description": config["description"],
            "thread_id": processed_thread.id,
            "response": new_messages[-1].content if new_messages else "No response"
        }
        results.append(result)
        
        print(f"✅ {config['name']}: {config['description']}")
    
    return results


async def example_tool_combinations():
    """Example showing different tool combinations for different use cases."""
    print("\n=== Tool Combinations Example ===")
    
    # Different agent configurations for different purposes
    agent_configs = [
        {
            "name": "researcher",
            "purpose": "Research and analysis",
            "tools": [*WEB_TOOLS, *FILES_TOOLS],
            "task": "Research the latest AI developments and save findings"
        },
        {
            "name": "content-creator", 
            "purpose": "Content creation and media",
            "tools": [*IMAGE_TOOLS, *FILES_TOOLS, *AUDIO_TOOLS],  
            "task": "Describe what tools you have for content creation"
        },
        {
            "name": "generalist",
            "purpose": "General assistance",
            "tools": [*WEB_TOOLS, *FILES_TOOLS, *IMAGE_TOOLS, *AUDIO_TOOLS],
            "task": "What can you help me with given your tools?"
        }
    ]
    
    for config in agent_configs:
        print(f"\n🤖 {config['name'].title()} Agent:")
        
        agent = Agent(
            name=config["name"],
            model_name="gpt-4o",
            purpose=config["purpose"],
            tools=config["tools"]
        )
        
        print(f"   Tools available: {len(agent._processed_tools)}")
        
        thread = Thread()
        message = Message(role="user", content=config["task"])
        thread.add_message(message)
        
        processed_thread, new_messages = await agent.run(thread)
        
        for msg in new_messages:
            if msg.role == "assistant":
                print(f"   Response: {msg.content[:150]}...")
                break


async def main():
    """Run all cross-package integration examples."""
    print("🔗 Cross-Package Integration Examples")
    print("=" * 50)
    print("Demonstrating Tyler + Lye + Narrator working together\n")
    
    try:
        # Run all examples
        await example_basic_integration()
        await example_selective_tools()
        await example_persistent_storage()
        await example_mixed_storage()
        await example_tool_combinations()
        
        print("\n" + "=" * 50)
        print("✅ All integration examples completed successfully!")
        print("\nKey takeaways:")
        print("- Tyler provides the agent framework")
        print("- Lye provides tools and capabilities")
        print("- Narrator handles storage and persistence")
        print("- All three work seamlessly together")
        
    except Exception as e:
        print(f"❌ Error in integration examples: {e}")
        raise


if __name__ == "__main__":
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting gracefully... 👋")
    except Exception as e:
        print(f"Error: {e}")
        raise