# Technical Design Review (TDR) — Agent `.run()` as Primary API

**Author**: AI Agent  
**Date**: 2025-10-29  
**Links**: 
- Spec: `/directive/specs/agent-run-primary/spec.md`
- Impact: `/directive/specs/agent-run-primary/impact.md`

---

## 1. Summary

We are making `agent.run()` the primary, documented method for executing Tyler agents, with `agent.go()` maintained as an undocumented backwards-compatible alias. This change addresses the friction users (including AI coding assistants) experience when they instinctively try `.run()` instead of `.go()`.

The implementation is trivial (renaming one method and creating an alias), but the impact is significant for developer experience. This aligns Tyler's API with Python ecosystem conventions (`asyncio.run()`, `app.run()`, etc.) and makes the framework more discoverable. The change is 100% backwards compatible - all existing code using `.go()` continues to work without modification.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Developer intuition**: Users naturally try `.run()` first (validated by AI assistant behavior)
- **Python conventions**: `.run()` is the standard execution pattern in Python async libraries
- **Reduced friction**: New users shouldn't need to consult docs for basic operations
- **Discoverability**: API should be guessable for experienced Python developers
- **Zero migration cost**: Must maintain backwards compatibility
- **Timing**: Pairs well with v5.0.0 which already includes `.go()` → `.stream()` split

### Non‑Goals
- **Breaking existing code**: `.go()` must continue to work indefinitely
- **Deprecating `.go()`**: No warnings, no sunset timeline (silent alias)
- **Renaming `.stream()`**: It's already a standard name
- **Internal refactoring**: No need to rename `._go_complete()` and other private methods
- **Migration tooling**: Not needed since backwards compatible
- **Supporting both names equally in docs**: Only `.run()` is documented

## 3. Current State — Codebase Map (concise)

### Key Modules

**Agent Implementation**:
- **`packages/tyler/tyler/models/agent.py`** (~1,801 lines)
  - `Agent` class extending Weave `Model`
  - `.go()` method (lines 587-617) - **Method to rename**
    - `async def go(self, thread_or_id: Union[Thread, str]) -> AgentResult`
    - Decorated with `@weave.op()`
    - Calls `self._go_complete(thread_or_id)`
  - `._go_complete()` (internal, no change needed)
  - `.stream()` method (lines 619-690) - **No changes**

**Documentation**:
- **`docs/`** - 20+ `.mdx` files referencing `.go()`
  - `quickstart.mdx` - Primary user entry point
  - `guides/*.mdx` - 8 guide files
  - `api-reference/tyler-agent.mdx` - API documentation
  
**Examples**:
- **`examples/`** - 8 files using `.go()`
- **`packages/tyler/examples/`** - 14 files using `.go()`
- **`packages/space-monkey/examples/`** - May use `.go()`

### Current Implementation

```python
# Current code (agent.py, lines 587-617)
@weave.op()
async def go(
    self, 
    thread_or_id: Union[Thread, str]
) -> AgentResult:
    """
    Execute the agent and return the complete result.
    
    This method runs the agent to completion, handling tool calls,
    managing conversation flow, and returning the final result with
    all messages and execution details.
    
    Args:
        thread_or_id: Thread object or thread ID to process. The thread will be
                     modified in-place with new messages.
        
    Returns:
        AgentResult containing the updated thread, new messages,
        final output, and complete execution details.
    
    Raises:
        ValueError: If thread_id is provided but thread is not found
        Exception: Re-raises any unhandled exceptions during execution,
                  but execution details are still available in the result
                  
    Example:
        result = await agent.go(thread)
        print(f"Response: {result.content}")
        print(f"New messages: {len(result.new_messages)}")
    """
    logger.debug("Agent.go() called (non-streaming mode)")
    return await self._go_complete(thread_or_id)
```

### External Contracts
- **Public API**: `Agent.go()` is the documented method
- **Return Type**: `AgentResult` (unchanged)
- **Weave Integration**: `@weave.op()` decorator (unchanged)
- **Async Model**: Returns awaitable (unchanged)

### Observability
- Weave tracing via `@weave.op()` decorator
- Debug logging: `logger.debug("Agent.go() called...")`
- Execution events via `ExecutionEvent` (unchanged)

## 4. Proposed Design (high level, implementation‑agnostic)

### Overall Approach

**Phase 1: Code Change** (agent.py only)
1. Rename `go()` → `run()` 
2. Create alias: `go = run`
3. Update docstrings to reference `.run()` as primary
4. Update debug log message

**Phase 2: Documentation Update** (all docs)
1. Find-replace `.go(` → `.run(` in all `.mdx` files
2. Update API reference to show `.run()` as primary
3. Verify no references to `.go()` in public docs

**Phase 3: Example Update** (all examples)
1. Find-replace `.go(` → `.run(` in all example files
2. Verify examples still run correctly
3. Update example READMEs if needed

**Phase 4: Testing** (verify both work)
1. Update ALL existing tests to use `.run()` (new primary method)
2. Add ONE new test verifying `.go()` alias works (backwards compatibility)
3. Verify identical behavior

### Component Responsibilities

**Agent Class**:
- Provide `run()` as primary execution method
- Maintain `go()` as alias for backwards compatibility
- Both decorated with `@weave.op()` for tracing

**Documentation**:
- Reference only `.run()` in all user-facing materials
- Provide clear examples of `.run()` usage
- Do not mention `.go()` (it exists but is not promoted)

**Examples**:
- Demonstrate `.run()` as the standard pattern
- Show async usage: `result = await agent.run(thread)`
- Pair with `.stream()` for streaming examples

### Interfaces & Data Contracts

**No changes to contracts**:
```python
# Both methods have identical signature
async def run(self, thread_or_id: Union[Thread, str]) -> AgentResult
async def go(self, thread_or_id: Union[Thread, str]) -> AgentResult  # Alias
```

**Weave Integration**:
```python
@weave.op()
async def run(self, thread_or_id: Union[Thread, str]) -> AgentResult:
    """..."""
    logger.debug("Agent.run() called (non-streaming mode)")
    return await self._go_complete(thread_or_id)

# Backwards compatibility alias
go = run  # Will inherit @weave.op() decoration
```

### Error Handling
- No changes to error handling
- Both methods raise identical exceptions
- Stack traces will show `run()` or `go()` based on what user called

### Performance
- Zero performance impact (alias has no overhead)
- Same code path for both methods
- No additional allocations or indirection

## 5. Alternatives Considered

### Option A: Keep `.go()` as Primary (Status Quo)
**Pros**:
- No work required
- No doc updates needed
- Familiar to existing users

**Cons**:
- Non-standard in Python ecosystem
- Users instinctively try `.run()` and fail
- Requires documentation lookup for basic operations
- AI assistants default to wrong method name
- Perpetuates Tyler-specific convention

**Verdict**: ❌ Rejected - User friction outweighs familiarity benefit

### Option B: Add `.run()` as Alias (Keep `.go()` Primary)
**Pros**:
- Minimal code change
- Both methods work
- Backwards compatible

**Cons**:
- Docs still show non-standard `.go()`
- Doesn't solve discoverability problem
- Maintains confusion for new users
- Two equally-promoted names causes choice paralysis

**Verdict**: ❌ Rejected - Doesn't solve the core problem

### Option C: Add `.run()` as Primary, `.go()` as Undocumented Alias (Chosen)
**Pros**:
- ✅ Aligns with Python conventions
- ✅ Improves discoverability
- ✅ Zero breaking changes (`.go()` still works)
- ✅ Clear migration path (use `.run()` in new code)
- ✅ AI assistants will default to correct method
- ✅ Reduces documentation friction
- ✅ Single recommended method (no choice paralysis)

**Cons**:
- Requires doc updates (one-time cost)
- Old blog posts may reference `.go()` (still works)
- Minimal confusion period during transition

**Verdict**: ✅ **Chosen** - Best balance of user experience and backwards compatibility

### Option D: Deprecate `.go()` with Warnings
**Pros**:
- Forces migration to new API
- Clear sunset timeline

**Cons**:
- ❌ Breaking change for existing users
- ❌ Noisy warnings in logs
- ❌ Unnecessary friction (`.go()` works fine)
- ❌ Violates backwards compatibility principle

**Verdict**: ❌ Rejected - Too disruptive for minimal benefit

## 6. Data Model & Contract Changes

### API Changes

**New Primary Method**:
```python
@weave.op()
async def run(
    self, 
    thread_or_id: Union[Thread, str]
) -> AgentResult:
    """
    Execute the agent and return the complete result.
    
    This method runs the agent to completion, handling tool calls,
    managing conversation flow, and returning the final result.
    
    Args:
        thread_or_id: Thread object or thread ID to process
        
    Returns:
        AgentResult containing the updated thread, new messages,
        final output, and complete execution details
    
    Raises:
        ValueError: If thread_id is provided but thread is not found
        Exception: Re-raises any unhandled exceptions during execution
                  
    Example:
        result = await agent.run(thread)
        print(f"Response: {result.content}")
    """
    logger.debug("Agent.run() called (non-streaming mode)")
    return await self._go_complete(thread_or_id)
```

**Backwards Compatibility Alias**:
```python
# Maintain backwards compatibility (undocumented)
go = run
```

### No Schema Changes
- No database migrations
- No message format changes
- No event schema changes
- No configuration changes

### Backward Compatibility
- **100% backwards compatible**
- All code using `.go()` continues to work
- No deprecation warnings
- No sunset timeline
- `.go()` is a permanent alias (not temporary)

### Versioning
- Include in **v5.0.0** release
- No semver bump needed (backwards compatible)
- Release notes document new recommended method

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- **No changes** to authentication or authorization
- Same execution model and permissions
- No new security surface area

### Secrets Management
- **No changes** to how API keys or secrets are handled
- Same configuration patterns

### PII Handling
- **No changes** to data handling
- Same thread/message storage patterns

### Threat Model
- **No new threats** introduced
- Same attack surface as before
- Both methods execute identical code paths

## 8. Observability & Operations

### Logs

**Update debug log message**:
```python
# Before
logger.debug("Agent.go() called (non-streaming mode)")

# After (in run method)
logger.debug("Agent.run() called (non-streaming mode)")

# Alias will show same message
```

**Impact**: Logs will show "Agent.run()" for new code, "Agent.run()" for aliased `.go()` calls (both use same method)

### Metrics

**Weave Tracing**:
- Both `run` and `go` will be traced
- Weave sees them as the same operation (alias)
- No changes needed to observability setup

**Optional Enhancement** (not required):
- Could track `.run()` vs `.go()` usage via telemetry
- Could measure adoption rate over time
- Not critical for this change

### Dashboards & Alerts
- **No changes required**
- Same execution patterns
- Same error conditions
- Same performance characteristics

### Runbooks
- Update runbooks to reference `.run()` instead of `.go()`
- No operational changes needed

## 9. Rollout & Migration

### Feature Flags
**Not needed** - This is a pure alias, no conditional behavior

### Rollout Strategy

**Single Release** (v5.0.0):
1. Ship code change (rename + alias)
2. Ship doc updates (all `.mdx` files)
3. Ship example updates (all `.py` files)
4. No gradual rollout needed (backwards compatible)

### User Migration

**Optional** (not required):
```python
# Users can continue using old code
result = await agent.go(thread)  # Still works

# Or update to new recommended pattern
result = await agent.run(thread)  # Recommended

# No action required - both work identically
```

### Data Migration
**Not applicable** - No data changes

### Revert Plan

**Revert is trivial**:
1. Rename `run()` back to `go()`
2. Remove alias
3. Revert doc changes

**Blast Radius**: Zero - alias means both methods always work

### Monitoring During Rollout
- Monitor for user confusion or questions
- Watch for issues in community forums
- Check for regression bugs (unlikely - minimal code change)

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
**Process**:
1. Write failing test for `.run()` method
2. Confirm test fails (method doesn't exist yet)
3. Implement `.run()` method
4. Verify test passes
5. Refactor if needed

### Spec→Test Mapping

**From Spec Acceptance Criteria**:

| Spec Criterion | Test ID | Type | Description |
|---------------|---------|------|-------------|
| `await agent.run(thread)` returns `AgentResult` | All existing tests (updated) | Unit | All existing tests updated to use `.run()` |
| `await agent.go(thread)` returns `AgentResult` (backwards compat) | `test_go_alias_backwards_compatibility` | Unit | Single new test verifying `.go()` alias works |
| Quickstart shows only `.run()` | `test_docs_use_run` | Doc validation | Grep docs to ensure `.go()` not present |
| Examples use `.run()` | `test_examples_use_run` | Example validation | Verify all examples updated |

### Test Tiers

**Unit Tests** (`test_agent.py`):

All existing tests will be updated to use `.run()`. Only add ONE new test:

```python
@pytest.mark.asyncio
async def test_go_alias_backwards_compatibility():
    """Test that .go() still works as an alias for backwards compatibility"""
    agent = Agent(name="TestAgent")
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Call .go() to verify the alias works
    result = await agent.go(thread)
    
    # Should work identically to .run()
    assert isinstance(result, AgentResult)
    assert result.thread == thread
    assert len(result.new_messages) > 0
```

All other existing tests update `.go(` → `.run(`

**Integration Tests**:
```python
@pytest.mark.asyncio
async def test_run_with_tools():
    """Test .run() with tool execution"""
    def test_tool():
        return "tool result"
    
    agent = Agent(name="TestAgent", tools=[test_tool])
    thread = Thread()
    thread.add_message(Message(role="user", content="Use the test tool"))
    
    result = await agent.run(thread)
    
    assert any(msg.role == "tool" for msg in result.new_messages)

@pytest.mark.asyncio  
async def test_run_with_thread_store():
    """Test .run() with thread persistence"""
    thread_store = ThreadStore()
    agent = Agent(name="TestAgent", thread_store=thread_store)
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    result = await agent.run(thread)
    
    # Verify thread was saved
    loaded_thread = await thread_store.load(thread.id)
    assert loaded_thread is not None
```

**Documentation Validation**:
```python
def test_docs_use_run_not_go():
    """Verify documentation uses .run() not .go()"""
    docs_path = Path("docs")
    violations = []
    
    for mdx_file in docs_path.rglob("*.mdx"):
        content = mdx_file.read_text()
        if ".go(" in content:
            violations.append(str(mdx_file))
    
    assert len(violations) == 0, f"Files still using .go(): {violations}"

def test_examples_use_run_not_go():
    """Verify examples use .run() not .go()"""
    examples_paths = [Path("examples"), Path("packages/tyler/examples")]
    violations = []
    
    for examples_path in examples_paths:
        for py_file in examples_path.rglob("*.py"):
            content = py_file.read_text()
            if "agent.go(" in content or ".go(" in content:
                violations.append(str(py_file))
    
    assert len(violations) == 0, f"Files still using .go(): {violations}"
```

### Negative & Edge Cases

```python
@pytest.mark.asyncio
async def test_run_with_invalid_thread_id():
    """Test .run() with non-existent thread ID"""
    thread_store = ThreadStore()
    agent = Agent(name="TestAgent", thread_store=thread_store)
    
    with pytest.raises(ValueError):
        await agent.run("nonexistent-thread-id")

@pytest.mark.asyncio
async def test_run_with_empty_thread():
    """Test .run() with thread containing no messages"""
    agent = Agent(name="TestAgent")
    thread = Thread()  # Empty thread
    
    result = await agent.run(thread)
    
    # Should handle gracefully (implementation-dependent)
    assert isinstance(result, AgentResult)
```

### Performance Tests

**Not required** for this change (alias has zero overhead), but could verify:

```python
@pytest.mark.benchmark
async def test_run_performance_equivalent_to_go():
    """Verify .run() has same performance as .go() (both are same method)"""
    agent = Agent(name="TestAgent")
    thread = Thread()
    thread.add_message(Message(role="user", content="Test"))
    
    # Both should have identical performance (same method)
    import time
    
    start = time.perf_counter()
    await agent.run(thread)
    run_time = time.perf_counter() - start
    
    thread2 = Thread()
    thread2.add_message(Message(role="user", content="Test"))
    
    start = time.perf_counter()
    await agent.go(thread2)
    go_time = time.perf_counter() - start
    
    # Should be nearly identical (within 10% variance)
    assert abs(run_time - go_time) / run_time < 0.1
```

### CI Integration

**All tests must**:
- Run in CI on every commit
- Block merge if any tests fail
- Include linting (no `.go(` in docs or examples)
- Include type checking

## 11. Risks & Open Questions

### Known Risks

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Users find old tutorials using `.go()` | Low | Old code still works (alias) | ✅ Mitigated |
| Confusion about which method to use | Low | Only document `.run()` | ✅ Mitigated |
| Breaking external dependencies | Low | Backwards compatible (`.go()` works) | ✅ Mitigated |
| Weave tracing issues with alias | Medium | Test thoroughly, verify alias inherits decorator | ⚠️ Needs testing |

### Open Questions

| Question | Proposed Resolution | Owner |
|----------|-------------------|-------|
| Should we rename internal `._go_complete()` method? | **No** - Internal implementation detail, no user impact | Engineer |
| Should we add telemetry to track `.run()` vs `.go()` usage? | **Optional** - Nice to have, not required | Product |
| Should we update blog posts or external content? | **Naturally** - Update over time, not blocking | Community |
| What about other packages (space-monkey, narrator)? | **Review** - Update any examples using `.go()` | Engineer |

### Paths to Resolve

**Weave Tracing with Alias**:
- **Test**: Create test verifying `go = run` inherits `@weave.op()`
- **Alternative**: If alias doesn't inherit decorator, create wrapper function instead
- **Timeline**: Resolve during implementation (before PR)

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

#### Task 1: Update Agent Class ✅
**DoD**:
- [ ] Rename `go()` → `run()` in `agent.py`
- [ ] Add alias: `go = run`
- [ ] Rename internal methods for consistency:
  - [ ] `_go_complete()` → `_run_complete()`
  - [ ] `_go_stream()` → `_stream_events()`
  - [ ] `_go_stream_raw()` → `_stream_raw()`
- [ ] Update internal method calls to use new names
- [ ] Update docstrings to reference `.run()` as primary
- [ ] Update debug log messages
- [ ] Tests pass (`.run()` works)
- [ ] Tests pass (`.go()` alias works)
- [ ] Linting passes

**Estimate**: 45 minutes  
**Owner**: Engineer  
**Dependencies**: None

#### Task 2: Update Tests ✅
**DoD**:
- [ ] Find-replace ALL existing tests: `.go(` → `.run(`
- [ ] Add single new test: `test_go_alias_backwards_compatibility()`
- [ ] Verify this test proves `.go()` still works
- [ ] All tests pass (382+ tests)
- [ ] Coverage maintained or increased

**Estimate**: 45 minutes  
**Owner**: Engineer  
**Dependencies**: Task 1

#### Task 3: Update Documentation ✅
**DoD**:
- [ ] Find-replace `.go(` → `.run(` in all `.mdx` files
- [ ] Update API reference (`tyler-agent.mdx`)
- [ ] Review all doc changes for correctness
- [ ] Add doc validation test (`test_docs_use_run`)
- [ ] Doc validation test passes

**Estimate**: 1 hour  
**Owner**: Engineer  
**Dependencies**: Task 1

#### Task 4: Update Examples ✅
**DoD**:
- [ ] Update all files in `examples/`
- [ ] Update all files in `packages/tyler/examples/`
- [ ] Check `packages/space-monkey/examples/`
- [ ] Verify examples still run correctly
- [ ] Add example validation test (`test_examples_use_run`)
- [ ] Example validation test passes

**Estimate**: 1 hour  
**Owner**: Engineer  
**Dependencies**: Task 1

#### Task 5: Integration Testing ✅
**DoD**:
- [ ] Run full test suite
- [ ] Verify all existing tests still pass
- [ ] Test with real LLM (smoke test)
- [ ] Test streaming still works (`.stream()` unchanged)
- [ ] Test thread persistence
- [ ] Test Weave tracing works

**Estimate**: 30 minutes  
**Owner**: Engineer  
**Dependencies**: Tasks 1-4

#### Task 6: Final Review & PR ✅
**DoD**:
- [ ] All tests passing (382+ tests)
- [ ] Linting passes
- [ ] No `.go(` in docs or examples (validation tests pass)
- [ ] PR description written
- [ ] Spec criteria verified
- [ ] Ready for review

**Estimate**: 30 minutes  
**Owner**: Engineer  
**Dependencies**: Tasks 1-5

### Total Estimate
**5 hours** (just over half a day of focused work)

### Dependencies
- No external dependencies
- No coordination with other teams needed
- Can be developed and tested independently

---

## Approval Gate

**Do not start coding until this TDR is reviewed and approved.**

### Review Checklist
- [ ] Spec approved
- [ ] Impact Analysis approved  
- [ ] TDR approved
- [ ] Test strategy approved
- [ ] Ready to implement

