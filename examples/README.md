# Slide Examples

This directory contains examples demonstrating how to use Slide's packages together to build complete AI applications.

## Structure

### 🚀 Getting Started
Simple examples to get you up and running quickly:
- **quickstart.py** - Basic agent with web search and file tools
- **basic-persistence.py** - Agent with conversation memory
- **tool-groups.py** - Different ways to use tools

### 🎯 Use Cases
Real-world examples for specific scenarios:
- **research-assistant/** - Comprehensive research agent
- **slack-bot/** - Slack integration examples  
- **automation/** - Task automation workflows

### 🔗 Integrations
Examples showing integration patterns:
- **cross-package.py** - Using all three packages together
- **storage-patterns.py** - Different storage configurations
- **streaming.py** - Real-time response streaming

## Running Examples

Most examples can be run directly:

```bash
# Basic example
python examples/getting-started/quickstart.py

# Use case example
python examples/use-cases/research-assistant/basic.py

# Integration example  
python examples/integrations/cross-package.py
```

## Prerequisites

Install all Slide packages:

```bash
# Using uv (recommended)
uv add slide-tyler slide-lye slide-narrator

# Using pip
pip install slide-tyler slide-lye slide-narrator
```

Set up your API key:
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Package-Specific Examples

For examples focusing on individual packages, see:
- [Tyler Examples](../packages/tyler/examples/) - Agent framework
- [Lye Examples](../packages/lye/) - Tools and capabilities  
- [Narrator Examples](../packages/narrator/) - Storage and persistence
- [Space Monkey Examples](../packages/space-monkey/examples/) - Slack integration

## Testing

All examples are tested to ensure they work correctly:

```bash
# Run example tests
pytest tests/test_examples.py
```