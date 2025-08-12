# Tyler

<div align="center">
    <img src="docs/static/img/tyler-soap.png" alt="Tyler Logo" width="200" style="border-radius: 8px;"/>
</div>

### A development kit for manifesting AI agents with a complete lack of conventional limitations

Tyler is the core agent framework in the Slide ecosystem. It makes it easy to build effective AI agents in just a few lines of code, providing all the essential components needed for production-ready AI agents that can understand context, manage conversations, and effectively use tools.

### Key Features

- **Multimodal support**: Process and understand images, audio, PDFs, and more out of the box
- **Ready-to-use tools**: Comprehensive set of built-in tools via the Lye package, with easy integration of custom tools
- **MCP compatibility**: Seamless integration with [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) compatible servers and tools
- **Real-time streaming**: Build interactive applications with streaming responses from both the assistant and tools
- **Structured data model**: Built-in support for threads, messages, and attachments to maintain conversation context
- **Persistent storage**: Powered by Narrator - choose between in-memory, SQLite, or PostgreSQL storage
- **Advanced debugging**: Integration with [W&B Weave](https://weave-docs.wandb.ai/) for powerful tracing and debugging capabilities
- **Flexible model support**: Use any LLM provider supported by LiteLLM (100+ providers including OpenAI, Anthropic, etc.)

![Tyler Chat UI Demo](docs/static/img/tyler_chat_UI_demo_short.gif)

---

<div style="display: flex; align-items: center; gap: 20px;">
    <span style="font-size: 1em;">Sponsored by</span>
    <a href="https://weave-docs.wandb.ai/"><img src="docs/static/img/weave_logo.png" alt="Weights & Biases Logo" height="40"/></a>
</div>

---

### For detailed documentation and guides, visit our [Docs](https://adamwdraper.github.io/tyler/).

While Tyler can be used as a library, it comes with two interactive interfaces:
1. A web-based chat interface available as a separate repository at [tyler-chat](https://github.com/adamwdraper/tyler-chat)
2. A built-in command-line interface (CLI) accessible via the `tyler-chat` command after installation. See the [Tyler chat CLI](https://adamwdraper.github.io/tyler/apps/tyler-chat-cli) documentation for details.


&nbsp;

![Workflow Status](https://github.com/adamwdraper/tyler/actions/workflows/pytest.yml/badge.svg)
[![PyPI version](https://img.shields.io/pypi/v/tyler-agent.svg?style=social)](https://pypi.org/project/tyler-agent/)


## Overview

### Core Components

### Agent

The central component that:
- Manages conversations through threads
- Processes messages using LLMs (GPT-4.1 by default)
- Executes tools when needed
- Maintains conversation state
- Supports streaming responses
- Handles file attachments and processing
- Integrates with Weave for monitoring

### Thread

Manages conversations and maintains:
- Message history with proper sequencing
- System prompts
- Conversation metadata and analytics
- Source tracking (e.g., Slack, web)
- Token usage statistics
- Performance metrics

### Message

Basic units of conversation containing:
- Content (text or multimodal)
- Role (user, assistant, system, tool)
- Sequence number for ordering
- Attachments (files with automatic processing)
- Metrics (token usage, timing, model info)
- Source information
- Custom attributes

### Attachment

Handles files in conversations:
- Support for binary and base64 encoded content
- Automatic storage management
- Content processing and extraction
- Status tracking (pending, stored, failed)
- URL generation for stored files
- Secure backend storage integration

### Tools

Tyler's tools are provided by the `slide-lye` package. Extend agent capabilities with:
- Web browsing and downloads (WEB_TOOLS)
- Slack integration (SLACK_TOOLS)
- Notion integration (NOTION_TOOLS)
- Image processing (IMAGE_TOOLS)
- Audio processing (AUDIO_TOOLS)
- File operations (FILES_TOOLS)
- Shell commands (COMMAND_LINE_TOOLS)
- Browser automation (BROWSER_TOOLS)

### MCP

Integrates with the Model Context Protocol for:
- Seamless connection to MCP-compatible servers
- Automatic tool discovery from MCP servers
- Support for multiple transport protocols (WebSocket, SSE, STDIO)
- Server lifecycle management
- Dynamic tool invocation
- Integration with any MCP-compatible tool ecosystem

### Storage

Storage is handled by the Narrator package, providing:
- Thread Storage:
  - Memory Store: Fast, in-memory storage for development
  - Database Store: PostgreSQL/SQLite for production
- File Storage:
  - Local filesystem with sharded organization
  - Automatic content processing and extraction
  - Configurable size limits and validation

## User Guide

### Prerequisites

- Python 3.12+
- uv (modern Python package manager) - recommended
- System dependencies for PDF and image processing

### Installation

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install required libraries for PDF and image processing
# macOS:
brew install libmagic poppler

# Ubuntu/Debian:
sudo apt-get install libmagic1 poppler-utils

# Using uv (recommended)
uv add slide-tyler

# Using pip (fallback)
pip install slide-tyler
```

# For development installation:
```bash
uv add slide-tyler --dev
```

When you install Tyler, all required runtime dependencies will be installed automatically, including:
- LLM support (LiteLLM, OpenAI)
- Storage components (Narrator)
- Tools package (Lye)
- Monitoring and metrics (Weave, Wandb)
- File processing (PDF, images)
- All core utilities

### Basic Setup

Create a `.env` file in your project directory with the following configuration:
```bash
# Database Configuration (used by Narrator)
# For local development with Docker: cd packages/narrator && docker-compose up -d
# Then use: NARRATOR_DATABASE_URL=postgresql+asyncpg://narrator:narrator_dev@localhost:5432/narrator
NARRATOR_DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
# Or for SQLite:
# NARRATOR_DATABASE_URL=sqlite+aiosqlite:///path/to/database.db

# Optional Database Settings
NARRATOR_DB_ECHO=false
NARRATOR_DB_POOL_SIZE=5
NARRATOR_DB_MAX_OVERFLOW=10
NARRATOR_DB_POOL_TIMEOUT=30
NARRATOR_DB_POOL_RECYCLE=300

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Logging Configuration
WANDB_API_KEY=your-wandb-api-key

# Optional Integrations (for Lye tools)
NOTION_TOKEN=your-notion-token
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret

# File storage configuration
NARRATOR_FILE_STORAGE_PATH=/path/to/files  # Optional, defaults to ~/.narrator/files
NARRATOR_MAX_FILE_SIZE=52428800  # 50MB default
NARRATOR_MAX_STORAGE_SIZE=5368709120  # 5GB default

# Other settings
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

Only the `OPENAI_API_KEY` (or whatever LLM provider you're using) is required for core functionality. Other environment variables are required only when using specific features:
- For Weave monitoring: `WANDB_API_KEY` is required (You will want to use this for monitoring and debugging) [https://weave-docs.wandb.ai/](Weave Docs)
- For Slack integration: `SLACK_BOT_TOKEN` is required  
- For Notion integration: `NOTION_TOKEN` is required
- For database storage:
  - By default uses in-memory storage (perfect for scripts and testing)
  - For PostgreSQL or SQLite: Set `NARRATOR_DATABASE_URL` with appropriate connection string
- For file storage: Defaults will be used if not specified

For more details about each setting, see the [Environment Variables](#environment-variables) section.

### LLM Provider Support

Tyler uses LiteLLM under the hood, which means you can use any of the 100+ supported LLM providers by simply configuring the appropriate environment variables. Some popular options include:

```bash
# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# Azure OpenAI
AZURE_API_KEY=your-azure-api-key
AZURE_API_BASE=your-azure-endpoint
AZURE_API_VERSION=2023-07-01-preview

# Google VertexAI
VERTEX_PROJECT=your-project-id
VERTEX_LOCATION=your-location

# AWS Bedrock
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION_NAME=your-region
```

When initializing an Agent, you can specify any supported model using the standard model identifier:

```python
# OpenAI
agent = Agent(model_name="gpt-4")

# Anthropic
agent = Agent(model_name="claude-2")

# Azure OpenAI
agent = Agent(model_name="azure/your-deployment-name")

# Google VertexAI
agent = Agent(model_name="chat-bison")

# AWS Bedrock
agent = Agent(model_name="anthropic.claude-v2")
```

For a complete list of supported providers and models, see the [LiteLLM documentation](https://docs.litellm.ai/).

### Quick Start

This example uses in-memory storage which is perfect for scripts and testing. 

```python
from dotenv import load_dotenv 
from tyler import Agent, Thread, Message
import asyncio
import os

# Load environment variables from .env file
load_dotenv()

# Initialize the agent (uses in-memory storage by default)
agent = Agent(
    model_name="gpt-4.1",
    purpose="To help with general questions"
)

async def main():
    # Create a new thread
    thread = Thread()

    # Add a user message
    message = Message(
        role="user",
        content="What can you help me with?"
    )
    thread.add_message(message)

    # Process the thread
    result = await agent.go(thread)

    # Print the assistant's response
    print(f"Assistant: {result.content}")
    
    # Access additional information if needed
    print(f"Execution time: {result.execution.duration_ms}ms")
    print(f"Tokens used: {result.execution.total_tokens}")

if __name__ == "__main__":
    asyncio.run(main())
```

See the complete examples in the documentation.

## Running Examples and Tests

Tyler comes with a variety of examples in the `examples/` directory that demonstrate different features and capabilities. These examples can also be run as integration tests to ensure everything is working correctly.

### Running Examples as Tests

The examples are integrated into the test suite with special markers to allow running them separately from unit tests:

```bash
# Run only the example tests
pytest -m examples

# Run only unit tests (excluding examples)
pytest -k "not examples"

# Run all tests (unit tests and examples)
pytest
```

This separation is particularly useful during development, allowing you to run the faster unit tests while making changes, and run the full test suite including examples before committing.

### Example Categories

The examples directory includes demonstrations of:

- Basic agent conversations
- Using built-in and custom tools
- Working with file attachments
- Image and audio processing
- Streaming responses
- MCP (Model Context Protocol) integration

Each example is a standalone Python script that can be run directly or as part of the test suite.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
