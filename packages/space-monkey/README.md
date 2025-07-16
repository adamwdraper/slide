# Space Monkey - Tyler Slack Bot

A simple, powerful way to deploy Tyler AI agents as Slack bots with just a few lines of code.

## Overview

Space Monkey provides a clean, class-based API for creating and deploying Tyler agents as Slack bots. It handles all the complexity of Slack integration, message routing, thread management, and storage while exposing a simple interface for agent configuration.

## Features

- **Simple API**: Just import `SlackApp`, `Agent`, and stores from one package
- **Intelligent Message Routing**: Automatically classifies messages and routes appropriately
- **Thread Management**: Persistent conversation threads with configurable storage backends
- **File Handling**: Built-in support for file attachments and processing
- **Health Monitoring**: Optional health check endpoints for production deployments
- **Weave Integration**: Built-in tracing and monitoring support

## Quick Start

### 1. Install the Package

```bash
pip install slide-space-monkey
```

### 2. Set Up Environment Variables

Create a `.env` file:

```bash
# Required: Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Optional: Weave Monitoring
WANDB_API_KEY=your-wandb-key
WANDB_PROJECT=your-project-name

# Optional: Health Check
HEALTH_CHECK_URL=http://healthcheck:8000/ping-receiver

# Optional: Database (defaults to in-memory)
NARRATOR_DB_TYPE=postgresql
NARRATOR_DB_USER=tyler
NARRATOR_DB_PASSWORD=password
NARRATOR_DB_HOST=localhost
NARRATOR_DB_PORT=5432
NARRATOR_DB_NAME=tyler

# Optional: File Storage (defaults to ~/.tyler/files)
NARRATOR_FILE_STORAGE_PATH=/data/files
```

### 3. Create Your Bot

```python
import asyncio
from space_monkey import SlackApp, ThreadStore, FileStore, Agent

async def main():
    # Create stores
    thread_store = await ThreadStore.create()  # In-memory by default
    file_store = await FileStore.create()      # Default file storage
    
    # Create your agent
    agent = Agent(
        name="SlackBot",
        model_name="gpt-4.1", 
        purpose="To be a helpful assistant in Slack",
        tools=["web", "files"],
        temperature=0.7
    )
    
    # Start the Slack app
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store
    )
    
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
```

That's it! Your Tyler agent is now running as a Slack bot.

## Advanced Configuration

### Database Storage

For production deployments, use a persistent database:

```python
from space_monkey import ThreadStore, FileStore

# PostgreSQL
thread_store = await ThreadStore.create(
    "postgresql+asyncpg://user:pass@localhost/db"
)

# SQLite
thread_store = await ThreadStore.create(
    "sqlite+aiosqlite:///path/to/db.sqlite"
)

# Custom file storage
file_store = await FileStore.create(
    base_path="/data/files",
    max_file_size=100 * 1024 * 1024,  # 100MB
    max_storage_size=10 * 1024 * 1024 * 1024  # 10GB
)
```

### Custom Agent Configuration

```python
# Create a custom agent with specific tools and settings
agent = Agent(
    name="CustomBot",
    model_name="gpt-4.1",
    purpose="Your custom agent purpose",
    tools=["notion:notion-search", "web", "files"],
    temperature=0.7,
    version="1.0.0"
)

# Tyler Agent with custom settings
agent = Agent(
    name="CustomBot", 
    model_name="gpt-4.1",
    purpose="Your custom agent purpose",
    tools=["notion:notion-search"],
    temperature=0.5
)
```

### App Configuration

```python
app = SlackApp(
    agent=agent,
    thread_store=thread_store,
    file_store=file_store,
    health_check_url="http://healthcheck:8000/ping-receiver",
    weave_project="my-slack-bot"
)

# Start with custom host/port
await app.start(host="0.0.0.0", port=8080)
```

## Agent Configuration

Space Monkey uses Tyler Agent directly, giving you full access to all Tyler's capabilities:

```python
agent = Agent(
    name="MyBot",             # Agent name
    model_name="gpt-4.1",     # Model to use
    purpose="Your agent's purpose and instructions",
    tools=["web", "files"],   # Available tools
    temperature=0.7,          # Model temperature
    version="1.0.0"           # Agent version
)
```

You can configure agents for any use case by adjusting the purpose and tools:
- HR/People assistance with Notion integration
- Customer support with web search
- Technical assistance with file processing
- And any other conversational AI use case

## Message Routing

Tyler Slack Bot automatically handles intelligent message routing:

1. **Direct Messages**: All DM messages are processed by your agent
2. **@Mentions**: Messages that mention the bot are always processed
3. **Channel Messages**: Automatically classified to determine if they need a response
4. **Thread Replies**: Continues conversations in threads appropriately
5. **Reactions**: Simple acknowledgments get emoji reactions instead of text responses

This happens automatically - you just define your agent's behavior and the bot handles the rest.

## Storage Backends

### Thread Storage

- **In-Memory**: Fast, ephemeral (default for development)
- **SQLite**: Local persistence (good for single-instance deployments)
- **PostgreSQL**: Production-ready with full ACID compliance

### File Storage

- **Local File System**: Sharded directory structure for efficient file organization
- **Configurable Limits**: Set maximum file sizes and total storage limits
- **MIME Type Validation**: Automatic file type detection and validation

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
```

### Environment Configuration

```bash
# Production .env
SLACK_BOT_TOKEN=xoxb-prod-token
SLACK_APP_TOKEN=xapp-prod-token

# Database
TYLER_DB_TYPE=postgresql
TYLER_DB_USER=tyler_prod
TYLER_DB_PASSWORD=secure_password
TYLER_DB_HOST=db.example.com
TYLER_DB_PORT=5432
TYLER_DB_NAME=tyler_prod

# File Storage
TYLER_FILE_STORAGE_PATH=/data/files

# Monitoring
WANDB_API_KEY=prod-key
WANDB_PROJECT=slack-bot-prod
HEALTH_CHECK_URL=http://healthcheck:8000/ping-receiver
```

### Health Monitoring

The bot includes built-in health check endpoints and optional external health monitoring:

```python
app = SlackApp(
    agent=agent,
    thread_store=thread_store,
    file_store=file_store,
    health_check_url="http://healthcheck:8000/ping-receiver"
)
```

## API Reference

### SlackApp

```python
class SlackApp:
    def __init__(
        self,
        agent: Agent,
        thread_store: ThreadStore,
        file_store: FileStore,
        health_check_url: Optional[str] = None,
        weave_project: Optional[str] = None
    ):
        """Initialize Slack app with agent and stores."""
        
    async def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8000
    ) -> None:
        """Start the Slack bot app."""
```

### Agent

```python
class Agent:
    def __init__(
        self,
        name: str,
        model_name: str,
        purpose: str,
        tools: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        version: str = "1.0.0",
        thread_store: Optional[ThreadStore] = None,
        file_store: Optional[FileStore] = None
    ):
        """Create a Tyler agent with full configuration options."""
```

### Stores

```python
# ThreadStore
thread_store = await ThreadStore.create()  # In-memory
thread_store = await ThreadStore.create(database_url)  # Database

# FileStore  
file_store = await FileStore.create()  # Default settings
file_store = await FileStore.create(
    base_path="/path/to/files",
    max_file_size=100 * 1024 * 1024,
    max_storage_size=10 * 1024 * 1024 * 1024
)
```

## Examples

### Simple HR Bot

```python
import asyncio
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

async def main():
    # Simple setup for an HR assistant
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    
    agent = Agent(
        name="HRBot",
        model_name="gpt-4.1",
        purpose="To help with HR and people team questions",
        tools=["notion:notion-search"],
        temperature=0.7
    )
    
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store
    )
    
    await app.start()

asyncio.run(main())
```

### Custom Agent with Database

```python
import asyncio
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

async def main():
    # Production setup with PostgreSQL
    thread_store = await ThreadStore.create(
        "postgresql+asyncpg://user:pass@localhost/db"
    )
    file_store = await FileStore.create(base_path="/data/files")
    
    # Custom agent
    agent = Agent(
        name="SupportBot",
        model_name="gpt-4.1",
        purpose="Help users with technical support questions",
        tools=["web", "files"],
        temperature=0.3
    )
    
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        weave_project="support-bot"
    )
    
    await app.start(port=8080)

asyncio.run(main())
```

## Contributing

Tyler Slack Bot is part of the Tyler ecosystem. See the main Tyler documentation for information about contributing to the project.

## License

MIT License - see LICENSE file for details. 