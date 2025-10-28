# Technical Design Review (TDR) — Async Agent.go() Method

**Author**: AI Agent  
**Date**: 2025-10-28  
**Links**: 
- Spec: `/directive/specs/agent-go-async/spec.md`
- Impact: `/directive/specs/agent-go-async/impact.md`

---

## 1. Summary

We are converting `Agent.go()` from a synchronous function to an async method to create a clearer, more semantically correct API that properly expresses its async nature. This change makes async operations explicit in the method signature, follows Python async best practices, and enables proper observability tooling integration (like Weave).

Currently, `.go()` appears synchronous but performs async operations internally (database calls, network requests, tool execution), creating confusion and breaking observability tools that expect async generators to come from async functions. By making it `async def`, we provide developers with clear API semantics, enable better IDE support, and ensure the method signature accurately represents its behavior.

This is an intentional breaking change for v5.0.0. Non-streaming usage requires adding `await`, while streaming usage remains unchanged. The migration is straightforward (add `await`), with clear Python error messages guiding developers.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **API clarity**: Method signature should reflect async nature (database I/O, network calls, tool execution)
- **Python best practices**: Async generators should come from async functions, not sync functions returning them
- **Developer experience**: Eliminate confusion about sync vs async behavior
- **Observability tooling**: Enable Weave and similar tools to properly trace execution
- **Consistency**: Align public API with internal implementation (all internal methods are async)
- **IDE support**: Better autocomplete, type hints, and error detection with proper async signatures

### Non‑Goals
- **Changing execution logic** - All tool execution, iteration limits, error handling stay identical
- **Changing return types** - `AgentResult`, `ExecutionEvent`, raw chunks remain the same
- **Backward compatibility** - This is an intentional breaking change for better DX
- **New features** - No new streaming modes, no new capabilities, pure API refactor
- **Performance optimization** - Async overhead is negligible; this is about correctness not speed
- **Deprecation period** - Clean break for v5.0.0 (framework is new, few users)

## 3. Current State — Codebase Map

### Key Modules

#### Agent Implementation
- **`tyler/models/agent.py`** (1,816 lines)
  - `Agent` class (extends Weave `Model`)
  - `.go()` method (lines 610-690) - **Current target for change**
    - Currently `def go(...)` (synchronous)
    - Routes to 3 implementations based on `stream` parameter
    - Returns awaitables or generators directly (no await/yield)
  - `._go_complete()` (lines 692-974) - Non-streaming implementation
    - Already `async def` ✅
    - Returns `AgentResult`
  - `._go_stream()` (lines 976-1,407) - Event streaming implementation
    - Already `async def` ✅
    - Yields `ExecutionEvent` objects
  - `._go_stream_raw()` (lines 1,512-1,748) - Raw chunk streaming
    - Already `async def` ✅
    - Yields raw LiteLLM chunks
  - All internal methods already async (no changes needed)

#### Related Components
- **`tyler/models/execution.py`** - `AgentResult`, `ExecutionEvent` (unchanged)
- **`tyler/models/completion_handler.py`** - LLM interaction (unchanged)
- **`tyler/models/message_factory.py`** - Message creation (unchanged)
- **`tyler/utils/tool_runner.py`** - Tool execution (unchanged)

### Current Implementation

#### The Problem Pattern
```python
@weave.op()
def go(self, thread_or_id, stream=False):
    """Process the thread with the agent."""
    # Normalize stream parameter
    if stream is True:
        stream_mode = "events"
    elif stream is False:
        stream_mode = None
    # ...
    
    # Route to implementations
    if stream_mode is None:
        return self._go_complete(thread_or_id)  # ❌ Returns awaitable (not awaited)
    elif stream_mode == "events":
        return self._go_stream(thread_or_id)   # ❌ Returns generator (not yielded from)
    elif stream_mode == "raw":
        return self._go_stream_raw(thread_or_id)  # ❌ Returns generator (not yielded from)
```

**Issues**:
1. Method is `def` but all return values require async context
2. Returns generators from async generator functions (unusual pattern)
3. Weave's `@weave.op()` expects async functions for async generators
4. Misleading signature - looks sync but does async work

#### Current Usage Patterns
```python
# Non-streaming (appears sync, but isn't)
result = agent.go(thread)  # ❌ No await needed? Confusing!

# Streaming (clearly async context required)
async for event in agent.go(thread, stream=True):  # ✅ But method signature says def, not async def
    print(event)
```

### External Contracts

#### Weave Integration (Currently Broken)
```python
@weave.op()  # Weave decorator
def go(...):  # Non-async function
    return self._go_stream(...)  # Returns async generator

# Result: Weave sees generator object creation, not actual yielded events
# Weave engineers confirmed: "it's because your func is not async"
```

#### Call Sites (from grep analysis)
- **151 call sites** in Python files
- **108 call sites** in documentation
- Most streaming calls already use `async for` (no change needed)
- Non-streaming calls need `await` added (~60-80 sites)

### Observability Currently Available
- `@weave.op()` decorator on `.go()` (doesn't work correctly for generators)
- Weave tracing on internal methods (works correctly)
- Standard Python logging throughout execution
- ExecutionEvent stream provides detailed telemetry

## 4. Proposed Design

### Architecture Overview

```
User Code
    │
    ├─ Non-streaming: await agent.go(thread)
    │       │
    │       └─→ async def go(...)
    │               └─→ return await self._go_complete(...)  ← Added await
    │                       │
    │                       └─→ Returns AgentResult
    │
    └─ Streaming: async for event in agent.go(thread, stream=True)
            │
            └─→ async def go(...)
                    └─→ async for event in self._go_stream(...):  ← Changed to yield from
                            yield event
                            │
                            └─→ Yields ExecutionEvent objects
```

### Component Changes

#### 1. Method Signature Change
```python
# BEFORE
@weave.op()
def go(
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:

# AFTER
@weave.op()
async def go(  # ← Change: def → async def
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
```

**No changes to**:
- Parameter types
- Return type annotations
- `@overload` decorators (they also get `async def`)
- Docstring structure

#### 2. Implementation Changes

**Non-streaming mode**:
```python
# BEFORE
if stream_mode is None:
    return self._go_complete(thread_or_id)

# AFTER
if stream_mode is None:
    return await self._go_complete(thread_or_id)  # ← Add await
```

**Event streaming mode**:
```python
# BEFORE
elif stream_mode == "events":
    return self._go_stream(thread_or_id)

# AFTER
elif stream_mode == "events":
    async for event in self._go_stream(thread_or_id):  # ← Yield from generator
        yield event
```

**Raw streaming mode**:
```python
# BEFORE
elif stream_mode == "raw":
    return self._go_stream_raw(thread_or_id)

# AFTER
elif stream_mode == "raw":
    async for chunk in self._go_stream_raw(thread_or_id):  # ← Yield from generator
        yield chunk
```

### Complete Implementation

```python
@overload
async def go(  # ← async added
    self, 
    thread_or_id: Union[Thread, str],
    stream: Literal[False] = False
) -> AgentResult:
    ...

@overload
async def go(  # ← async added
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[Literal[True], Literal["events"]]
) -> AsyncGenerator[ExecutionEvent, None]:
    ...

@overload
async def go(  # ← async added
    self, 
    thread_or_id: Union[Thread, str],
    stream: Literal["raw"]
) -> AsyncGenerator[Any, None]:
    ...

@weave.op()
async def go(  # ← Change: def → async def
    self, 
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
    """
    Process the thread with the agent.
    
    [Docstring updated with await in examples]
    """
    # Normalize and validate stream parameter (unchanged)
    if stream is True:
        stream_mode = "events"
    elif stream is False:
        stream_mode = None
    elif stream in ("events", "raw"):
        stream_mode = stream
    else:
        raise ValueError(
            f"Invalid stream value: {stream}. "
            f"Must be False, True, 'events', or 'raw'"
        )
    
    logger.debug(f"Agent.go() called with stream mode: {stream_mode}")
    
    # Route to appropriate implementation
    if stream_mode is None:
        return await self._go_complete(thread_or_id)  # ← Add await
    elif stream_mode == "events":
        async for event in self._go_stream(thread_or_id):  # ← Yield from
            yield event
    elif stream_mode == "raw":
        async for chunk in self._go_stream_raw(thread_or_id):  # ← Yield from
            yield chunk
    else:
        # Should never reach here due to validation above
        raise ValueError(f"Unexpected stream mode: {stream_mode}")
```

### Error Handling

No changes to error handling logic - all errors propagate identically:

```python
# Internal errors (unchanged)
try:
    return await self._go_complete(thread_or_id)
except ValueError:
    raise  # Thread not found, etc.
except Exception as e:
    # Still handled inside _go_complete()
    ...

# Validation errors (unchanged)
raise ValueError("Invalid stream value...")
```

### Performance Expectations

**Negligible overhead**:
- `async def` vs `def` has minimal performance cost
- No additional async/await in hot paths (already async internally)
- Generator delegation (`async for ... yield`) is optimized by Python

**Expected metrics**:
- Latency: No measurable change (<1ms overhead per call)
- Memory: No change (same object lifecycle)
- Throughput: No change (same execution flow)

## 5. Alternatives Considered

### Option A: Keep sync wrapper, remove `@weave.op()` from internal methods
**Approach**: Leave `.go()` as `def`, remove `@weave.op()` from `._go_stream()` and `._go_stream_raw()`

**Pros**:
- No breaking changes
- Simpler migration

**Cons**:
- ❌ Doesn't solve the core problem (API still misleading)
- ❌ Loses granular Weave tracing for streaming modes
- ❌ Still violates async best practices
- ❌ Doesn't improve developer experience

**Why rejected**: Fixes symptom (Weave), not disease (misleading API)

### Option B: Provide both sync wrapper and async method
**Approach**: Keep `.go()` as sync, add `.go_async()` as async alternative

```python
def go(...):
    """Deprecated wrapper"""
    return self.go_async(...)

async def go_async(...):
    """New async implementation"""
    ...
```

**Pros**:
- Backward compatible
- Gradual migration path

**Cons**:
- ❌ API fragmentation (two ways to do same thing)
- ❌ Confusing for new users
- ❌ Maintenance burden (two methods to maintain)
- ❌ Sync wrapper still misleading
- ❌ Delayed migration (tech debt lingers)

**Why rejected**: Framework is new, clean break is better than API bloat

### Option C: Make entire Agent class async context manager
**Approach**: Require `async with Agent(...) as agent:` pattern

**Pros**:
- Clear async semantics
- Could auto-connect/disconnect MCP

**Cons**:
- ❌ Much larger breaking change
- ❌ Unnecessary ceremony for non-MCP usage
- ❌ Doesn't match existing patterns
- ❌ Confusing scope implications

**Why rejected**: Over-engineered, doesn't match the problem

### Option D (Chosen): Make `.go()` async, clean break
**Approach**: Convert to `async def`, update all call sites, release as v5.0.0

**Pros**:
- ✅ Semantically correct API
- ✅ Follows Python best practices
- ✅ Enables proper tooling (Weave, IDEs)
- ✅ Clear migration path (add `await`)
- ✅ No API fragmentation
- ✅ Clean break while framework is young

**Cons**:
- ⚠️ Breaking change (but users expect this pre-v1.0)
- ⚠️ ~60 files to update (manageable)

**Why chosen**: Best long-term solution, clean API, acceptable migration cost

## 6. Data Model & Contract Changes

### API Changes

#### Breaking Change: Method Signature
```python
# v4.x
def go(...) -> Union[AgentResult, AsyncGenerator[...]]

# v5.0.0
async def go(...) -> Union[AgentResult, AsyncGenerator[...]]
```

**Impact**:
- Non-streaming: `result = agent.go(thread)` → `result = await agent.go(thread)`
- Streaming: No change (`async for event in agent.go(...)`)

#### No Changes To
- Return types (AgentResult, ExecutionEvent, raw chunks)
- Parameter types (thread_or_id, stream)
- Event structures or data models
- Thread/Message/Attachment schemas
- Tool execution contracts

### Backward Compatibility

**None** - This is an intentional breaking change:

```python
# v4.x (OLD)
result = agent.go(thread)  # Works
result = await agent.go(thread)  # Also works (awaiting returns AgentResult)

# v5.0.0 (NEW)
result = agent.go(thread)  # RuntimeWarning: coroutine never awaited
result = await agent.go(thread)  # Works ✅
```

### Deprecation Plan

**No deprecation period** - Clean break for v5.0.0:
1. Framework is new (Tyler v4.x is months old)
2. Limited production usage
3. Simple migration (add `await`)
4. Clear error messages guide users

## 7. Security, Privacy, Compliance

### AuthN/AuthZ Impact
**None** - No changes to:
- API key handling
- Authentication flows
- Authorization checks
- User permissions

### Secrets Management
**None** - No changes to:
- Environment variable handling
- API key storage
- MCP server credentials
- Tool authentication

### PII Handling
**None** - No changes to:
- Message content processing
- File attachment handling
- Thread storage
- Data retention

### Threat Model
**No new threats**:
- No new network calls
- No new file operations
- No new user input processing
- No new attack surface

**Existing mitigations remain**:
- Tool execution sandboxing (unchanged)
- Input validation (unchanged)
- Rate limiting (application level, unchanged)

## 8. Observability & Operations

### Logs

**No new log points** - All existing logging works:
```python
# In .go() (unchanged)
logger.debug(f"Agent.go() called with stream mode: {stream_mode}")

# In ._go_complete() (unchanged)
logger.info("Starting agent execution...")
logger.error("Error during execution: ...")

# In ._go_stream() (unchanged)
logger.debug("Streaming execution started...")
```

### Metrics

**Primary benefit** - Weave observability now works correctly:

#### Before (Broken)
```
Weave Call Tree:
├─ Agent.go() - <generator object at 0x...>  ← Empty, unhelpful
└─ (no nested operations captured)
```

#### After (Fixed)
```
Weave Call Tree:
├─ Agent.go()
│  ├─ _go_stream()
│  │  ├─ step() - LLM request
│  │  │  └─ acompletion() - 1.2s, 150 tokens
│  │  ├─ tool_execution: web_search - 0.8s
│  │  ├─ step() - LLM request
│  │  │  └─ acompletion() - 0.9s, 200 tokens
│  │  └─ ...
```

### Dashboards & Alerts

**No changes required**:
- Existing Weave dashboards automatically improve (better traces)
- No new alerting needed
- No operational thresholds changed

### Runbooks & SLOs

**No impact**:
- Async/await doesn't change failure modes
- Same retry logic
- Same timeout behavior
- Same error conditions

## 9. Rollout & Migration

### Feature Flags

**Not applicable** - This is a code-level change, not a runtime feature toggle

### Guardrails

**Python runtime** provides guardrails:
```python
# Automatic detection of missing await
result = agent.go(thread)
# RuntimeWarning: coroutine 'Agent.go' was never awaited
# RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

### Migration Strategy

#### Phase 1: Update Core Implementation (1 hour)
1. Change `def go(...)` → `async def go(...)`
2. Add `await` to `_go_complete()` call
3. Change `return` → `async for ... yield` for streaming modes
4. Update docstring examples

#### Phase 2: Update Examples (4 hours)
1. Add `await` to ~30 example files
2. Verify each example runs correctly
3. Update README snippets

#### Phase 3: Update Tests (4 hours)
1. Add `await` to ~100 test call sites
2. Run full test suite
3. Fix any test failures

#### Phase 4: Update Documentation (6 hours)
1. Update ~80 code samples in docs
2. Update API reference
3. Add migration guide to CHANGELOG

#### Phase 5: Integration Updates (1 hour)
1. Verify Space Monkey (already has `await`)
2. Verify CLI (already has `await`)
3. Test cross-package integrations

### Revert Plan

**Simple rollback** - Single commit:
```bash
git revert <commit-hash>  # Reverts all changes
```

**Low blast radius**:
- No database migrations to roll back
- No data format changes
- No deployed services affected (Python package)
- Users can downgrade: `pip install tyler==4.2.0`

### Version Strategy

**Semantic Versioning**:
- v4.2.0 → v5.0.0 (major version bump)
- Breaking change clearly documented
- Migration guide in CHANGELOG

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment

We will follow strict TDD:
1. ✅ **Write failing test** - Add `await` to test, verify it passes
2. ✅ **Confirm failure** - Remove `await`, verify test fails with "coroutine never awaited"
3. ✅ **Implement** - Change `def go` → `async def go`
4. ✅ **Verify pass** - All tests pass
5. ✅ **Refactor** - Clean up, ensure consistency

### Spec → Test Mapping

From `spec.md` acceptance criteria:

| Acceptance Criterion | Test ID(s) | Test File |
|---------------------|------------|-----------|
| **Non-Streaming Mode - Clear Async Semantics** | `test_agent_go_async_non_streaming` | `test_agent.py` |
| Non-streaming returns AgentResult when awaited | `test_go_returns_agent_result` | `test_agent.py` |
| Non-streaming processes messages correctly | `test_go_processes_thread` | `test_agent.py` |
| **Event Streaming Mode - Consistent Async Pattern** | `test_agent_go_async_event_streaming` | `test_agent_streaming.py` |
| Event streaming yields ExecutionEvents | `test_go_stream_events` | `test_agent_streaming.py` |
| Event streaming works with async for | `test_go_stream_async_iteration` | `test_agent_streaming.py` |
| **Raw Streaming Mode - Consistent Async Pattern** | `test_agent_go_async_raw_streaming` | `test_agent_streaming.py` |
| Raw streaming yields LiteLLM chunks | `test_go_stream_raw_chunks` | `test_agent_streaming.py` |
| **API Clarity - Developer Can See Async Nature** | `test_agent_go_signature_is_async` | `test_agent.py` |
| Method signature shows async def | `test_go_is_coroutine_function` | `test_agent.py` |
| **Invalid Stream Parameter (Negative Case)** | `test_go_invalid_stream_raises` | `test_agent.py` |
| Invalid stream value raises ValueError | `test_go_invalid_stream_error_message` | `test_agent.py` |
| **Observability Tooling Works (Validation)** | `test_weave_traces_go_correctly` | `test_agent_observability.py` |
| Weave captures complete execution trace | `test_weave_streaming_trace` | `test_agent_observability.py` |
| **Breaking Change - Clear Error Message** | `test_go_without_await_warns` | `test_agent.py` |
| Forgetting await produces clear error | (manual validation - Python runtime) | - |

### Test Tiers

#### Unit Tests
```python
# test_agent.py
async def test_go_is_async():
    """Verify .go() is an async function"""
    assert inspect.iscoroutinefunction(Agent.go)

async def test_go_non_streaming_requires_await():
    """Verify non-streaming mode returns AgentResult when awaited"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    result = await agent.go(thread)
    assert isinstance(result, AgentResult)
    assert result.content is not None

async def test_go_streaming_events():
    """Verify event streaming yields ExecutionEvents"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    events = []
    async for event in agent.go(thread, stream=True):
        events.append(event)
        if event.type == EventType.EXECUTION_COMPLETE:
            break
    
    assert len(events) > 0
    assert all(isinstance(e, ExecutionEvent) for e in events)

async def test_go_streaming_raw():
    """Verify raw streaming yields chunks"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = []
    async for chunk in agent.go(thread, stream="raw"):
        chunks.append(chunk)
        if hasattr(chunk, 'choices') and chunk.choices[0].finish_reason:
            break
    
    assert len(chunks) > 0

async def test_go_invalid_stream_raises():
    """Verify invalid stream parameter raises ValueError"""
    agent = Agent(tools=[])
    thread = Thread()
    
    with pytest.raises(ValueError, match="Invalid stream value"):
        async for _ in agent.go(thread, stream="invalid"):
            pass
```

#### Integration Tests
```python
# test_agent_observability.py
async def test_weave_traces_async_go():
    """Verify Weave captures complete trace with async .go()"""
    weave.init("test-project")
    
    agent = Agent(tools=["web"])
    thread = Thread()
    thread.add_message(Message(role="user", content="Search for Python"))
    
    result = await agent.go(thread)
    
    # Verify Weave captured the call
    # (Weave-specific assertions - check dashboard/API)
    assert result is not None

async def test_weave_traces_streaming_go():
    """Verify Weave captures streaming execution"""
    weave.init("test-project")
    
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    async for event in agent.go(thread, stream=True):
        if event.type == EventType.EXECUTION_COMPLETE:
            break
    
    # Verify Weave captured streaming events
```

#### Examples Validation
```python
# test_examples.py
async def test_all_examples_use_await():
    """Verify all updated examples use await correctly"""
    # Run each example and verify no coroutine warnings
    examples = [
        "examples/002_basic.py",
        "examples/003_agent_from_config.py",
        # ... all examples
    ]
    
    for example in examples:
        result = subprocess.run(
            ["python", example],
            capture_output=True,
            text=True
        )
        assert "coroutine" not in result.stderr
        assert result.returncode == 0
```

### Negative & Edge Cases

| Test Case | Expected Behavior |
|-----------|-------------------|
| Missing `await` on non-streaming call | Python RuntimeWarning |
| Invalid stream parameter | ValueError with clear message |
| Thread not found | ValueError propagates |
| Connection error during execution | Exception in AgentResult, thread saved |
| Interrupt during streaming | Generator cleanup, resources released |
| Multiple concurrent `.go()` calls | Each independent, no interference |

### Performance Tests

**Not required** - This is an API change, not a performance change:
- Async/await overhead is negligible (<1ms)
- No hot path changes
- No new operations added
- Existing performance characteristics maintained

**Validation**:
```python
async def test_go_performance_unchanged():
    """Verify async .go() has similar performance to v4.x"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    # Measure execution time
    start = time.time()
    for _ in range(10):
        await agent.go(thread)
    duration = time.time() - start
    
    # Should complete 10 runs in reasonable time
    assert duration < 30  # ~3s per run max
```

### CI Requirements

**All tests must**:
- ✅ Run in GitHub Actions
- ✅ Block merge if failing
- ✅ Include all test tiers (unit, integration, examples)
- ✅ Test Python 3.11, 3.12, 3.13
- ✅ Check type hints with mypy
- ✅ Run linter (ruff)

## 11. Risks & Open Questions

### Risks

#### Risk 1: Unexpected Breaking Changes
**Description**: Call sites we haven't identified might break

**Likelihood**: Low  
**Impact**: Medium  
**Mitigation**:
- Comprehensive grep search completed (151 Python files, 108 docs)
- Clear Python error messages guide users to fix
- Migration guide in CHANGELOG
- Example code updated as templates

#### Risk 2: IDE/Tooling Compatibility
**Description**: Some IDEs might not handle async generator type hints correctly

**Likelihood**: Very Low  
**Impact**: Low  
**Mitigation**:
- Type hints unchanged (only method signature becomes async)
- Modern IDEs (PyCharm, VS Code) handle this correctly
- Python 3.11+ fully supports async generators
- Existing streaming code already works (no IDE issues reported)

#### Risk 3: Third-Party Integration Breakage
**Description**: External packages using Tyler might break

**Likelihood**: Low  
**Impact**: Medium  
**Mitigation**:
- Space Monkey already uses `await` (verified)
- Narrator doesn't call `.go()` (different layer)
- Major version bump signals breaking change
- Migration guide provided

#### Risk 4: Weave Integration Still Broken
**Description**: Making `.go()` async might not fix Weave observability

**Likelihood**: Very Low  
**Impact**: Low (still worth doing for API clarity)  
**Mitigation**:
- Weave engineers confirmed the issue ("func is not async")
- Similar patterns work in user examples
- Will validate before release
- API clarity benefit stands alone

### Open Questions

#### Q1: Should we add async validation to CI?
**Question**: Add linter to detect missing `await` on `.go()` calls?

**Options**:
- A) Manual review only
- B) Add ruff rule for missing await
- C) Custom script to detect pattern

**Proposed Answer**: B (ruff rule if available, else manual review)  
**Rationale**: Catch errors early, low maintenance

**Resolution needed**: Before implementation starts

---

#### Q2: Version bump timing?
**Question**: Release v5.0.0 immediately or batch with other breaking changes?

**Options**:
- A) Release v5.0.0 with just this change
- B) Wait for other breaking changes to batch
- C) Release as v4.3.0-alpha for testing

**Proposed Answer**: A (release v5.0.0 immediately)  
**Rationale**: Clean break, don't delay good API design, framework is young

**Resolution needed**: Before release planning

---

#### Q3: Documentation versioning?
**Question**: Keep v4.x docs accessible or only show v5.0.0?

**Options**:
- A) Single version (v5.0.0 only)
- B) Dropdown version selector
- C) Archive v4.x docs in separate folder

**Proposed Answer**: A (single version)  
**Rationale**: Framework is new, users should migrate, reduces maintenance

**Resolution needed**: Before docs update

---

#### Q4: Should we provide example migration script?
**Question**: Create automated migration script for users?

**Options**:
- A) No script (manual migration is simple)
- B) Provide regex patterns for find/replace
- C) Full codemod script (libCST or similar)

**Proposed Answer**: B (regex patterns in migration guide)  
**Rationale**: Balance between helpful and over-engineering

**Resolution needed**: During documentation phase

## 12. Milestones / Plan (post‑approval)

### Milestone 1: Core Implementation (1 hour)
**Goal**: Update agent.py with async .go()

**Tasks**:
1. ✅ Change method signature: `def go(...)` → `async def go(...)`
2. ✅ Update all `@overload` decorators to `async def`
3. ✅ Add `await` to non-streaming return: `return await self._go_complete(...)`
4. ✅ Change streaming returns to yield from:
   - `async for event in self._go_stream(...): yield event`
   - `async for chunk in self._go_stream_raw(...): yield chunk`
5. ✅ Update docstring examples to show `await`
6. ✅ Run mypy type check

**DoD**:
- [ ] Code changes complete
- [ ] Type checking passes
- [ ] Docstring updated
- [ ] No linter errors

---

### Milestone 2: Test Updates (4 hours)
**Goal**: Update all tests to use await

**Tasks**:
1. ✅ Update `test_agent.py` (~17 functions)
   - Add `await` to all non-streaming `.go()` calls
   - Add new test: `test_go_is_async()`
2. ✅ Update `test_agent_observability.py` (~8 functions)
   - Add `await` where needed
   - Add new test: `test_weave_traces_async_go()`
3. ✅ Update `test_agent_delegation.py` (~3 functions)
4. ✅ Update other test files (~5 functions total)
5. ✅ Verify streaming tests unchanged (all pass)
6. ✅ Run full test suite

**DoD**:
- [ ] All tests updated
- [ ] All tests passing
- [ ] Coverage maintained >95%
- [ ] No coroutine warnings in test output

---

### Milestone 3: Examples Update (4 hours)
**Goal**: Update all example files

**Tasks**:
1. ✅ Update workspace examples (4 files)
   - `examples/getting-started/quickstart.py`
   - `examples/getting-started/basic-persistence.py`
   - `examples/getting-started/tool-groups.py`
   - `examples/integrations/cross-package.py`
2. ✅ Update Tyler examples (~26 files)
   - All files in `packages/tyler/examples/`
   - Add `await` to non-streaming calls
   - Verify streaming examples unchanged
3. ✅ Run each example manually
4. ✅ Verify no coroutine warnings

**DoD**:
- [ ] All examples updated
- [ ] All examples run successfully
- [ ] No warnings in output
- [ ] README snippets updated

---

### Milestone 4: Documentation Update (6 hours)
**Goal**: Update all documentation

**Tasks**:
1. ✅ Update API Reference (6 files)
   - `docs/api-reference/tyler-agent.mdx` (~6 samples)
   - `docs/api-reference/tyler-agentresult.mdx` (~5 samples)
   - Other API ref files
2. ✅ Update Guides (8 files)
   - `docs/guides/your-first-agent.mdx` (~5 samples)
   - `docs/guides/mcp-integration.mdx` (~6 samples)
   - Other guide files
3. ✅ Update Concepts (4 files)
   - `docs/concepts/how-agents-work.mdx` (~7 samples)
   - Other concept files
4. ✅ Update intro/quickstart (2 files)
5. ✅ Create migration guide in CHANGELOG

**DoD**:
- [ ] All code samples updated with `await`
- [ ] Migration guide written
- [ ] CHANGELOG updated
- [ ] No outdated examples remain

---

### Milestone 5: Integration Verification (1 hour)
**Goal**: Verify all integrations work

**Tasks**:
1. ✅ Verify Space Monkey
   - Check `slack_app.py` (already has `await`)
   - Run integration tests
2. ✅ Verify CLI
   - Check `init.py` (already has `await`)
   - Run CLI commands
3. ✅ Verify cross-package examples
4. ✅ Run integration test suite

**DoD**:
- [ ] Space Monkey tests pass
- [ ] CLI tests pass
- [ ] Cross-package tests pass
- [ ] No regressions found

---

### Milestone 6: Validation & Testing (4 hours)
**Goal**: Comprehensive testing and validation

**Tasks**:
1. ✅ Run full test suite (all packages)
2. ✅ Run mypy type checking
3. ✅ Run linters (ruff, black)
4. ✅ Weave observability validation
   - Run examples with Weave initialized
   - Check Weave dashboard for complete traces
   - Verify both streaming and non-streaming
5. ✅ Manual smoke testing
   - Create agent from scratch
   - Test all three modes (non-streaming, events, raw)
   - Verify error messages clear

**DoD**:
- [ ] All tests passing (100%)
- [ ] Type checking clean
- [ ] Linting clean
- [ ] Weave traces working
- [ ] Manual testing complete

---

### Milestone 7: Release Preparation (2 hours)
**Goal**: Prepare for v5.0.0 release

**Tasks**:
1. ✅ Update version numbers
   - `packages/tyler/pyproject.toml` → 5.0.0
   - `packages/tyler/tyler/__init__.py` → 5.0.0
2. ✅ Update CHANGELOG.md
   - Add v5.0.0 section
   - Document breaking change
   - Include migration guide
3. ✅ Update README if needed
4. ✅ Create PR with all changes
5. ✅ Request review

**DoD**:
- [ ] Version bumped to 5.0.0
- [ ] CHANGELOG complete
- [ ] PR created
- [ ] CI passing

---

### Milestone 8: Post-Release (ongoing)
**Goal**: Monitor adoption and handle issues

**Tasks**:
1. ✅ Monitor GitHub issues for migration questions
2. ✅ Update documentation based on feedback
3. ✅ Verify Weave observability in production usage
4. ✅ Track v5.0.0 adoption metrics

**DoD**:
- [ ] <10 migration issues in first month
- [ ] All critical issues resolved
- [ ] User feedback incorporated

---

## Timeline Summary

| Milestone | Duration | Dependencies |
|-----------|----------|--------------|
| 1. Core Implementation | 1 hour | None |
| 2. Test Updates | 4 hours | M1 complete |
| 3. Examples Update | 4 hours | M1 complete |
| 4. Documentation Update | 6 hours | M1 complete |
| 5. Integration Verification | 1 hour | M2, M3 complete |
| 6. Validation & Testing | 4 hours | M2, M3, M5 complete |
| 7. Release Preparation | 2 hours | M6 complete |
| 8. Post-Release | Ongoing | M7 complete |

**Total Implementation Time**: ~22 hours (~3 days)  
**Critical Path**: M1 → M2 → M6 → M7

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved.

**Reviewers**: @adamdraper  
**Expected Review Time**: 1-2 hours  
**Start Implementation**: After approval

