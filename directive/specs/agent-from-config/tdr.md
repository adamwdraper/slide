# Technical Design Review (TDR) — Agent.from_config()

**Author**: AI Agent  
**Date**: 2025-10-25  
**Links**: 
- Spec: `/directive/specs/agent-from-config/spec.md`
- Impact: `/directive/specs/agent-from-config/impact.md`

---

## 1. Summary

We are adding `Agent.from_config()` class method and `load_config()` function to enable Python users to instantiate Tyler agents from the same YAML configuration files used by the `tyler-chat` CLI. This eliminates configuration duplication between CLI and programmatic usage, improves developer experience, and establishes config files as a first-class way to configure Tyler agents.

The implementation extracts and enhances the existing config loading logic from the CLI (`tyler/cli/chat.py`) into a new public module (`tyler/config.py`), refactors the CLI to use the shared code, and adds a convenient `Agent.from_config()` class method that wraps the config loading and agent instantiation. This is a pure additive change with zero breaking changes to existing APIs.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **DX improvement**: Developers want to reuse CLI configs in Python scripts/apps
- **Code reuse**: Eliminate ~150 lines of duplicated config logic between CLI and potential Python usage
- **Consistency**: Ensure CLI and Python code behave identically with same config
- **Maintainability**: Single source of truth for config loading reduces bugs
- **Convention**: Establish YAML configs as standard pattern for Tyler agents

### Non‑Goals
- **Auto-connecting MCP servers** - Users must still call `await agent.connect_mcp()` explicitly
- **Merging tool lists** - Override parameters replace, don't merge (keeps semantics simple)
- **New config formats** - Support only existing YAML/JSON formats
- **Config validation schema** - Rely on existing Pydantic validation in Agent class
- **Config hot-reloading** - Load once at instantiation only
- **Config fragments/includes** - Single file only for this iteration
- **CLI behavior changes** - CLI works exactly as before (internal refactor only)

## 3. Current State — Codebase Map

### Key Modules

#### Agent Implementation
- **`tyler/models/agent.py`** (248 lines)
  - `Agent` class (extends Weave `Model`)
  - `__init__(**data)` accepts arbitrary kwargs (Pydantic model)
  - Already validates all parameters via Pydantic Field definitions
  - Already handles MCP config via `self.mcp` field
  - Uses `ToolManager` to process tools list
  - No class methods currently exist for alternative construction

#### CLI Implementation  
- **`tyler/cli/chat.py`** (~720 lines)
  - `load_config(config_file: Optional[str])` function (lines 530-656)
    - Searches standard locations if no path provided
    - Loads YAML/JSON
    - Substitutes environment variables (`${VAR_NAME}` pattern)
    - Processes custom tool files
    - Returns dict ready for `Agent(**config)`
  - `load_custom_tool(file_path: str)` function (lines 502-528)
    - Imports Python file as module
    - Extracts `TOOLS` list
    - Returns tool definitions
  - `ChatManager.initialize_agent(config: Dict)` (line 142-149)
    - Simply calls `self.agent = Agent(**config)`
    - Auto-connects to MCP if `config["mcp"]` exists

#### MCP Configuration
- **`tyler/mcp/config_loader.py`** (288 lines)
  - `_substitute_env_vars(obj)` - Recursive env var substitution
  - `_validate_mcp_config(config)` - Schema validation (called from Agent.__init__)
  - `_load_mcp_config(config)` - Connects to servers, returns tools
  - Pattern: ${VAR_NAME} substitution with fallback to original if not found

#### Package Exports
- **`tyler/__init__.py`** (15 lines)
  - Currently exports: `Agent`, `AgentResult`, `ExecutionEvent`, `EventType`
  - Re-exports from narrator: `Thread`, `Message`, `ThreadStore`, `FileStore`, `Attachment`
  - No config-related exports yet

### Existing Data Models

#### Agent Parameters (from agent.py)
```python
model_name: str = "gpt-4.1"
api_base: Optional[str] = None
api_key: Optional[str] = None  
extra_headers: Optional[Dict[str, str]] = None
temperature: float = 0.7
drop_params: bool = True
reasoning: Optional[Union[str, Dict[str, Any]]] = None
name: str = "Tyler"
purpose: Union[str, Prompt] = "To be a helpful assistant."
notes: Union[str, Prompt] = ""
version: str = "1.0.0"
tools: List[Union[str, Dict, Callable, types.ModuleType]] = []
max_tool_iterations: int = 10
agents: List["Agent"] = []
thread_store: Optional[ThreadStore] = None
file_store: Optional[FileStore] = None
mcp: Optional[Dict[str, Any]] = None
step_errors_raise: bool = False
```

#### Config File Format (YAML)
```yaml
name: "Tyler"
purpose: "..."
notes: "..."
model_name: "gpt-4.1"
temperature: 0.7
max_tool_iterations: 10
reasoning: "low"  # or dict
tools:
  - "web"           # Built-in module name
  - "./my_tools.py" # Custom tool file path
mcp:
  servers:
    - name: "docs"
      transport: "streamablehttp"
      url: "https://..."
```

### External Contracts

#### Agent Construction (existing)
```python
# Direct construction (current, continues to work)
agent = Agent(name="Tyler", model_name="gpt-4o", tools=["web"])
```

#### CLI Config Loading (current)
```bash
# CLI searches standard locations
tyler-chat

# Or explicit config
tyler-chat --config ./my-config.yaml
```

### Observability Currently Available
- Standard Python logging via `tyler.utils.logging.get_logger()`
- Weave tracing for Agent operations (if WANDB_PROJECT set)
- CLI uses Rich console for user-facing messages
- No specific config loading metrics tracked

## 4. Proposed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  tyler/__init__.py                              │
│  - Export: Agent, load_config                   │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
┌───────────────────┐      ┌──────────────────────┐
│  tyler/config.py  │      │  tyler/models/       │
│  (NEW)            │      │  agent.py            │
│                   │      │                      │
│  - load_config()  │◄─────│  + from_config()    │
│  - load_custom... │      │    (NEW)             │
│  - resolve_path() │      │                      │
│  - SEARCH_PATHS   │      │  __init__(**data)    │
└───────────────────┘      │    (unchanged)       │
        ▲                  └──────────────────────┘
        │
┌───────┴──────────┐
│  tyler/cli/      │
│  chat.py         │
│                  │
│  (refactored to  │
│   use shared     │
│   load_config)   │
└──────────────────┘
```

### Component Responsibilities

#### 1. `tyler/config.py` (NEW)
**Purpose**: Public API for loading Tyler config files

**Public Functions**:
```python
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load and process a Tyler configuration file.
    
    Search order when config_path is None:
    1. ./tyler-chat-config.yaml
    2. ~/.tyler/chat-config.yaml
    3. /etc/tyler/chat-config.yaml
    
    Processing:
    - Load YAML file (.yaml or .yml extension required)
    - Substitute environment variables (${VAR_NAME})
    - Load custom tool files (resolve relative paths to config dir)
    - Return dict ready for Agent(**config)
    
    Raises:
        FileNotFoundError: If explicit path not found
        ValueError: If no config in standard locations (path=None) or invalid file extension
        yaml.YAMLError: If invalid YAML syntax
    """
```

```python
def load_custom_tool(file_path: str, config_dir: Path) -> List[Dict]:
    """
    Load custom tools from a Python file.
    
    Expects file to have TOOLS list of dicts with:
    - definition: OpenAI function definition
    - implementation: callable
    - attributes: optional metadata
    
    Args:
        file_path: Path to .py file (may be relative)
        config_dir: Directory containing config (for relative path resolution)
    
    Returns:
        List of tool dicts
        
    Raises:
        ImportError: If module can't be loaded
        AttributeError: If TOOLS not found in module
    """
```

**Internal Functions**:
```python
def _resolve_config_path(config_path: Optional[str]) -> Path:
    """
    Resolve config file path.
    
    If config_path provided: resolve and validate exists
    If None: search standard locations, raise if not found
    """

def _substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute ${VAR_NAME} in config values.
    
    Reuse pattern from tyler/mcp/config_loader.py
    Returns original string if env var not found.
    """

def _process_tools_list(
    tools: List[Any], 
    config_dir: Path
) -> List[Any]:
    """
    Process tools list: load custom files, pass through built-ins.
    
    For each tool:
    - If string with path chars: load_custom_tool()
    - Else: pass through unchanged (built-in module name or dict)
    """
```

**Constants**:
```python
CONFIG_SEARCH_PATHS: List[Path] = [
    Path.cwd() / "tyler-chat-config.yaml",
    Path.home() / ".tyler" / "chat-config.yaml",
    Path("/etc/tyler/chat-config.yaml",
]
```

#### 2. `tyler/models/agent.py` (MODIFIED)
**Changes**: Add class method only

```python
@classmethod
def from_config(
    cls,
    config_path: Optional[str] = None,
    **overrides
) -> "Agent":
    """
    Create Agent from YAML/JSON config file.
    
    Args:
        config_path: Path to config. None = auto-discover
        **overrides: Override any config values
        
    Returns:
        Agent instance
        
    Example:
        agent = Agent.from_config()
        agent = Agent.from_config("config.yaml", temperature=0.9)
    """
    from tyler.config import load_config
    
    # Load config
    config = load_config(config_path)
    
    # Apply overrides (dict update - replacement semantics)
    config.update(overrides)
    
    # Create agent using standard __init__
    return cls(**config)
```

**No other changes to Agent class** - All validation, tool processing, etc. happens in existing `__init__`.

#### 3. `tyler/cli/chat.py` (REFACTORED)
**Changes**: Replace local functions with imports

```python
# OLD (delete ~150 lines)
def load_config(config_file: Optional[str]) -> Dict[str, Any]:
    # ... 126 lines ...

def load_custom_tool(file_path: str) -> list:
    # ... 26 lines ...

# NEW (add imports)
from tyler.config import load_config, load_custom_tool

# ChatManager.initialize_agent() - UNCHANGED
async def initialize_agent(self, config: Dict[str, Any] = None) -> None:
    if config is None:
        config = {}
    self.agent = Agent(**config)  # Still works!
    # ... MCP auto-connect logic unchanged ...
```

**Behavior**: Identical to current CLI, just uses shared code.

#### 4. `tyler/__init__.py` (MODIFIED)
**Changes**: Add export

```python
from tyler.config import load_config

# Now available:
# from tyler import Agent, load_config
```

### Interfaces & Data Contracts

#### Public API
```python
# Simple usage
from tyler import Agent
agent = Agent.from_config()

# Advanced usage  
from tyler import load_config
config = load_config("config.yaml")
config["temperature"] = 0.9
agent = Agent(**config)
```

#### Config Schema
No changes - existing YAML format works as-is. See section 3 for schema.
**Note**: YAML only - JSON not supported for simplicity and consistency.

### Error Handling

#### Config File Not Found
```python
# Explicit path
agent = Agent.from_config("/nonexistent.yaml")
# Raises: FileNotFoundError with clear message

# Auto-discovery
agent = Agent.from_config()  # No configs in standard locations
# Raises: ValueError("No config file found in: ./tyler-chat-config.yaml, ...")
```

#### Invalid YAML
```python
agent = Agent.from_config("invalid.yaml")
# Raises: yaml.YAMLError (from PyYAML) with line number
```

#### Invalid File Extension
```python
agent = Agent.from_config("config.json")
# Raises: ValueError("Config file must be .yaml or .yml, got .json")
```

#### Invalid Agent Parameters
```python
# Config has temperature = "not-a-number"
agent = Agent.from_config("bad-config.yaml")
# Raises: pydantic.ValidationError (from Agent.__init__)
```

#### Custom Tool Loading Failure
```python
# Config references ./missing_tools.py
agent = Agent.from_config("config.yaml")
# Logs warning, skips tool (matches current CLI behavior)
# Agent still created, just without that tool
```

### Idempotency
- Config loading is read-only (idempotent)
- Multiple calls with same config produce equivalent agents
- No side effects except tool module imports (same as current Agent creation)

### Performance Expectations
- Config load: <10ms for typical configs (<10KB YAML)
- Custom tool import: Depends on tool file (same as current CLI)
- Overall: Negligible overhead vs direct Agent() construction

## 5. Alternatives Considered

### Option A: Config Loading Only (No Class Method)
**Approach**: Export `load_config()` but no `Agent.from_config()`

```python
from tyler import Agent, load_config
config = load_config("config.yaml")
agent = Agent(**config)
```

**Pros**:
- Simpler (fewer lines of code)
- More explicit (clear two-step process)

**Cons**:
- Less convenient (extra import, extra line)
- Less discoverable (class method is more Pythonic)
- Doesn't match common pattern (e.g., `dict.fromkeys()`, `datetime.fromisoformat()`)

**Decision**: ❌ Rejected - Class method provides better DX

### Option B: Config Module in utils (tyler/utils/config.py)
**Approach**: Put config.py in utils/ instead of top-level

**Pros**:
- Groups with other utilities
- Matches some existing patterns

**Cons**:
- Longer import: `from tyler.utils.config import load_config`
- Signals "internal" rather than "public API"
- Less discoverable for users

**Decision**: ❌ Rejected - This is public API, deserves top-level module

### Option C: Auto-Connect MCP Servers
**Approach**: `from_config()` automatically calls `await agent.connect_mcp()`

**Pros**:
- More convenient (one step instead of two)
- Matches CLI behavior completely

**Cons**:
- Requires async class method (more complex)
- Implicit side effects (network connections)
- Users might not want immediate connection
- Breaks "configuration vs initialization" separation

**Decision**: ❌ Rejected per user preference - No auto-connect

### Option D: Merge Tool Lists on Override
**Approach**: `Agent.from_config("config.yaml", tools=["extra"])` adds to config tools

**Pros**:
- Allows extending config without modifying file
- Might be convenient for some use cases

**Cons**:
- Different semantics than other overrides
- More complex to implement and explain
- Can achieve same result by loading config manually

**Decision**: ❌ Rejected per user preference - Simple replacement semantics

### **Chosen Design: Simple & Pythonic**
- Public `tyler/config.py` module
- `Agent.from_config()` class method
- No auto-connect
- Replacement semantics for overrides
- **Why**: Best balance of convenience, discoverability, and simplicity

## 6. Data Model & Contract Changes

### No Database/Persistent Changes
This feature has no database, migrations, or persistent state changes.

### API Changes (Pure Additive)

#### New Public API
```python
# tyler/config.py
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and process Tyler config file"""

# tyler/models/agent.py
class Agent(Model):
    @classmethod
    def from_config(cls, config_path: Optional[str] = None, **overrides) -> "Agent":
        """Create Agent from config file"""
```

#### Existing API (Unchanged)
```python
# All existing Agent usage continues to work
agent = Agent(name="Tyler", model_name="gpt-4o")  # ✅ Still works
agent.go(thread)  # ✅ Still works
```

### Backward Compatibility
- ✅ 100% backward compatible
- ✅ No breaking changes
- ✅ Existing code requires zero modifications
- ✅ CLI behavior unchanged (internal refactor transparent)

### Deprecation Plan
- N/A - No APIs being deprecated

## 7. Security, Privacy, Compliance

### Authentication/Authorization
- ✅ No changes to AuthN/AuthZ
- ✅ Config files are local user files (trust model unchanged)
- ✅ Environment variable substitution already exists (CLI, MCP config)

### Secrets Management
- ✅ Pattern: Secrets in env vars, referenced as `${API_KEY}` in config
- ✅ No secrets stored in config files (existing best practice)
- ✅ Warning in docs: "Never commit API keys to version control"

### Threat Model

#### Threat: Malicious Config File
**Scenario**: Attacker provides malicious config with custom tool files
```yaml
tools:
  - "/tmp/malicious_tools.py"  # Contains evil code
```

**Mitigation**:
- ✅ Trust model: Users must trust config files (same as CLI)
- ✅ Documentation: "Only load configs from trusted sources"
- ✅ No new attack vector (CLI already allows this)

#### Threat: Path Traversal
**Scenario**: Config tries to load tools from unexpected locations
```yaml
tools:
  - "../../../etc/passwd"  # Path traversal attempt
```

**Mitigation**:
- ✅ Python import system provides natural protection
- ✅ Only .py files can be imported (others fail safely)
- ✅ No special handling needed (existing behavior)

#### Threat: Environment Variable Leakage
**Scenario**: Config accidentally logs sensitive env vars

**Mitigation**:
- ✅ Env var values not logged (only substitution events)
- ✅ Existing logging guidelines: "No PII/secrets in logs"
- ✅ Pattern already used in MCP config (proven safe)

### Privacy
- ✅ No PII collected or transmitted
- ✅ Config files are local only
- ✅ No new telemetry or tracking

### Compliance
- ✅ No compliance impact (local functionality only)
- ✅ No data retention concerns

## 8. Observability & Operations

### Logging Strategy

#### Log Levels & Events

**INFO - Success Path**
```python
logger.info(f"Loading config from {config_path}")
logger.info(f"Loaded {len(tools)} custom tools from {tool_file}")
logger.info(f"Created agent '{name}' from config")
```

**WARNING - Recoverable Issues**
```python
logger.warning(f"Config file not found at {path}, trying next location")
logger.warning(f"Failed to load custom tool from {tool_file}: {error}")
logger.warning(f"Environment variable {var_name} not found, using literal value")
```

**DEBUG - Detailed Flow**
```python
logger.debug(f"Searching for config in: {CONFIG_SEARCH_PATHS}")
logger.debug(f"Resolved relative path {rel_path} to {abs_path}")
logger.debug(f"Config overrides applied: {list(overrides.keys())}")
logger.debug(f"Substituted env vars: {substituted_vars}")
```

**ERROR - Failures**
```python
logger.error(f"Invalid YAML in config file {path}: {error}")
logger.error(f"Failed to import custom tool module {module_path}: {error}")
```

### Metrics
**Not implementing metrics** for this feature because:
- Config loading is infrequent (agent initialization only)
- Errors surface immediately to users (fail-fast)
- No production/SRE concerns (library code, not service)

**Future consideration**: Could add Weave tracking:
- Count of `from_config()` vs direct `Agent()` usage
- Config file paths used (for debugging)
- Would require Weave integration (out of scope for this PR)

### Dashboards & Alerts
- ✅ Not applicable (library code, not deployed service)
- ✅ No SLAs or uptime concerns
- ✅ Errors appear in user code (Python exceptions)

### Runbooks
Not needed - failures are immediate and self-explanatory:
- FileNotFoundError → Check config path
- YAML/JSON errors → Fix syntax
- ValidationError → Fix config values

## 9. Rollout & Migration

### Feature Flags
- ✅ Not needed - Pure additive API
- ✅ No runtime configuration required
- ✅ Users opt-in by using new API

### Migration Strategy

#### Phase 1: Release (Immediate)
- Deploy new `tyler` package version
- Update documentation
- Add examples

#### Phase 2: Adoption (Gradual)
- Users discover via docs
- Gradually migrate to config-based approach (optional)
- No forced migration

#### Example Migration (Optional)
```python
# Before (still works!)
agent = Agent(
    name="MyAgent",
    model_name="gpt-4o",
    temperature=0.7,
    tools=["web"]
)

# After (optional)
# 1. Create config.yaml with same values
# 2. Replace with:
agent = Agent.from_config("config.yaml")
```

### Rollback Plan

#### If Critical Bug Found
1. **Patch release** with bug fix (preferred)
2. **Document workaround** for users
3. **Deprecate in next major** (last resort)

#### Rollback Complexity: LOW
- No database migrations to revert
- No deployed services to roll back
- Users can simply not use new API
- CLI refactor is internal (can be reverted independently)

### Blast Radius
- ✅ Minimal - Only affects users who opt-in to new API
- ✅ Existing usage unaffected
- ✅ CLI users unaffected (internal refactor transparent)

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
1. ✅ Write failing test first for each acceptance criterion
2. ✅ Confirm test fails (proves test is valid)
3. ✅ Implement minimal code to pass
4. ✅ Refactor while keeping tests green
5. ✅ Commit order: `test:` → `feat:` → `refactor:`

### Spec → Test Mapping

#### Config Loading Tests (`tests/test_config.py`)

| Spec AC | Test ID | Description | Type |
|---------|---------|-------------|------|
| AC-1 | `test_load_config_from_current_directory` | Load from ./tyler-chat-config.yaml | Unit |
| AC-2 | `test_load_config_from_explicit_path` | Load from /path/to/config.yaml | Unit |
| AC-3 | `test_load_config_substitutes_env_vars` | ${API_KEY} → env value | Unit |
| AC-4 | `test_load_config_loads_custom_tools` | Load custom tool files | Unit |
| AC-5 | `test_load_config_preserves_mcp_config` | MCP config in returned dict | Unit |
| AC-6 | `test_load_config_missing_file_explicit_path` | FileNotFoundError on missing | Unit |
| AC-7 | `test_load_config_missing_file_auto_discover` | ValueError with search paths | Unit |
| AC-8 | `test_load_config_invalid_yaml` | yaml.YAMLError on syntax error | Unit |
| AC-9 | `test_load_config_missing_env_var_preserved` | ${MISSING} stays as literal | Unit |
| AC-10 | `test_load_custom_tool_relative_path` | Resolve ./tool relative to config | Unit |
| AC-11 | `test_load_custom_tool_absolute_path` | Handle absolute paths | Unit |
| AC-12 | `test_load_custom_tool_home_path` | Expand ~/tools/custom.py | Unit |
| AC-13 | `test_load_custom_tool_missing_file` | Log warning, skip tool | Unit |
| AC-14 | `test_load_config_invalid_extension` | ValueError for .json or other | Unit |
| AC-15 | `test_load_config_search_order` | Try cwd → home → /etc | Unit |

#### Agent.from_config Tests (`tests/models/test_agent_from_config.py`)

| Spec AC | Test ID | Description | Type |
|---------|---------|-------------|------|
| AC-16 | `test_agent_from_config_basic` | Create agent from config | Unit |
| AC-17 | `test_agent_from_config_auto_discover` | No path → search locations | Unit |
| AC-18 | `test_agent_from_config_explicit_path` | Specific config file | Unit |
| AC-19 | `test_agent_from_config_with_overrides` | Override temperature, model | Unit |
| AC-20 | `test_agent_from_config_tools_replaced_not_merged` | tools kwarg replaces config | Unit |
| AC-21 | `test_agent_from_config_mcp_preserved_not_connected` | MCP config set, not connected | Unit |
| AC-22 | `test_agent_from_config_all_params_applied` | Name, purpose, notes, etc | Unit |
| AC-23 | `test_agent_from_config_custom_tools_loaded` | Custom tool in agent._processed_tools | Unit |
| AC-24 | `test_agent_from_config_env_vars_substituted` | ${VAR} in config → value in agent | Unit |
| AC-25 | `test_agent_from_config_invalid_params` | pydantic.ValidationError raised | Unit |

#### CLI Refactor Tests (verify no regression)

| Spec AC | Test ID | Description | Type |
|---------|---------|-------------|------|
| AC-26 | `test_cli_loads_config_with_refactored_code` | CLI still works | Integration |
| AC-27 | `test_cli_custom_tools_still_work` | Tool loading unchanged | Integration |
| AC-28 | `test_cli_env_vars_still_work` | Env substitution unchanged | Integration |

### Test Tiers

#### Unit Tests
- **Config loading logic** - Mock file system, test parsing
- **Agent.from_config()** - Mock load_config, test method logic  
- **Path resolution** - Test relative/absolute/home paths
- **Env var substitution** - Test ${VAR} → value logic
- **Custom tool loading** - Mock module imports

#### Integration Tests
- **CLI refactor** - Existing CLI tests continue to pass
- **Example files** - New example runs without errors
- **Real config files** - Load actual tyler-chat-config.yaml

#### E2E Tests
- Not needed - This is library code, not deployed service
- User's integration tests will cover their specific use cases

### Negative & Edge Cases

| Test ID | Negative Case | Expected Behavior |
|---------|---------------|-------------------|
| `test_config_file_not_found` | Missing file | FileNotFoundError with path |
| `test_config_invalid_yaml_syntax` | Bad YAML | yaml.YAMLError with line # |
| `test_config_invalid_extension` | .json/.txt file | ValueError with message |
| `test_config_invalid_agent_params` | Wrong types | pydantic.ValidationError |
| `test_custom_tool_file_missing` | Tool file gone | Warning logged, agent created |
| `test_custom_tool_no_tools_list` | Missing TOOLS | Warning logged, skip file |
| `test_env_var_not_set` | ${MISSING_VAR} | Literal "${MISSING_VAR}" used |
| `test_empty_config_file` | Empty YAML | Agent with defaults created |
| `test_config_with_unknown_keys` | Extra keys | Pydantic extra='allow' accepts |

### Performance Tests
Not needed for this feature:
- Config loading is one-time, non-critical path
- No performance SLAs
- YAML parsing is already fast (<10ms typical)

### CI Requirements
- ✅ All tests run in CI (pytest)
- ✅ Must pass to merge
- ✅ Coverage target: >90% for new code
- ✅ Linting: ruff, mypy pass

### Test File Structure
```
tests/
├── test_config.py                    # NEW - Config loading tests (AC-1 to AC-15)
└── models/
    └── test_agent_from_config.py     # NEW - Agent.from_config tests (AC-16 to AC-25)

# Existing tests that should still pass:
tests/
├── models/
│   ├── test_agent.py                 # No changes, all should pass
│   ├── test_agent_mcp.py             # No changes, all should pass
│   └── test_agent_tools.py           # No changes, all should pass
└── cli/
    └── test_chat.py                  # Refactored code, should still pass (AC-26 to AC-28)
```

## 11. Risks & Open Questions

### Known Risks

#### Risk 1: Custom Tool Import Side Effects
**Issue**: Importing custom tool files could have side effects
```python
# bad_tool.py
print("Loading...")  # Side effect on import
TOOLS = [...]
```

**Likelihood**: LOW (users control their tool files)  
**Impact**: LOW (cosmetic - unexpected output)  
**Mitigation**: 
- Document: "Custom tool files should not have side effects on import"
- Existing CLI has same issue (no worse than current state)

#### Risk 2: Path Resolution Confusion
**Issue**: Relative paths resolved to config dir, not cwd
```yaml
tools:
  - "./my_tools.py"  # Relative to config file, not cwd
```

**Likelihood**: MEDIUM (might confuse some users)  
**Impact**: LOW (error message will guide users)  
**Mitigation**:
- Document clearly: "Relative paths are relative to config file location"
- Error message includes full resolved path
- Same behavior as CLI (consistent)

#### Risk 3: Environment Variable Confusion
**Issue**: Missing env vars return literal string, not error
```yaml
api_key: "${OPENAI_API_KEY}"  # If not set → literal "${OPENAI_API_KEY}"
```

**Likelihood**: MEDIUM (easy to miss typo in var name)  
**Impact**: LOW (API calls will fail with clear auth error)  
**Mitigation**:
- Document: "Check env var names carefully"
- Warning log when var not found
- Same behavior as MCP config (consistent)

### Open Questions

#### Q1: Add config source to Weave metadata?
**Question**: Should Agent track which config file created it?

**Options**:
- A) Add `_config_source: Optional[str]` private attr to Agent
- B) Don't track (minimal approach)

**Recommendation**: Option A
- **Why**: Helpful for debugging in Weave UI
- **Cost**: One extra field (negligible)
- **Implementation**: `self._config_source = config_path` in from_config()

**Decision needed**: User approval ✅ Proceed with Option A

#### Q2: JSON file support?
**Question**: Should we support JSON config files at all?

**Options**:
- A) YAML only - Reject .json files with clear error
- B) Support both YAML and JSON

**Decision**: ✅ Option A - YAML-only (user approved)
- **Why**: YAML more human-friendly for config (comments, multi-line)
- **Why**: Simplicity (no format detection logic)
- **Why**: No evidence of JSON usage in codebase
- **Why**: Clearer expectations ("Tyler configs are YAML")
- **Implementation**: Validate file extension, raise ValueError for non-YAML

#### Q3: Validate custom tool files exist before loading?
**Question**: Check file existence before importing?

**Options**:
- A) Pre-validate (check Path.exists())
- B) Try to load, handle ImportError (current CLI)

**Recommendation**: Option B
- **Why**: File might exist but import fail anyway (syntax error, deps)
- **Why**: Simpler code (one error path, not two)
- **Why**: Matches current CLI behavior

**Decision needed**: User approval ✅ Proceed with Option B

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

#### Milestone 1: Core Config Loading (2-3 hours)
**Tasks**:
1. ✅ Create `/tests/test_config.py` with failing tests (AC-1 to AC-15)
2. ✅ Create `/tyler/config.py` module
3. ✅ Implement `load_config()` function
4. ✅ Implement `load_custom_tool()` function
5. ✅ Implement `_substitute_env_vars()` helper
6. ✅ Implement `_resolve_config_path()` helper
7. ✅ Implement `_process_tools_list()` helper
8. ✅ All tests in `test_config.py` pass
9. ✅ Code coverage >90%

**DoD**:
- [ ] All 15 config loading tests passing
- [ ] Linting passes (ruff, mypy)
- [ ] Coverage >90% for tyler/config.py
- [ ] Docstrings complete

**Commit sequence**:
```bash
git commit -m "test: add failing tests for config loading (AC-1 to AC-15)"
git commit -m "feat: implement load_config() function"
git commit -m "feat: implement custom tool loading"
git commit -m "refactor: extract env var substitution helper"
```

#### Milestone 2: Agent.from_config() (1 hour)
**Tasks**:
1. ✅ Create `/tests/models/test_agent_from_config.py` with failing tests (AC-16 to AC-25)
2. ✅ Add `Agent.from_config()` class method to `/tyler/models/agent.py`
3. ✅ All tests pass

**DoD**:
- [ ] All 10 from_config tests passing
- [ ] Linting passes
- [ ] Coverage >90% for new code
- [ ] Docstrings complete

**Commit sequence**:
```bash
git commit -m "test: add failing tests for Agent.from_config() (AC-16 to AC-25)"
git commit -m "feat: add Agent.from_config() class method"
```

#### Milestone 3: CLI Refactor (1 hour)
**Tasks**:
1. ✅ Refactor `/tyler/cli/chat.py` to use shared load_config
2. ✅ Delete local load_config() and load_custom_tool()
3. ✅ Add imports from tyler.config
4. ✅ Verify all existing CLI tests pass (AC-26 to AC-28)

**DoD**:
- [ ] CLI tests pass (no regression)
- [ ] Code reduced by ~150 lines
- [ ] Behavior identical to before
- [ ] Linting passes

**Commit sequence**:
```bash
git commit -m "refactor: migrate CLI to use shared config loading"
```

#### Milestone 4: Package Exports (15 minutes)
**Tasks**:
1. ✅ Update `/tyler/__init__.py` to export load_config
2. ✅ Verify imports work: `from tyler import Agent, load_config`

**DoD**:
- [ ] Public API exports correct
- [ ] Import test passes

**Commit sequence**:
```bash
git commit -m "feat: export load_config from tyler package"
```

#### Milestone 5: Documentation & Examples (1-2 hours)
**Tasks**:
1. ✅ Create `/packages/tyler/examples/003_agent_from_config.py`
2. ✅ Update `/docs/guides/your-first-agent.mdx`
3. ✅ Update `/docs/api-reference/tyler-agent.mdx`
4. ✅ Update `/packages/tyler/README.md`
5. ✅ Add docstrings to all new functions
6. ✅ Run example to verify it works

**DoD**:
- [ ] Example runs successfully
- [ ] Documentation clear and accurate
- [ ] All public APIs documented
- [ ] README updated with quick example

**Commit sequence**:
```bash
git commit -m "docs: add Agent.from_config() examples and docs"
git commit -m "docs: update API reference for config loading"
```

#### Milestone 6: Final Testing & Polish (30 minutes)
**Tasks**:
1. ✅ Run full test suite
2. ✅ Check coverage report (>90% for new code)
3. ✅ Run linters (ruff, mypy)
4. ✅ Manual smoke test: Load CLI config, create agent, verify tools
5. ✅ Review PR description and commits

**DoD**:
- [ ] All tests passing
- [ ] Coverage >90%
- [ ] Linting clean
- [ ] PR description complete
- [ ] Conventional commits followed

### Total Estimated Time: 6-8 hours

### Dependencies
- ✅ No external dependencies (all packages already available)
- ✅ No team dependencies (self-contained feature)
- ✅ No infrastructure changes needed

### Review Checkpoints
1. ✅ Spec approved (DONE)
2. ✅ Impact Analysis approved (DONE)
3. ⏳ TDR approved (PENDING)
4. ⏳ Implementation complete
5. ⏳ Tests passing
6. ⏳ Documentation complete
7. ⏳ PR reviewed and merged

---

## Approval Gate

**Status**: ⏳ Awaiting approval

**Reviewer**: Please review and approve before implementation begins.

**Questions for Reviewer**:
1. Approve Open Question Q1? (Add config source to Weave metadata)
2. Approve Open Question Q2? (YAML-only auto-discovery)
3. Approve Open Question Q3? (No pre-validation of custom tool files)
4. Any concerns with the proposed design?
5. Any missing test cases?

**Once approved, implementation will proceed following strict TDD workflow.**

