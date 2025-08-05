# Getting Started Examples

Simple examples to get you up and running with Slide packages.

## Examples

### 🚀 [quickstart.py](./quickstart.py)
Basic agent using Tyler and Lye tools together.
- Demonstrates web search, image analysis, and file operations
- Shows basic agent setup and tool integration
- Good first example to run

**Run:** `uv run examples/getting-started/quickstart.py`

### 💾 [basic-persistence.py](./basic-persistence.py)  
Agent with conversation memory using Narrator storage.
- Shows how to set up ThreadStore and FileStore
- Demonstrates persistent conversation history
- Multiple agents sharing the same storage

**Run:** `uv run examples/getting-started/basic-persistence.py`

### 🔧 [tool-groups.py](./tool-groups.py)
Different ways to import and use tools.
- Tool groups vs individual tools
- Selective tool usage
- Tool filtering and customization

**Run:** `uv run examples/getting-started/tool-groups.py`

## Prerequisites

From the project root:

```bash
# Sync the workspace (installs all packages in dev mode)
uv sync --dev

# Set API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

If running outside the workspace:
```bash
uv add slide-tyler slide-lye slide-narrator
```

## Next Steps

After running these examples, check out:
- [Use Cases](../use-cases/) - Real-world applications
- [Integrations](../integrations/) - Advanced patterns
- [Package Examples](../../packages/tyler/examples/) - Package-specific features