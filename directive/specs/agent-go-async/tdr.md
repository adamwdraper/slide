# Technical Design Review (TDR) — Split Agent.go() into .go() and .stream()

**Author**: AI Agent  
**Date**: 2025-10-28  
**Links**: 
- Spec: `/directive/specs/agent-go-async/spec.md`
- Impact: `/directive/specs/agent-go-async/impact.md`
- Design Pivot Notes: `/directive/specs/agent-go-async/PIVOT_NOTES.md`

---

## 1. Summary

We are splitting `Agent.go()` into two distinct methods to follow industry best practices and overcome Python async/await limitations. The new design provides:
- `agent.go(thread)` - async method that returns `AgentResult` (non-streaming only)
- `agent.stream(thread, mode="events")` - async generator that yields events or raw chunks

**Why the split?** We initially attempted to make `.go()` async while keeping the `stream` parameter, but discovered a fundamental Python limitation: **you cannot mix `return value` and `yield` in the same function**. After evaluating alternatives, we determined that splitting into two methods is the industry-standard pattern (httpx, aiohttp, FastAPI all do this) and provides superior developer experience.

This is an intentional breaking change for v5.0.0 that affects ALL users (both streaming and non-streaming). The migration is straightforward with clear patterns and regex examples provided.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **API clarity**: Separate methods for different behaviors (industry standard pattern)
- **Python limitations**: Cannot mix `return value` and `yield` in same function
- **Single responsibility**: Each method should do one thing well
- **Type safety**: Eliminate complex Union return types
- **Developer experience**: `.go()` vs `.stream()` is self-documenting
- **Observability tooling**: Enable Weave and similar tools to properly trace execution
- **Industry patterns**: Follow httpx, aiohttp, FastAPI conventions
- **Better IDE support**: Simpler types mean better autocomplete and hints

### Non‑Goals
- **Changing execution logic** - All tool execution, iteration limits, error handling stay identical
- **Changing return types** - `AgentResult`, `ExecutionEvent`, raw chunks remain the same
- **Backward compatibility** - This is an intentional breaking change for better DX
- **New features** - No new streaming modes, no new capabilities, pure API refactor
- **Deprecation period** - Clean break for v5.0.0 (framework is new, few users)
- **Keeping single method** - Tried this, Python doesn't allow it (SyntaxError)

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
    │       └─→ async def go(thread)  ← NEW METHOD (no stream param)
    │               └─→ return await self._go_complete(thread)
    │                       │
    │                       └─→ Returns AgentResult
    │
    └─ Streaming: async for event in agent.stream(thread)
            │
            └─→ async def stream(thread, mode="events")  ← NEW METHOD
                    │
                    ├─ mode="events" → async for event in self._go_stream(thread):
                    │                       yield event
                    │                           │
                    │                           └─→ Yields ExecutionEvent
                    │
                    └─ mode="raw" → async for chunk in self._go_stream_raw(thread):
                                        yield chunk
                                            │
                                            └─→ Yields raw LiteLLM chunks
```

### Component Changes

#### 1. Remove Old Unified Method
```python
# DELETE THIS (lines ~586-690 in agent.py)
@overload
def go(...) -> AgentResult: ...

@overload  
def go(...) -> AsyncGenerator[ExecutionEvent, None]: ...

@overload
def go(...) -> AsyncGenerator[Any, None]: ...

@weave.op()
def go(self, thread_or_id, stream=False):
    # ... routing logic ...
    if stream_mode is None:
        return self._go_complete(thread_or_id)
    elif stream_mode == "events":
        return self._go_stream(thread_or_id)
    elif stream_mode == "raw":
        return self._go_stream_raw(thread_or_id)
```

#### 2. Add New Non-Streaming Method
```python
# ADD THIS
@weave.op()
async def go(
    self,
    thread_or_id: Union[Thread, str]
) -> AgentResult:
    """
    Execute agent and return complete result.
    
    This method runs the agent to completion and returns the final
    result with all messages, content, and execution details.
    
    Args:
        thread_or_id: Thread object or thread ID to process
        
    Returns:
        AgentResult with complete execution details
        
    Example:
        result = await agent.go(thread)
        print(f"Response: {result.content}")
    """
    return await self._go_complete(thread_or_id)
```

#### 3. Add New Streaming Method
```python
# ADD THIS
@weave.op()
async def stream(
    self,
    thread_or_id: Union[Thread, str],
    mode: Literal["events", "raw"] = "events"
) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
    """
    Stream agent execution events or raw chunks in real-time.
    
    This method yields events as the agent executes, providing
    real-time visibility into the agent's reasoning and actions.
    
    Args:
        thread_or_id: Thread object or thread ID to process
        mode: "events" for ExecutionEvent objects (default),
              "raw" for raw LiteLLM chunks
              
    Yields:
        ExecutionEvent objects (mode="events") or
        Raw LiteLLM chunks (mode="raw")
        
    Example:
        # Event streaming
        async for event in agent.stream(thread):
            if event.type == EventType.MESSAGE_CREATED:
                print(event.data['message'].content)
        
        # Raw chunk streaming
        async for chunk in agent.stream(thread, mode="raw"):
            if hasattr(chunk.choices[0].delta, 'content'):
                print(chunk.choices[0].delta.content, end="")
    """
    if mode == "events":
        async for event in self._go_stream(thread_or_id):
            yield event
    elif mode == "raw":
        async for chunk in self._go_stream_raw(thread_or_id):
            yield chunk
    else:
        raise ValueError(
            f"Invalid mode: {mode}. Must be 'events' or 'raw'"
        )
```

### Complete Implementation Summary

**Changes to agent.py**:
1. Delete old `.go()` method (~105 lines including overloads)
2. Add new `.go()` method (~20 lines)
3. Add new `.stream()` method (~40 lines)
4. Net change: ~-45 lines (simpler code!)

**Type improvements**:
- **Before**: `Union[AgentResult, AsyncGenerator[...]]` (complex)
- **After**: 
  - `.go()` → `AgentResult` (clear!)
  - `.stream()` → `AsyncGenerator[ExecutionEvent | Any, None]` (clear!)

**No overload decorators needed** - Each method has single clear signature

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

### The Discovery Process

We initially planned to make `.go()` async while keeping the `stream` parameter. However, during implementation, we discovered:

```python
# This causes SyntaxError!
async def go(self, thread, stream=False):
    if not stream:
        return await self._go_complete(thread)  # return with value
    else:
        async for event in self._go_stream(thread):
            yield event  # yield

# Python Error: 'return' with value in async generator
```

**Python limitation**: You cannot mix `return value` and `yield` in the same function.

This forced us to reconsider our approach and explore alternatives.

### Option A: Make `.go()` always a generator (yield once for non-streaming)
**Approach**: Always yield, even for non-streaming

```python
async def go(self, thread, stream=False):
    if not stream:
        result = await self._go_complete(thread)
        yield result  # Yield once
    else:
        async for event in self._go_stream(thread):
            yield event
```

**Pros**:
- Single async method
- Technically works

**Cons**:
- ❌ Terrible UX: `result = await anext(agent.go(thread))` 
- ❌ Different consumption patterns for same method
- ❌ Confusing semantics (why yield once?)

**Why rejected**: Bad developer experience

### Option B: Smart return object (awaitable + iterable)
**Approach**: Return object that implements both `__await__()` and `__aiter__()`

```python
def go(self, thread, stream=False):
    return _GoResult(self, thread, stream)

class _GoResult:
    def __await__(self):  # For: await agent.go()
        return self._agent._go_complete(...)
    
    def __aiter__(self):  # For: async for x in agent.go()
        return self._agent._go_stream(...)
```

**Pros**:
- Could preserve exact API
- Clever technical solution

**Cons**:
- ❌ `.go()` still not async (Weave problem remains!)
- ❌ Added complexity for wrapper class
- ❌ Unusual pattern (less discoverable)
- ❌ Doesn't solve root issue

**Why rejected**: Doesn't fix Weave observability, adds complexity

### Option C: Keep it as `def` (status quo)
**Approach**: Accept current pattern, improve documentation

**Pros**:
- Zero migration cost
- Works functionally

**Cons**:
- ❌ Doesn't fix Weave logging
- ❌ Still misleading API
- ❌ Still violates best practices
- ❌ Missed opportunity for better design

**Why rejected**: Doesn't solve any of our goals

### Option D (Chosen): Split into `.go()` and `.stream()` 
**Approach**: Two separate methods, each with single responsibility

```python
async def go(self, thread) -> AgentResult:
    """Non-streaming only"""
    return await self._go_complete(thread)

async def stream(self, thread, mode="events"):
    """Streaming only"""
    if mode == "events":
        async for event in self._go_stream(thread):
            yield event
    else:
        async for chunk in self._go_stream_raw(thread):
            yield chunk
```

**Pros**:
- ✅ No Python syntax limitations (both methods work perfectly)
- ✅ Clear intent (method name indicates behavior)
- ✅ Single responsibility (each does one thing)
- ✅ Industry standard (httpx, aiohttp, FastAPI all split these)
- ✅ Better type safety (no Union return types)
- ✅ Proper async (enables Weave observability)
- ✅ Simpler code (~45 lines less)

**Cons**:
- ⚠️ Breaking change for streaming users too
- ⚠️ More call sites to update (~100 streaming + ~150 non-streaming)

**Why chosen**: 
- Best long-term design
- Follows industry best practices
- Solves all our problems
- Framework is young enough to make this change
- Clear migration path with regex patterns

## 6. Data Model & Contract Changes

### API Changes

#### Breaking Change: Split into Two Methods

```python
# v4.x - Single overloaded method
def go(
    self,
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
    """Process thread (streaming or not based on parameter)"""

# v5.0.0 - Two focused methods
async def go(
    self,
    thread_or_id: Union[Thread, str]
) -> AgentResult:
    """Execute agent and return complete result."""

async def stream(
    self,
    thread_or_id: Union[Thread, str],
    mode: Literal["events", "raw"] = "events"
) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
    """Stream agent execution events or raw chunks."""
```

**Impact**:
- Non-streaming: `result = agent.go(thread)` → `result = await agent.go(thread)`
- Event streaming: `async for event in agent.go(thread, stream=True)` → `async for event in agent.stream(thread)`
- Raw streaming: `async for chunk in agent.go(thread, stream="raw")` → `async for chunk in agent.stream(thread, mode="raw")`

#### No Changes To
- Return data types (AgentResult, ExecutionEvent, raw chunks)
- Event structures or data models
- Thread/Message/Attachment schemas
- Tool execution contracts
- Internal implementation methods

### Backward Compatibility

**None** - This is an intentional breaking change for ALL users:

```python
# v4.x (OLD)
result = agent.go(thread)  # Works
async for event in agent.go(thread, stream=True):  # Works

# v5.0.0 (NEW)
result = agent.go(thread)  # RuntimeWarning: coroutine never awaited
result = await agent.go(thread)  # ✅ Works

async for event in agent.go(thread, stream=True):  # TypeError: unexpected keyword 'stream'
async for event in agent.stream(thread):  # ✅ Works
```

### Deprecation Plan

**No deprecation period** - Clean break for v5.0.0:
1. Framework is new (Tyler v4.x is months old)
2. Limited production usage
3. Clear migration patterns with regex examples
4. Clear Python error messages guide users

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
1. ✅ **Write failing test** - Update test to use new `.go()` and `.stream()` methods
2. ✅ **Confirm failure** - Test fails with AttributeError or TypeError (methods don't exist yet)
3. ✅ **Implement** - Add new `.go()` and `.stream()` methods, remove old `.go()`
4. ✅ **Verify pass** - All tests pass
5. ✅ **Refactor** - Clean up docstrings, ensure consistency

### Spec → Test Mapping

From `spec.md` acceptance criteria:

| Acceptance Criterion | Test ID(s) | Test File |
|---------------------|------------|-----------|
| **Non-Streaming Mode - Clear, Focused Method** | `test_agent_go_non_streaming` | `test_agent.py` |
| Returns AgentResult when awaited | `test_go_returns_agent_result` | `test_agent.py` |
| No stream parameter exists | `test_go_no_stream_parameter` | `test_agent.py` |
| **Event Streaming Mode - Separate Method** | `test_agent_stream_events` | `test_agent_streaming.py` |
| `.stream()` yields ExecutionEvents | `test_stream_yields_events` | `test_agent_streaming.py` |
| Works with async for iteration | `test_stream_async_iteration` | `test_agent_streaming.py` |
| **Raw Streaming Mode - Same Method, Different Mode** | `test_agent_stream_raw` | `test_agent_streaming.py` |
| `.stream(mode="raw")` yields chunks | `test_stream_raw_yields_chunks` | `test_agent_streaming.py` |
| **API Clarity - Single Responsibility** | `test_api_clarity_split_methods` | `test_agent.py` |
| `.go()` and `.stream()` both exist | `test_methods_exist_separately` | `test_agent.py` |
| **Type Safety - No Union Types** | `test_go_type_is_agentresult` | `test_agent.py` |
| `.go()` returns AgentResult only | `test_go_return_type_annotation` | `test_agent.py` |
| `.stream()` returns AsyncGenerator | `test_stream_return_type_annotation` | `test_agent.py` |
| **Invalid Stream Mode (Negative Case)** | `test_stream_invalid_mode_raises` | `test_agent_streaming.py` |
| Invalid mode raises ValueError | `test_stream_invalid_mode_message` | `test_agent_streaming.py` |
| **Observability Tooling Works (Validation)** | `test_weave_traces_go` | `test_agent_observability.py` |
| Weave traces `.go()` correctly | `test_weave_traces_stream` | `test_agent_observability.py` |
| Weave traces `.stream()` correctly | `test_weave_both_methods` | `test_agent_observability.py` |
| **Breaking Change - Clear Migration Path** | (manual validation) | - |
| Old `stream` parameter raises TypeError | `test_go_stream_parameter_error` | `test_agent.py` |

### Test Tiers

#### Unit Tests
```python
# test_agent.py
async def test_go_is_async():
    """Verify .go() is an async function"""
    assert inspect.iscoroutinefunction(Agent.go)

async def test_stream_is_async():
    """Verify .stream() is an async function"""
    assert inspect.isasyncgenfunction(Agent.stream)

async def test_go_no_stream_parameter():
    """Verify .go() doesn't accept stream parameter"""
    agent = Agent(tools=[])
    thread = Thread()
    
    with pytest.raises(TypeError, match="unexpected keyword argument 'stream'"):
        await agent.go(thread, stream=True)

async def test_go_returns_agent_result():
    """Verify .go() returns AgentResult when awaited"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    result = await agent.go(thread)
    assert isinstance(result, AgentResult)
    assert result.content is not None

async def test_stream_yields_events():
    """Verify .stream() yields ExecutionEvents"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    events = []
    async for event in agent.stream(thread):
        events.append(event)
        if event.type == EventType.EXECUTION_COMPLETE:
            break
    
    assert len(events) > 0
    assert all(isinstance(e, ExecutionEvent) for e in events)

async def test_stream_raw_yields_chunks():
    """Verify .stream(mode='raw') yields chunks"""
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    chunks = []
    async for chunk in agent.stream(thread, mode="raw"):
        chunks.append(chunk)
        if hasattr(chunk, 'choices') and chunk.choices[0].finish_reason:
            break
    
    assert len(chunks) > 0

async def test_stream_invalid_mode_raises():
    """Verify invalid mode parameter raises ValueError"""
    agent = Agent(tools=[])
    thread = Thread()
    
    with pytest.raises(ValueError, match="Invalid mode"):
        async for _ in agent.stream(thread, mode="invalid"):
            pass
```

#### Integration Tests
```python
# test_agent_observability.py
async def test_weave_traces_go():
    """Verify Weave captures complete trace for .go()"""
    weave.init("test-project")
    
    agent = Agent(tools=["web"])
    thread = Thread()
    thread.add_message(Message(role="user", content="Search for Python"))
    
    result = await agent.go(thread)
    
    # Verify Weave captured the call
    assert result is not None

async def test_weave_traces_stream():
    """Verify Weave captures streaming execution for .stream()"""
    weave.init("test-project")
    
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    async for event in agent.stream(thread):
        if event.type == EventType.EXECUTION_COMPLETE:
            break
    
    # Verify Weave captured streaming events

async def test_weave_traces_stream_raw():
    """Verify Weave captures raw streaming"""
    weave.init("test-project")
    
    agent = Agent(tools=[])
    thread = Thread()
    thread.add_message(Message(role="user", content="Hello"))
    
    async for chunk in agent.stream(thread, mode="raw"):
        if hasattr(chunk, 'choices') and chunk.choices[0].finish_reason:
            break
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

### Milestone 1: Core Implementation (2 hours)
**Goal**: Split .go() into two methods in agent.py

**Tasks**:
1. ✅ Remove old `.go()` method (lines ~586-690)
   - Delete `@overload` decorators
   - Delete routing logic
2. ✅ Add new `async def go(thread)` method (~20 lines)
   - Simple signature: `thread_or_id` → `AgentResult`
   - Implementation: `return await self._go_complete(thread_or_id)`
   - Docstring with examples
3. ✅ Add new `async def stream(thread, mode="events")` method (~40 lines)
   - Signature: `thread_or_id, mode` → `AsyncGenerator[...]`
   - Implementation: yield from `_go_stream()` or `_go_stream_raw()`
   - Docstring with examples
4. ✅ Run linter (ruff)
5. ✅ Verify syntax (Python imports agent.py)

**DoD**:
- [ ] Old `.go()` removed
- [ ] New `.go()` added (non-streaming only)
- [ ] New `.stream()` added (streaming only)
- [ ] No linter errors
- [ ] File imports successfully

---

### Milestone 2: Test Updates (6 hours)
**Goal**: Update all tests for new API

**Tasks**:
1. ✅ Update `test_agent.py` (~17 functions)
   - Add `await` to all `.go()` calls
   - Add new test: `test_go_no_stream_parameter()`
   - Add new test: `test_stream_is_async_gen()`
2. ✅ Update `test_agent_streaming.py` (~30+ functions)
   - Change ALL `agent.go(thread, stream=True)` → `agent.stream(thread)`
   - Change `.go(stream="raw")` → `.stream(mode="raw")`
3. ✅ Update `test_agent_observability.py` (~8 functions)
   - Add `await` to `.go()` calls
   - Change streaming calls to `.stream()`
4. ✅ Update `test_agent_thinking_tokens.py` (~4 functions)
   - Change all streaming calls to `.stream()`
5. ✅ Update other test files (~8 functions)
6. ✅ Run full test suite

**DoD**:
- [ ] All tests updated
- [ ] All tests passing
- [ ] Coverage maintained >95%
- [ ] No coroutine warnings

---

### Milestone 3: Examples Update (6 hours)
**Goal**: Update all example files

**Tasks**:
1. ✅ Update workspace examples (8 files)
   - Add `await` to non-streaming
   - Change `.go(stream=True)` → `.stream()`
2. ✅ Update Tyler examples (~26 files)
   - Mixed updates (await + method changes)
   - ~15 files need `.stream()` changes
   - ~11 files just need `await`
3. ✅ Run each example manually
4. ✅ Verify no errors or warnings

**DoD**:
- [ ] All examples updated
- [ ] All examples run successfully
- [ ] No warnings in output
- [ ] README snippets updated

---

### Milestone 4: Documentation Update (8 hours)
**Goal**: Update all documentation

**Tasks**:
1. ✅ Update API Reference (6 files)
   - Document both `.go()` and `.stream()` methods
   - Update all code samples (~15 samples mix of both)
2. ✅ Update Guides (8 files)
   - `docs/guides/streaming-responses.mdx` - Major updates
   - Other guides - Mixed updates
3. ✅ Update Concepts (4 files)
   - Show both methods appropriately
4. ✅ Update intro/quickstart (2 files)
5. ✅ Create comprehensive migration guide in CHANGELOG

**DoD**:
- [ ] Both methods documented
- [ ] All code samples updated
- [ ] Migration guide complete with regex patterns
- [ ] CHANGELOG updated
- [ ] No outdated examples

---

### Milestone 5: Integration Verification (2 hours)
**Goal**: Verify all integrations work

**Tasks**:
1. ✅ Update CLI
   - Change `chat.py` line ~544 to `.stream()`
   - Verify `init.py` has `await`
   - Run CLI manually
2. ✅ Verify Space Monkey
   - Check `slack_app.py` (should have `await` already)
   - Run integration tests
3. ✅ Verify cross-package examples
4. ✅ Run integration test suite

**DoD**:
- [ ] CLI updated and working
- [ ] Space Monkey tests pass
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
| 1. Core Implementation | 2 hours | None |
| 2. Test Updates | 6 hours | M1 complete |
| 3. Examples Update | 6 hours | M1 complete |
| 4. Documentation Update | 8 hours | M1 complete |
| 5. Integration Verification | 2 hours | M2, M3 complete |
| 6. Validation & Testing | 5 hours | M2, M3, M5 complete |
| 7. Release Preparation | 2 hours | M6 complete |
| 8. Post-Release | Ongoing | M7 complete |

**Total Implementation Time**: ~31 hours (~4 days)  
**Critical Path**: M1 → M2 → M6 → M7

**Note**: Increased from initial async-only estimate due to:
- All streaming calls need method changes (not just non-streaming)
- Two methods to implement and test
- More complex migration (await + method name changes)

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved.

**Reviewers**: @adamdraper  
**Expected Review Time**: 1-2 hours  
**Start Implementation**: After approval

