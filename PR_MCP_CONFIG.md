# First-Class MCP Configuration Support

## Summary

Add declarative MCP (Model Context Protocol) server configuration to Tyler, making it a first-class feature with **perfect API symmetry**: Python `Agent(mcp={...})` matches YAML `mcp:` exactly.

**Before (manual adapter code):**
```python
# 15+ lines of boilerplate
mcp = MCPAdapter()
await mcp.connect("mintlify", "sse", url="https://docs.wandb.ai/mcp")
tools = mcp.get_tools_for_agent(["mintlify"])
agent = Agent(tools=tools)
await mcp.disconnect_all()
```

**After (config-driven):**
```python
# Clean, simple config
agent = Agent(
    tools=["web"],
    mcp={"servers": [{"name": "mintlify", "transport": "sse", "url": "https://docs.wandb.ai/mcp"}]}
)
await agent.connect_mcp()  # Fail fast!
result = await agent.go(thread)
await agent.cleanup()
```

## Key Features

✅ **Perfect symmetry** - Python dict structure === YAML structure  
✅ **Fail fast** - Config errors in `__init__`, connection errors in `connect_mcp()` (before first use)  
✅ **No factory pattern** - Standard `Agent()` init (consistent with Thread, Message)  
✅ **CLI seamless** - `tyler chat` auto-connects, transparent to users  
✅ **Security** - Env var substitution (`${TOKEN}`), no credential logging  
✅ **Production-ready** - Graceful degradation, clear errors, comprehensive logging  

## Implementation

### Core Changes (TDD throughout)

**New Modules:**
- `tyler/mcp/config_loader.py` (102 lines, 93% coverage)
  - Config validation, env var substitution, tool filtering, namespacing
  
**Agent Updates:**
- Added `mcp: Optional[Dict]` field
- Added `connect_mcp()` method - connects to servers, registers tools
- Added `cleanup()` method - disconnects MCP servers
- __init__ validates MCP schema immediately (fail fast!)

**CLI Updates:**
- `ChatManager.initialize_agent()` now async
- Auto-calls `agent.connect_mcp()` after creation
- Auto-calls `agent.cleanup()` on exit
- Shows connection status to users

**Namespace Change (Breaking):**
- Changed from `servername__toolname` (double underscore) to `servername_toolname` (single)
- Only affects low-level `MCPAdapter` users (minimal impact)

### Test Coverage

**51 new tests added:**
- Config loader: 33 tests (validation, filtering, namespacing, env vars)
- Agent MCP: 11 tests (init validation, connect, cleanup, idempotency)
- Integration: 7 tests (full flow, multiple servers, error handling)

**All tests passing:** 257/257 ✓

### Documentation

**Major Updates:**
- Complete rewrite of `docs/guides/mcp-integration.mdx` - config-first approach
- Updated `docs/concepts/mcp.mdx` and `docs/apps/tyler-cli.mdx`
- Rewrote examples 300/301, created 302/303 (config-only, no adapter code!)
- Updated config templates with comprehensive MCP examples

## API

### Python

```python
from tyler import Agent

agent = Agent(
    model_name="gpt-4.1",
    tools=["web"],
    mcp={
        "servers": [{
            "name": "wandb_docs",
            "transport": "sse",
            "url": "https://docs.wandb.ai/mcp"
        }]
    }
)

await agent.connect_mcp()
result = await agent.go(thread)
await agent.cleanup()
```

### YAML (CLI)

```yaml
name: "Tyler"
model_name: "gpt-4.1"
tools: ["web"]

mcp:
  servers:
    - name: wandb_docs
      transport: sse
      url: https://docs.wandb.ai/mcp
```

Then: `tyler chat` (auto-connects on startup!)

## Config Schema

```python
{
    "servers": [
        {
            "name": str,              # Required: Server identifier
            "transport": str,         # Required: stdio|sse|websocket
            "url": str,              # Required for sse/websocket
            "command": str,          # Required for stdio
            "args": List[str],       # Optional for stdio
            "env": Dict,             # Optional for stdio
            "headers": Dict,         # Optional HTTP headers
            "include_tools": List,   # Optional whitelist
            "exclude_tools": List,   # Optional blacklist  
            "prefix": str,           # Optional custom namespace
            "fail_silent": bool      # Optional (default: true)
        }
    ]
}
```

## Testing

**Run all MCP tests:**
```bash
cd packages/tyler
uv run pytest tests/mcp/ tests/models/test_agent_mcp.py tests/cli/test_chat_integration.py -v
```

**Manual test with real Mintlify server:**
```bash
# Run the W&B docs example (connects to real https://docs.wandb.ai/mcp)
python packages/tyler/examples/303_mcp_mintlify.py

# Or test with Brave Search (requires BRAVE_API_KEY)
export BRAVE_API_KEY=your_key
python packages/tyler/examples/300_mcp_basic.py
```

## Design Decisions

**Why two-step init (`Agent()` + `connect_mcp()`) vs factory?**
- Fail fast: Schema errors in `__init__`, connection errors in `connect_mcp()`
- Consistency: Agent is a normal Model like Thread/Message (no factory pattern)
- Explicit: Clear async step for MCP users only
- CLI transparent: Auto-connects for tyler-chat users

**Why not lazy init (connect on first `go()` call)?**
- User feedback: "I want initialization to fail if MCP doesn't connect, not the first go() call"
- Fail-fast >> convenience for production

## Breaking Changes

- Namespace format: `servername__toolname` → `servername_toolname`
- Only affects users manually using `MCPAdapter` (low-level API)
- Acceptable for pre-1.0 product

## Migration

**For existing `MCPAdapter` users (minimal):**

Low-level API continues to work unchanged, but docs guide to config approach.

## Checklist

- [x] All tests pass (257/257)
- [x] TDD followed throughout
- [x] Documentation updated (guides, examples, config templates)
- [x] No linter errors
- [x] Spec, Impact, TDR approved
- [x] Examples rewritten (config-only)
- [x] Integration tests added
- [x] Manual test script provided

## Related

- Spec: `directive/specs/mcp-config/spec.md`
- Impact: `directive/specs/mcp-config/impact.md`
- TDR: `directive/specs/mcp-config/tdr.md`
- Mintlify MCP docs: https://www.mintlify.com/docs/ai/model-context-protocol

