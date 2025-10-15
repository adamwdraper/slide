# Tyler Examples

This directory contains examples demonstrating various Tyler features and capabilities.

## Basic Examples

### 001_docs_introduction.py
Introduction to Tyler's core concepts - agents, threads, and messages.

### 002_basic.py
Basic agent usage with simple message exchanges.

### 003_docs_quickstart.py
Quick start guide showing the essential Tyler workflow.

## Streaming Examples

### 004_streaming.py
**Event-based streaming** - demonstrates the new event streaming API with different event types (LLM_REQUEST, LLM_STREAM_CHUNK, LLM_RESPONSE, TOOL_SELECTED, etc.).

### 005_raw_streaming.py
**Raw streaming mode** - shows how to use `stream="raw"` to get unmodified LiteLLM chunks in OpenAI-compatible format, useful for building proxies or direct OpenAI client integration.

### 005_thread_persistence.py
Thread persistence with streaming responses.

### 006_thinking_tokens.py ✨ NEW
**Thinking tokens (reasoning) streaming** - demonstrates:
- Enabling thinking tokens with `reasoning` parameter
- Streaming both thinking and content separately
- Using models that support reasoning (OpenAI o1/o3, DeepSeek-R1, etc.)
- W&B Inference integration with DeepSeek-R1
- Comparing responses with and without thinking tokens

## Tool Examples (100-199)

### 100_tools_basic.py
Basic tool usage and function calling.

### 101_tools_streaming.py
Tool calls with streaming responses.

### 102_selective_tools.py
Selectively enabling specific tools for different tasks.

### 103_tools_files.py
Working with file attachments in tool calls.

### 104_tools_image.py
Image generation and processing with tools.

### 105_tools_audio.py
Audio processing and transcription tools.

### 106_tools_wandb.py
Weights & Biases integration for experiment tracking.

### 107_tools_group_import.py
Importing and using tool groups.

## Attachment Examples (200-299)

### 200_attachments.py
Working with message attachments (files, images, etc.).

### 201_reactions_example.py
Adding reactions to messages.

## MCP & Observability Examples (300-399)

### 300_mcp_basic.py
Model Context Protocol (MCP) basic usage.

### 301_mcp_connect_existing.py
Connecting to existing MCP servers.

### 302_execution_observability.py
Execution observability and monitoring.

## Agent Delegation & A2A Examples (400-499)

### 400_agent_delegation.py
Delegating tasks between multiple agents.

### 401_a2a_basic_server.py
Agent-to-Agent communication - setting up a server.

### 402_a2a_basic_client.py
Agent-to-Agent communication - client connecting to server.

### 403_a2a_multi_agent.py
Multi-agent systems with A2A communication.

## Evaluation Examples (500-599)

### 500_eval_example.py
Evaluating agent performance with real LLM calls.

### 501_eval_mock_example.py
Testing agent logic with mocked LLM responses.

## Running Examples

Most examples can be run directly:

```bash
# Run with Python
python 004_streaming.py

# Or use uv (recommended)
uv run python 006_thinking_tokens.py
```

### Environment Variables

Some examples require API keys. Create a `.env` file or set environment variables:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# W&B Inference (set as OPENAI_API_KEY for compatibility)
WANDB_API_KEY=...
OPENAI_API_KEY=<your-wandb-api-key>

# Weights & Biases tracing
WANDB_API_KEY=...

# Other integrations
NOTION_TOKEN=...
SLACK_BOT_TOKEN=...
BRAVE_API_KEY=...
```

## Feature Highlights

### 🌊 Streaming Modes

Tyler supports three streaming modes:

1. **Events mode** (`stream=True` or `stream="events"`): High-level event stream with structured data
   - Best for: Building UIs, collecting metrics, custom event handling
   - Example: `004_streaming.py`

2. **Raw mode** (`stream="raw"`): Unmodified LiteLLM chunks (OpenAI-compatible)
   - Best for: Building API proxies, direct OpenAI client integration
   - Example: `005_raw_streaming.py`

3. **Thinking tokens** (`reasoning="low|medium|high"`): Stream model reasoning separately
   - Best for: Showing model's thought process, debugging, transparency
   - Example: `006_thinking_tokens.py`

### 💭 Thinking Tokens

Thinking tokens (also called reasoning tokens) allow you to see the model's internal reasoning process before it generates its final answer. This is particularly useful for:

- Complex problem-solving tasks
- Mathematical calculations
- Logical reasoning
- Debugging model behavior
- Building transparent AI systems

Supported models:
- OpenAI o1, o3 series
- DeepSeek-R1
- Other reasoning-capable models

Usage:
```python
agent = Agent(
    model_name="gpt-4.1",
    reasoning="low",  # Options: "low", "medium", "high" or dict for advanced config
    temperature=0.7
)

async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:
        # Handle thinking/reasoning tokens
        print(f"💭 {event.data['thinking_chunk']}")
    elif event.type == EventType.LLM_STREAM_CHUNK:
        # Handle final content
        print(event.data['content_chunk'])
```

### 🔧 Tools & Function Calling

Tyler supports extensive tool integration:
- Built-in tools (web, slack, notion, command_line)
- Custom Python functions as tools
- Streaming tool calls
- File and media processing

### 🤝 Agent Delegation & A2A

Multiple agents can work together:
- Delegate tasks to specialized agents
- Agent-to-Agent (A2A) communication
- Multi-agent systems and workflows

### 📊 Observability

Track and debug agent execution:
- Execution events and metrics
- Weave integration for tracing
- W&B experiment tracking
- MCP for model context

## Contributing

To add a new example:

1. Follow the numbering convention (e.g., 007_new_feature.py)
2. Include docstring explaining what the example demonstrates
3. Add environment variable checks with helpful error messages
4. Update this README with a description
5. Make the file executable: `chmod +x your_example.py`

## Getting Help

- Documentation: https://slide-ai.github.io/docs/
- Issues: https://github.com/slide-ai/slide/issues
- Discord: [Join our community](#)

