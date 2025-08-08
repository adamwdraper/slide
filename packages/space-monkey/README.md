# Space Monkey - Tyler Slack Agent

A simple, powerful way to deploy Tyler AI agents as Slack agents. Space Monkey handles all the complexity of Slack integration while you focus on building your agent's capabilities.

## Overview

Space Monkey bridges the gap between Tyler agents and Slack, providing:
- Seamless integration of Tyler agents into Slack workspaces
- Intelligent message classification and routing
- Persistent conversation management using Narrator
- Built-in file handling and health monitoring
- Production-ready deployment with Docker support

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
# Using uv (recommended)
uv add slide-space-monkey

# Using pip (fallback)
pip install slide-space-monkey
```

### 2. Set Up Environment Variables

Copy the example environment file and add your tokens:

```bash
cp env.example .env
# Then edit .env with your actual tokens
```

Required variables:

```bash
# Required: Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Required: LLM Configuration (at least one)
OPENAI_API_KEY=sk-your-openai-api-key      # For GPT models
# ANTHROPIC_API_KEY=sk-ant-your-key         # For Claude models
# GEMINI_API_KEY=your-gemini-api-key        # For Gemini models
# XAI_API_KEY=xai-your-grok-api-key         # For Grok models

# Optional: Weave Monitoring
WANDB_API_KEY=your-wandb-key
WANDB_PROJECT=your-project-name

# Optional: Health Check
HEALTH_CHECK_URL=http://healthcheck:8000/ping-receiver
HEALTH_PING_INTERVAL_SECONDS=120  # How often to ping (defaults to 120)

# Optional: Environment & Logging
ENV=development  # Environment name for Weave tracing
LOG_LEVEL=INFO   # Log level (DEBUG, INFO, WARNING, ERROR)

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

### 3. Create Your Agent

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

That's it! Your Tyler agent is now running as a Slack agent.

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
    weave_project="my-slack-agent"
)

# Start with custom host/port
await app.start(host="0.0.0.0", port=8080)
```

### Message Classification Configuration

Space Monkey includes intelligent message routing that determines when your agent should respond. You can customize what topics your agent should respond to:

```python
# Default configuration (responds to general questions and requests)
app = SlackApp(
    agent=agent,
    thread_store=thread_store,
    file_store=file_store
)

# Custom topic configuration
app = SlackApp(
    agent=agent,
    thread_store=thread_store,
    file_store=file_store,
    response_topics="technical support, troubleshooting, or product questions"
)

# HR/People team configuration
app = SlackApp(
    agent=agent,
    thread_store=thread_store,
    file_store=file_store,
    response_topics="people topics, HR, company culture, recognition, or employee experience"
)
```

## How It Works

Space Monkey acts as the bridge between Slack and Tyler:

1. **SlackApp** - Manages the Slack connection and message handling
2. **Tyler Agent** - Provides the AI capabilities and tool usage
3. **Narrator Storage** - Persists conversations and files
4. **Message Classifier** - Intelligently routes messages based on context

The integration is designed to be invisible to users - they simply interact with a helpful AI agent in their Slack workspace.

## Message Routing

Tyler Slack Agent automatically handles intelligent message routing:

1. **Direct Messages**: All DM messages are processed by your agent
2. **@Mentions**: Messages that mention the agent are always processed
3. **Channel Messages**: Automatically classified to determine if they need a response
4. **Thread Replies**: Continues conversations in threads appropriately
5. **Reactions**: Simple acknowledgments get emoji reactions instead of text responses

This happens automatically - you just define your agent's behavior and Space Monkey handles the rest.

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

Space Monkey includes Docker support for easy deployment. A production-ready Dockerfile and docker-compose.yml are included in the package.

#### Quick Start with Docker

```bash
# Build the image
docker build -t my-slack-agent .

# Run with environment variables
docker run -d \
  --name slack-agent \
  -p 8000:8000 \
  -e SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN \
  -e SLACK_APP_TOKEN=$SLACK_APP_TOKEN \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  my-slack-agent
```

#### Using Docker Compose

```bash
# Copy environment template
cp env.example .env
# Edit .env with your credentials

# Start the agent
docker-compose up -d

# View logs
docker-compose logs -f slack-agent

# Stop
docker-compose down
```

#### Production Deployment

The included Dockerfile follows best practices:
- Non-root user for security
- Health checks for monitoring
- Proper signal handling for graceful shutdown
- Multi-stage build for smaller images
- Layer caching for faster builds

### Environment Configuration

```bash
# Production .env
SLACK_BOT_TOKEN=xoxb-prod-token
SLACK_APP_TOKEN=xapp-prod-token

# LLM Configuration (choose one or more)
OPENAI_API_KEY=sk-prod-openai-key
# ANTHROPIC_API_KEY=sk-ant-prod-key
# GEMINI_API_KEY=prod-gemini-api-key
# XAI_API_KEY=xai-prod-grok-key

# Database
NARRATOR_DB_TYPE=postgresql
NARRATOR_DB_USER=tyler_prod
NARRATOR_DB_PASSWORD=secure_password
NARRATOR_DB_HOST=db.example.com
NARRATOR_DB_PORT=5432
NARRATOR_DB_NAME=tyler_prod

# File Storage
NARRATOR_FILE_STORAGE_PATH=/data/files

# Monitoring
WANDB_API_KEY=prod-wandb-key
WANDB_PROJECT=slack-agent-prod
HEALTH_CHECK_URL=http://healthcheck:8000/ping-receiver
HEALTH_PING_INTERVAL_SECONDS=120

# Environment & Logging
ENV=production
LOG_LEVEL=INFO
```

### Health Monitoring

The agent includes built-in health check endpoints and optional external health monitoring:

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
        weave_project: Optional[str] = None,
        response_topics: Optional[str] = None
    ):
        """
        Initialize Slack app with agent and stores.
        
        Args:
            agent: The main Tyler agent to handle conversations
            thread_store: ThreadStore instance for conversation persistence  
            file_store: FileStore instance for file handling
            health_check_url: Optional URL for health check pings
            weave_project: Optional Weave project name for tracing
            response_topics: Simple sentence describing what topics the agent should respond to
        """
        
    async def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8000
    ) -> None:
        """Start the Slack agent app."""
```

### Classifier Configuration

```python
def format_classifier_prompt(
    agent_name: str = "Assistant",
    bot_user_id: str = "",
    response_topics: str = "general questions, requests for help, or inquiries directed at the assistant"
) -> str:
    """Format the classifier prompt with custom configuration."""
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

### Simple HR Agent

```python
import asyncio
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

async def main():
    # Simple setup for an HR assistant with HR-specific topic classification
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
        file_store=file_store,
        response_topics="people topics, HR, company culture, recognition, or employee experience"
    )
    
    await app.start()

asyncio.run(main())
```

### Technical Support Agent

```python
import asyncio
from space_monkey import SlackApp, Agent, ThreadStore, FileStore

async def main():
    # Technical support agent with custom topic classification
    thread_store = await ThreadStore.create()
    file_store = await FileStore.create()
    
    agent = Agent(
        name="TechSupport",
        model_name="gpt-4.1",
        purpose="To help users with technical support and troubleshooting",
        tools=["web", "files"],
        temperature=0.3
    )
    
    app = SlackApp(
        agent=agent,
        thread_store=thread_store,
        file_store=file_store,
        response_topics="technical issues, bugs, troubleshooting, or product support"
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
        weave_project="support-agent"
    )
    
    await app.start(port=8080)

asyncio.run(main())
```

## Use Cases

- **HR/People Bots**: Answer employee questions using Notion as a knowledge base
- **Technical Support**: Help users troubleshoot issues with web search and file analysis
- **Team Assistants**: Automate routine tasks and answer common questions
- **Custom Workflows**: Build any conversational AI use case with Tyler's full capabilities

## Contributing

Space Monkey is part of the Slide ecosystem. See the main repository for contribution guidelines.

## License

MIT License - see LICENSE file for details. 