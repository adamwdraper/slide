# Slide 🎯

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
from tyler import Agent

# Create an AI agent
agent = Agent(
    name="MyAgent",
    instructions="You are a helpful assistant"
)

# Chat with the agent
response = agent.chat("Hello, how are you?")
print(response)
```

### Using The Narrator

```python
from narrator import ThreadStore

# Create a thread store for conversation management
store = ThreadStore()

# Save and retrieve conversations
thread = store.create_thread("user123")
thread.add_message("Hello!", role="user")
```

### Using Both Together

```python
from tyler import Agent
from narrator import ThreadStore

# Create persistent storage
store = ThreadStore()

# Create an agent with conversation history
agent = Agent(
    name="PersistentAgent",
    thread_store=store
)

# Chat with persistent memory
response = agent.chat("Remember this: my name is John")
response = agent.chat("What's my name?")  # Will remember "John"
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