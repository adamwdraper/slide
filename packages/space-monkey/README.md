# Space Monkey

Scaffolding and template generation for building agentic Slack bots with the Slide AI framework.

## Overview

Space Monkey is a developer productivity tool that provides code generation and scaffolding specifically for **Slack bot agents**. It helps developers quickly create new Slack bot agents with consistent patterns, proper message handling, and integration with Slack's API, reducing setup time from hours to minutes.

## Key Features

- **Slack Bot Agent Scaffolding**: Generate complete Slack bot agent structures with proper patterns
- **Message Classification**: Templates for agents that classify Slack messages and determine response types
- **Multi-Agent Orchestration**: Support for main agents with specialized sub-agents
- **Slack Integration Patterns**: Built-in support for @mentions, DMs, threads, and emoji reactions
- **Template System**: Extensible template system for customizing generated Slack bot code
- **CLI Tools**: Command-line interface for rapid Slack bot agent creation
- **Best Practices**: Embeds proven patterns from production Slack bot implementations

## Installation

```bash
pip install slide-space-monkey
```

## CLI Usage

Space Monkey provides a command-line interface for generating Slack bot agent scaffolding:

### Generate a Basic Slack Bot Agent

```bash
space-monkey generate agent hr-bot --description "answering HR-related questions for employees"
```

### Generate a Slack Bot Agent with Tools and Slack Integration

```bash
space-monkey generate agent hr-assistant \
  --description "providing HR support via Slack" \
  --tools "notion:notion-search" \
  --tools "slack:send-message" \
  --bot-user-id \
  --citations
```

### Generate a Multi-Agent Slack Bot System

```bash
# Main orchestrator agent
space-monkey generate agent perci \
  --description "coordinating HR responses in Slack" \
  --tools "notion:notion-search" \
  --sub-agents "notion-page-reader" \
  --sub-agents "message-classifier" \
  --bot-user-id \
  --citations

# Message classification agent
space-monkey generate agent message-classifier \
  --description "classifying Slack messages to determine response types" \
  --bot-user-id

# Specialized sub-agent
space-monkey generate agent notion-page-reader \
  --description "reading and analyzing Notion pages for HR information"
```

### CLI Options

- `--description, -d`: Agent description for the purpose prompt (focus on Slack interactions)
- `--tools, -t`: Tools to include like `notion:notion-search`, `slack:send-message` (can be used multiple times)
- `--sub-agents, -s`: Sub-agents for specialized tasks like `message-classifier`, `notion-page-reader` (can be used multiple times)
- `--citations`: Require source citations in responses (important for information bots)
- `--bot-user-id`: Include Slack bot user ID handling for @mentions (essential for Slack bots)
- `--guidelines, -g`: Specific guidelines for the agent (e.g., "Use 'people team' instead of 'HR'")
- `--output-dir, -o`: Custom output directory (defaults to `./agents/AGENT_NAME`)

## Programmatic Usage

You can also use Space Monkey programmatically to generate Slack bot agents:

```python
from space_monkey import TemplateManager

# Initialize template manager
template_manager = TemplateManager()

# Generate Slack bot agent files
files = template_manager.generate_agent(
    agent_name="HRBot",
    description="answering employee HR questions via Slack",
    tools=["notion:notion-search", "slack:send-message"],
    citations_required=True,
    bot_user_id=True  # Essential for Slack bot @mention handling
)

# Files is a dict with 'agent.py' and 'purpose.py' keys
print(files['agent.py'])
print(files['purpose.py'])
```

## Generated Structure

Space Monkey generates Slack bot agents with this structure:

```
agents/
├── my_agent/
│   ├── agent.py      # Slack bot agent initialization with proper patterns
│   └── purpose.py    # Slack-optimized purpose prompt with structured sections
```

### Agent.py Pattern (Slack Bot Optimized)

- Proper imports and logging setup
- `@weave.op()` decorator for observability and tracing
- Standard initialization function signature with `bot_user_id` parameter
- Configurable tools and sub-agents for Slack bot orchestration
- Thread and file store integration for conversation persistence
- Consistent error handling and logging

### Purpose.py Pattern (Slack Bot Focused)

- Structured prompt with Slack-specific sections:
  - **Role and Context**: Includes Slack User ID for @mention handling
  - **Tool-specific notes**: Guidance for Slack integrations (Notion, etc.)
  - **Core workflow**: Message processing and response patterns
  - **Response guidelines**: Slack formatting and communication style
  - **Citations**: Source attribution for information responses

## Examples

### HR Slack Bot (Like Perci)

```bash
space-monkey generate agent hr-assistant \
  --description "answering employee HR questions in Slack channels and DMs" \
  --tools "notion:notion-search" \
  --bot-user-id \
  --citations \
  --guidelines "Use 'people team' instead of 'HR' in responses"
```

### Multi-Agent Slack Bot System

```bash
# Main HR agent with message classification
space-monkey generate agent perci \
  --description "providing HR support and coordinating responses in Slack" \
  --tools "notion:notion-search" \
  --sub-agents "notion-page-reader" \
  --sub-agents "message-classifier" \
  --bot-user-id \
  --citations

# Message classifier for determining response types
space-monkey generate agent message-classifier \
  --description "classifying Slack messages to determine if Perci should respond with text, emoji, or ignore" \
  --bot-user-id \
  --guidelines "Return JSON with response_type, suggested_emoji, confidence, and reasoning"

# Specialized Notion reader sub-agent  
space-monkey generate agent notion-page-reader \
  --description "reading and analyzing Notion pages to extract HR policy information"
```

### Customer Support Slack Bot

```bash
space-monkey generate agent support-bot \
  --description "providing customer support through Slack" \
  --tools "notion:notion-search" \
  --tools "zendesk:create-ticket" \
  --bot-user-id \
  --citations \
  --guidelines "Escalate complex issues to human support agents"
```

## CLI Commands

### Status

```bash
space-monkey status
```

Shows Space Monkey version and status.

### Generate

```bash
space-monkey generate agent NAME [OPTIONS]
```

Generates a new agent with the specified configuration.

## Slack Bot Architecture

Space Monkey generates agents that fit into this proven Slack bot architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Slack Events    │───▶│ Message          │───▶│ Message         │
│ (Messages,      │    │ Processing       │    │ Classification  │
│ @mentions, DMs) │    │ (Thread Mgmt)    │    │ (Agent)         │
└─────────────────┘    └──────────────────┘    └─────────┬───────┘
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              │                           │                           │
                              ▼                           ▼                           ▼
                    ┌─────────────┐            ┌─────────────┐            ┌─────────────┐
                    │ Ignore      │            │ Emoji       │            │ Full        │
                    │ (No Action) │            │ Reaction    │            │ Response    │
                    └─────────────┘            └─────────────┘            └─────┬───────┘
                                                                                │
                                                                                ▼
                                                                    ┌─────────────────┐
                                                                    │ Main Agent      │
                                                                    │ (with sub-      │◀─┐
                                                                    │ agents)         │  │
                                                                    └─────┬───────────┘  │
                                                                          │              │
                                                                          ▼              │
                                                                ┌─────────────────┐      │
                                                                │ Response        │      │
                                                                │ Formatting &    │      │
                                                                │ Slack Delivery  │      │
                                                                └─────────────────┘      │
                                                                                         │
                                                    ┌────────────────────────────────────┘
                                                    │
                                                    ▼
                                            ┌─────────────────┐
                                            │ Sub-Agents      │
                                            │ (Notion reader, │
                                            │ other tools)    │
                                            └─────────────────┘
```

## Development

This package is part of the Slide AI framework workspace. For development:

```bash
# Install in development mode
uv sync --dev

# Run tests
cd packages/space-monkey
uv run pytest tests/

# Test the CLI with a Slack bot agent
uv run space-monkey generate agent test-slack-bot \
  --description "testing Slack bot scaffolding" \
  --bot-user-id \
  --tools "notion:notion-search"
```

## License

MIT License - see LICENSE file for details.
