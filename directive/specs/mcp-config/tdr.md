# Technical Design Review (TDR) — First-Class MCP Configuration Support

**Author**: AI Agent + Adam Draper  
**Date**: 2025-01-23  
**Links**: 
- Spec: `/directive/specs/mcp-config/spec.md`
- Impact: `/directive/specs/mcp-config/impact.md`
- Mintlify MCP Docs: https://www.mintlify.com/docs/ai/model-context-protocol#using-your-mcp-server

---

## 1. Summary

Add declarative MCP (Model Context Protocol) server configuration to Tyler, making it a first-class feature with **symmetric API**: Python `Agent.create(mcp={...})` matches YAML `mcp:` exactly. Currently, using MCP requires writing boilerplate adapter code. This change eliminates that friction entirely.

**User Impact:**
- **CLI users**: Add 5-line YAML block to `tyler-chat-config.yaml` → instant MCP tool access
- **Python users**: Use `Agent.create(mcp={...})` → same structure as YAML

**Example (before):**
```python
# 15+ lines of boilerplate
mcp = MCPAdapter()
await mcp.connect("mintlify", "sse", url="https://docs.wandb.ai/mcp")
tools = mcp.get_tools_for_agent(["mintlify"])
agent = Agent(tools=tools)
await mcp.disconnect_all()
```

**Example (after - Python matches YAML):**
```python
# Two-step init - no factory needed!
agent = Agent(
    tools=["web"],
    mcp={"servers": [{"name": "mintlify", "transport": "sse", "url": "https://docs.wandb.ai/mcp"}]}
)

# Connect to MCP servers (fail fast!)
await agent.connect_mcp()

# Use normally
result = await agent.go(thread)
await agent.cleanup()
```

**Effort:** 3-5 days (new config layer, comprehensive testing, docs)

## 2. Decision Drivers & Non‑Goals

### Drivers
- **API Symmetry** - Python `Agent(mcp={...})` and YAML `mcp:` have identical structure
- **Fail Fast** - Config errors in __init__, connection errors in connect_mcp() (before first use)
- **Simplicity** - No factory pattern, standard sync init, explicit async step
- **Developer experience** - Make MCP trivial to use (config-first, zero boilerplate)
- **Discoverability** - MCP should feel like a core feature, not an advanced addon
- **Ecosystem alignment** - Mintlify and other MCP servers are proliferating; make Tyler compatible
- **Production readiness** - Graceful degradation, env var substitution, clear errors

### Non‑Goals
- Building MCP servers (Tyler is a client only)
- Auto-discovery of MCP servers (must be explicitly configured)
- MCP protocol extensions beyond what `mcp` package supports
- Connection pooling across agents (YAGNI for now)
- URL validation/filtering (document security, don't enforce)
- Public helper functions (all config logic is internal to Agent)
- Async factory pattern (two-step init avoids factory complexity)
- Lazy initialization (fail fast is more important than convenience)

## 3. Current State — Codebase Map

### Relevant Modules

**Tyler MCP (`packages/tyler/tyler/mcp/`):**
```
tyler/mcp/
├── __init__.py           # Exports MCPAdapter
├── adapter.py            # MCPAdapter class (converts MCP tools → Tyler format)
└── client.py             # MCPClient (connects to servers, discovers tools)
```

**Current MCP flow (low-level):**
1. User instantiates `MCPAdapter()`
2. User calls `await adapter.connect(name, transport, **kwargs)` for each server
3. Adapter discovers tools via MCP protocol
4. User calls `adapter.get_tools_for_agent()` to get Tyler-formatted tools
5. User passes tools to `Agent(..., tools=mcp_tools)`
6. User calls `await adapter.disconnect_all()` for cleanup

**Tyler CLI (`packages/tyler/tyler/cli/`):**
```
tyler/cli/
├── chat.py               # ChatManager, load_config(), main loop
└── init.py               # Project scaffolding
```

**Configuration:**
```
packages/tyler/
├── tyler-chat-config.yaml        # Template config
└── tyler-chat-config-wandb.yaml  # W&B-specific example
```

### Current MCPAdapter API

**Key methods:**
```python
class MCPAdapter:
    async def connect(self, name: str, transport: str, **kwargs) -> bool
    async def disconnect(self, name: str) -> None
    async def disconnect_all() -> None
    def get_tools_for_agent(self, server_names: List[str] = None) -> List[Dict]
```

**Transport types:**
- `stdio`: Local processes (command, args, env)
- `sse`: HTTP/Server-Sent Events (url, headers)
- `websocket`: WebSocket (url, headers)

**Tool format:**
```python
{
    "definition": {"type": "function", "function": {...}},
    "implementation": <async callable>,
    "attributes": {"source": "mcp", "server_name": "...", ...}
}
```

### Namespace Format (Current)

Tools are currently namespaced as `servername__toolname` (double underscore). We'll change to single underscore: `servername_toolname`.

## 4. Proposed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  User Input (YAML or Python dict)                          │
│  mcp:                                                       │
│    servers:                                                 │
│      - name: mintlify                                       │
│        transport: sse                                       │
│        url: https://docs.wandb.ai/mcp                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  config_loader.py                                           │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 1. Validate config (schema, required fields)          │ │
│  │ 2. Substitute env vars (${VAR} → value)               │ │
│  │ 3. Connect to servers in parallel                     │ │
│  │ 4. Discover tools from each server                    │ │
│  │ 5. Apply filters (include/exclude)                    │ │
│  │ 6. Namespace tools (prefix_toolname)                  │ │
│  │ 7. Register with tool_runner                          │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MCPAdapter (existing, used internally)                     │
│  - connect() to servers                                     │
│  - get_tools_for_agent()                                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Output: (tools, disconnect_callback)                       │
│  tools = [{"definition": {...}, "implementation": fn}, ...]│
│  disconnect = async () => adapter.disconnect_all()          │
└─────────────────────────────────────────────────────────────┘
```

### Core API: Two-Step Initialization

**Agent class additions:**
```python
class Agent(Model):
    # New field - stores config, validates in __init__
    mcp: Optional[Dict[str, Any]] = Field(
        default=None,
        description="MCP server configuration (same structure as YAML config)"
    )
    
    # Private attributes
    _mcp_connected: bool = PrivateAttr(default=False)
    _mcp_disconnect: Optional[Callable[[], Awaitable[None]]] = PrivateAttr(default=None)
    
    def __init__(self, **kwargs):
        """Standard sync initialization - validates MCP config schema."""
        super().__init__(**kwargs)
        
        # Validate MCP config schema immediately (fail fast!)
        if self.mcp:
            from tyler.mcp.config_loader import _validate_mcp_config
            _validate_mcp_config(self.mcp)  # Raises ValueError if invalid
    
    async def connect_mcp(self) -> None:
        """
        Connect to MCP servers configured in the mcp field.
        
        Call this after creating an Agent with mcp config and before using it.
        Connects to servers, discovers tools, and registers them.
        
        Raises:
            ValueError: If connection fails and fail_silent=False for a server
        
        Example:
            agent = Agent(mcp={"servers": [...]})
            await agent.connect_mcp()  # Fails immediately if server unreachable
            result = await agent.go(thread)
        """
        if not self.mcp:
            logger.warning("connect_mcp() called but no mcp config provided")
            return
        
        if self._mcp_connected:
            logger.debug("MCP already connected, skipping")
            return
        
        logger.info("Connecting to MCP servers...")
        
        from tyler.mcp.config_loader import _load_mcp_config
        
        # Connect and get tools (fails fast if server unreachable)
        mcp_tools, disconnect_callback = await _load_mcp_config(self.mcp)
        
        # Store disconnect callback
        self._mcp_disconnect = disconnect_callback
        
        # Merge MCP tools
        if not isinstance(self.tools, list):
            self.tools = list(self.tools) if self.tools else []
        self.tools.extend(mcp_tools)
        
        # Re-process tools with ToolManager
        from tyler.models.tool_manager import ToolManager
        tool_manager = ToolManager(tools=self.tools, agents=self.agents)
        self._processed_tools = tool_manager.register_all_tools()
        
        # Regenerate system prompt with new tools
        self._system_prompt = self._prompt.system_prompt(
            self.purpose, 
            self.name, 
            self.model_name, 
            self._processed_tools, 
            self.notes
        )
        
        self._mcp_connected = True
        logger.info(f"MCP connected with {len(mcp_tools)} tools")
    
    async def cleanup(self) -> None:
        """
        Cleanup MCP connections and resources.
        
        Call this when done with the agent to properly close MCP connections.
        Agent can be reused by calling connect_mcp() again if needed.
        """
        if self._mcp_disconnect:
            await self._mcp_disconnect()
            self._mcp_disconnect = None
            self._mcp_connected = False
```

**Internal helpers (in config_loader.py):**

```python
def _validate_mcp_config(config: Dict[str, Any]) -> None:
    """
    Validate MCP config schema (sync validation).
    
    Called from Agent.__init__ to fail fast on invalid config.
    
    Raises:
        ValueError: If config schema is invalid
    """
    if "servers" not in config:
        raise ValueError("MCP config must have 'servers' key")
    
    if not isinstance(config["servers"], list):
        raise ValueError("MCP 'servers' must be a list")
    
    for server in config["servers"]:
        _validate_server_config(server)

async def _load_mcp_config(
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Callable[[], Awaitable[None]]]:
    """
    Internal helper to load MCP configuration.
    
    NOT A PUBLIC API - used by Agent.connect_mcp() and CLI.
    
    Implementation flow:
    1. Create shared MCPAdapter instance
    2. For each server:
       - Substitute environment variables
       - Connect (parallel via asyncio.gather)
       - Get tools
       - Apply filters
       - Namespace tools
    3. Flatten all tools into single list
    4. Return (tools, disconnect_callback)
    
    Note: Schema validation happens earlier in Agent.__init__
    """
```

### Config Schema

**YAML Format:**
```yaml
mcp:
  servers:
    - name: string              # Required: Unique server identifier
      transport: string         # Required: "stdio" | "sse" | "websocket" | "streamablehttp"
      
      # Transport-specific (mutually exclusive based on transport)
      url: string              # Required for sse/websocket/streamablehttp
      command: string          # Required for stdio
      args: list[string]       # Optional for stdio
      env: dict[string, string] # Optional for stdio
      
      # Optional authentication
      headers: dict[string, string]  # Optional: Custom headers (sse/websocket)
      
      # Optional tool management
      include_tools: list[string]    # Optional: Whitelist (default: all)
      exclude_tools: list[string]    # Optional: Blacklist (default: none)
      prefix: string                 # Optional: Custom namespace (default: server name)
      fail_silent: bool              # Optional: Graceful degradation (default: true)
```

**Python Dict Format:**
```python
{
    "servers": [
        {
            "name": "mintlify",
            "transport": "sse",
            "url": "https://docs.wandb.ai/mcp",
            "headers": {"Authorization": "Bearer ${MCP_TOKEN}"},  # Env var substitution
            "include_tools": ["search", "query"],
            "prefix": "docs",
            "fail_silent": True
        },
        {
            "name": "filesystem",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            "exclude_tools": ["write_file", "delete_file"]
        }
    ]
}
```

### Validation Logic

**Server-level validation:**
```python
def _validate_server_config(server: Dict) -> None:
    """Validate a single server config."""
    # Required fields
    if "name" not in server:
        raise ValueError("Server config missing required field 'name'")
    if "transport" not in server:
        raise ValueError(f"Server '{server['name']}' missing required field 'transport'")
    
    transport = server["transport"]
    if transport not in ["stdio", "sse", "websocket", "streamablehttp"]:
        raise ValueError(
            f"Invalid transport '{transport}'. Must be one of: stdio, sse, websocket, streamablehttp"
        )
    
    # Transport-specific required fields
    if transport in ["sse", "websocket", "streamablehttp"]:
        if "url" not in server:
            raise ValueError(
                f"Server '{server['name']}' with transport '{transport}' requires 'url' field"
            )
    elif transport == "stdio":
        if "command" not in server:
            raise ValueError(
                f"Server '{server['name']}' with transport 'stdio' requires 'command' field"
            )
```

### Environment Variable Substitution

**Pattern:** `${VAR_NAME}` in string values

**Implementation:**
```python
import os
import re

def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute environment variables in config values."""
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Match ${VAR_NAME} pattern
        pattern = r'\$\{([^}]+)\}'
        def replacer(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))  # Return original if not found
        return re.sub(pattern, replacer, obj)
    return obj
```

### Tool Filtering

**Implementation:**
```python
def _apply_tool_filters(tools: List[Dict], server: Dict) -> List[Dict]:
    """Filter tools based on include/exclude lists."""
    include = server.get("include_tools")
    exclude = server.get("exclude_tools", [])
    
    filtered = tools
    
    # Apply include filter (whitelist)
    if include is not None:
        filtered = [
            t for t in filtered 
            if t["definition"]["function"]["name"] in include
        ]
    
    # Apply exclude filter (blacklist)
    if exclude:
        filtered = [
            t for t in filtered 
            if t["definition"]["function"]["name"] not in exclude
        ]
    
    return filtered
```

### Tool Namespacing

**Format:** `prefix_toolname` (single underscore)

**Implementation:**
```python
def _namespace_tools(tools: List[Dict], prefix: str) -> List[Dict]:
    """Add namespace prefix to tool names."""
    import re
    
    # Sanitize prefix (alphanumeric + underscore only)
    clean_prefix = re.sub(r'[^a-zA-Z0-9_]', '_', prefix)
    
    namespaced = []
    for tool in tools:
        # Clone tool dict
        tool_copy = tool.copy()
        tool_copy["definition"] = tool["definition"].copy()
        tool_copy["definition"]["function"] = tool["definition"]["function"].copy()
        
        # Get original name
        original_name = tool["definition"]["function"]["name"]
        
        # Create namespaced name
        new_name = f"{clean_prefix}_{original_name}"
        
        # Update name in definition
        tool_copy["definition"]["function"]["name"] = new_name
        
        namespaced.append(tool_copy)
    
    return namespaced
```

### CLI Integration

**Update `ChatManager` in `tyler/cli/chat.py`:**

```python
class ChatManager:
    async def initialize_agent(self, config_data: Dict):
        """Initialize the agent from config."""
        # Create agent (Agent.__init__ validates MCP config schema)
        self.agent = Agent(**config_data)
        
        # Auto-connect MCP servers if configured (NEW)
        if self.agent.mcp:
            try:
                logger.info("Connecting to MCP servers...")
                await self.agent.connect_mcp()
                logger.info("MCP servers connected successfully")
            except Exception as e:
                # MCP connection failed
                console.print(f"[red]Failed to connect to MCP servers: {e}[/]")
                # Decide based on fail_silent (could exit or continue)
                raise  # For now, fail startup if MCP configured but broken
    
    async def cleanup(self):
        """Cleanup on CLI exit."""
        if self.agent:
            await self.agent.cleanup()
```

**Key points:**
- ✅ CLI calls `agent.connect_mcp()` automatically after creating agent
- ✅ Users never see the two-step (transparent)
- ✅ Startup fails if MCP server unreachable (fail fast!)
- ✅ Clear error messages for connection failures

### Error Handling

**Connection failures:**
```python
async def _connect_server(server: Dict, adapter: MCPAdapter) -> bool:
    """Connect to a single MCP server."""
    name = server["name"]
    transport = server["transport"]
    fail_silent = server.get("fail_silent", True)
    
    try:
        # Build connection kwargs
        kwargs = {}
        if transport in ["sse", "websocket"]:
            kwargs["url"] = server["url"]
            if "headers" in server:
                kwargs["headers"] = server["headers"]
        elif transport == "stdio":
            kwargs["command"] = server["command"]
            kwargs["args"] = server.get("args", [])
            kwargs["env"] = server.get("env", {})
        
        # Attempt connection
        connected = await adapter.connect(name, transport, **kwargs)
        
        if not connected:
            msg = f"Failed to connect to MCP server '{name}'"
            if fail_silent:
                logger.warning(msg)
                return False
            else:
                raise RuntimeError(msg)
        
        logger.info(f"Connected to MCP server '{name}'")
        return True
        
    except Exception as e:
        msg = f"Error connecting to MCP server '{name}': {e}"
        if fail_silent:
            logger.warning(msg)
            return False
        else:
            raise ValueError(msg) from e
```

## 5. Alternatives Considered

### Option A: Helper function `connect_from_config()` (NOT CHOSEN)
```python
tools, disconnect = await connect_from_config({"servers": [...]})
agent = Agent(tools=tools)
```

**Pros:** Works with sync Agent.__init__  
**Cons:** ❌ Two-step process, ❌ Python API doesn't match YAML, ❌ Manual tool merging  
**Decision:** Inconsistent with YAML experience

### Option B: Async factory `Agent.create()` (NOT CHOSEN)
```python
agent = await Agent.create(mcp={"servers": [...]})
```

**Pros:** Python matches YAML, fail fast  
**Cons:** ❌ New pattern (no other objects use factory), ❌ Inconsistent with rest of codebase  
**Decision:** User feedback - avoid factory pattern

### Option C: Lazy initialization in agent.go() (NOT CHOSEN)
```python
agent = Agent(mcp={"servers": [...]})
result = await agent.go(thread)  # Lazy connect on first use
```

**Pros:** Transparent, single step  
**Cons:** ❌ Fail late (connection errors during agent.go()), ❌ User wants fail fast  
**Decision:** Fail-fast is more important than convenience

### Option D: CLI-only feature (NOT CHOSEN)
Only add MCP config to tyler-chat, not Python API.

**Pros:** Fewer components  
**Cons:** ❌ Inconsistent experience, ❌ Python users still write boilerplate  
**Decision:** Both CLI + Python need it

### Option E: CHOSEN - Two-step explicit init `Agent(mcp={...})` + `connect_mcp()`
```python
agent = Agent(mcp={"servers": [...]})  # Validates schema in __init__
await agent.connect_mcp()               # Connects, fails fast
result = await agent.go(thread)         # Use normally
```

**Pros:** ✅ Fail fast (config errors in __init__, connection errors in connect_mcp()), ✅ No factory pattern, ✅ Explicit and clear, ✅ Python matches YAML structure  
**Cons:** Two-step for MCP users (acceptable - only affects MCP users, CLI is automatic)  
**Decision:** Best balance - fail fast without factory complexity

## 6. Data Model & Contract Changes

### No Database Changes
MCP tools are ephemeral (registered at Agent init, not persisted).

### New Config Contract

**tyler-chat-config.yaml gains `mcp` section:**
```yaml
mcp:
  servers:
    - name: mintlify
      transport: sse
      url: https://docs.wandb.ai/mcp
```

### Tool Naming Contract Change

**Breaking change (low-level API only):**
- **Before**: `servername__toolname` (double underscore)
- **After**: `servername_toolname` (single underscore)

**Impact:** Only affects users manually using `MCPAdapter` (low-level escape hatch). Acceptable.

### New Public API

**Agent mcp parameter + connect_mcp() method:**
```python
from tyler import Agent

# Primary API - matches YAML structure exactly
agent = Agent(
    name="Tyler",
    model_name="gpt-4.1",
    tools=["web"],
    mcp={"servers": [...]}  # Validates schema in __init__
)

# Connect to MCP servers (fail fast!)
await agent.connect_mcp()

# Use normally
result = await agent.go(thread)

# Cleanup when done
await agent.cleanup()
```

**New Agent methods:**
```python
async def connect_mcp(self) -> None:
    """Connect to configured MCP servers. Fails fast if unreachable."""

async def cleanup(self) -> None:
    """Disconnect MCP servers and free resources."""
```

**No new exports from `tyler.mcp`:**
- `config_loader` module is internal only
- `MCPAdapter` remains as low-level escape hatch (not featured in docs)

## 7. Security, Privacy, Compliance

### Security Considerations

**1. Credential exposure**
- **Risk:** Users might hardcode API keys in YAML files
- **Mitigation:** 
  - Environment variable substitution (`${VAR}`)
  - Documentation warning about git-committed configs
  - Example configs show `${TOKEN}` pattern

**2. Untrusted MCP servers**
- **Risk:** Malicious MCP server could expose harmful tools
- **Mitigation:**
  - Document "only connect to trusted servers"
  - User responsibility (same as any HTTP client)
  
**3. SSRF via MCP URLs**
- **Risk:** User could configure internal URLs
- **Mitigation:**
  - Document risks of internal URLs
  - No URL filtering in MVP (user responsibility)
  
**4. Secret logging**
- **Risk:** Auth headers logged in debug output
- **Mitigation:**
  - Sanitize URLs/headers before logging
  - Never log `Authorization` header values

### Privacy & Compliance
- **No PII handling** - MCP tools execute user-provided queries, no PII storage
- **No data retention** - MCP tools are ephemeral
- **User data** - Passed to external servers per user config (user controls)

## 8. Observability & Operations

### Logging Strategy

**Connection lifecycle:**
```python
logger.info("Connecting to MCP server", extra={
    "server_name": "mintlify",
    "transport": "sse",
    "url": "https://docs.wandb.ai/mcp"  # Sanitized (no query params)
})

logger.info("Connected to MCP server", extra={
    "server_name": "mintlify",
    "tools_discovered": 3,
    "tools_registered": 3
})

logger.warning("Failed to connect to MCP server", extra={
    "server_name": "offline",
    "error": "Connection refused",
    "fail_silent": True
})
```

**Tool operations:**
```python
logger.debug("Filtered MCP tools", extra={
    "server_name": "filesystem",
    "total_tools": 10,
    "included": 5,
    "excluded": ["write_file", "delete_file"]
})

logger.debug("Namespaced MCP tools", extra={
    "server_name": "mintlify",
    "prefix": "docs",
    "sample_names": ["docs_search", "docs_query"]
})
```

**Security:**
- ⚠️ **Never log**: Authorization headers, API keys, tokens
- ⚠️ **Sanitize**: URLs (remove query params with secrets)

### Metrics

**Use existing weave tracing:**
- MCP tool execution time (via `tool_runner.execute_tool_call`)
- No custom metrics needed for MVP

### Dashboards & Alerts

**Not needed for MVP** (CLI tool, not production service)

## 9. Rollout & Migration

### Rollout Strategy

**Single PR with feature flag:**
```python
# config_loader.py
ENABLE_MCP_CONFIG = os.getenv("TYLER_MCP_CONFIG_ENABLED", "true").lower() == "true"

async def connect_from_config(...):
    if not ENABLE_MCP_CONFIG:
        raise ValueError("MCP config is not enabled. Set TYLER_MCP_CONFIG_ENABLED=true")
    # ... implementation ...
```

**Rollout phases:**
1. Merge PR (feature flagged off by default)
2. Enable internally, test with real servers
3. Enable by default in next release
4. Remove flag after 1-2 releases

### Migration

**No data migration needed** (new feature, additive)

**Existing MCPAdapter users:**
- No changes required (backward compatible)
- Docs guide to config approach
- Small callout in docs about low-level API

### Revert Plan

1. Set `TYLER_MCP_CONFIG_ENABLED=false` env var
2. Or revert PR if critical issue
3. Blast radius: New feature only, no existing functionality affected

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment

✅ **Write failing tests BEFORE implementation**  
✅ **Confirm tests fail** (red)  
✅ **Implement minimal code** to pass (green)  
✅ **Refactor** while keeping tests green  

### Spec→Test Mapping

| Spec AC | Test ID | Priority |
|---------|---------|----------|
| AC1: Minimal config works | `test_connect_from_config_minimal` | P0 |
| AC2: All tools registered by default | `test_all_tools_registered_default` | P0 |
| AC3: Tool filtering works | `test_tool_filtering_include_exclude` | P0 |
| AC4: Namespace with default prefix | `test_namespace_default_prefix` | P0 |
| AC5: Namespace with custom prefix | `test_namespace_custom_prefix` | P0 |
| AC6: Env var substitution | `test_env_var_substitution` | P0 |
| AC7: Graceful degradation (fail_silent) | `test_graceful_degradation_fail_silent` | P0 |
| AC8: Error on failure (fail_silent=false) | `test_error_on_connection_failure` | P0 |
| AC9: Multiple servers | `test_multiple_servers_no_collision` | P0 |
| AC10: CLI config loading | `test_cli_loads_mcp_config` | P0 |
| AC11: Invalid transport error | `test_invalid_transport_error` | P1 |
| AC12: Missing required field error | `test_missing_required_field_error` | P1 |

### Test Implementation

**Unit Tests (`test_config_loader.py`):**

```python
import pytest
from tyler.mcp import connect_from_config
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_agent_with_mcp_two_step_init():
    """Test Agent(mcp={...}) with explicit connect_mcp()."""
    mcp_config = {
        "servers": [{
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp"
        }]
    }
    
    # Mock MCP connection
    with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
        mock_load.return_value = (
            [{
                "definition": {"type": "function", "function": {"name": "test_search"}},
                "implementation": AsyncMock()
            }],
            AsyncMock()  # disconnect callback
        )
        
        # Create agent with MCP (sync, validates schema)
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        # MCP not connected yet
        assert not agent._mcp_connected
        mock_load.assert_not_called()
        
        # Explicitly connect to MCP servers
        await agent.connect_mcp()
        
        # Now MCP should be connected
        assert agent._mcp_connected
        mock_load.assert_called_once()
        
        # Verify tools registered
        assert any("test_search" in str(t) for t in agent._processed_tools)
        
        # Verify cleanup works
        await agent.cleanup()
        assert not agent._mcp_connected

@pytest.mark.asyncio
async def test_agent_mcp_validates_schema_in_init():
    """Test Agent.__init__ validates MCP config schema immediately."""
    invalid_config = {
        "servers": [{
            "name": "test",
            "transport": "sse"
            # Missing required 'url' field
        }]
    }
    
    # Should raise immediately in __init__
    with pytest.raises(ValueError, match="requires 'url' field"):
        agent = Agent(mcp=invalid_config)

@pytest.mark.asyncio
async def test_tool_filtering_include_exclude():
    """Test include/exclude tool filters work correctly."""
    config = {
        "servers": [{
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp",
            "include_tools": ["search", "query"],
            "exclude_tools": ["query"]  # Include search, exclude query
        }]
    }
    
    with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
        mock_adapter = AsyncMock()
        mock_adapter.connect.return_value = True
        mock_adapter.get_tools_for_agent.return_value = [
            {"definition": {"function": {"name": "search"}}},
            {"definition": {"function": {"name": "query"}}},
            {"definition": {"function": {"name": "delete"}}}
        ]
        mock_adapter_class.return_value = mock_adapter
        
        tools, _ = await connect_from_config(config)
        
        # Only 'search' should remain (included and not excluded)
        assert len(tools) == 1
        assert "search" in tools[0]["definition"]["function"]["name"]

@pytest.mark.asyncio
async def test_env_var_substitution():
    """Test environment variable substitution works."""
    import os
    os.environ["TEST_MCP_TOKEN"] = "secret123"
    
    config = {
        "servers": [{
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp",
            "headers": {
                "Authorization": "Bearer ${TEST_MCP_TOKEN}"
            }
        }]
    }
    
    with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
        mock_adapter = AsyncMock()
        mock_adapter.connect.return_value = True
        mock_adapter.get_tools_for_agent.return_value = []
        mock_adapter_class.return_value = mock_adapter
        
        await connect_from_config(config)
        
        # Verify substitution happened
        call_args = mock_adapter.connect.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer secret123"
    
    del os.environ["TEST_MCP_TOKEN"]

@pytest.mark.asyncio
async def test_graceful_degradation_fail_silent():
    """Test fail_silent=True logs warning but continues."""
    config = {
        "servers": [
            {"name": "working", "transport": "sse", "url": "https://working.com/mcp"},
            {"name": "broken", "transport": "sse", "url": "https://broken.com/mcp", "fail_silent": True}
        ]
    }
    
    with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
        mock_adapter = AsyncMock()
        mock_adapter.connect.side_effect = [True, False]  # First succeeds, second fails
        mock_adapter.get_tools_for_agent.return_value = [
            {"definition": {"function": {"name": "tool1"}}}
        ]
        mock_adapter_class.return_value = mock_adapter
        
        # Should not raise despite second server failing
        tools, _ = await connect_from_config(config)
        
        # Should have tools from first server only
        assert len(tools) > 0

def test_invalid_transport_error():
    """Test invalid transport raises clear error."""
    config = {
        "servers": [{
            "name": "test",
            "transport": "http",  # Invalid
            "url": "https://example.com/mcp"
        }]
    }
    
    with pytest.raises(ValueError, match="Invalid transport 'http'"):
        asyncio.run(connect_from_config(config))

def test_missing_required_field_error():
    """Test missing required field raises clear error."""
    config = {
        "servers": [{
            "name": "test",
            "transport": "sse"
            # Missing 'url'
        }]
    }
    
    with pytest.raises(ValueError, match="requires 'url' field"):
        asyncio.run(connect_from_config(config))
```

**Integration Tests (`test_mcp_integration.py`):**

```python
@pytest.mark.asyncio
async def test_end_to_end_agent_with_mcp_config():
    """Test full flow: Agent(mcp={...}) → connect_mcp() → tool execution."""
    mcp_config = {
        "servers": [{
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp"
        }]
    }
    
    # Mock MCP config loader
    with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
        # Setup mock tool
        async def mock_search(query: str) -> str:
            return f"Results for: {query}"
        
        mock_load.return_value = (
            [{
                "definition": {
                    "type": "function",
                    "function": {
                        "name": "test_search",
                        "description": "Search docs",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    }
                },
                "implementation": mock_search
            }],
            AsyncMock()  # disconnect callback
        )
        
        # Create agent with MCP (sync init, validates schema)
        agent = Agent(
            name="test",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        # Not connected yet
        assert not agent._mcp_connected
        
        # Explicitly connect to MCP servers
        await agent.connect_mcp()
        
        # Verify MCP was connected
        assert agent._mcp_connected
        mock_load.assert_called_once()
        
        # Create thread with tool use
        thread = Thread()
        thread.add_message(Message(role="user", content="Search for MCP"))
        
        # Execute (MCP already connected, works normally)
        result = await agent.go(thread)
        
        # Cleanup
        await agent.cleanup()
        assert not agent._mcp_connected
```

**CLI Tests (`test_chat_mcp.py`):**

```python
def test_cli_loads_mcp_config_from_yaml(tmp_path):
    """Test tyler-chat loads MCP servers from config file."""
    # Create temp config
    config_file = tmp_path / "test-config.yaml"
    config_file.write_text("""
    name: "TestBot"
    model_name: "gpt-4o-mini"
    mcp:
      servers:
        - name: test
          transport: sse
          url: https://example.com/mcp
    """)
    
    # Load config
    config = load_config(str(config_file))
    
    # Verify MCP tools were loaded
    assert 'tools' in config
    assert any('test_' in str(t) for t in config['tools'])
```

### CI Requirements

**All tests must:**
- Run in CI (GitHub Actions)
- Block merge if failing
- Pass with 100% coverage on new code
- Include both positive and negative cases

## 11. Risks & Open Questions

### Known Risks

**Risk 1: MCP server downtime blocks CLI startup**
- **Severity:** Medium
- **Mitigation:** Default `fail_silent: true`, parallel connections with timeout
- **Action:** Document expected startup latency

**Risk 2: Tool name collisions**
- **Severity:** Low
- **Mitigation:** Mandatory namespacing, custom prefix override
- **Action:** Clear error messages if collision detected

**Risk 3: Security - credential leaks**
- **Severity:** High
- **Mitigation:** Env var substitution, docs warning, log sanitization
- **Action:** Security review of logging code

**Risk 4: Backward compat - namespace format change**
- **Severity:** Low
- **Mitigation:** Only affects low-level API users (minimal)
- **Action:** Release notes mention breaking change

### Open Questions

**Q1: Connection pooling for multiple agents?**
- **Status:** Not needed for MVP
- **Decision:** Single agent = single adapter. Revisit if users report issues.

**Q2: URL validation (block localhost/private IPs)?**
- **Status:** Document risks, don't enforce
- **Decision:** Users might use localhost for dev. Trust users.

**Q3: Async Agent factory pattern?**
- **Status:** Nice-to-have, not MVP
- **Decision:** `connect_from_config()` helper sufficient for now

**Q4: Connection timeout configuration?**
- **Status:** Hardcode 5s for MVP
- **Decision:** Add to config if users request it

**Q5: Tool discovery caching?**
- **Status:** Not needed for MVP
- **Decision:** Re-discover on each agent init. Optimize if slow.

**Q6: Multiple transports per server?**
- **Status:** One transport per server for MVP
- **Decision:** Users can add multiple server entries if needed

## 12. Milestones / Plan (post‑approval)

### Phase 1: Core Config Loader + Agent Two-Step Init (Day 1-2)
1. ✅ Create `packages/tyler/tyler/mcp/config_loader.py`
2. ✅ Implement `_validate_mcp_config()` sync validation function
3. ✅ Implement `_validate_server_config()` for individual servers
4. ✅ Implement `_load_mcp_config()` async connection function
5. ✅ Implement env var substitution (`_substitute_env_vars`)
6. ✅ Implement tool filtering (`_apply_tool_filters`)
7. ✅ Implement namespacing (`_namespace_tools`)
8. ✅ Update `adapter.py` namespace format (__ → _)
9. ✅ Add `mcp` field to Agent model
10. ✅ Add `_mcp_connected` and `_mcp_disconnect` private attributes
11. ✅ Update `Agent.__init__()` to call `_validate_mcp_config()` if mcp present
12. ✅ Add `Agent.connect_mcp()` public method
13. ✅ Add `Agent.cleanup()` public method
14. ✅ Write unit tests (`test_config_loader.py`, `test_agent_mcp.py`)

**DoD:** All unit tests pass, 100% coverage on new code

### Phase 2: CLI Integration (Day 2)
15. ✅ Update `ChatManager.initialize_agent()` to call `agent.connect_mcp()` if mcp present
16. ✅ Add error handling for MCP connection failures in CLI
17. ✅ Add `ChatManager.cleanup()` to call `agent.cleanup()` on exit
18. ✅ Write CLI tests (`test_chat_mcp.py`)

Note: No changes to load_config() needed - mcp field passes through to Agent normally!

**DoD:** tyler-chat auto-connects MCP servers on startup, fails fast if unreachable, tests pass

### Phase 3: Config Templates (Day 2)
18. ✅ Update `tyler-chat-config.yaml` with MCP example (commented)
19. ✅ Update `tyler-chat-config-wandb.yaml` with MCP example

**DoD:** Templates have clear MCP examples with inline docs

### Phase 4: Examples (Day 3)
20. ✅ Rewrite `examples/300_mcp_basic.py` (Agent(mcp={...}), config-only)
21. ✅ Rewrite `examples/301_mcp_connect_existing.py` (Agent(mcp={...}), config-only)
22. ✅ Create `examples/302_mcp_config_cli.py` (YAML loading)
23. ✅ Create `examples/303_mcp_mintlify.py` (W&B docs example)
24. ✅ Update `examples/README.md` (add new examples)

**DoD:** All examples runnable, Agent(mcp={...}) + connect_mcp() two-step init approach

### Phase 5: Documentation (Day 3-4)
25. ✅ Rewrite `docs/guides/mcp-integration.mdx` (Agent(mcp={...}) first, config-first)
26. ✅ Update `docs/concepts/mcp.mdx` (Agent(mcp={...}) examples)
27. ✅ Update `docs/apps/tyler-cli.mdx` (add MCP section)
28. ✅ Update `docs/introduction.mdx` (mention MCP config)
29. ✅ Update `docs/concepts/tools.mdx` (MCP as tool source)
30. ✅ Update `docs/guides/adding-tools.mdx` (MCP config)
31. ✅ Update `docs/concepts/how-agents-work.mdx` (terminology)
32. ✅ Update `docs/concepts/architecture.mdx` (config layer)
33. ✅ Update main `README.md` (features section)
34. ✅ Update `packages/tyler/README.md` (MCP section)
35. ✅ Update `packages/tyler/ARCHITECTURE.md` (config module)

**DoD:** All docs updated, Agent(mcp={...}) + connect_mcp() shown as primary API, Python matches YAML exactly, CLI auto-connects noted

### Phase 6: Integration Tests (Day 4)
36. ✅ Write `test_mcp_integration.py` (end-to-end flows with two-step init)
37. ✅ Test with real Mintlify server (manual)
38. ✅ Test error scenarios (manual)

**DoD:** All integration tests pass, manual testing complete

### Phase 7: Polish & Review (Day 5)
39. ✅ Run full test suite
40. ✅ Check test coverage (aim for 90%+)
41. ✅ Run linter/formatter
42. ✅ Update CHANGELOG
43. ✅ Create PR
44. ✅ Address review comments

**DoD:** PR ready for merge, all CI checks pass

**Total: 3-5 days** (depending on review cycles)

---

## Approval Gate

**DO NOT START CODING UNTIL THIS TDR IS REVIEWED AND APPROVED**

This TDR defines:
- ✅ Config schema (YAML + Python dict)
- ✅ Validation logic
- ✅ Tool filtering and namespacing
- ✅ CLI integration strategy
- ✅ Test coverage (unit + integration)
- ✅ Documentation plan
- ✅ Security considerations
- ✅ Rollout strategy

**Approver:** _______________ Date: _______________

