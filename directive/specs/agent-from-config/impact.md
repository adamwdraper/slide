# Impact Analysis — Agent.from_config()

## Modules/packages likely touched

### New Files
- **`/packages/tyler/tyler/config.py`** (NEW)
  - Extract and enhance `load_config()` from CLI
  - Extract `load_custom_tool()` from CLI
  - New `_resolve_config_path()` helper
  - Environment variable substitution (reuse from MCP config loader)
  - Public exports: `load_config()`, standard search paths constant

### Modified Files

#### Core Agent Implementation
- **`/packages/tyler/tyler/models/agent.py`**
  - Add `Agent.from_config()` class method
  - No changes to `__init__()` required (already accepts **kwargs)

#### Package Exports
- **`/packages/tyler/tyler/__init__.py`**
  - Export `load_config()` function for advanced usage
  - Optionally export `CONFIG_SEARCH_PATHS` constant

#### CLI Refactor (Code Reuse)
- **`/packages/tyler/tyler/cli/chat.py`**
  - Replace local `load_config()` with import from `tyler.config`
  - Replace local `load_custom_tool()` with import from `tyler.config`
  - Reduce code duplication (~150 lines extracted)

### Test Files
- **`/packages/tyler/tests/test_config.py`** (NEW)
  - Test `load_config()` with various scenarios
  - Test environment variable substitution
  - Test custom tool loading
  - Test path resolution (relative, absolute, home directory)
  - Test error handling (missing files, invalid YAML, etc.)

- **`/packages/tyler/tests/models/test_agent_from_config.py`** (NEW)
  - Test `Agent.from_config()` with valid configs
  - Test parameter overrides
  - Test auto-discovery of config files
  - Test MCP config preservation (without auto-connect)
  - Test tool loading from config
  - Test error scenarios

### Documentation
- **`/docs/guides/your-first-agent.mdx`**
  - Add section on config-based agent creation
  - Show both approaches (Python vs config)

- **`/docs/api-reference/tyler-agent.mdx`**
  - Document `Agent.from_config()` class method
  - Document `load_config()` function

- **`/packages/tyler/README.md`**
  - Add quick example of config-based usage

### Examples
- **`/packages/tyler/examples/003_agent_from_config.py`** (NEW)
  - Basic config loading example
  - Auto-discovery example
  - Parameter override example
  - Advanced usage with custom config manipulation

## Contracts to update (APIs, events, schemas, migrations)

### Public API Additions

#### New Class Method
```python
@classmethod
def from_config(
    cls,
    config_path: Optional[str] = None,
    **overrides
) -> "Agent":
    """Create an Agent from a YAML/JSON config file.
    
    Args:
        config_path: Path to config file. If None, searches standard locations:
                    1. ./tyler-chat-config.yaml (current directory)
                    2. ~/.tyler/chat-config.yaml (user home)
                    3. /etc/tyler/chat-config.yaml (system-wide)
        **overrides: Override any config values (e.g., temperature=0.9)
    
    Returns:
        Agent instance initialized with config values
        
    Raises:
        FileNotFoundError: If config_path specified but not found
        ValueError: If config file has invalid syntax or schema
    
    Examples:
        >>> agent = Agent.from_config()  # Auto-discover
        >>> agent = Agent.from_config("./config.yaml")
        >>> agent = Agent.from_config("config.yaml", temperature=0.9)
    """
```

#### New Public Function
```python
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load and process a Tyler config file.
    
    Args:
        config_path: Path to YAML/JSON config file. If None, searches
                    standard locations.
    
    Returns:
        Processed config dict with:
        - Environment variables substituted
        - Custom tools loaded
        - Relative paths resolved
        
    Raises:
        FileNotFoundError: If config_path specified but not found
        ValueError: If no config found in standard locations (when path=None) or invalid file extension
        yaml.YAMLError: If YAML syntax is invalid
    
    Examples:
        >>> config = load_config("config.yaml")
        >>> config["temperature"] = 0.9  # Modify
        >>> agent = Agent(**config)
    """
```

#### New Constant
```python
CONFIG_SEARCH_PATHS: List[Path] = [
    Path.cwd() / "tyler-chat-config.yaml",
    Path.home() / ".tyler" / "chat-config.yaml",
    Path("/etc/tyler/chat-config.yaml")
]
```

### Schema/Config Format
No changes to existing YAML config format. Existing `tyler-chat-config.yaml` files work as-is.
**Note**: YAML-only (no JSON support) for simplicity and consistency.

### Backward Compatibility
- ✅ No breaking changes to `Agent.__init__()` 
- ✅ Existing code continues to work unchanged
- ✅ CLI behavior unchanged (code refactored but logic identical)
- ✅ Pure additive API (new class method, new exported function)

## Risks

### Security
**LOW RISK** - No new security surface
- ✅ Environment variable substitution already exists (MCP config, CLI)
- ✅ Custom tool loading already exists (CLI)
- ✅ File path resolution already exists (CLI)
- ⚠️ **Mitigation**: Document that config files may execute custom tool code - users should trust config files
- ⚠️ **Mitigation**: Path traversal already handled by pathlib (no new vulnerability)

### Performance/Availability
**LOW RISK** - Minimal performance impact
- ✅ Config loading is one-time at agent initialization
- ✅ YAML parsing is fast for typical config sizes (<10KB)
- ✅ Custom tool imports happen synchronously (same as current CLI behavior)
- ⚠️ **Watch**: Custom tool file loading could be slow if files are large or have heavy imports
- ✅ **Mitigation**: This is existing behavior from CLI; no worse than current state

### Data integrity
**MINIMAL RISK** - No data persistence
- ✅ Config loading is read-only operation
- ✅ No database or persistent state changes
- ✅ Agent initialization is already validated by Pydantic
- ⚠️ **Edge case**: Invalid config could create misconfigured agent
- ✅ **Mitigation**: Pydantic validation in Agent.__init__() catches invalid configs

### Code Quality/Maintainability
**POSITIVE IMPACT** - Reduces duplication
- ✅ Eliminates ~150 lines of duplicated code between CLI and new module
- ✅ Single source of truth for config loading logic
- ✅ Better testability (config loading testable independently)
- ✅ Consistent behavior between CLI and Python usage

### Breaking Changes
**NONE** - Pure additive change
- ✅ No changes to existing Agent API surface
- ✅ CLI refactored but behavior unchanged
- ✅ All existing examples/tests continue to work

## Observability needs

### Logs
**Reuse existing logger** (`tyler.utils.logging.get_logger`)

#### New log points in `tyler/config.py`:
```python
# INFO level
logger.info(f"Loading config from {config_path}")
logger.info(f"Loaded {len(tools)} custom tools from {tool_file}")
logger.info(f"Substituted {count} environment variables in config")

# WARNING level  
logger.warning(f"Config file not found at {path}, trying next location")
logger.warning(f"Failed to load custom tool from {tool_file}: {error}")

# DEBUG level
logger.debug(f"Searching for config in: {search_paths}")
logger.debug(f"Resolved relative path {rel_path} to {abs_path}")
```

#### Modified log points in `tyler/models/agent.py`:
```python
# Add to Agent.from_config()
logger.info(f"Creating agent from config: {config_path or 'auto-discovered'}")
logger.debug(f"Config overrides: {overrides}")
```

### Metrics
**Not required** - Config loading is infrequent (agent initialization only)

Optional future enhancement:
- Count of `Agent.from_config()` vs direct `Agent()` usage (would require Weave integration)

### Alerts
**Not required** - No production/runtime concerns
- Config loading errors are immediate (fail-fast at initialization)
- Users will see exceptions directly in their code

### Observability Integration
- ✅ Leverage existing Weave tracing (already tracks Agent initialization)
- ✅ Config load errors will appear in stack traces
- ⚠️ Consider: Should we add config file path to Agent metadata for Weave UI?
  - Would help debugging: "Which config created this agent?"
  - Can add to Agent's Weave model representation

## Dependencies

### New Dependencies
**NONE** - All required packages already in use:
- ✅ `pyyaml` - Already required (used in CLI)
- ✅ `pathlib` - Standard library
- ✅ `typing` - Standard library

### Modified Dependencies
**NONE**

## Migration Path

### For CLI Users
**NO ACTION REQUIRED**
- CLI behavior unchanged
- Existing configs work as-is

### For Python Users
**OPTIONAL ADOPTION**
- Existing `Agent()` usage continues to work
- Can gradually migrate to `Agent.from_config()` if desired

### Example Migration
```python
# Before (still works!)
agent = Agent(
    name="MyAgent",
    model_name="gpt-4o",
    temperature=0.7,
    tools=["web", "slack"]
)

# After (optional, if you prefer config files)
# Create config.yaml once, then:
agent = Agent.from_config("config.yaml")
```

## Testing Strategy

### Unit Tests
1. **Config Loading** (`test_config.py`)
   - Valid YAML/JSON loading
   - Environment variable substitution
   - Custom tool loading (mocked)
   - Path resolution (relative, absolute, ~)
   - Error cases (missing file, invalid syntax, missing env var)
   - Standard location search order

2. **Agent.from_config()** (`test_agent_from_config.py`)
   - Basic config loading
   - Parameter overrides (verify override semantics)
   - Auto-discovery (temp directory setup)
   - MCP config preservation
   - Tool loading from config
   - Error propagation

### Integration Tests
1. **CLI Refactor** (existing `test_chat.py` continues to pass)
   - Verify CLI still works after extracting `load_config()`
   - Verify custom tool loading still works
   - Verify env var substitution still works

2. **Example Files** (`test_examples.py`)
   - Run new `003_agent_from_config.py` example
   - Verify it creates valid agent

### Manual Testing
1. Create agent from example `tyler-chat-config.yaml`
2. Verify tools loaded correctly
3. Verify MCP config preserved (without auto-connect)
4. Test override behavior
5. Test auto-discovery in different directories

## Rollback Plan

**LOW RISK** - Easy rollback if needed

### If Issues Found
1. **Revert commit** - All changes in single PR/commit
2. **No data migration** - No persistent state changes
3. **No breaking changes** - Existing code unaffected

### Partial Rollback (if needed)
Could keep CLI refactor and only revert public API:
1. Keep `tyler/config.py` as internal module
2. Remove `Agent.from_config()` 
3. Remove exports from `__init__.py`
4. CLI still benefits from refactor

## Open Questions

1. ~~Should we support config file auto-creation if not found?~~
   - **Decision**: No, only for CLI. Python users should create configs explicitly.

2. ~~Should `load_config()` be in `tyler.config` or `tyler.utils.config`?~~
   - **Decision**: `tyler.config` (shorter import, public API)

3. Should we add config path to Agent's Weave metadata?
   - **Proposed**: Yes, add optional `_config_source: Optional[str]` private attr
   - **Benefit**: Helps debugging in Weave UI
   - **Cost**: Minimal (one extra field)

4. Should we validate that custom tool files exist before loading?
   - **Current behavior**: CLI tries to load and shows error if fails
   - **Proposed**: Keep current behavior (fail at load time, not validation time)

5. Should `.json` files be in auto-discovery search paths?
   - **Current**: CLI only searches for `.yaml` files
   - **Proposed**: Keep YAML-only for auto-discovery, but allow explicit JSON paths
   - **Rationale**: YAML is more human-friendly for config files

## Success Metrics

### Adoption Metrics
- Number of examples using `from_config()` (target: 1+ examples)
- Documentation coverage (target: 3+ pages mention it)

### Quality Metrics
- Test coverage of new code (target: >90%)
- Zero regression in existing tests
- CLI behavior unchanged (all CLI tests pass)

### Developer Experience
- Config reuse between CLI and Python (qualitative feedback)
- Reduced support questions about "how to replicate CLI config in Python"

