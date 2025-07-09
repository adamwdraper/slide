# Slide 🐧

A comprehensive toolkit for building AI agents with powerful conversation management and file storage capabilities.

## Overview

Slide is a monorepo containing a collection of AI agent development tools:

- **Tyler** (`slide-tyler`) - A development kit for manifesting AI agents with a complete lack of conventional limitations
- **The Narrator** (`slide-narrator`) - Thread and file storage components for conversational AI

## Installation

### Install Individual Components

```bash
# Install Tyler only
pip install slide-tyler

# Install The Narrator only
pip install slide-narrator

# Install both
pip install slide-tyler slide-narrator
```

### Install Everything

```bash
# Install the complete Slide toolkit
pip install slide
```

## Quick Start

### Using Tyler

```python
import asyncio
from tyler import Agent
from narrator import Thread, Message

async def main():
    # Create an AI agent
    agent = Agent(
        name="MyAgent",
        purpose="You are a helpful assistant"
    )

    # Create a thread and add a message
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello, how are you?"))

    # Process the thread
    updated_thread, new_messages = await agent.go(thread)
    
    # Print the assistant's response
    for message in new_messages:
        if message.role == "assistant":
            print(f"Assistant: {message.content}")

asyncio.run(main())
```

### Using The Narrator

```python
import asyncio
from narrator import ThreadStore, Thread, Message

async def main():
    # Create a thread store for conversation management
    store = await ThreadStore.create()

    # Create and save a thread
    thread = Thread(title="My Conversation")
    thread.add_message(Message(role="user", content="Hello!"))
    thread.add_message(Message(role="assistant", content="Hi there!"))
    
    # Save the thread
    await store.save(thread)
    
    # Retrieve the thread
    retrieved_thread = await store.get(thread.id)
    print(f"Thread: {retrieved_thread.title}")
    print(f"Messages: {len(retrieved_thread.messages)}")

asyncio.run(main())
```

### Using Both Together

```python
import asyncio
from tyler import Agent
from narrator import ThreadStore, Thread, Message

async def main():
    # Create persistent storage
    store = await ThreadStore.create("sqlite+aiosqlite:///conversations.db")

    # Create an agent with persistent storage
    agent = Agent(
        name="PersistentAgent",
        purpose="You are a helpful assistant with memory",
        thread_store=store
    )

    # Create a thread and add a message
    thread = Thread(title="Persistent Conversation")
    thread.add_message(Message(role="user", content="Remember this: my name is John"))
    
    # Process the first message
    updated_thread, new_messages = await agent.go(thread)
    
    # Add another message to the same thread
    thread.add_message(Message(role="user", content="What's my name?"))
    
    # Process the second message (will remember "John")
    final_thread, final_messages = await agent.go(thread)
    
    # Print the assistant's response
    for message in final_messages:
        if message.role == "assistant":
            print(f"Assistant: {message.content}")

asyncio.run(main())
```

## Project Structure

```
slide/
├── packages/
│   ├── tyler/           # Tyler agent framework
│   ├── narrator/        # Thread and file storage
│   └── future-tools/    # Additional tools (coming soon)
├── docs/               # Unified documentation
├── examples/           # Cross-component examples
└── scripts/            # Build and development scripts
```

## Development

### Setting up Development Environment

```bash
# Clone the repository
git clone https://github.com/adamwdraper/slide.git
cd slide

# Install development dependencies
pip install -e packages/tyler[dev]
pip install -e packages/narrator[dev]

# Run tests
pytest packages/tyler/tests
pytest packages/narrator/tests
```

### Building and Testing

```bash
# Build individual packages
cd packages/tyler && python -m build
cd packages/narrator && python -m build

# Test all packages
pytest packages/*/tests
```

## Documentation

- [Tyler Documentation](./packages/tyler/README.md)
- [The Narrator Documentation](./packages/narrator/README.md)
- [Full Documentation](./docs/) (coming soon)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

- Tyler: CC BY-NC 4.0
- The Narrator: MIT
- Slide (meta-package): MIT

## Support

- [GitHub Issues](https://github.com/adamwdraper/slide/issues)
- [Documentation](https://github.com/adamwdraper/slide#readme)

---

**Slide** - Building the future of AI agents, one conversation at a time. 🚀 