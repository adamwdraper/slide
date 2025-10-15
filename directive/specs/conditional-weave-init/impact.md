# Impact Analysis — Conditional Weave Initialization in Tyler Chat CLI

## Modules/packages likely touched

### Core Implementation
- **`packages/tyler/tyler/cli/chat.py`**
  - `ChatManager.__init__()` method - Conditional Weave initialization
  - `load_config()` function - Environment variable substitution
  - Template config generation - Weave documentation
  
- **`packages/tyler/tyler/models/agent.py`**
  - Added `api_key` field to Agent model
  - Pass `api_key` to CompletionHandler

- **`packages/tyler/tyler/models/completion_handler.py`**
  - Added `api_key` parameter to `__init__()`
  - Include `api_key` in LiteLLM completion params

### Testing
- **`packages/tyler/tests/cli/test_chat_weave.py`** (NEW)
  - 5 unit tests for Weave initialization
  
- **`packages/tyler/tests/cli/test_chat_integration.py`** (NEW)
  - 3 integration tests for CLI functionality

- **`packages/tyler/tests/models/test_agent_properties.py`** (NEW)
  - 8 property validation tests

### Documentation & Configuration
- **`packages/tyler/CHANGELOG.md`**
  - Breaking change notice and migration guide

- **`packages/tyler/README.md`**
  - Document example config files location

- **`packages/tyler/.env.example`** (UPDATED)
  - Comprehensive environment variable documentation

- **`packages/space-monkey/env.example`** (UPDATED)
  - Clarified WANDB_PROJECT usage

- **`packages/tyler/tyler-chat-config-wandb.yaml`** (MOVED & UPDATED)
  - Moved from root to packages/tyler/
  - Added `api_key: "${WANDB_API_KEY}"` configuration

- **`packages/tyler/tyler-chat-config.yaml`** (MOVED)
  - Moved from root to packages/tyler/

### Examples
- **`packages/tyler/examples/006_thinking_tokens.py`**
  - Updated W&B Inference demo to use `WANDB_API_KEY` correctly
  - Uses explicit `api_key` parameter

## Contracts to update (APIs, events, schemas, migrations)

### Breaking Changes
- **CLI behavior change**: Weave will no longer initialize by default
  - **Before**: `tyler-chat` automatically tracked all sessions to "tyler-cli" project
  - **After**: `tyler-chat` only tracks when `WANDB_PROJECT` is set
  - **Migration**: Users must set `WANDB_PROJECT=tyler-cli` (or their preferred name) to restore tracking

### Environment Variables
- **New behavior for `WANDB_PROJECT`**:
  - **Before**: Not used by Tyler Chat CLI
  - **After**: Controls whether Weave initializes and which project to use
  - **Note**: Already used by Space Monkey package, so this creates consistency

### API Changes
- **Agent model** (backward compatible addition):
  - **Added**: `api_key: Optional[str]` field
  - **Benefit**: Supports W&B Inference and custom providers requiring explicit API keys
  - **Backward compatible**: Optional field, defaults to None
  
- **CompletionHandler** (internal change):
  - **Added**: `api_key` parameter to `__init__()`
  - **Impact**: Internal only, not part of public API

### Config Loader Enhancement
- **Added**: Environment variable substitution in YAML configs
- **Syntax**: `${VARIABLE_NAME}` in YAML values
- **Use case**: Secure API key configuration without hardcoding

## Risks

### Security
- **Low risk**: No security implications
- Weave authentication still controlled by `WANDB_API_KEY` env var
- No new attack surface introduced
- Potentially more secure by reducing external dependencies by default

### Performance/Availability
- **Low risk, positive impact**:
  - Reduced overhead when Weave is disabled (no network calls to W&B)
  - Faster CLI startup when tracking is not needed
  - No performance impact when Weave is enabled (same as current behavior)
  
- **Risk**: If Weave decorators (`@weave.op()`) fail when Weave isn't initialized
  - **Mitigation**: Need to verify that `@weave.op()` decorators are no-ops when `weave.init()` hasn't been called
  - **Testing**: Run CLI without `WANDB_PROJECT` and ensure no errors from decorated methods

### Data integrity
- **Low risk**:
  - No data storage changes
  - No database migrations
  - Weave traces will be in user-specified projects instead of hardcoded "tyler-cli"
  
- **Historical data**: 
  - Existing traces in "tyler-cli" project remain unchanged
  - New traces go to user-specified project
  - No automatic migration needed or desired

### User Impact
- **High risk: Breaking change for existing users**
  - Users who rely on automatic Weave tracking will lose visibility until they set `WANDB_PROJECT`
  - **Severity**: Medium - affects observability, but doesn't break core functionality
  - **Affected users**: Anyone using Tyler Chat CLI with W&B/Weave
  - **Mitigation strategies**:
    1. Clear documentation in CHANGELOG about breaking change
    2. Migration guide showing how to restore previous behavior
    3. Consider logging a helpful message on first run without `WANDB_PROJECT`
    4. Update example .env files to include `WANDB_PROJECT` (commented out)

## Observability needs

### Logs
- **Optional**: Add debug log when Weave initialization is skipped
  - Example: `logger.debug("WANDB_PROJECT not set, skipping Weave initialization")`
  - Should be DEBUG level to avoid noise
  - Already suppressed by existing `suppress_output()` context manager
  
- **Optional**: Log when Weave successfully initializes
  - Example: `logger.debug(f"Weave initialized with project: {project_name}")`
  - Useful for debugging configuration issues

### Metrics
- **Not applicable**: This is a CLI tool, no centralized metrics
- Users can still see Weave traces in their own W&B projects when enabled

### Alerts
- **Not applicable**: No alerting infrastructure for CLI tools

## Testing Requirements

### Unit Tests
- Test `ChatManager.__init__()` with `WANDB_PROJECT` set
- Test `ChatManager.__init__()` without `WANDB_PROJECT` set
- Test with empty string `WANDB_PROJECT=""`
- Mock `weave.init()` to verify it's called/not called appropriately

### Integration Tests
- Run full CLI session without `WANDB_PROJECT` - should work normally
- Run full CLI session with `WANDB_PROJECT` - should track to Weave
- Verify no errors from `@weave.op()` decorated methods when Weave disabled

### Manual Testing
- Test with existing `.env` file configurations
- Test template config file generation
- Verify help/documentation is clear

## Dependencies

### No new dependencies
- Only uses existing `os.getenv()` for environment variable reading
- No new packages required

### Dependency on Weave behavior
- Assumes `@weave.op()` decorators are safe no-ops when `weave.init()` not called
- Should verify this with Weave documentation or testing

## Rollback Plan

### Easy rollback
- Change is localized to one method in `chat.py`
- Can easily revert to hardcoded `weave.init("tyler-cli")` if issues arise
- No database migrations or complex state changes to undo

### Forward compatibility
- Users who set `WANDB_PROJECT` now will continue to work if we rollback
- Rollback would just re-enable automatic tracking for everyone

## Documentation Updates Required

1. **`docs/apps/tyler-cli.mdx`**:
   - Update environment variables section
   - Add breaking change notice
   - Provide migration example

2. **CHANGELOG**:
   - Add breaking change entry
   - Explain new behavior
   - Show migration path

3. **README** (if applicable):
   - Update any examples using tyler-chat
   - Add `WANDB_PROJECT` to example .env files

4. **Example .env files**:
   - Add commented `# WANDB_PROJECT=tyler-cli` to examples

## Timeline Estimate

- **Code changes**: 30 minutes (very small change)
- **Testing**: 1 hour (unit tests + manual verification)
- **Documentation**: 1 hour (update docs, CHANGELOG, examples)
- **Total**: ~2.5 hours

## Related Work

- Consistent with Space Monkey package which uses same pattern
- Aligns with 12-factor app principles for configuration
- Similar to how examples in `packages/tyler/examples/` conditionally initialize Weave

