# Space Monkey 🚀🐒

A powerful, extensible Slack bot framework built on the slide-narrator storage system.

Space Monkey makes it easy to build production-ready Slack bots with AI agent capabilities, robust storage, and a clean architecture that scales from simple echo bots to complex multi-agent systems.

## Features

- **Agent-Based Architecture**: Build bots using composable agents with clear responsibilities
- **Built-in Storage**: Powered by slide-narrator for persistent thread and file storage
- **Production Ready**: FastAPI server, health checks, proper logging, and error handling
- **Extensible**: Middleware system, custom agents, and plugin architecture
- **Easy to Use**: Simple API for first-time developers, powerful for advanced use cases

## Quick Start

### 1. Installation

```bash
pip install slide-space-monkey
```

### 2. Environment Setup

Create a `.env` file with your Slack credentials:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
NARRATOR_DATABASE_URL=postgresql://user:pass@localhost/dbname  # Optional
```

### 3. Create Your First Bot

```python
# bot.py
from space_monkey import SpaceMonkey, SlackAgent
from narrator import Thread, Message

class HelloAgent(SlackAgent):
    def should_handle(self, event, thread):
        return "hello" in event.get("text", "").lower()
    
    async def process_message(self, thread, event):
        return "👋 Hello! I'm Space Monkey!"

# Create and run bot
bot = SpaceMonkey.from_env()
bot.add_agent("hello", HelloAgent)
bot.run()
```

### 4. Run Your Bot

```bash
python bot.py
```

## Architecture Overview

Space Monkey uses an agent-based architecture where each agent handles specific types of messages:

```
┌─────────────────┐
│   Slack Event   │
└─────────┬───────┘
          │
┌─────────▼───────┐
│   Event Router  │
└─────────┬───────┘
          │
┌─────────▼───────┐
│   Classifiers   │ (Optional: determine response type)
└─────────┬───────┘
          │
┌─────────▼───────┐
│  Regular Agents │ (Process and respond)
└─────────┬───────┘
          │
┌─────────▼───────┐
│ Slack Response  │
└─────────────────┘
```

## Agent Types

### Basic Agent

Handle simple message patterns:

```python
class EchoAgent(SlackAgent):
    def should_handle(self, event, thread):
        return event.get("text", "").startswith("echo:")
    
    async def process_message(self, thread, event):
        text = event.get("text", "")[5:]  # Remove "echo:"
        return f"🔊 {text}"
```

### Classifier Agent

Determine how the bot should respond (ignore, emoji, or full response):

```python
class MessageClassifier(ClassifierAgent):
    async def classify_message(self, thread, event):
        text = event.get("text", "")
        
        if "spam" in text.lower():
            return {
                "response_type": "ignore",
                "reasoning": "Message appears to be spam"
            }
        
        if "thanks" in text.lower():
            return {
                "response_type": "emoji_reaction",
                "suggested_emoji": "thumbsup",
                "reasoning": "Simple thanks message"
            }
        
        return {
            "response_type": "full_response",
            "reasoning": "Message requires detailed response"
        }
```

### AI Agent

Build agents that use AI models:

```python
class AIAssistant(SlackAgent):
    def should_handle(self, event, thread):
        # Handle all messages not handled by other agents
        return True
    
    async def process_message(self, thread, event):
        # Your AI processing logic here
        # Access thread history, file attachments, etc.
        return "AI-generated response"
```

## Configuration

### Environment Variables

```env
# Required
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token

# Optional Database (defaults to in-memory)
NARRATOR_DATABASE_URL=postgresql://user:pass@localhost/dbname

# Optional File Storage
NARRATOR_FILE_STORAGE_PATH=/path/to/files
NARRATOR_MAX_FILE_SIZE=52428800  # 50MB
NARRATOR_MAX_STORAGE_SIZE=5368709120  # 5GB

# Optional Monitoring
WANDB_API_KEY=your-wandb-key
WANDB_PROJECT=your-project-name

# Optional Health Checks
HEALTH_CHECK_URL=http://healthcheck:8000/ping-receiver
HEALTH_PING_INTERVAL_SECONDS=120

# Server Configuration
HOST=0.0.0.0
PORT=8000
ENV=development
```

### Programmatic Configuration

```python
from space_monkey import SpaceMonkey, Config

config = Config(
    slack_bot_token="xoxb-...",
    slack_app_token="xapp-...",
    database_url="postgresql://...",
    environment="production"
)

bot = SpaceMonkey(config)
```

## Advanced Features

### Middleware

Add custom middleware for logging, rate limiting, etc.:

```python
async def logging_middleware(event):
    logger.info(f"Processing event: {event.get('type')}")
    return event

async def rate_limit_middleware(event):
    user_id = event.get("user")
    if is_rate_limited(user_id):
        return None  # Skip processing
    return event

bot.add_middleware(logging_middleware)
bot.add_middleware(rate_limit_middleware)
```

### Reaction Handling

Agents can respond to emoji reactions:

```python
class ReactionAgent(SlackAgent):
    async def on_reaction_added(self, event, thread):
        if event.get("reaction") == "thumbsup":
            # Do something when someone adds 👍
            pass
    
    async def on_reaction_removed(self, event, thread):
        # Handle reaction removal
        pass
```

### Thread and File Storage

Access conversation history and file attachments:

```python
class ContextAgent(SlackAgent):
    async def process_message(self, thread, event):
        # Access message history
        previous_messages = thread.messages[-5:]  # Last 5 messages
        
        # Access file attachments
        for message in thread.messages:
            for attachment in message.attachments:
                if attachment.mime_type.startswith("image/"):
                    # Process image attachment
                    pass
        
        # Save custom data
        thread.attributes["custom_data"] = "value"
        await self.thread_store.save(thread)
        
        return "Processed with context!"
```

## Examples

### Basic Bot

See `space_monkey/examples/basic_bot.py` for a complete example with echo, help, and greeting agents.

### AI Assistant Bot

```python
from space_monkey import SpaceMonkey, SlackAgent, ClassifierAgent

class SmartClassifier(ClassifierAgent):
    async def classify_message(self, thread, event):
        # Use AI to classify messages
        # Return appropriate response type
        pass

class AIAgent(SlackAgent):
    def should_handle(self, event, thread):
        return True  # Handle all messages
    
    async def process_message(self, thread, event):
        # Process with AI model
        # Return intelligent response
        pass

bot = SpaceMonkey.from_env()
bot.add_agent("classifier", SmartClassifier)
bot.add_agent("ai", AIAgent)
bot.run()
```

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest tests/
```

### Project Structure

```
space-monkey/
├── space_monkey/
│   ├── core/           # Core bot infrastructure
│   ├── agents/         # Agent system
│   ├── utils/          # Utilities
│   ├── templates/      # Bot templates
│   └── examples/       # Example bots
├── tests/
└── README.md
```

## Migration from Tyler

If you're migrating from the original Tyler framework:

1. **Update imports**: `from tyler import` → `from space_monkey import`
2. **Update agent interface**: Inherit from `SlackAgent` instead of custom base
3. **Update configuration**: Use `Config` class or environment variables
4. **Update storage**: Storage is now handled automatically by the framework

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: [Full API Reference](https://github.com/adamwdraper/slide)
- **Issues**: [GitHub Issues](https://github.com/adamwdraper/slide/issues)
- **Discussions**: [GitHub Discussions](https://github.com/adamwdraper/slide/discussions)

---

Built with ❤️ by the Space Monkey team 🚀🐒 