# Impact Analysis — Split Agent.go() into .go() and .stream()

## Modules/packages likely touched

### Core Agent Implementation

#### Modified Files
- **`/packages/tyler/tyler/models/agent.py`**
  - **Remove** old `.go()` method with `stream` parameter
  - **Add** new `async def go(thread)` - returns `AgentResult` only
    - Uses `return await self._go_complete(thread)`
    - No streaming logic, single responsibility
  - **Add** new `async def stream(thread, mode="events")` - yields events/chunks
    - Uses `async for ... yield` from `_go_stream()` or `_go_stream_raw()`
    - Handles `mode="events"` (default) and `mode="raw"`
  - **Remove** `@overload` decorators for old unified method
  - **Add** simple type signatures (no Union types)
  - ~40 lines modified (method split + docstrings)

### Examples (30 files)

Examples need two types of changes:
1. **Non-streaming**: Add `await` to `agent.go(thread)` calls
2. **Streaming**: Change `agent.go(thread, stream=True)` → `agent.stream(thread)`

#### Tyler Examples (`/packages/tyler/examples/`)
- **`001_docs_introduction.py`** - Add `await` to `agent.go(thread)`
- **`002_basic.py`** - Add `await` to `agent.go()` calls
- **`003_agent_from_config.py`** - Add `await` to `agent.go()` calls
- **`003_docs_quickstart.py`** - Change to `agent.stream(thread)`
- **`004_streaming.py`** - Change to `agent.stream(thread)`
- **`005_raw_streaming.py`** - Change to `agent.stream(thread, mode="raw")`
- **`005_thread_persistence.py`** - Add `await` to both `agent.go()` calls
- **`006_thinking_tokens.py`** - Change to `agent.stream(thread)`
- **`007_thinking_tokens_streaming.py`** - Mixed (some `.stream()`, some `.stream(mode="raw")`)
- **`100_tools_basic.py`** - Add `await` to `agent.go()`
- **`101_tools_streaming.py`** - Change to `agent.stream(thread)`
- **`102_selective_tools.py`** - Add `await` to `agent.go()`
- **`103_tools_files.py`** - Add `await` to both calls
- **`104_tools_image.py`** - Add `await` to both calls
- **`105_tools_audio.py`** - Add `await` to both calls
- **`106_tools_wandb.py`** - Add `await` to both calls
- **`107_tools_group_import.py`** - Add `await` to `agent.go()`
- **`200_attachments.py`** - Add `await` to `agent.go()`
- **`300_mcp_basic.py`** - Mixed (add `await`, change streaming to `.stream()`)
- **`301_mcp_advanced.py`** - Change to `agent.stream(thread)`
- **`302_execution_observability.py`** - Mixed (add `await`, change streaming to `.stream()`)
- **`400_agent_delegation.py`** - Add `await` to `agent.go()`
- **`402_a2a_basic_client.py`** - Change to `agent.stream(thread)`
- **`403_a2a_multi_agent.py`** - Change to `agent.stream(thread)`

#### Workspace Examples (`/examples/`)
- **`getting-started/quickstart.py`** - Add `await` to `agent.go()`
- **`getting-started/basic-persistence.py`** - Add `await` to `agent.go()`
- **`getting-started/tool-groups.py`** - Add `await` to `agent.go()`
- **`integrations/cross-package.py`** - Add `await` to all 5 `agent.go()` calls
- **`integrations/streaming.py`** - Change to `agent.stream(thread)`
- **`use-cases/research-assistant/basic.py`** - Add `await` to `agent.go()`
- **`agent_observability_demo.py`** - Mixed (add `await`, change to `.stream()`)
- **`test_streaming_chunks.py`** - Change to `agent.stream(thread)`
- **`test_execution_observability.py`** - Mixed (add `await`, change to `.stream()`)

### Tests (13 files, ~100+ test functions)

#### Tyler Tests (`/packages/tyler/tests/`)
- **`models/test_agent.py`** - ~17 test functions need `await` added
  - All non-streaming `agent.go()` calls need `await`
  - Tests that call `.go()` directly
  
- **`models/test_agent_streaming.py`** - ALL need method change
  - Change all `agent.go(thread, stream=True)` → `agent.stream(thread)`
  - ~30+ test functions affected

- **`models/test_agent_observability.py`** - ~8 test functions need updates
  - Mixed: Add `await` to `.go()`, change `.go(stream=True)` → `.stream()`
  
- **`models/test_agent_thinking_tokens.py`** - ALL need method change
  - Change all `agent.go(thread, stream=True)` → `agent.stream(thread)`
  - ~4 test functions affected

- **`models/test_agent_delegation.py`** - ~3 test functions need `await` added
  
- **`integration/test_agent_delegation_integration.py`** - ~2 test functions need `await` added

- **`mcp/test_mcp_integration.py`** - ~1 test function needs `await` added

### CLI (`/packages/tyler/tyler/cli/`)
- **`chat.py`** - Change to `agent.stream(thread)`
  - Line ~544: `async for event in agent.go(..., stream=True)` → `async for event in agent.stream(...)`
- **`init.py`** - Add `await` to `agent.go()` call
  - Line ~124: `processed_thread, new_messages = await agent.go(thread)`

### Integrations

#### Space Monkey (`/packages/space-monkey/`)
- **`space_monkey/slack_app.py`** - Add `await` to 2 calls (already have it, verify syntax)
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

#### Breaking Change: Split into two methods
```python
# BEFORE (v4.x) - Single overloaded method
def go(
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
    """Process the thread with the agent."""

# Usage:
result = agent.go(thread)  # ❌ No await (misleading!)
async for event in agent.go(thread, stream=True):  # Overloaded parameter
```

```python
# AFTER (v5.0.0) - Two focused methods
async def go(
    self, 
    thread_or_id: Union[Thread, str]
) -> AgentResult:
    """Execute agent and return complete result."""
    return await self._go_complete(thread_or_id)

async def stream(
    self,
    thread_or_id: Union[Thread, str],
    mode: Literal["events", "raw"] = "events"
) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
    """Stream agent execution events or raw chunks."""
    if mode == "events":
        async for event in self._go_stream(thread_or_id):
            yield event
    else:
        async for chunk in self._go_stream_raw(thread_or_id):
            yield chunk

# Usage:
result = await agent.go(thread)  # ✅ Clear: returns result
async for event in agent.stream(thread):  # ✅ Clear: yields events
async for chunk in agent.stream(thread, mode="raw"):  # ✅ Clear: yields chunks
```

### Implementation Pattern Changes

#### Pattern: Two Separate Methods (No more parameter routing!)

```python
# BEFORE - Routing based on parameter
def go(self, thread_or_id, stream=False):
    # Complex routing logic
    if stream is True:
        stream_mode = "events"
    elif stream is False:
        stream_mode = None
    # ... more validation
    
    # Route to different implementations
    if stream_mode is None:
        return self._go_complete(thread_or_id)  # Returns awaitable
    elif stream_mode == "events":
        return self._go_stream(thread_or_id)  # Returns generator
    elif stream_mode == "raw":
        return self._go_stream_raw(thread_or_id)  # Returns generator

# AFTER - Two simple methods, each does one thing
async def go(self, thread_or_id):
    """Non-streaming only"""
    return await self._go_complete(thread_or_id)

async def stream(self, thread_or_id, mode="events"):
    """Streaming only"""
    if mode == "events":
        async for event in self._go_stream(thread_or_id):
            yield event
    elif mode == "raw":
        async for chunk in self._go_stream_raw(thread_or_id):
            yield chunk
    else:
        raise ValueError(f"Invalid mode: {mode}")
```

### Type Signatures (IMPROVED!)
- **Before**: Complex Union types `Union[AgentResult, AsyncGenerator[...]]`
- **After**: Clear, focused types
  - `.go()` → `AgentResult` (no Union!)
  - `.stream()` → `AsyncGenerator[ExecutionEvent | Any, None]`
- **Before**: Multiple `@overload` decorators needed
- **After**: Simple signatures, no overloads needed

### Backward Compatibility
**NONE** - This is a breaking change for ALL usage:
- ❌ `result = agent.go(thread)` → Needs `await` added
- ❌ `async for event in agent.go(thread, stream=True)` → Change to `agent.stream(thread)`
- ❌ `async for chunk in agent.go(thread, stream="raw")` → Change to `agent.stream(thread, mode="raw")`

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
**VERY HIGH IMPACT** - Intentional breaking change for v5.0.0

#### Who's Affected?
**EVERYONE** - Both streaming and non-streaming users need changes

1. **Non-streaming users** - Must add `await`
   ```python
   # BEFORE
   result = agent.go(thread)
   
   # AFTER
   result = await agent.go(thread)
   ```

2. **Streaming users** - Must change method AND possibly parameter ⚠️
   ```python
   # BEFORE
   async for event in agent.go(thread, stream=True):
       print(event)
   
   # AFTER
   async for event in agent.stream(thread):
       print(event)
   ```

3. **Raw streaming users** - Must change method AND parameter name ⚠️
   ```python
   # BEFORE
   async for chunk in agent.go(thread, stream="raw"):
       process(chunk)
   
   # AFTER
   async for chunk in agent.stream(thread, mode="raw"):
       process(chunk)
   ```

#### Migration Complexity
- **Medium complexity**: 
  - Non-streaming: Add `await` (simple)
  - Streaming: Change method name + parameter (requires attention)
- **Easy detection**: 
  - Missing `await`: Runtime error
  - Old `stream` parameter: TypeError (unexpected keyword argument)
- **IDE support**: Most Python IDEs will highlight errors immediately

#### Estimated Impact
Based on grep results:
- **~30 example files** to update (~40% streaming)
- **~13 test files** with ~100+ test functions (~50% streaming in test files)
- **~14 documentation files** with ~80+ code samples (~30% streaming)
- **~2 integration files** (Space Monkey) to update
- **~1 CLI file** to update (uses streaming)

Total: ~60 files, ~250+ call sites (~100 streaming, ~150 non-streaming)

### Developer Experience
**POSITIVE IMPACT** - Significant improvements despite migration cost
- ✅ **Clear intent**: `.go()` vs `.stream()` is self-documenting
- ✅ **Single responsibility**: Each method does one thing well
- ✅ **Better types**: No Union return types to confuse type checkers
- ✅ **Industry standard**: Matches httpx, aiohttp, FastAPI patterns
- ✅ **Proper async**: Both methods work correctly with Python async/await
- ✅ **Enables observability**: Weave and similar tools work correctly
- ✅ **Prevents confusion**: No more `stream=True` changing everything

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

#### Detection - Two Error Types

**Error 1: Missing await**
```python
result = agent.go(thread)
# RuntimeWarning: coroutine 'Agent.go' was never awaited
```

**Error 2: Invalid parameter**
```python
async for event in agent.go(thread, stream=True):
# TypeError: go() got an unexpected keyword argument 'stream'
```

#### Migration Patterns

**Pattern 1: Non-streaming (add await)**
```python
# Find: agent.go(thread)
# Replace: await agent.go(thread)

# Find: agent.go(thread, stream=False)
# Replace: await agent.go(thread)
```

**Pattern 2: Event streaming (change method)**
```python
# Find: agent.go(thread, stream=True)
# Replace: agent.stream(thread)

# Find: agent.go(thread, stream="events")
# Replace: agent.stream(thread)
```

**Pattern 3: Raw streaming (change method + parameter)**
```python
# Find: agent.go(thread, stream="raw")
# Replace: agent.stream(thread, mode="raw")
```

#### Automated Migration Script
```python
# Can be done with regex find/replace in most editors:

# Step 1: Fix streaming calls
# Find:    \.go\((.*?),\s*stream=True\)
# Replace: .stream(\1)

# Find:    \.go\((.*?),\s*stream="events"\)
# Replace: .stream(\1)

# Find:    \.go\((.*?),\s*stream="raw"\)
# Replace: .stream(\1, mode="raw")

# Step 2: Fix non-streaming calls  
# Find:    =\s*agent\.go\(
# Replace: = await agent.go(

# Step 3: Remove now-invalid stream=False
# Find:    \.go\((.*?),\s*stream=False\)
# Replace: .go(\1)
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
Update 2 files:

**`chat.py`** - Change streaming call:
```python
# Line ~544
# FROM: async for event in agent.go(thread, stream=True):
# TO:   async for event in agent.stream(thread):
```

**`init.py`** - Add await:
```python
# Line ~124 (already has await, verify)
processed_thread, new_messages = await agent.go(thread)
```

### Documentation Update Strategy

1. **API Reference** - Update to show two separate methods
2. **Guides** - Update all code samples (both `.go()` and `.stream()`)
3. **Introduction/Quickstart** - Update first examples (critical for new users)
4. **CHANGELOG** - Document breaking change prominently with migration guide

### Migration Guide Template
Create `MIGRATION_V5.md` or add to CHANGELOG:

```markdown
## Migrating to Tyler v5.0.0

### Breaking Change: Split `.go()` into two methods

Tyler now has separate methods for streaming and non-streaming execution:
- `agent.go(thread)` - Returns final result (non-streaming)
- `agent.stream(thread)` - Yields events (streaming)

#### What Changed?

**1. Non-streaming: Add `await`**
```python
# v4.x (old)
result = agent.go(thread)

# v5.0.0 (new)  
result = await agent.go(thread)
```

**2. Streaming: Change method name**
```python
# v4.x (old)
async for event in agent.go(thread, stream=True):
    print(event)

# v5.0.0 (new)
async for event in agent.stream(thread):
    print(event)
```

**3. Raw streaming: Change method + parameter**
```python
# v4.x (old)
async for chunk in agent.go(thread, stream="raw"):
    process(chunk)

# v5.0.0 (new)
async for chunk in agent.stream(thread, mode="raw"):
    process(chunk)
```

#### Why This Change?

- **Clearer API**: Method names indicate behavior (`.go()` vs `.stream()`)
- **Better types**: No complex Union types, better IDE support
- **Industry standard**: Matches httpx, aiohttp, FastAPI patterns
- **Proper async**: Both methods work correctly with Python async/await
- **Single responsibility**: Each method does one thing well

#### How to Migrate?

**Quick Find/Replace (recommended order):**
```
1. Find:    .go(thread, stream=True)
   Replace: .stream(thread)

2. Find:    .go(thread, stream="events")
   Replace: .stream(thread)

3. Find:    .go(thread, stream="raw")
   Replace: .stream(thread, mode="raw")

4. Find:    = agent.go(
   Replace: = await agent.go(

5. Find:    .go(thread, stream=False)
   Replace: .go(thread)
```

Test after each step!
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
- **Core change** (agent.py): 2 hours (split into two methods, update routing)
- **Examples update**: 6 hours (30 files, ~40% need method change + await)
- **Tests update**: 6 hours (100+ functions, ~50% need method change)
- **Documentation update**: 8 hours (80+ samples, mix of .go() and .stream())
- **Integration updates** (Space Monkey, CLI): 2 hours (CLI uses streaming)
- **Testing & validation**: 5 hours (both methods need validation)
- **Total**: ~29 hours (~3.5 days)

### Review & Release
- **PR review**: 3 hours (more complex change)
- **Weave validation**: 2 hours (test both methods)
- **CHANGELOG & migration guide**: 3 hours (comprehensive guide needed)
- **Release prep**: 2 hours
- **Total**: ~10 hours (1.5 days)

### Grand Total: ~39 hours (~5 days)

**Note**: Increased from original estimate due to:
- Streaming calls need method changes (not just await)
- Two methods to implement and test instead of one
- More complex migration guide
- Higher % of code affected (everyone, not just non-streaming users)

