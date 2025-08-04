# Getting Started Examples

Simple examples to get you up and running with Slide packages.

## Examples

### 🚀 [quickstart.py](./quickstart.py)
Basic agent using Tyler and Lye tools together.
- Demonstrates web search, image analysis, and file operations
- Shows basic agent setup and tool integration
- Good first example to run

**Run:** `python examples/getting-started/quickstart.py`

### 💾 [basic-persistence.py](./basic-persistence.py)  
Agent with conversation memory using Narrator storage.
- Shows how to set up ThreadStore and FileStore
- Demonstrates persistent conversation history
- Multiple agents sharing the same storage

**Run:** `python examples/getting-started/basic-persistence.py`

### 🔧 [tool-groups.py](./tool-groups.py)
Different ways to import and use tools.
- Tool groups vs individual tools
- Selective tool usage
- Tool filtering and customization

**Run:** `python examples/getting-started/tool-groups.py`

## Prerequisites

```bash
# Install required packages
pip install slide-tyler slide-lye slide-narrator

# Set API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Next Steps

After running these examples, check out:
- [Use Cases](../use-cases/) - Real-world applications
- [Integrations](../integrations/) - Advanced patterns
- [Package Examples](../../packages/tyler/examples/) - Package-specific features