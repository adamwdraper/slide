# Impact Analysis — First-Class MCP Configuration Support

## Modules/packages likely touched

### Tyler MCP Module (HIGH Impact - New Feature)

#### New Module (Internal)
- **`packages/tyler/tyler/mcp/config_loader.py`** (NEW, ~150-200 lines)
  - `_load_mcp_config(config: Dict) -> Tuple[List[Dict], Callable]` - internal helper
  - `_validate_server_config(server: Dict) -> None`
  - `_connect_server(server: Dict, adapter: MCPAdapter) -> bool`
  - `_apply_tool_filters(tools: List[Dict], server: Dict) -> List[Dict]`
  - `_namespace_tools(tools: List[Dict], prefix: str) -> List[Dict]`

#### Existing Modules
- **`packages/tyler/tyler/mcp/__init__.py`** (1-2 lines)
  - No new exports needed (config_loader is internal only)

- **`packages/tyler/tyler/mcp/adapter.py`** (10-15 lines)
  - Update `_create_tyler_name()` to use single underscore (`_`) instead of double (`__`)
  - Add docstring note at top: "Note: Most users should use `Agent.create(mcp={...})`. This low-level API is for advanced use cases only."
  - Update existing docstrings to mention config approach where relevant

### Tyler CLI (MEDIUM Impact)

- **`packages/tyler/tyler/cli/chat.py`** (40-60 lines)
  - Add MCP config parsing in `load_config()` (15-20 lines)
  - Add `_load_mcp_servers(mcp_config: Dict) -> List[Dict]` helper (20-30 lines)
  - Update `ChatManager.initialize_agent()` to merge MCP tools (10-15 lines)
  - Add error handling for MCP connection failures

### Tyler Agent (MEDIUM Impact)

- **`packages/tyler/tyler/models/agent.py`** (30-40 lines)
  - Add `mcp: Optional[Dict[str, Any]]` field
  - Add `_mcp_initialized: bool` private attribute (tracks lazy init state)
  - Add `_mcp_disconnect: Optional[Callable]` private attribute for cleanup
  - Add `async def _initialize_mcp()` - lazy init helper (called on first go())
  - Update `_go_complete()` and `_go_stream()` to lazy init MCP
  - Add `async def cleanup()` - disconnect MCP servers
  - Update docstrings to show `Agent(mcp={...})` usage

### Configuration Files (LOW Impact)

- **`packages/tyler/tyler-chat-config.yaml`** (10-15 lines)
  - Add commented example `mcp.servers` block
  - Add inline documentation

- **`packages/tyler/tyler-chat-config-wandb.yaml`** (10-15 lines)
  - Same updates as above

### Examples (HIGH Impact - Complete Rewrite)

#### Existing MCP Examples (Config-Only Rewrites)

- **`packages/tyler/examples/300_mcp_basic.py`** (~50-70 lines rewrite)
  - Pure config approach - NO low-level adapter code
  - Use `connect_from_config()` with simple example
  - Clean, focused example showing the happy path
  - Updated comments and docstrings

- **`packages/tyler/examples/301_mcp_connect_existing.py`** (~70-90 lines rewrite)
  - Pure config approach for multiple servers
  - Show filesystem + GitHub servers in one config
  - Demonstrate tool filtering and custom prefixes
  - NO low-level adapter code - just config

#### New Examples

- **`packages/tyler/examples/302_mcp_config_cli.py`** (NEW, ~60-80 lines)
  - Demonstrate loading from YAML config file
  - Show how to validate config before creating agent
  - Show environment variable substitution
  - Error handling examples
  
- **`packages/tyler/examples/303_mcp_mintlify.py`** (NEW, ~50-70 lines)
  - Real-world Mintlify MCP server example
  - Connect to `https://docs.wandb.ai/mcp`
  - Search W&B docs with agent
  - Perfect copy-paste starter example

#### Example README Update

- **`packages/tyler/examples/README.md`** (~15-20 lines)
  - Update "MCP Integration" section
  - Add descriptions for new examples (302, 303)
  - Reorder to show config examples first
  - Add quick reference table

### Documentation (HIGH Impact - Comprehensive Updates)

#### Primary Docs (Major Updates)

- **`docs/guides/mcp-integration.mdx`** (REWRITE ~120-150 lines)
  - **Section 1 (NEW)**: "Quick Start with Config" - show 5-line YAML example FIRST
  - **Section 2**: Python API with `connect_from_config()`
  - **Section 3**: CLI configuration examples
  - **Section 4**: Comprehensive config reference (all fields documented)
  - **Section 5**: Troubleshooting section (common errors, solutions)
  - **Section 6**: Security best practices
  - **Small callout box at end**: "Advanced: Low-Level MCPAdapter API" - 3-4 lines noting it exists for edge cases, link to API reference
  - Update all code snippets (Python + CLI) to use config only
  - Remove all manual adapter examples from main content

- **`docs/concepts/mcp.mdx`** (~50-75 lines updates)
  - Update "Using MCP with Tyler" section to show config approach
  - Update examples throughout
  - Add link to mcp-integration.mdx for full guide
  - Update diagrams/flow if any

- **`docs/apps/tyler-cli.mdx`** (~25-35 lines)
  - Add new "MCP Configuration" section under tool configuration
  - Show example `mcp.servers` block with all options
  - Document environment variable substitution (`${VAR}` syntax)
  - Link to mcp-integration.mdx for detailed guide

#### Supporting Docs (Minor Updates)

- **`docs/introduction.mdx`** (~5-10 lines)
  - Update MCP mention to reference new config approach
  - Add "declarative MCP config" to feature list if present

- **`docs/concepts/tools.mdx`** (~10-15 lines)
  - Update section on external tools to mention MCP config
  - Add example of MCP tools appearing in agent tool set
  - Link to mcp-integration.mdx

- **`docs/guides/adding-tools.mdx`** (~10-15 lines)
  - Add MCP config as a tool source (alongside built-in, custom)
  - Show how MCP tools are registered automatically
  - Link to mcp-integration.mdx

- **`docs/concepts/how-agents-work.mdx`** (~5-10 lines)
  - Update if it mentions MCP tool execution
  - Ensure terminology aligns with config approach

- **`docs/concepts/architecture.mdx`** (~5-10 lines)
  - Update architecture diagram/description if it shows MCP
  - Note config layer if architecture is detailed

- **`docs/concepts/a2a.mdx`** (~2-5 lines)
  - Update if it mentions MCP + A2A integration
  - Minimal changes expected

#### Navigation Updates

- **`docs/docs.json`** (~2-5 lines)
  - Ensure mcp-integration.mdx is prominently placed in nav
  - Consider moving to "Getting Started" if not there
  - Update page title/description if needed

#### Root Documentation

- **`README.md`** (main repo, ~15-25 lines)
  - Update "Features" section to highlight declarative MCP config
  - Update quick start example if it shows tools
  - Add MCP config example to "Quick Start" or "Examples" section
  - Ensure links point to docs/guides/mcp-integration.mdx

#### Package-Level Documentation

- **`packages/tyler/README.md`** (~20-30 lines)
  - Update "MCP Integration" section (if present)
  - Show config approach in examples
  - Update installation/setup instructions if needed
  - Ensure consistency with main README

- **`packages/tyler/ARCHITECTURE.md`** (~10-15 lines)
  - Update MCP section to reflect new config layer
  - Add `mcp/config_loader.py` to module structure
  - Update any architecture diagrams showing MCP flow
  - Document config → adapter → tools flow

### Tests (HIGH Impact - New Coverage)

#### Unit Tests (NEW)
- **`packages/tyler/tests/mcp/test_config_loader.py`** (NEW, ~300-400 lines)
  - Test `connect_from_config()` with various server configs
  - Test tool namespacing (prefix override, default naming)
  - Test tool filtering (`include_tools`, `exclude_tools`)
  - Test validation (invalid transport, missing fields)
  - Test environment variable substitution
  - Test error handling (connection failures, malformed config)
  - Test multiple servers

#### Integration Tests
- **`packages/tyler/tests/mcp/test_mcp_integration.py`** (NEW, ~200-250 lines)
  - Test full flow: config → agent → tool execution
  - Test CLI config loading
  - Test graceful degradation (`fail_silent`)
  - Mock MCP server responses

#### CLI Tests
- **`packages/tyler/tests/cli/test_chat_mcp.py`** (NEW, ~150-200 lines)
  - Test tyler-chat with MCP config
  - Test config file loading
  - Test error messages for invalid configs

## Contracts to update (APIs, events, schemas, migrations)

### New Public API

**Agent mcp parameter (lazy initialization):**
```python
from tyler import Agent

# Standard sync initialization
agent = Agent(
    name="Tyler",
    model_name="gpt-4.1",
    tools=["web"],
    mcp={
        "servers": [{
            "name": "mintlify",
            "transport": "sse",
            "url": "https://docs.wandb.ai/mcp"
        }]
    }
)

# MCP servers connect lazily on first agent.go() call
result = await agent.go(thread)
```

**Agent.cleanup() method:**
```python
async def cleanup(self) -> None:
    """
    Cleanup MCP connections and resources.
    
    Call this when done with the agent to properly close MCP server connections.
    """
```

**Full usage:**
```python
# Create agent (sync, stores config)
agent = Agent(
    tools=["web"],
    mcp={"servers": [{...}]}
)

# Use agent (lazy MCP init on first call)
result = await agent.go(thread)

# Cleanup when done
await agent.cleanup()
```

### Config Schema (YAML)

**New top-level `mcp` field in tyler-chat-config.yaml:**

```yaml
# Optional MCP server configuration
mcp:
  servers:
    - name: string              # Required: Unique server identifier
      transport: string         # Required: "stdio" | "sse" | "websocket"
      
      # Transport-specific fields (mutually exclusive)
      url: string              # Required for sse/websocket
      command: string          # Required for stdio
      args: list[string]       # Optional for stdio
      env: dict[string, string] # Optional for stdio
      
      # Optional authentication/headers
      headers: dict[string, string]  # Optional: Custom headers
      
      # Optional tool management
      include_tools: list[string]    # Optional: Whitelist tools (default: all)
      exclude_tools: list[string]    # Optional: Blacklist tools (default: none)
      prefix: string                 # Optional: Custom namespace prefix
      fail_silent: bool              # Optional: Graceful degradation (default: true)
```

**Example:**
```yaml
mcp:
  servers:
    # Minimal config
    - name: mintlify
      transport: sse
      url: https://docs.wandb.ai/mcp
    
    # Full config with all options
    - name: api
      transport: websocket
      url: wss://api.example.com/mcp
      headers:
        Authorization: "Bearer ${MCP_TOKEN}"
      include_tools: ["search", "query"]
      prefix: "docs"
      fail_silent: false
    
    # Stdio server
    - name: filesystem
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      exclude_tools: ["write_file", "delete_file"]
```

### Tool Naming Contract

**Namespace format change:**
- **Before**: `servername__toolname` (double underscore)
- **After**: `servername_toolname` (single underscore)

**Rationale:** Single underscore is more conventional, cleaner for tab-completion

**Examples:**
- `mintlify_search`
- `filesystem_read_file`
- `docs_query` (with custom prefix)

**Impact:** ✅ Breaking for existing `MCPAdapter` users, but low-level API (acceptable)

### No Database/Schema Changes
- No migrations needed
- MCP tools are ephemeral (registered at startup)
- No persistent storage impact

### No Event Schema Changes
- Uses existing `ExecutionEvent` types
- Tool execution events unchanged
- MCP connection events can use existing logging

## Risks

### Security
**Risk Level:** 🟡 **MEDIUM**

**Concerns:**
1. **Credential exposure in config files**
   - Users might hardcode API keys in YAML
   - Config files could be committed to git

   **Mitigation:**
   - ✅ Environment variable substitution (`${VAR}`) already supported
   - ✅ Document best practices prominently
   - ✅ Add warning in config template about not hardcoding secrets
   - ✅ Example configs use `${MCP_TOKEN}` pattern

2. **Untrusted MCP servers**
   - Users could connect to malicious MCP servers
   - MCP tools execute with agent's permissions

   **Mitigation:**
   - ✅ Document security considerations
   - ✅ Recommend only connecting to trusted servers
   - ✅ MCP protocol itself has auth mechanisms
   - ⚠️ Consider adding `allowed_domains` whitelist in future

3. **SSRF via MCP URLs**
   - Users could configure internal URLs
   - MCP client makes HTTP/WebSocket requests

   **Mitigation:**
   - ⚠️ Document risks of internal URLs
   - ⚠️ Consider URL validation in future (block localhost, private IPs in production)
   - ✅ For now: user responsibility (same as any HTTP client config)

### Performance/Availability
**Risk Level:** 🟡 **MEDIUM**

**Concerns:**
1. **Startup latency**
   - Connecting to MCP servers adds startup time
   - Multiple servers = sequential connections
   - Network timeouts could block CLI startup

   **Impact:**
   - CLI startup delay: +100-500ms per server (network dependent)
   - tyler-chat could feel slow if servers are slow/down

   **Mitigation:**
   - ✅ Connect in parallel (asyncio.gather)
   - ✅ Set reasonable connection timeout (5s default)
   - ✅ `fail_silent: true` default (continue if server down)
   - ✅ Log connection progress for user feedback

2. **Runtime tool execution latency**
   - MCP tools make network calls
   - Could be slower than built-in tools

   **Impact:**
   - Tool execution: +50-500ms per call (network dependent)
   - Acceptable for most use cases (docs search, API calls)

   **Mitigation:**
   - ⚠️ Document expected latency
   - ✅ MCP protocol supports streaming (future optimization)
   - ✅ Weave tracing will show tool latency clearly

3. **Resource leaks**
   - WebSocket/SSE connections must be properly closed
   - Orphaned connections if agent cleanup fails

   **Mitigation:**
   - ✅ `disconnect()` callback for explicit cleanup
   - ✅ Use asyncio context managers in adapter
   - ✅ Document cleanup in examples
   - ⚠️ Consider auto-cleanup on agent `__del__` (future)

### Data Integrity
**Risk Level:** 🟢 **LOW**

**Concerns:**
1. **Tool name collisions**
   - Multiple servers might expose tools with same name
   - Could override built-in tools if prefix matches

   **Mitigation:**
   - ✅ Mandatory namespacing (servername_toolname)
   - ✅ Custom prefix override for control
   - ✅ Tool registration errors logged clearly

2. **Invalid MCP responses**
   - MCP server could return malformed tool results
   - Could break agent execution

   **Mitigation:**
   - ✅ MCP client library validates responses
   - ✅ Tyler tool runner catches exceptions
   - ✅ Error messages added to conversation thread

### Backward Compatibility
**Risk Level:** 🟢 **LOW**

**Changes:**
1. **Namespace format** (`__` → `_`)
   - Only affects users manually using `MCPAdapter`
   - Low-level API (minimal usage expected)

2. **Config schema** (additive only)
   - New `mcp` field in tyler-chat-config.yaml
   - Fully optional (no changes for users without MCP)

**Impact:** ✅ Minimal - additive feature, low-level breaking change acceptable

## Observability needs

### Logs

**Add structured logging for MCP operations:**

```python
# Connection lifecycle
logger.info("Connecting to MCP server", extra={
    "server_name": "mintlify",
    "transport": "sse",
    "url": "https://docs.wandb.ai/mcp"  # sanitized (no auth headers)
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

# Tool filtering
logger.debug("Filtered MCP tools", extra={
    "server_name": "filesystem",
    "total_tools": 10,
    "included": 5,
    "excluded": ["write_file", "delete_file"]
})

# Namespacing
logger.debug("Namespaced MCP tools", extra={
    "server_name": "mintlify",
    "prefix": "docs",
    "sample_names": ["docs_search", "docs_query"]
})
```

**Log levels:**
- `INFO`: Connection success, tool registration
- `WARNING`: Connection failures (with fail_silent=true)
- `ERROR`: Connection failures (with fail_silent=false), validation errors
- `DEBUG`: Tool filtering, namespacing details

**Security:**
- ⚠️ Never log auth headers or API keys
- ⚠️ Sanitize URLs before logging (remove query params with tokens)

### Metrics

**No new custom metrics needed initially**

- Use existing weave tracing for:
  - MCP tool execution time (via `tool_runner.execute_tool_call`)
  - Agent iteration counts
  - Token usage

**Future enhancements (not MVP):**
- MCP connection success rate
- MCP tool execution latency percentiles
- MCP server availability

### Alerts

**No alerts needed for MVP**

- MCP is opt-in feature
- Failures are graceful (fail_silent default)
- CLI usage (not production service)

**Future considerations (if Tyler becomes a service):**
- Alert on repeated MCP connection failures
- Alert on MCP tool execution timeout rate

## Testing Strategy

### Unit Tests

**`test_config_loader.py`** (comprehensive coverage):

```python
# Config validation
- test_validate_valid_sse_config()
- test_validate_valid_stdio_config()
- test_validate_valid_websocket_config()
- test_validate_missing_url_for_sse()
- test_validate_missing_command_for_stdio()
- test_validate_invalid_transport()
- test_validate_missing_name()

# Tool filtering
- test_include_tools_filters_correctly()
- test_exclude_tools_filters_correctly()
- test_include_and_exclude_together()
- test_no_filters_includes_all()

# Tool namespacing
- test_namespace_with_default_prefix()
- test_namespace_with_custom_prefix()
- test_namespace_sanitizes_special_chars()

# Connection
- test_connect_from_config_single_server()
- test_connect_from_config_multiple_servers()
- test_connect_handles_connection_failure_fail_silent_true()
- test_connect_raises_on_failure_fail_silent_false()

# Environment variable substitution
- test_env_var_substitution_in_url()
- test_env_var_substitution_in_headers()
- test_env_var_missing_uses_default()

# Disconnect
- test_disconnect_callback_closes_all_connections()
```

**Mock strategy:**
- Mock `MCPAdapter.connect()` to avoid real network calls
- Mock `MCPAdapter.get_tools_for_agent()` to return fake tools
- Use real config parsing logic

### Integration Tests

**`test_mcp_integration.py`** (end-to-end flows):

```python
# Full agent flow
- test_agent_with_mcp_config_executes_tool()
  - Load config, create agent, execute MCP tool
  - Verify tool result appears in thread

# CLI flow
- test_cli_loads_mcp_config()
  - Mock tyler-chat config with MCP servers
  - Verify tools registered in agent

# Error handling
- test_graceful_degradation_on_connection_failure()
  - Server down + fail_silent=true
  - Verify agent still works with other tools

- test_error_on_connection_failure_when_not_silent()
  - Server down + fail_silent=false
  - Verify error raised, clear message

# Multiple servers
- test_multiple_mcp_servers_no_collisions()
  - Two servers with overlapping tool names
  - Verify namespacing prevents collisions
```

**Mock MCP server:**
- Use `pytest-httpserver` or similar for SSE endpoint
- Return minimal valid MCP responses (tool list, tool results)

### Manual Testing Scenarios

**Before merge, manually verify:**

1. ✅ Connect to real Mintlify MCP server (`https://docs.wandb.ai/mcp`)
   - Config loads successfully
   - Tools discovered and registered
   - Search tool executes and returns results

2. ✅ tyler-chat with MCP config
   - Config file loads
   - Agent uses MCP tools
   - Error messages are clear

3. ✅ Connection failure graceful degradation
   - Point to fake/down URL
   - Verify warning logged
   - Verify agent continues with built-in tools

4. ✅ Environment variable substitution
   - Set `MCP_TOKEN` env var
   - Use `${MCP_TOKEN}` in config
   - Verify substitution works (check logs, not the token!)

## Success Metrics

### Technical
- [ ] All unit tests pass (100% coverage on new code)
- [ ] All integration tests pass
- [ ] Manual testing checklist complete
- [ ] No performance regression (startup < 1s added latency per server)
- [ ] Documentation updated and reviewed

### Developer Experience
- [ ] 5-line YAML config connects to MCP server (no Python code)
- [ ] Clear error messages for common mistakes
- [ ] Examples use config approach (not low-level adapter)
- [ ] Users can copy-paste config and it works

## Open Questions

1. **Should we add connection pooling for multiple agents?**
   - If 10 agents use same MCP server, should they share connection?
   - Current: Each agent creates separate MCPAdapter instance
   - Recommendation: Not for MVP (YAGNI - users can pass shared adapter)

2. **Should we validate MCP URLs (block localhost/private IPs)?**
   - Security vs. flexibility tradeoff
   - Recommendation: Document risks, don't block (users might use localhost for dev)

3. **Should we add `--mcp` CLI flag for quick overrides?**
   - Example: `tyler chat --mcp https://docs.wandb.ai/mcp#mintlify`
   - Nice UX, but adds complexity
   - Recommendation: Not for MVP (config file is sufficient)

4. **Async Agent factory pattern?**
   - `Agent.create(..., mcp={...})` requires async
   - Current Agent.__init__ is sync
   - Recommendation: Keep as helper function for MVP, consider factory in future

5. **Should we cache MCP tool discoveries across agent instances?**
   - Avoid re-discovering tools if config unchanged
   - Could speed up agent creation
   - Recommendation: Not for MVP (optimize if users report slow startup)

6. **Connection timeout configuration?**
   - Should users control MCP connection timeout?
   - Recommendation: Hardcode 5s for MVP, add config if requested

## Migration Path

**For existing MCPAdapter users (minimal, likely none in the wild):**

The low-level `MCPAdapter` API continues to work unchanged (no breaking changes), but all documentation and examples will guide users to `Agent(mcp={...})`:

**Old way (still works, not recommended):**
```python
mcp = MCPAdapter()
await mcp.connect("mintlify", "sse", url="https://docs.wandb.ai/mcp")
tools = mcp.get_tools_for_agent(["mintlify"])
agent = Agent(tools=tools)
```

**New way (recommended for everyone):**
```python
# Simple, just add mcp parameter
agent = Agent(
    model_name="gpt-4.1",
    tools=["web"],
    mcp={
        "servers": [{"name": "mintlify", "transport": "sse", "url": "https://docs.wandb.ai/mcp"}]
    }
)

# Use normally (MCP connects lazily on first call)
result = await agent.go(thread)

# Cleanup when done
await agent.cleanup()
```

**Documentation strategy:**
- ✅ All examples show `Agent(mcp={...})` only
- ✅ Python API matches YAML structure exactly (no factory needed!)
- ✅ Lazy initialization on first use (transparent to users)
- ✅ Docs have config approach as primary content
- ✅ Small callout box in docs: "Advanced users can use `MCPAdapter` directly (not recommended)"
- ✅ No migration guide needed (new feature, config is the default path)

## Complete File Checklist

### Code Files
**New Files (6):**
- ✅ `packages/tyler/tyler/mcp/config_loader.py` (~200-250 lines)
- ✅ `packages/tyler/examples/302_mcp_config_cli.py` (~60-80 lines)
- ✅ `packages/tyler/examples/303_mcp_mintlify.py` (~50-70 lines)
- ✅ `packages/tyler/tests/mcp/test_config_loader.py` (~300-400 lines)
- ✅ `packages/tyler/tests/mcp/test_mcp_integration.py` (~200-250 lines)
- ✅ `packages/tyler/tests/cli/test_chat_mcp.py` (~150-200 lines)

**Modified Files (10):**
- ✅ `packages/tyler/tyler/mcp/__init__.py` (export config_loader)
- ✅ `packages/tyler/tyler/mcp/adapter.py` (namespace format change)
- ✅ `packages/tyler/tyler/cli/chat.py` (MCP config loading)
- ✅ `packages/tyler/tyler-chat-config.yaml` (add MCP example)
- ✅ `packages/tyler/tyler-chat-config-wandb.yaml` (add MCP example)
- ✅ `packages/tyler/examples/300_mcp_basic.py` (rewrite: config-first)
- ✅ `packages/tyler/examples/301_mcp_connect_existing.py` (rewrite: config-first)
- ✅ `packages/tyler/examples/README.md` (update MCP section)
- ✅ `packages/tyler/README.md` (update MCP section)
- ✅ `packages/tyler/ARCHITECTURE.md` (add config layer)

### Documentation Files
**Modified Files (11):**
- ✅ `README.md` (main repo - add MCP config to features)
- ✅ `docs/guides/mcp-integration.mdx` (MAJOR REWRITE - config-first)
- ✅ `docs/concepts/mcp.mdx` (update examples to config)
- ✅ `docs/apps/tyler-cli.mdx` (add MCP config section)
- ✅ `docs/introduction.mdx` (mention MCP config)
- ✅ `docs/concepts/tools.mdx` (add MCP config as tool source)
- ✅ `docs/guides/adding-tools.mdx` (add MCP config example)
- ✅ `docs/concepts/how-agents-work.mdx` (align terminology)
- ✅ `docs/concepts/architecture.mdx` (update MCP flow)
- ✅ `docs/concepts/a2a.mdx` (minimal if MCP+A2A mentioned)
- ✅ `docs/docs.json` (navigation/metadata)

**Total files to touch: 27 files**
- New: 6 files
- Modified: 21 files

