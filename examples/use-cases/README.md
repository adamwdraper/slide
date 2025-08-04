# Use Cases Examples

Real-world examples showing complete applications built with Slide.

## Examples

### 🔬 [Research Assistant](./research-assistant/)
Comprehensive research agent using all three packages.
- Uses Tyler for agent framework
- Uses Lye for web search, files, and analysis tools  
- Uses Narrator for persistent storage
- Supports different research depths
- Generates and saves reports

**Features:**
- Multi-depth research (quick, standard, comprehensive)
- Targeted research with specific questions
- Fact-checking capabilities  
- Report generation and export
- Research history tracking

**Run:** `uv run examples/use-cases/research-assistant/basic.py`

### 💬 [Slack Bot](./slack-bot/)
AI agent integrated with Slack using Space Monkey.
- Multiple bot personalities (research, assistant, support)
- Persistent conversation memory
- File and image handling
- Real-time responses

**Features:**
- Research-focused bot for information gathering
- General assistant for workplace help
- Support bot for customer service
- Configurable via environment variables

**Setup:** See [slack-bot/basic.py](./slack-bot/basic.py) for Slack app configuration

### 🤖 [Automation](./automation/) *(Coming Soon)*
Task automation workflows and scheduled agents.

## Getting Started

1. **Choose an example** based on your use case
2. **Install dependencies** for the specific example
3. **Set up environment variables** (API keys, tokens, etc.)
4. **Run the example** and explore the code

## Common Prerequisites

### From Project Root (Recommended)

```bash
# Sync workspace to install all packages in dev mode
uv sync --dev

# Environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."  # Alternative

# For Slack examples
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
```

### Standalone Installation

```bash
# Core packages
uv add slide-tyler slide-lye slide-narrator

# For Slack integration
uv add slide-space-monkey
```

## Customization

These examples are designed to be:
- **Modular** - Easy to extract specific features
- **Configurable** - Environment variables and parameters
- **Extensible** - Add your own tools and capabilities
- **Production-ready** - Error handling and logging included