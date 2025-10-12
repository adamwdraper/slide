# Tyler Architecture

## Overview

Tyler is built on a modular architecture with clear separation of concerns. The framework is organized into focused components that work together to provide powerful AI agent capabilities.

## Core Components

### Agent (Orchestrator)
**Location**: `tyler/models/agent.py`

The main `Agent` class orchestrates the execution of AI agents:
- Coordinates all components
- Implements the public `go()` API
- Manages iteration loops
- Handles thread and file stores
- Inherits from `weave.Model` for observability

**Key Methods**:
- `go(thread, stream=False)` - Main entry point for agent execution
- `step(thread, stream=False)` - Execute one LLM interaction step

### ToolCall
**Location**: `tyler/models/tool_call.py`

Value object that normalizes tool call formats from LLM responses:
- Handles both dict and object formats
- Provides consistent interface for tool execution
- Validates required fields
- Handles edge cases (empty args, invalid JSON)

**Usage**:
```python
from tyler.models.tool_call import ToolCall

# Normalize any format
tool_call = ToolCall.from_llm_response(llm_response)

# Use consistent interface
print(tool_call.id, tool_call.name, tool_call.arguments)
```

### MessageFactory
**Location**: `tyler/models/message_factory.py`

Centralized factory for creating standardized Message objects:
- Creates assistant messages with metrics
- Creates tool result messages with attachments
- Creates error messages with timing
- Ensures consistent source metadata

**Usage**:
```python
factory = MessageFactory(agent_name="MyAgent", model_name="gpt-4")

# Create different message types
assistant_msg = factory.create_assistant_message("Hello!")
tool_msg = factory.create_tool_message("tool_name", "result", "call_id")
error_msg = factory.create_error_message("Error occurred")
```

### ToolManager
**Location**: `tyler/models/tool_manager.py`

Manages tool registration and agent delegation:
- Coordinates tool registration using strategies
- Creates delegation tools for child agents
- Handles tool lifecycle

**Responsibilities**:
- Register tools from various sources
- Set up agent-to-agent delegation
- Provide clean API for Agent class

### Tool Registration Strategies
**Location**: `tyler/utils/tool_strategies.py`

Strategy pattern for registering different tool types:
- **StringToolStrategy** - Handles "web" or "web:tool1,tool2" format
- **ModuleToolStrategy** - Handles module objects with TOOLS attribute
- **DictToolStrategy** - Handles dict tool definitions
- **CallableToolStrategy** - Handles direct function references
- **ToolRegistrar** - Coordinates all strategies

**Benefits**:
- Easy to add new tool types
- Clean separation per format
- Better error messages
- Testable in isolation

### CompletionHandler
**Location**: `tyler/models/completion_handler.py`

Handles LLM communication and response processing:
- Builds completion parameters
- Handles model-specific adjustments (e.g., Gemini)
- Manages API configuration
- Collects metrics and timing data
- Integrates with Weave for tracking

**Features**:
- Custom API base URL support
- Extra headers for authentication
- Parameter dropping for model compatibility
- Streaming and non-streaming modes

### ToolRunner
**Location**: `tyler/utils/tool_runner.py`

Global singleton for tool execution:
- Registers tool implementations
- Executes tools (sync and async)
- Caches loaded modules
- Manages tool attributes

**Usage**:
```python
from tyler.utils.tool_runner import tool_runner

# Register a tool
tool_runner.register_tool(
    name="my_tool",
    implementation=my_function,
    definition=openai_function_def
)

# Execute a tool
result = await tool_runner.run_tool_async("my_tool", {"param": "value"})
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent (Orchestrator)                  │
│  - Public API: go(), step()                                  │
│  - Coordinates components                                    │
│  - Manages execution flow                                    │
│  - Handles storage (thread_store, file_store)               │
└───────┬─────────────┬──────────────┬──────────────┬─────────┘
        │             │              │              │
        ▼             ▼              ▼              ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────────┐
│ ToolManager  │ │ Message   │ │ Completion   │ │ ToolCall     │
│              │ │ Factory   │ │ Handler      │ │              │
│ - Register   │ │           │ │              │ │ - Normalize  │
│   tools      │ │ - Create  │ │ - Build      │ │   formats    │
│ - Delegate   │ │   msgs    │ │   params     │ │ - Validate   │
│   to agents  │ │ - Format  │ │ - Call LLM   │ │ - Serialize  │
└──────┬───────┘ └───────────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌─────────────────────────────────┐
│    Tool Registration            │
│    Strategies                   │
│                                 │
│  ┌──────────────────────────┐  │
│  │ StringToolStrategy       │  │
│  │ ModuleToolStrategy       │  │
│  │ DictToolStrategy         │  │
│  │ CallableToolStrategy     │  │
│  └──────────────────────────┘  │
│                                 │
│  ToolRegistrar coordinates      │
└─────────────┬───────────────────┘
              │
              ▼
    ┌──────────────────┐
    │   ToolRunner     │
    │   (Singleton)    │
    │                  │
    │ - Execute tools  │
    │ - Cache modules  │
    │ - Manage state   │
    └──────────────────┘
```

## Data Flow

### 1. Agent Initialization
```
Agent.__init__
  ├─> MessageFactory(agent_name, model_name)
  ├─> CompletionHandler(model_name, temp, ...)
  ├─> ToolManager(tools, agents)
  │    └─> ToolRegistrar.register_tools()
  │         ├─> StringToolStrategy.register()
  │         ├─> DictToolStrategy.register()
  │         └─> ... (delegates to appropriate strategy)
  └─> Generate system prompt with tools
```

### 2. Agent Execution (go)
```
agent.go(thread)
  ├─> Get thread from store
  ├─> Reset iteration count
  └─> Main loop:
       ├─> step(thread, stream)
       │    ├─> CompletionHandler.get_completion()
       │    └─> Return (response, metrics)
       ├─> Process response
       ├─> If tool_calls:
       │    ├─> Execute tools in parallel
       │    ├─> Create tool messages via MessageFactory
       │    └─> Add to thread
       └─> Return AgentResult or yield ExecutionEvents
```

### 3. Tool Execution
```
Tool Call Received
  ├─> ToolCall.from_llm_response(raw_tool_call)
  │    └─> Normalize to consistent format
  ├─> ToolRunner.execute_tool_call(tool_call)
  │    ├─> Look up registered implementation
  │    ├─> Parse arguments
  │    └─> Execute (async or sync)
  └─> MessageFactory.create_tool_message(result)
       └─> Return formatted Message
```

## Benefits of This Architecture

### Modularity
- Each component has single, clear responsibility
- Easy to understand and navigate
- Components can be tested in isolation

### Extensibility
- Strategy pattern makes adding new tool types trivial
- CompletionHandler can support new models easily
- MessageFactory ensures consistent formatting

### Maintainability
- Changes localized to specific components
- Clear boundaries reduce side effects
- Better error messages per context

### Testability
- Each component independently testable
- Easier to mock for testing
- Better test coverage

## Package Structure

```
tyler/
├── models/
│   ├── agent.py              # Main Agent orchestrator
│   ├── execution.py          # ExecutionEvent, AgentResult
│   ├── tool_call.py          # ToolCall value object
│   ├── message_factory.py    # Message creation factory
│   ├── tool_manager.py       # Tool registration manager
│   └── completion_handler.py # LLM communication handler
│
├── utils/
│   ├── tool_runner.py        # Global tool executor (singleton)
│   ├── tool_strategies.py    # Tool registration strategies
│   ├── logging.py            # Logger configuration
│   └── files.py              # File utilities
│
├── mcp/
│   ├── adapter.py            # MCP protocol adapter
│   └── client.py             # MCP client
│
├── a2a/
│   ├── adapter.py            # A2A protocol adapter
│   ├── client.py             # A2A client
│   └── server.py             # A2A server
│
├── cli/
│   ├── main.py               # CLI entry point
│   ├── chat.py               # Chat interface
│   └── init.py               # Project initialization
│
└── eval/
    ├── agent_eval.py         # Evaluation framework
    ├── conversations.py      # Conversation management
    ├── expectations.py       # Test expectations
    ├── mock_tools.py         # Mock tools for testing
    ├── results.py            # Evaluation results
    └── scorers.py            # Scoring functions
```

## Design Principles

### 1. Separation of Concerns
Each component handles one aspect:
- **Agent**: Orchestration and flow control
- **ToolManager**: Tool lifecycle
- **MessageFactory**: Message formatting
- **CompletionHandler**: LLM communication
- **ToolCall**: Data normalization

### 2. Composition Over Inheritance
Agent composes specialized components rather than inheriting everything:
```python
class Agent(Model):
    def __init__(self, ...):
        self.message_factory = MessageFactory(...)
        self.completion_handler = CompletionHandler(...)
        self.tool_manager = ToolManager(...)
```

### 3. Strategy Pattern for Flexibility
Different tool types handled by dedicated strategies:
- Easy to add new types
- Clear handling per type
- Better error messages

### 4. Factory Pattern for Consistency
MessageFactory ensures all messages have:
- Correct source metadata
- Proper metrics structure
- Consistent formatting

### 5. Backward Compatibility
All changes are internal - public APIs unchanged:
```python
# This still works identically
agent = Agent(model_name="gpt-4.1", tools=["web"])
result = await agent.go(thread)
```

## Performance Characteristics

### Agent Initialization
- Simple agent: ~0.3ms
- With tools: ~4ms (includes module loading)

### Message Creation
- ~0.006ms per message
- MessageFactory adds negligible overhead

### Tool Execution
- Depends on tool implementation
- Parallel execution for multiple tools
- Async-first design

## Evolution and Refactoring

This architecture is the result of a comprehensive refactoring (October 2025) that:
- Reduced Agent class from 1,597 to 1,345 lines (15.8%)
- Created 5 new focused components
- Maintained 100% backward compatibility
- Kept all tests passing throughout

See `/directive/specs/tyler-code-organization/` for complete refactoring documentation.

---

## For Developers

### Adding a New Tool Type

1. Create a new strategy class:
```python
class MyToolStrategy(ToolRegistrationStrategy):
    def can_handle(self, tool):
        return isinstance(tool, MyToolType)
    
    def register(self, tool, tool_runner):
        # Registration logic
        return [tool_definition]
```

2. Add to ToolRegistrar:
```python
self.strategies.append(MyToolStrategy())
```

### Creating Custom Messages

Use MessageFactory for consistency:
```python
# In Agent or component
message = self.message_factory.create_assistant_message(
    content="Response",
    metrics={"usage": {...}}
)
```

### Extending CompletionHandler

Subclass for custom LLM providers:
```python
class CustomCompletionHandler(CompletionHandler):
    def _build_completion_params(self, ...):
        params = super()._build_completion_params(...)
        # Add custom modifications
        return params
```

---

**Last Updated**: 2025-01-11  
**Version**: 2.0.6+refactor  
**Status**: Production Ready ✅

