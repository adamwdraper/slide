#!/usr/bin/env python3
"""
Example usage of Tyler Stores

This script demonstrates basic usage of ThreadStore and FileStore.
"""

import asyncio
from narrator import ThreadStore, FileStore, Thread, Message, Attachment

async def thread_store_example():
    """Demonstrate ThreadStore usage"""
    print("=== ThreadStore Example ===")
    
    # Create an in-memory thread store
    store = await ThreadStore.create()
    print("Created in-memory ThreadStore")
    
    # Create a thread
    thread = Thread(title="Example Conversation")
    
    # Add some messages
    thread.add_message(Message(role="user", content="Hello, I need help with Python"))
    thread.add_message(Message(role="assistant", content="I'd be happy to help you with Python! What specific topic would you like to learn about?"))
    thread.add_message(Message(role="user", content="How do I use async/await?"))
    
    print(f"Created thread '{thread.title}' with {len(thread.messages)} messages")
    
    # Save the thread
    await store.save(thread)
    print(f"Saved thread with ID: {thread.id}")
    
    # Retrieve the thread
    retrieved = await store.get(thread.id)
    if retrieved:
        print(f"Retrieved thread: '{retrieved.title}' with {len(retrieved.messages)} messages")
        for i, msg in enumerate(retrieved.messages, 1):
            print(f"  {i}. {msg.role}: {msg.content[:50]}...")
    
    # List recent threads
    recent = await store.list_recent(limit=5)
    print(f"Found {len(recent)} recent threads")
    
    print()

async def file_store_example():
    """Demonstrate FileStore usage"""
    print("=== FileStore Example ===")
    
    # Create a file store
    store = await FileStore.create()
    print("Created FileStore")
    
    # Save a text file
    content = b"This is a sample text file content.\nIt contains multiple lines."
    metadata = await store.save(content, "sample.txt", "text/plain")
    print(f"Saved text file: {metadata['filename']}")
    print(f"  File ID: {metadata['id']}")
    print(f"  Storage path: {metadata['storage_path']}")
    
    # Retrieve the file
    retrieved_content = await store.get(metadata['id'])
    print(f"Retrieved content: {retrieved_content.decode()[:50]}...")
    
    # Check storage health
    health = await store.check_health()
    print(f"Storage health: {health}")
    
    print()

async def attachment_example():
    """Demonstrate message attachments"""
    print("=== Attachment Example ===")
    
    file_store = await FileStore.create()
    thread_store = await ThreadStore.create()
    
    # Create a message with an attachment
    message = Message(role="user", content="Here's a document for you to review")
    
    # Create an attachment with sample content
    sample_text = "This is a sample document.\n\nIt contains some important information."
    attachment = Attachment(
        filename="document.txt",
        content=sample_text.encode('utf-8'),
        mime_type="text/plain"
    )
    
    # Add attachment to message
    message.add_attachment(attachment)
    
    # Process and store the attachment
    await attachment.process_and_store(file_store)
    print(f"Processed attachment: {attachment.filename}")
    print(f"  Status: {attachment.status}")
    print(f"  File ID: {attachment.file_id}")
    if attachment.attributes:
        print(f"  Extracted text: {attachment.attributes.get('text', 'N/A')[:50]}...")
    
    # Create a thread with the message
    thread = Thread(title="Document Review")
    thread.add_message(message)
    
    # Save to thread store
    await thread_store.save(thread)
    print(f"Saved thread with attachment")
    
    # Retrieve and verify
    retrieved = await thread_store.get(thread.id)
    if retrieved and retrieved.messages:
        msg = retrieved.messages[0]
        if msg.attachments:
            att = msg.attachments[0]
            print(f"Retrieved attachment: {att.filename} (status: {att.status})")
    
    print()

async def platform_example():
    """Demonstrate platform integration"""
    print("=== Platform Integration Example ===")
    
    store = await ThreadStore.create()
    
    # Create a thread linked to a Slack conversation
    thread = Thread(
        title="Customer Support Ticket #123",
        platforms={
            "slack": {
                "channel": "C1234567890",
                "thread_ts": "1234567890.123456"
            }
        },
        attributes={
            "customer_id": "cust_12345",
            "priority": "high",
            "department": "support"
        }
    )
    
    # Add some messages
    thread.add_message(Message(
        role="user", 
        content="I'm having trouble with my account",
        source={
            "id": "U123456",
            "name": "John Doe",
            "type": "user"
        }
    ))
    
    thread.add_message(Message(
        role="assistant",
        content="I'll help you with your account issue. Can you provide more details?"
    ))
    
    await store.save(thread)
    print(f"Saved thread with platform data: {thread.platforms}")
    
    # Find threads by platform
    slack_threads = await store.find_by_platform("slack", {"channel": "C1234567890"})
    print(f"Found {len(slack_threads)} threads in Slack channel")
    
    # Find threads by attributes
    high_priority = await store.find_by_attributes({"priority": "high"})
    print(f"Found {len(high_priority)} high priority threads")
    
    print()

async def main():
    """Run all examples"""
    print("Tyler Stores Examples")
    print("=" * 50)
    
    await thread_store_example()
    await file_store_example()
    await attachment_example()
    await platform_example()
    
    print("All examples completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 