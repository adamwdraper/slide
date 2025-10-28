# Impact Analysis — Async Agent.go() Method

## Modules/packages likely touched

### Core Agent Implementation

#### Modified Files
- **`/packages/tyler/tyler/models/agent.py`**
  - Change `def go(...)` to `async def go(...)`
  - For non-streaming mode: change `return self._go_complete(...)` to `return await self._go_complete(...)`
  - For streaming modes: change from `return self._go_stream(...)` to `async for x in self._go_stream(...): yield x`
  - Update docstring examples to show `await agent.go(thread)`
  - ~20 lines modified in the `.go()` method implementation

### Examples (30 files)

All examples that use `agent.go()` need `await` added for non-streaming calls:

#### Tyler Examples (`/packages/tyler/examples/`)
- **`001_docs_introduction.py`** - Change to `asyncio.run(agent.go(thread))` → needs await wrapper
- **`002_basic.py`** - Add `await` to `agent.go()` calls
- **`003_agent_from_config.py`** - Add `await` to `agent.go()` calls
- **`003_docs_quickstart.py`** - Already streaming (no change needed)
- **`004_streaming.py`** - Already streaming (no change needed)
- **`005_raw_streaming.py`** - Already streaming (no change needed)
- **`005_thread_persistence.py`** - Add `await` to both `agent.go()` calls
- **`006_thinking_tokens.py`** - Already streaming (no change needed)
- **`007_thinking_tokens_streaming.py`** - Already streaming (no change needed)
- **`100_tools_basic.py`** - Add `await` to `agent.go()`
- **`101_tools_streaming.py`** - Already streaming (no change needed)
- **`102_selective_tools.py`** - Add `await` to `agent.go()`
- **`103_tools_files.py`** - Add `await` to both calls
- **`104_tools_image.py`** - Add `await` to both calls
- **`105_tools_audio.py`** - Add `await` to both calls
- **`106_tools_wandb.py`** - Add `await` to both calls
- **`107_tools_group_import.py`** - Add `await` to `agent.go()`
- **`200_attachments.py`** - Add `await` to `agent.go()`
- **`300_mcp_basic.py`** - Mixed (some streaming, some not)
- **`301_mcp_advanced.py`** - Already streaming (no change needed)
- **`302_execution_observability.py`** - Mixed (some streaming, some not)
- **`400_agent_delegation.py`** - Add `await` to `agent.go()`
- **`402_a2a_basic_client.py`** - Already streaming (no change needed)
- **`403_a2a_multi_agent.py`** - Already streaming (no change needed)

#### Workspace Examples (`/examples/`)
- **`getting-started/quickstart.py`** - Add `await` to `agent.go()`
- **`getting-started/basic-persistence.py`** - Add `await` to `agent.go()`
- **`getting-started/tool-groups.py`** - Add `await` to `agent.go()`
- **`integrations/cross-package.py`** - Add `await` to all 5 `agent.go()` calls
- **`use-cases/research-assistant/basic.py`** - Add `await` to `agent.go()`
- **`agent_observability_demo.py`** - Mixed (some streaming, some not)
- **`test_streaming_chunks.py`** - Already streaming (no change needed)
- **`test_execution_observability.py`** - Mixed (some streaming, some not)

### Tests (13 files, ~100+ test functions)

#### Tyler Tests (`/packages/tyler/tests/`)
- **`models/test_agent.py`** - ~17 test functions need `await` added
  - All non-streaming `agent.go()` calls
  - Tests that call `.go()` directly
  
- **`models/test_agent_streaming.py`** - Already all streaming (no changes needed)
  - All tests already use `async for event in agent.go(...)`

- **`models/test_agent_observability.py`** - ~8 test functions need updates
  - Mixed streaming and non-streaming calls
  
- **`models/test_agent_thinking_tokens.py`** - Already all streaming (no changes needed)

- **`models/test_agent_delegation.py`** - ~3 test functions need `await` added
  
- **`integration/test_agent_delegation_integration.py`** - ~2 test functions need `await` added

- **`mcp/test_mcp_integration.py`** - ~1 test function needs `await` added

### CLI (`/packages/tyler/tyler/cli/`)
- **`chat.py`** - Already uses streaming (`async for event in agent.go(...)`) - No change needed
- **`init.py`** - One `agent.go()` call needs `await` added

### Integrations

#### Space Monkey (`/packages/space-monkey/`)
- **`space_monkey/slack_app.py`** - 2 `agent.go()` calls need `await` added
  - Line ~423: `classifier_result = await self.message_classifier_agent.go(...)`
  - Line ~468: `result = await self.agent.go(...)`

### Tyler Internal

#### Tool Manager
- **`packages/tyler/tyler/models/tool_manager.py`** - 1 delegation call needs update
  - Line ~166: Already has `await agent.go(thread)` ✅ (no change needed)

#### Eval
- **`packages/tyler/tyler/eval/agent_eval.py`** - 1 call needs verification
  - Line ~111: Already has `await safe_agent.go(thread)` ✅ (no change needed)

### Documentation (14 files, ~100+ code samples)

All documentation files with code samples need updates:

#### API Reference
- **`docs/api-reference/tyler-agent.mdx`** - Update all code samples (6 samples)
- **`docs/api-reference/tyler-agentresult.mdx`** - Update code samples (5 samples)
- **`docs/api-reference/tyler-executionevent.mdx`** - Streaming only (no changes)
- **`docs/api-reference/tyler-eventtype.mdx`** - Streaming only (no changes)
- **`docs/api-reference/lye-tool-format.mdx`** - Update 1 sample
- **`docs/api-reference/lye-collections.mdx`** - Update 1 sample

#### Guides
- **`docs/guides/your-first-agent.mdx`** - Update all code samples (5 samples)
- **`docs/guides/streaming-responses.mdx`** - Streaming samples (no changes needed)
- **`docs/guides/mcp-integration.mdx`** - Update code samples (6 samples)
- **`docs/guides/patterns.mdx`** - Update non-streaming samples (4 samples)
- **`docs/guides/agent-delegation.mdx`** - Update code samples (8 samples)
- **`docs/guides/a2a-integration.mdx`** - Update code samples (3 samples)
- **`docs/guides/conversation-persistence.mdx`** - Update code samples (5 samples)
- **`docs/guides/testing-agents.mdx`** - Update code samples (2 samples)

#### Concepts
- **`docs/concepts/how-agents-work.mdx`** - Update code samples (7 samples)
- **`docs/concepts/mcp.mdx`** - Update code samples (8 samples)
- **`docs/concepts/a2a.mdx`** - Update code samples (4 samples)
- **`docs/concepts/tools.mdx`** - Update 1 sample

#### Other
- **`docs/introduction.mdx`** - Update 1 sample
- **`docs/quickstart.mdx`** - Update 1 sample
- **`docs/examples/research-assistant.mdx`** - Update code samples (4 samples)
- **`docs/apps/slack-agent.mdx`** - Update 1 sample

### Package Metadata
- **`packages/tyler/CHANGELOG.md`** - Add breaking change entry for v5.0.0
- **`packages/tyler/pyproject.toml`** - Bump version to 5.0.0
- **`README.md`** (workspace root) - Update if it has examples

### Lock Files
- **`uv.lock`** - Will auto-update when version changes

## Contracts to update (APIs, events, schemas, migrations)

### Public API Changes

#### Breaking Change: `Agent.go()` signature
```python
# BEFORE (v4.x)
def go(
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
    """Process the thread with the agent."""
    # ... implementation

# Usage (non-streaming):
result = agent.go(thread)  # ❌ No await needed (misleading!)

# Usage (streaming):
async for event in agent.go(thread, stream=True):  # ✅ Works
    print(event)
```

```python
# AFTER (v5.0.0)
async def go(
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
    """Process the thread with the agent."""
    # ... implementation

# Usage (non-streaming):
result = await agent.go(thread)  # ✅ Await required (clear!)

# Usage (streaming):
async for event in agent.go(thread, stream=True):  # ✅ Still works
    print(event)
```

### Implementation Pattern Changes

#### Non-Streaming Mode
```python
# BEFORE
def go(self, thread_or_id, stream=False):
    if stream_mode is None:
        return self._go_complete(thread_or_id)  # Returns awaitable

# AFTER
async def go(self, thread_or_id, stream=False):
    if stream_mode is None:
        return await self._go_complete(thread_or_id)  # Awaits and returns
```

#### Streaming Modes
```python
# BEFORE
def go(self, thread_or_id, stream=False):
    elif stream_mode == "events":
        return self._go_stream(thread_or_id)  # Returns generator
    elif stream_mode == "raw":
        return self._go_stream_raw(thread_or_id)  # Returns generator

# AFTER
async def go(self, thread_or_id, stream=False):
    elif stream_mode == "events":
        async for event in self._go_stream(thread_or_id):
            yield event
    elif stream_mode == "raw":
        async for chunk in self._go_stream_raw(thread_or_id):
            yield chunk
```

### Type Signatures (No Changes)
- Return types remain identical
- `@overload` decorators remain identical (except function becomes `async def`)
- Generic types unchanged: `AgentResult`, `AsyncGenerator[ExecutionEvent, None]`, etc.

### Backward Compatibility
**NONE** - This is a breaking change for non-streaming usage:
- ❌ `result = agent.go(thread)` → Runtime error (coroutine not awaited)
- ✅ `async for event in agent.go(thread, stream=True)` → Still works (no change)

## Risks

### Security
**NO RISK** - No security implications
- ✅ No changes to authentication, authorization, or data access
- ✅ No new attack surface
- ✅ No changes to tool execution or validation

### Performance/Availability
**LOW RISK / SLIGHT IMPROVEMENT**
- ✅ **Negligible overhead**: `async def` vs `def` has minimal performance impact
- ✅ **Better runtime behavior**: Proper async/await allows Python's event loop to manage concurrency better
- ✅ **No blocking changes**: Already async internally, just making it explicit
- ⚠️ **Potential concern**: If someone was running non-streaming `.go()` in a non-async context
  - **Mitigation**: Clean error message from Python ("coroutine not awaited")
  - **Reality**: Already impossible since internal methods are async

### Data integrity
**NO RISK** - No data model changes
- ✅ No changes to database schemas
- ✅ No changes to message formats
- ✅ No changes to thread storage
- ✅ No changes to tool execution logic
- ✅ All existing data remains valid

### Breaking Changes
**HIGH IMPACT** - Intentional breaking change for v5.0.0

#### Who's Affected?
1. **Non-streaming users** - Must add `await`
   ```python
   # BEFORE
   result = agent.go(thread)
   
   # AFTER
   result = await agent.go(thread)
   ```

2. **Streaming users** - No changes needed ✅
   ```python
   # BEFORE and AFTER (identical)
   async for event in agent.go(thread, stream=True):
       print(event)
   ```

#### Migration Complexity
- **Low complexity**: Single character change (`await`) per call
- **Easy detection**: Runtime error if `await` missing (clear message)
- **IDE support**: Most Python IDEs will highlight missing `await`

#### Estimated Impact
Based on grep results:
- **~30 example files** to update
- **~13 test files** with ~100+ test functions to update  
- **~14 documentation files** with ~80+ code samples to update
- **~2 integration files** (Space Monkey) to update
- **~1 CLI file** to update

Total: ~60 files, ~200+ call sites

### Developer Experience
**POSITIVE IMPACT** - Improves clarity and correctness
- ✅ API signature clearly shows async behavior
- ✅ Consistent with Python async best practices
- ✅ Better IDE support and autocomplete
- ✅ Enables proper observability tooling (Weave)
- ✅ Prevents confusion about sync vs async behavior

## Observability needs

### Logs
**NO CHANGES REQUIRED** - Existing logging works as-is
- ✅ All logging is inside `_go_complete()`, `_go_stream()`, etc. (unchanged)
- ✅ No new log points needed
- ✅ Existing debug/info/error logs remain intact

### Metrics
**VALIDATION METRIC** - Confirm Weave logging works
- **New validation**: Verify Weave captures execution traces correctly
- **Success criteria**: Weave dashboard shows complete traces for both streaming and non-streaming
- **How to verify**: Run examples with Weave initialized and check dashboard

### Alerts
**NOT REQUIRED** - No runtime monitoring changes
- ✅ Error handling unchanged
- ✅ No new failure modes
- ✅ Breaking change detected at import/runtime (not production monitoring concern)

### Observability Integration
**PRIMARY BENEFIT** - This change enables proper Weave integration

#### Before (Broken)
```python
@weave.op()
def go(self, ...):  # Not async
    return self._go_stream(...)  # Returns generator

# Result: Weave logs empty generator object, not execution details
```

#### After (Fixed)
```python
@weave.op()
async def go(self, ...):  # Properly async
    async for event in self._go_stream(...):
        yield event

# Result: Weave logs complete execution trace with all events
```

#### Validation Plan
1. Run example with Weave initialized
2. Check Weave dashboard for complete traces
3. Verify nested operations (tools, completions) are captured
4. Confirm both streaming and non-streaming modes work

## Dependencies

### New Dependencies
**NONE** - No new packages required

### Modified Dependencies
**NONE** - Python version already requires async/await support (3.11+)

### Dependency Impact
- ✅ No changes to `pyproject.toml` dependencies
- ✅ No changes to version constraints
- ✅ Python 3.11+ already supports all needed async features

## Migration Path

### For Tyler Users (Python API)

#### Detection
Users will get clear Python error if they forget `await`:
```python
result = agent.go(thread)
# RuntimeWarning: coroutine 'Agent.go' was never awaited
# RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

#### Fix
Add `await` to non-streaming calls:
```python
# Find and replace pattern:
# FROM: result = agent.go(thread)
# TO:   result = await agent.go(thread)

# FROM: response = agent.go(thread, stream=False)  
# TO:   response = await agent.go(thread, stream=False)
```

Streaming calls need no changes:
```python
# No change needed - these still work
async for event in agent.go(thread, stream=True):
    print(event)

async for chunk in agent.go(thread, stream="raw"):
    print(chunk)
```

### For Package Maintainers

#### Space Monkey
Update 2 call sites in `slack_app.py`:
```python
# Line ~423
classifier_result = await self.message_classifier_agent.go(classifier_thread)

# Line ~468
result = await self.agent.go(thread)
```
Both already have `await` ✅ - verify they still work correctly

#### Tyler CLI
Update 1 call site in `init.py`:
```python
# Already has await ✅
processed_thread, new_messages = await agent.go(thread)
```

### Documentation Update Strategy

1. **API Reference** - Update signature and all examples
2. **Guides** - Update all code samples to show `await`
3. **Introduction/Quickstart** - Update first examples (critical for new users)
4. **CHANGELOG** - Document breaking change prominently

### Migration Guide Template
Create `MIGRATION_V5.md` or add to CHANGELOG:

```markdown
## Migrating to Tyler v5.0.0

### Breaking Change: `Agent.go()` is now async

The `Agent.go()` method is now `async def` instead of `def`.

#### What Changed?
Non-streaming calls now require `await`:
```python
# v4.x (old)
result = agent.go(thread)

# v5.0.0 (new)
result = await agent.go(thread)
```

Streaming calls are unchanged:
```python
# v4.x and v5.0.0 (same)
async for event in agent.go(thread, stream=True):
    print(event)
```

#### Why?
- Makes async behavior explicit and clear
- Follows Python async best practices
- Enables proper observability tooling
- Improves developer experience

#### How to Migrate?
1. Search your code for `agent.go(`
2. Add `await` before non-streaming calls
3. Leave streaming calls (`async for`) unchanged
4. Test your code
```

## Testing Strategy

### Unit Tests Update
1. **Add `await` to all non-streaming calls** in test files
   - `test_agent.py` - ~17 functions
   - `test_agent_observability.py` - ~8 functions
   - `test_agent_delegation.py` - ~3 functions
   - Other test files - ~5 functions

2. **No changes to streaming tests** (already correct)
   - `test_agent_streaming.py` - all use `async for`
   - `test_agent_thinking_tokens.py` - all use `async for`

3. **Verify all existing tests still pass**
   - Run: `pytest packages/tyler/tests/`
   - Expected: All tests pass with `await` added

### Integration Tests
1. **Space Monkey Integration**
   - Verify Slack bot still works
   - Test classifier agent and main agent
   
2. **CLI Integration**
   - Run `tyler-chat` commands
   - Verify no regression in CLI behavior

### Example Validation
1. **Run all examples** - verify they work with `await` added
   - Use `pytest tests/test_examples.py`
   - Manually run examples that aren't in automated tests

2. **New validation**: Weave observability
   - Run examples with `weave.init()`
   - Verify Weave dashboard shows complete traces
   - Test both streaming and non-streaming modes

### Regression Testing
1. **Type checking** - Verify type hints still work
   ```bash
   mypy packages/tyler/tyler/models/agent.py
   ```

2. **Existing functionality** - All features still work:
   - Tool execution
   - Agent delegation
   - MCP integration
   - File attachments
   - Thread persistence

### Test Coverage
- **Target**: >95% coverage maintained
- **Focus areas**:
  - `.go()` method with all stream modes
  - Error handling paths
  - Type checking with overloads

## Rollback Plan

### Easy Rollback
**LOW RISK** - Single commit rollback possible

1. **Git revert** - All changes in one PR/commit
   ```bash
   git revert <commit-hash>
   ```

2. **Version rollback** - Downgrade to v4.x
   ```bash
   pip install tyler==4.2.0
   ```

3. **No data migration** - No persistent state changes

### Partial Rollback (Not Recommended)
Could theoretically keep internal async methods and only revert public API:
- **Not recommended**: Would lose the benefits (clarity, observability)
- **Only if**: Critical production issue discovered

### Rollback Testing
Before release:
1. Create test project using v4.2.0
2. Upgrade to v5.0.0
3. Verify migration works
4. Downgrade back to v4.2.0
5. Verify rollback works

## Open Questions

1. **Should we provide a deprecation warning in v4.x?**
   - **Current plan**: No, clean break for v5.0.0
   - **Rationale**: Framework is new, few users, cleaner migration
   - **Alternative**: Could add warning in v4.3.0 if needed

2. **Should we provide a codemod/migration script?**
   - **Current plan**: No, manual migration is simple (`await` addition)
   - **Rationale**: Easy to find/replace, IDE support, clear error messages
   - **Alternative**: Could provide regex patterns for common editors

3. ~~Should internal generator methods keep `@weave.op()` decorators?~~
   - **Decision**: Yes, keep them for granular tracing
   - **Rationale**: Weave can handle nested ops, provides better detail

4. **Should we add async validation to CI?**
   - **Proposed**: Add linter check for missing `await` on `.go()` calls
   - **Tool**: Could use `ruff` or custom script
   - **Benefit**: Catch errors before runtime

5. **Documentation versioning strategy?**
   - **Current plan**: Update all docs to v5.0.0 (no version toggle)
   - **Alternative**: Keep v4.x docs as archive
   - **Decision needed**: Does docs site support version selection?

## Success Metrics

### Adoption Metrics
- **Version adoption**: Track v5.0.0 downloads vs v4.x (1 month post-release)
- **GitHub issues**: Monitor migration-related questions
- **Target**: <10 migration issues reported

### Quality Metrics
- **Test coverage**: Maintain >95% coverage
- **All tests pass**: 100% passing tests before merge
- **No regressions**: All examples work after migration
- **Zero security issues**: No new vulnerabilities introduced

### Developer Experience (Qualitative)
- **API clarity**: Developer survey/feedback on async clarity
- **Migration ease**: Time to migrate (should be <1 hour for typical project)
- **Weave integration**: Observability works correctly (validate in Weave dashboard)

### Technical Validation
- ✅ **Weave logging works**: Complete traces in dashboard
- ✅ **Streaming unchanged**: All streaming tests pass without modification
- ✅ **Error messages clear**: Missing `await` produces helpful Python error
- ✅ **IDE support**: PyCharm, VS Code show proper async hints

## Timeline Estimate

### Implementation
- **Core change** (agent.py): 1 hour
- **Examples update**: 4 hours (30 files)
- **Tests update**: 4 hours (100+ functions)
- **Documentation update**: 6 hours (80+ code samples)
- **Integration updates** (Space Monkey, CLI): 1 hour
- **Testing & validation**: 4 hours
- **Total**: ~20 hours (2.5 days)

### Review & Release
- **PR review**: 2 hours
- **Weave validation**: 2 hours
- **CHANGELOG & migration guide**: 2 hours
- **Release prep**: 2 hours
- **Total**: ~8 hours (1 day)

### Grand Total: ~28 hours (~3.5 days)

