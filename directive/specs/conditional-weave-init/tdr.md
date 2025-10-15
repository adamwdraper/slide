# Technical Design Review (TDR) — Conditional Weave Initialization in Tyler Chat CLI

**Author**: AI Agent  
**Date**: 2025-10-15  
**Links**: 
- Spec: `/directive/specs/conditional-weave-init/spec.md`
- Impact: `/directive/specs/conditional-weave-init/impact.md`

---

## 1. Summary

We are making Weave initialization in the Tyler Chat CLI conditional based on the `WANDB_PROJECT` environment variable. Currently, the CLI unconditionally initializes Weave with a hardcoded project name "tyler-cli" on every startup, which forces tracking overhead even when users don't want it and prevents users from customizing the project name.

This change will only initialize Weave when `WANDB_PROJECT` is explicitly set by the user, providing opt-in tracking behavior. This aligns with the Space Monkey package's approach, follows 12-factor app principles, and gives users control over their observability tools. The implementation is minimal - a simple environment variable check before calling `weave.init()`.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **User control**: Users need the ability to opt-out of tracking overhead
- **Consistency**: Space Monkey package already uses `WANDB_PROJECT` env var
- **Performance**: Avoid unnecessary network calls and initialization overhead
- **12-factor principles**: Configuration should be in environment, not code
- **Simplicity**: Keep the solution simple - no complex configuration logic

### Non‑Goals
- Adding YAML configuration for Weave project (keeping it env-var only)
- Supporting other Weave configuration options (entity, API key) - use env vars directly
- Migrating existing traces from "tyler-cli" to new project names
- Adding CLI commands to toggle Weave during runtime
- Checking for `WANDB_API_KEY` before initialization (Weave handles this)

## 3. Current State — Codebase Map (concise)

### Key modules
- **`packages/tyler/tyler/cli/chat.py`**:
  - `ChatManager` class (lines 129-182): Manages chat sessions and agent interaction
  - `ChatManager.__init__()` (lines 130-137): Currently calls `weave.init("tyler-cli")` unconditionally
  - `load_config()` (lines 492-596): Loads configuration from YAML files, generates template
  - Various suppression mechanisms to hide Weave/W&B output noise

### Existing behavior
```python
class ChatManager:
    def __init__(self):
        # ... other init code ...
        # Initialize Weave with suppressed output
        with suppress_output():
            weave.init("tyler-cli")  # ← Always called, hardcoded project
```

### Related patterns in codebase
- **Space Monkey** (`packages/space-monkey/space_monkey/slack_app.py` lines 154-155):
  ```python
  if os.getenv("WANDB_API_KEY") and self.weave_project:
      weave.init(self.weave_project)
  ```
- **Tyler examples** (e.g., `packages/tyler/examples/002_basic.py` lines 20-25):
  ```python
  try:
      if os.getenv("WANDB_API_KEY"):
          weave.init("tyler")
  except Exception as e:
      logger.warning(f"Failed to initialize weave tracing: {e}")
  ```

### Observability currently available
- Weave traces automatically sent to "tyler-cli" project
- All `@weave.op()` decorated methods in Agent class tracked
- No CLI-specific logging for Weave initialization (suppressed)

## 4. Proposed Design (high level, implementation‑agnostic)

### Overall approach
Replace unconditional `weave.init("tyler-cli")` with conditional initialization based on `WANDB_PROJECT` environment variable.

### Pseudo-code
```python
class ChatManager:
    def __init__(self):
        self.agent = None
        self.current_thread = None
        self.thread_store = ThreadStore()
        self.thread_count = 0
        
        # Initialize Weave only if WANDB_PROJECT is set
        weave_project = os.getenv("WANDB_PROJECT")
        if weave_project:
            with suppress_output():
                weave.init(weave_project)
```

### Interface changes
- **Input**: `WANDB_PROJECT` environment variable (string, optional)
- **Behavior**: 
  - If set and non-empty: Initialize Weave with that project name
  - If not set or empty: Skip Weave initialization entirely
- **Output**: No return value, side effect is Weave initialization state

### Error handling
- Wrap in `suppress_output()` context manager (already exists)
- No explicit try/except needed - let Weave handle its own errors
- Weave will gracefully handle missing `WANDB_API_KEY` if needed

### Performance expectations
- Minimal performance impact: One `os.getenv()` call and one conditional
- When disabled: Saves ~100-500ms of Weave initialization overhead
- When enabled: Same performance as current behavior

## 5. Alternatives Considered

### Option A: YAML configuration only
**Approach**: Add `wandb_project` field to tyler-chat-config.yaml
```yaml
wandb_project: "my-project"
```

**Pros**:
- More discoverable in config file
- Can have different projects per config file

**Cons**:
- More complex implementation (config loading)
- Inconsistent with Space Monkey
- Users would need separate configs for weave/non-weave
- Config file is optional, env vars always available

**Rejected**: Too complex for minimal benefit

### Option B: Both YAML and env var with precedence
**Approach**: Support both, with YAML taking precedence over env var

**Pros**:
- Maximum flexibility

**Cons**:
- Unnecessary complexity
- Two places to configure the same thing
- Harder to document and debug

**Rejected**: Over-engineering, env var alone is sufficient

### Option C: Check both WANDB_API_KEY and WANDB_PROJECT
**Approach**: Only init if both API key and project are set
```python
if os.getenv("WANDB_API_KEY") and os.getenv("WANDB_PROJECT"):
    weave.init(os.getenv("WANDB_PROJECT"))
```

**Pros**:
- More explicit about requirements
- Matches Space Monkey pattern exactly

**Cons**:
- Weave already handles missing API key gracefully
- Extra complexity
- Users might be confused if they set project but forget API key

**Considered but simplified**: We'll just check project; Weave handles auth

### Chosen Option: Environment variable only (WANDB_PROJECT)
**Why**: 
- Simplest implementation
- Consistent with Space Monkey and 12-factor principles
- Users already use .env files for WANDB_API_KEY
- Single source of truth
- Easy to test and document

## 6. Data Model & Contract Changes

### No data model changes
- No database tables affected
- No schema migrations needed
- No persistent storage changes

### No API changes
- No Python API changes
- No CLI argument changes
- No function signature changes

### Environment variable contract
**New**: `WANDB_PROJECT` environment variable
- **Type**: String (optional)
- **Default**: Not set (Weave disabled)
- **Example**: `WANDB_PROJECT=tyler-cli`
- **Behavior**: If set, used as Weave project name

### Backward compatibility
**Breaking change**: Existing users who rely on automatic tracking to "tyler-cli" will need to set `WANDB_PROJECT=tyler-cli` to restore previous behavior.

**Migration path**:
```bash
# Add to .env file or environment
export WANDB_PROJECT=tyler-cli
```

**Documentation**: Will include migration guide in CHANGELOG and docs.

## 7. Security, Privacy, Compliance

### Authentication/Authorization
- **No change**: Weave authentication still controlled by `WANDB_API_KEY`
- **No new secrets**: Using existing W&B/Weave authentication model
- **Access control**: Project name doesn't affect access control

### Privacy
- **Positive impact**: Users can now opt-out of sending traces to Weave
- **No PII changes**: Data sent to Weave same as before (when enabled)
- **User control**: Users decide if/where to track

### Threat model
- **No new attack surface**: Only checking environment variable
- **Reduced surface**: By default, no external network calls to W&B
- **Existing protections**: Weave SDK handles authentication securely

### Compliance
- **No impact**: Same data flows as before, just optional now
- **Benefit**: Easier to comply with policies requiring opt-out of telemetry

## 8. Observability & Operations

### Logs
**Optional additions** (debug level only):
```python
if weave_project:
    logger.debug(f"Initializing Weave with project: {weave_project}")
    weave.init(weave_project)
else:
    logger.debug("WANDB_PROJECT not set, skipping Weave initialization")
```

Note: These would be suppressed by existing `suppress_output()` unless user enables debug logging.

### Metrics
- **Not applicable**: CLI tool has no centralized metrics
- **User visibility**: Users see traces in their W&B project when enabled

### Dashboards/Alerts
- **Not applicable**: No centralized monitoring for CLI tools
- **User responsibility**: Users monitor their own Weave projects

### Operational impact
- **Reduced**: Fewer failed initialization attempts when API key missing
- **Cleaner**: No Weave overhead in local development by default

## 9. Rollout & Migration

### Feature flags
- **Not needed**: Simple conditional, can be tested directly
- **Toggle mechanism**: Environment variable itself is the toggle

### Migration strategy
1. **Release notes**: Document breaking change in CHANGELOG
2. **Documentation**: Update CLI docs with migration instructions
3. **Examples**: Update example .env files with commented `WANDB_PROJECT`
4. **Template**: Update generated config template with Weave documentation

### Migration guide for users
```markdown
## Breaking Change: Weave Initialization

Tyler Chat CLI no longer automatically initializes Weave tracking. 

**To restore Weave tracking:**

Add to your `.env` file or environment:
```bash
WANDB_PROJECT=tyler-cli  # or your preferred project name
```

**To disable tracking:**
Simply don't set `WANDB_PROJECT` (new default behavior).
```

### Rollback plan
- **Easy rollback**: Single line change can be reverted
- **No data loss**: Existing traces unchanged
- **Forward compatible**: Users who add `WANDB_PROJECT` won't break if we rollback

### Blast radius
- **Scope**: Only affects Tyler Chat CLI users
- **No impact on**: Library users, other packages, agent behavior
- **Severity**: Low - only affects observability, not core functionality

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
1. Write failing tests first
2. Confirm tests fail
3. Implement minimal code to pass
4. Refactor while keeping tests green

### Spec → Test Mapping

| Acceptance Criterion | Test ID | Test Type |
|---------------------|---------|-----------|
| Given `WANDB_PROJECT="my-project"`, then Weave initializes with "my-project" | `test_weave_init_with_project` | Unit |
| Given no `WANDB_PROJECT`, then Weave does NOT initialize | `test_weave_no_init_without_project` | Unit |
| Given empty `WANDB_PROJECT=""`, then Weave does NOT initialize | `test_weave_no_init_with_empty_project` | Unit |
| Given Weave disabled, agent functionality works normally | `test_cli_works_without_weave` | Integration |
| Given Weave disabled, `@weave.op()` methods don't error | `test_weave_ops_safe_without_init` | Integration |

### Test Implementation Details

#### Unit Tests (`packages/tyler/tests/cli/test_chat_weave.py`)

```python
import os
from unittest.mock import patch, MagicMock
import pytest
from tyler.cli.chat import ChatManager

class TestChatManagerWeaveInit:
    """Test Weave initialization behavior in ChatManager"""
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': 'test-project'})
    def test_weave_init_with_project(self, mock_weave):
        """Test that Weave initializes when WANDB_PROJECT is set"""
        manager = ChatManager()
        mock_weave.init.assert_called_once_with('test-project')
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {}, clear=True)
    def test_weave_no_init_without_project(self, mock_weave):
        """Test that Weave does NOT initialize when WANDB_PROJECT not set"""
        manager = ChatManager()
        mock_weave.init.assert_not_called()
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': ''})
    def test_weave_no_init_with_empty_project(self, mock_weave):
        """Test that Weave does NOT initialize with empty WANDB_PROJECT"""
        manager = ChatManager()
        mock_weave.init.assert_not_called()
    
    @patch('tyler.cli.chat.weave')
    @patch.dict(os.environ, {'WANDB_PROJECT': '   '})
    def test_weave_no_init_with_whitespace_project(self, mock_weave):
        """Test that Weave does NOT initialize with whitespace-only WANDB_PROJECT"""
        manager = ChatManager()
        mock_weave.init.assert_not_called()
```

#### Integration Tests

```python
@pytest.mark.asyncio
@patch.dict(os.environ, {}, clear=True)
async def test_cli_works_without_weave():
    """Test that CLI functions normally without Weave initialization"""
    manager = ChatManager()
    manager.initialize_agent({'model_name': 'gpt-4o'})
    
    thread = await manager.create_thread(title="Test")
    assert thread is not None
    assert thread.title == "Test"
    
    # Should be able to add messages and process
    thread.add_message(Message(role="user", content="Hello"))
    # Agent operations should work...
```

### Negative & Edge Cases
- Empty string for `WANDB_PROJECT`
- Whitespace-only string for `WANDB_PROJECT`
- Very long project name
- Special characters in project name (Weave SDK should validate)
- Missing `WANDB_API_KEY` with `WANDB_PROJECT` set (Weave handles gracefully)

### Performance Tests
- **Not needed**: Trivial code path (one getenv call)
- **Manual verification**: Measure startup time with/without Weave

### CI Integration
- All tests must pass in CI
- Tests run on every PR
- No special CI configuration needed

## 11. Risks & Open Questions

### Known Risks

1. **Risk**: `@weave.op()` decorators might fail when `weave.init()` not called
   - **Likelihood**: Low - decorators are designed to be no-ops
   - **Impact**: High - would break agent functionality
   - **Mitigation**: Test extensively, verify in Weave documentation
   - **Resolution**: Add integration test specifically for this

2. **Risk**: Breaking change affects existing users
   - **Likelihood**: High - this is a breaking change
   - **Impact**: Medium - affects observability only
   - **Mitigation**: Clear documentation, migration guide, CHANGELOG entry
   - **Resolution**: Accept as intentional breaking change with path forward

3. **Risk**: Users confused about why tracking stopped working
   - **Likelihood**: Medium - users might not read CHANGELOG
   - **Impact**: Low - doesn't break core functionality
   - **Mitigation**: Consider adding optional warning message on first run
   - **Resolution**: Document clearly, provide migration guide

### Open Questions

**Q1**: Should we add a warning message when WANDB_PROJECT is not set?
- **Options**: 
  - A) Silent (no message)
  - B) Debug log only
  - C) One-time info message
- **Proposal**: Start with (A) silent, can add (B) debug log if needed
- **Resolution needed before**: Implementation

**Q2**: Should we validate the project name format?
- **Options**:
  - A) No validation (let Weave handle it)
  - B) Basic validation (non-empty, no special chars)
- **Proposal**: (A) - Weave SDK will validate and error appropriately
- **Resolution needed before**: Implementation

**Q3**: Should we update ALL examples to use WANDB_PROJECT pattern?
- **Scope**: 20+ example files currently hardcode project names
- **Proposal**: Out of scope for this PR, can be follow-up
- **Resolution needed before**: Documentation

**Decisions**:
- Q1: Go with (A) silent, add debug log in implementation
- Q2: Go with (A) no validation, trust Weave SDK
- Q3: Out of scope, track as future improvement

## 12. Milestones / Plan (post‑approval)

### Task 1: Update ChatManager initialization
**Files**: `packages/tyler/tyler/cli/chat.py`
**Changes**:
- Add `import os` if not present
- Replace unconditional `weave.init("tyler-cli")` with conditional logic
- Add optional debug logging

**DoD**:
- [ ] Code passes linting
- [ ] Unit tests written and passing
- [ ] Manual test: CLI starts without WANDB_PROJECT
- [ ] Manual test: CLI starts with WANDB_PROJECT

### Task 2: Write unit tests
**Files**: `packages/tyler/tests/cli/test_chat_weave.py` (new file)
**Changes**:
- Create test file with ChatManager Weave tests
- Mock weave module
- Test all scenarios from spec

**DoD**:
- [ ] All 5 test cases implemented
- [ ] Tests pass locally
- [ ] Tests pass in CI
- [ ] Code coverage maintained

### Task 3: Write integration tests
**Files**: `packages/tyler/tests/cli/test_chat_integration.py`
**Changes**:
- Add integration test for full CLI flow without Weave
- Verify agent operations work correctly

**DoD**:
- [ ] Integration test passes
- [ ] Verified `@weave.op()` methods don't error
- [ ] No regression in existing tests

### Task 4: Update documentation
**Files**: 
- `docs/apps/tyler-cli.mdx`
- `packages/tyler/CHANGELOG.md`
- `packages/tyler/tyler/cli/chat.py` (template config)

**Changes**:
- Document breaking change
- Add migration guide
- Update environment variables section
- Add example to config template

**DoD**:
- [ ] CHANGELOG entry added
- [ ] Documentation clearly explains new behavior
- [ ] Migration guide provided
- [ ] Example .env updated

### Task 5: Manual testing & validation
**Testing**:
- Test with real W&B project
- Test without WANDB_PROJECT set
- Test template config generation
- Verify no error messages

**DoD**:
- [ ] CLI works normally without WANDB_PROJECT
- [ ] CLI tracks correctly with WANDB_PROJECT
- [ ] No unexpected errors or warnings
- [ ] Template config includes Weave documentation

### Dependencies
- No external dependencies
- No coordination with other teams
- Self-contained change

### Estimated Timeline
- Task 1: 30 minutes
- Task 2: 45 minutes
- Task 3: 30 minutes
- Task 4: 1 hour
- Task 5: 30 minutes
- **Total**: ~3 hours

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved.

