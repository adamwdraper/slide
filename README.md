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

### Setting up Development Environment with UV

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management and uses a workspace structure for developing multiple packages together.

```bash
# Clone the repository
git clone https://github.com/adamwdraper/slide.git
cd slide

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync the entire workspace (installs all packages in development mode)
uv sync

# Include development dependencies
uv sync --dev
```

### UV Workspace Commands

#### Working from the Root Directory (Recommended)

```bash
# Sync all packages at once
uv sync

# Add a dependency to a specific package
uv add --package tyler requests
uv add --package lye beautifulsoup4

# Add development dependencies
uv add --dev pytest-mock

# Run commands in workspace context
uv run python -m tyler.cli
uv run --package tyler pytest
uv run --package lye python examples/demo.py

# Build specific packages
uv build --package tyler
uv build --package narrator

# See the entire dependency tree
uv tree

# Update dependencies
uv lock --upgrade                    # Upgrade all packages
uv lock --upgrade-package openai     # Upgrade specific package
```

#### Working from Package Directories

```bash
# Navigate to a package
cd packages/tyler

# Commands still use the workspace
uv sync              # Uses root uv.lock
uv add pandas        # Adds to tyler's pyproject.toml
uv run pytest        # Runs with workspace packages

# The workspace detects you're in a subdirectory
uv tree              # Shows tyler's dependencies
```

#### Key UV Commands for Development

```bash
# Python version management
uv python list           # List available Python versions
uv python install 3.12   # Install Python 3.12
uv python pin 3.12       # Set project to use Python 3.12

# Running code and tests
uv run python script.py              # Run a script
uv run --package tyler pytest        # Run tyler's tests
uv run pytest packages/*/tests       # Run all package tests

# Publishing packages
uv build --package lye              # Build lye for distribution
uv publish --package lye            # Publish lye to PyPI

# Tool management
uv tool install ruff               # Install tools globally
uv tool run ruff check             # Run without installing
```

### Understanding the Workspace Structure

```
slide/                    # Workspace root
├── pyproject.toml       # Workspace configuration
├── uv.lock             # Single lock file for all packages
├── .venv/              # Single virtual environment
└── packages/
    ├── tyler/          # Individual package
    │   └── pyproject.toml  # Package-specific dependencies
    ├── lye/
    │   └── pyproject.toml
    ├── narrator/
    │   └── pyproject.toml
    └── space-monkey/
        └── pyproject.toml
```

**Key Points:**
- ONE `uv.lock` file at the root (never in packages)
- ONE `.venv` at the root (never in packages)
- Each package has its own `pyproject.toml` with dependencies
- Packages can depend on each other and changes are immediate

### Common Development Workflows

```bash
# After cloning or pulling changes
uv sync --dev

# Making changes to lye that tyler depends on
cd packages/lye
# ... make code changes ...
cd ../tyler
uv run pytest  # Tests immediately see lye changes

# Adding a new feature that requires a dependency
uv add --package tyler httpx
uv run --package tyler python test_new_feature.py

# Before committing
uv lock  # Update lock file if dependencies changed
git add uv.lock packages/*/pyproject.toml

# Testing package installation
uv build --package tyler
uv pip install dist/*.whl --python /tmp/test-env
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