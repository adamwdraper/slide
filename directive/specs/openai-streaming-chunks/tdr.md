# Technical Design Review (TDR) — Raw Streaming Mode for OpenAI Compatibility

**Author**: AI Agent  
**Date**: 2025-10-12  
**Links**: 
- Spec: `/directive/specs/openai-streaming-chunks/spec.md`
- Impact: `/directive/specs/openai-streaming-chunks/impact.md`

---

## 1. Summary

This feature adds a new streaming mode to Tyler's `Agent.go()` method that exposes raw LiteLLM chunks in OpenAI-compatible format. Currently, Tyler transforms all streaming responses into `ExecutionEvent` objects, which provides excellent observability but prevents direct integration with OpenAI-compatible clients and SDKs.

We will extend the `stream` parameter to accept string literals (`"events"`, `"raw"`) in addition to boolean values, allowing developers to choose between Tyler's event-based streaming (for observability) and raw chunk streaming (for OpenAI compatibility). This enables use cases like building OpenAI API proxies, debugging provider behavior, and integrating with existing OpenAI-compatible tooling.

The design maintains full backward compatibility—existing code using `stream=True` or `stream=False` will continue to work identically.

## 2. Decision Drivers & Non‑Goals

### Drivers
- **Interoperability**: Enable Tyler agents to integrate with OpenAI-compatible ecosystems
- **Performance**: Raw mode should have minimal overhead (no transformation)
- **Backward Compatibility**: Zero breaking changes for existing users
- **Developer Experience**: Simple, intuitive API with excellent type safety
- **Future Extensibility**: Design allows adding more stream formats later (e.g., `"json"`, `"anthropic"`)

### Non‑Goals
- SSE serialization utilities (developers handle serialization themselves)
- Converting ExecutionEvents back to raw chunks
- Building a proxy/gateway server (out of scope)
- Supporting raw chunks in non-streaming mode
- Modifying or enhancing the raw chunk format
- Deprecating or removing `stream=True` boolean support

## 3. Current State — Codebase Map

### Key Modules
**`packages/tyler/tyler/models/agent.py`** (1,346 lines)
- `Agent` class: Main agent implementation
- `Agent.go()`: Entry point for agent execution (lines 500-564)
  - Current signature: `go(thread_or_id, stream: bool = False)`
  - Two overloads for type safety
  - Routes to `_go_complete()` or `_go_stream()`
- `Agent._go_complete()`: Non-streaming implementation (lines 567-847)
- `Agent._go_stream()`: Streaming implementation (lines 850-1346)
  - Iterates over LiteLLM streaming response
  - Transforms chunks into `ExecutionEvent` objects
  - Handles content deltas, tool calls, usage info

**`packages/tyler/tyler/models/execution.py`**
- `EventType` enum: Defines all event types (LLM_STREAM_CHUNK, TOOL_SELECTED, etc.)
- `ExecutionEvent`: Dataclass with type, timestamp, data, attributes
- `AgentResult`: Return type for non-streaming mode

**`packages/tyler/tyler/models/tool_manager.py`**
- Handles tool registration and schema generation
- Not directly affected by this change

### Current Streaming Flow
1. User calls `agent.go(thread, stream=True)`
2. `go()` routes to `_go_stream(thread_or_id)`
3. `_go_stream()` calls LiteLLM `acompletion()` with `stream=True`
4. For each chunk from LiteLLM:
   - Extract content delta → yield `ExecutionEvent(LLM_STREAM_CHUNK)`
   - Extract tool call deltas → accumulate, yield events when complete
   - Extract usage info → yield `ExecutionEvent(LLM_RESPONSE)`
5. After streaming completes, create messages, handle tool calls, iterate if needed

### External Contracts
- **LiteLLM API**: `acompletion()` with `stream=True` returns async generator
- **LiteLLM Chunk Format**: Objects with `choices[0].delta` containing:
  - `content`: Text delta (str or None)
  - `tool_calls`: List of tool call deltas
  - Final chunk may have `usage`: Token counts
- **OpenAI SSE Format**: What LiteLLM mimics (JSON objects per line)

### Observability Currently Available
- Weave tracing on `@weave.op()` decorated methods
- Debug logging throughout agent execution
- ExecutionEvents provide rich telemetry (event types, timestamps, token counts)

## 4. Proposed Design (High Level)

### Overview
Extend the `stream` parameter to be a union type that accepts:
- `False` (default) → Return `AgentResult` (non-streaming)
- `True` → Return async generator of `ExecutionEvent` (backward compat)
- `"events"` → Return async generator of `ExecutionEvent` (explicit)
- `"raw"` → Return async generator of raw LiteLLM chunks (new)

### Component Responsibilities

**1. Parameter Normalization** (in `Agent.go()`)
- Accept `Union[bool, Literal["events", "raw"]]`
- Normalize `True` → `"events"` internally
- Normalize `False` → `None` or `"none"` internally
- Validate: ensure value is one of the allowed options

**2. Routing Logic** (in `Agent.go()`)
```python
if stream_mode is None or stream_mode is False:
    return self._go_complete(thread_or_id)
elif stream_mode == "events" or stream_mode is True:
    return self._go_stream(thread_or_id)
elif stream_mode == "raw":
    return self._go_stream_raw(thread_or_id)
else:
    raise ValueError(f"Invalid stream mode: {stream_mode}")
```

**3. New Method: `_go_stream_raw()` - Fully Agentic**
- Full iteration loop like `_go_stream()` (not simplified!)
- Initialize iteration tracking: `self._iteration_count = 0`
- While loop: `while self._iteration_count < self.max_tool_iterations:`
- For each iteration:
  1. Get streaming response: `await self.step(thread, stream=True)`
  2. Yield ALL raw chunks from LLM (including tool_calls deltas)
  3. Accumulate tool calls while streaming
  4. Create assistant message with tool_calls
  5. If tool calls present: **Execute them silently** (no chunks yielded)
  6. Add tool result messages to thread
  7. Increment iteration, loop back for next LLM call
- Matches OpenAI Agents SDK pattern (reference: https://openai.github.io/openai-agents-python/streaming/)

**Key Implementation Details:**
```python
async def _go_stream_raw(self, thread_or_id) -> AsyncGenerator[Any, None]:
    thread = await self._get_thread(thread_or_id)
    self._iteration_count = 0
    
    while self._iteration_count < self.max_tool_iterations:
        # Get streaming LLM response
        streaming_response, metrics = await self.step(thread, stream=True)
        
        # Accumulate tool calls while yielding chunks
        current_tool_calls = []
        async for chunk in streaming_response:
            yield chunk  # Raw chunk pass-through
            # Track tool calls from deltas
            if has_tool_calls(chunk):
                current_tool_calls.append(...)
        
        # Create assistant message
        message = Message(content=..., tool_calls=current_tool_calls)
        thread.add_message(message)
        
        # If no tools, done
        if not current_tool_calls:
            break
        
        # EXECUTE TOOLS SILENTLY (no chunks during this)
        tool_results = await asyncio.gather(...)
        for result in tool_results:
            tool_message = create_tool_message(result)
            thread.add_message(tool_message)
        
        self._iteration_count += 1
```

**4. Type Overloads** (for type checker)
```python
@overload
def go(self, thread_or_id, stream: Literal[False] = False) -> AgentResult: ...

@overload  
def go(self, thread_or_id, stream: Union[Literal[True], Literal["events"]]) -> AsyncGenerator[ExecutionEvent, None]: ...

@overload
def go(self, thread_or_id, stream: Literal["raw"]) -> AsyncGenerator[Any, None]: ...
```

### Interfaces & Data Contracts

**API Signature**
```python
def go(
    self,
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
```

**Raw Chunk Format** (pass-through from LiteLLM)
```python
# Example chunk structure
{
    "id": "chatcmpl-123",
    "object": "chat.completion.chunk",
    "created": 1677652288,
    "model": "gpt-4",
    "choices": [
        {
            "index": 0,
            "delta": {
                "content": "Hello"  # or "tool_calls": [...]
            },
            "finish_reason": None  # or "stop", "tool_calls", etc.
        }
    ],
    "usage": None  # Present in final chunk
}
```

**No Schema Changes**
- `ExecutionEvent` remains unchanged
- `AgentResult` remains unchanged
- No database migrations needed

### Error Handling

**Invalid Stream Value**
```python
if stream not in (False, True, "events", "raw"):
    raise ValueError(
        f"Invalid stream value: {stream}. "
        f"Must be False, True, 'events', or 'raw'"
    )
```

**Raw Mode Error Propagation**
- In `_go_stream_raw()`, catch LiteLLM exceptions and re-raise with context
- Do NOT yield ExecutionEvent errors (not applicable in raw mode)
- Let caller handle exceptions (same as current behavior)

**Tool Call Handling in Raw Mode**
- Raw chunks contain partial tool calls across multiple chunks
- Tyler accumulates tool call deltas from chunks
- Tyler **DOES execute tools** after streaming completes (fully agentic)
- No chunks yielded during tool execution (silent phase)
- Next iteration's chunks follow after tools complete
- Frontend sees `finish_reason: "tool_calls"` to know tools are executing

### Performance Expectations

**Raw Mode**
- Should be ~10-15% faster than events mode (no transformation)
- Minimal memory overhead (direct pass-through)
- No buffering except what LiteLLM does internally

**Backward Compatibility**
- Events mode performance unchanged
- Non-streaming mode performance unchanged

**Back-pressure Behavior**
- If consumer is slow, async generator will naturally back-pressure to LiteLLM
- No explicit rate limiting or buffering needed

## 5. Alternatives Considered

### Option A: Separate `go_raw()` Method
**Pros:**
- Clear separation of concerns
- No changes to existing `go()` signature
- Easier to understand for new users

**Cons:**
- API fragmentation (multiple entry points)
- Harder to add more formats later (need more methods)
- Duplicates validation and setup logic

**Decision:** Rejected in favor of unified parameter approach

### Option B: Two Parameters (`stream=True`, `raw_chunks=True`)
**Pros:**
- Each parameter has single responsibility
- Explicit about what you're requesting

**Cons:**
- Confusing combinations (`stream=False, raw_chunks=True` invalid)
- Less extensible (what if we want 5 formats?)
- More verbose API

**Decision:** Rejected in favor of single parameter with multiple values

### Option C: Chosen - Union Parameter with Literals ✅
**Pros:**
- Single source of truth for output format
- Type-safe with overloads
- Naturally extensible (add more literals)
- Backward compatible (bool values still work)
- Pythonic (similar to `httpx`, `aiohttp` patterns)

**Cons:**
- Slightly complex type signature
- Requires good documentation

**Why Chosen:** Best balance of API clarity, extensibility, and type safety

## 6. Data Model & Contract Changes

### API Changes

**Current:**
```python
@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal[False] = False) -> AgentResult: ...

@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal[True]) -> AsyncGenerator[ExecutionEvent, None]: ...

def go(self, thread_or_id: Union[Thread, str], stream: bool = False) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None]]:
```

**Proposed:**
```python
@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal[False] = False) -> AgentResult: ...

@overload
def go(self, thread_or_id: Union[Thread, str], stream: Union[Literal[True], Literal["events"]]) -> AsyncGenerator[ExecutionEvent, None]: ...

@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal["raw"]) -> AsyncGenerator[Any, None]: ...

def go(
    self,
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]:
```

### Backward Compatibility

**100% Backward Compatible**
- `stream=False` → Same behavior (returns `AgentResult`)
- `stream=True` → Same behavior (yields `ExecutionEvent`)
- Type checkers will accept existing code without changes
- No deprecation warnings

**Migration Path**
- Existing users: No action required
- New users wanting raw mode: Use `stream="raw"`
- Explicit users: Can use `stream="events"` for clarity

### Deprecation Plan
- None needed - all existing APIs remain supported indefinitely

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- No changes to authentication or authorization
- `go()` method already requires agent instance (implicit auth via API keys)

### Secrets Management
- No changes - LiteLLM handles API keys as before
- Raw chunks do not expose additional secrets

### PII Handling
- Raw chunks contain same data as ExecutionEvents (LLM responses)
- No additional PII exposure
- Existing PII policies apply

### Threat Model

**Threat: Provider Response Leakage**
- Raw chunks expose exact provider response format
- Could leak provider-specific metadata (internal model IDs, rate limit headers)
- **Mitigation**: Document that raw mode should be used carefully; sanitize before forwarding to untrusted clients

**Threat: Malformed Chunk Injection**
- If LiteLLM has bug, malformed chunks could be passed through
- **Mitigation**: Tyler doesn't validate chunks (by design); consumers must handle malformed data
- Document error handling best practices

**No New Threats**
- Raw mode doesn't introduce new attack surface
- Same LiteLLM dependency, same network calls

## 8. Observability & Operations

### Logs to Add

**In `Agent.go()` method:**
```python
logger.debug(f"Agent.go() called with stream mode: {stream_mode}")
```

**In `Agent._go_stream_raw()` method:**
```python
logger.debug(f"Starting raw streaming for thread {thread.id}")
logger.debug(f"Raw streaming complete - {chunk_count} chunks yielded")
```

### Metrics to Add (if using Weave or similar)

**Counter: `tyler.agent.go.stream_mode`**
- Labels: `mode: "none" | "events" | "raw"`
- Tracks which streaming modes are used in production
- Helps understand adoption of raw mode

**Histogram: `tyler.agent.go.duration_ms`**
- Labels: `mode: "none" | "events" | "raw"`
- Compare performance between modes
- Identify performance regressions

**Histogram: `tyler.agent.go.chunks_yielded`**
- Labels: `mode: "events" | "raw"`
- Track chunk volume per request
- Identify high-volume streams

### Dashboards

**Add panel to existing agent dashboard:**
- Stream mode usage breakdown (pie chart)
- Performance comparison: events vs raw (histogram overlay)
- Error rate by stream mode

### Alerts

**No new alerts required**
- Existing error rate alerts cover raw mode
- No SLO changes

### Runbooks

**Add section to agent runbook:**
- "Debugging Raw Streaming Issues"
  - Check LiteLLM version compatibility
  - Verify provider supports streaming
  - Compare output with events mode for same input
  - Common pitfall: tool calls require reassembly in raw mode

## 9. Rollout & Migration

### Feature Flags
- **Not needed** - this is additive functionality with no risk to existing behavior
- Users opt-in by using `stream="raw"`

### Guardrails
- Parameter validation ensures only valid values accepted
- Type hints provide compile-time safety

### Data Migration
- None required - no schema changes

### Revert Plan
- If critical bug found in raw mode:
  1. Add validation to reject `stream="raw"` (raise error)
  2. Deploy fix
  3. Remove validation after fix verified
- **Blast radius**: Only affects users actively using `stream="raw"` (new feature)
- Existing users unaffected

### Rollout Phases

**Phase 1: Alpha (Week 1)**
- Merge feature to main branch
- Document in API reference (mark as "New")
- Create example file: `examples/005_raw_streaming.py`
- Internal testing with OpenAI, Anthropic providers

**Phase 2: Beta (Week 2-3)**
- Add to quickstart documentation
- Announce in release notes
- Gather feedback from early adopters

**Phase 3: GA (Week 4)**
- Mark as stable in documentation
- Add advanced examples (SSE server, proxy patterns)
- Performance benchmarks published

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
1. Write failing test for each acceptance criterion
2. Run test to confirm failure
3. Implement minimal code to pass test
4. Refactor while keeping tests green
5. All tests run in CI and block merge on failure

### Spec→Test Mapping

| Spec Criterion | Test ID | Test File | Description |
|----------------|---------|-----------|-------------|
| AC-1: Raw mode yields LiteLLM chunks with required fields | `test_raw_mode_yields_chunks_with_openai_fields` | `test_agent_streaming.py` | Verify chunk structure has `id`, `object`, `created`, `model`, `choices` |
| AC-2: Raw mode includes usage information in final chunk | `test_raw_mode_includes_usage_in_final_chunk` | `test_agent_streaming.py` | Verify last chunk contains `usage` with token counts |
| AC-3: Raw mode passes through tool call deltas unmodified | `test_raw_mode_tool_call_deltas` | `test_agent_streaming.py` | Verify tool call chunks not transformed |
| AC-4: stream=True yields ExecutionEvents (backward compat) | `test_stream_true_backward_compatibility` | `test_agent_streaming.py` | Existing test, verify still passes |
| AC-5: stream="events" yields ExecutionEvents | `test_stream_events_explicit` | `test_agent_streaming.py` | New test, same behavior as stream=True |
| AC-6: stream=False returns AgentResult | `test_stream_false_returns_agent_result` | `test_agent_streaming.py` | Existing test, verify still passes |

### Test Tiers

**Unit Tests** (`tests/models/test_agent_streaming.py`)
- `test_raw_mode_yields_chunks_with_openai_fields` - Verify chunk structure
- `test_raw_mode_includes_usage_in_final_chunk` - Verify usage info
- `test_raw_mode_tool_call_deltas` - Verify tool calls not transformed  
- `test_stream_events_explicit` - Test `stream="events"` 
- `test_stream_true_backward_compatibility` - Verify `stream=True` unchanged
- `test_invalid_stream_value_raises_error` - Verify validation
- `test_raw_mode_content_matches_events_mode` - Compare content equivalence

**Integration Tests** (`tests/integration/test_raw_streaming_integration.py`)
- `test_raw_mode_with_openai_api` - Real OpenAI API call
- `test_raw_mode_with_anthropic_api` - Real Anthropic API call
- `test_raw_chunks_can_be_serialized_to_sse` - Verify SSE compatibility
- `test_raw_mode_performance_vs_events_mode` - Benchmark comparison

**Contract Tests**
- Verify LiteLLM chunks match expected OpenAI format
- Test with multiple LiteLLM versions (0.x compatibility)

### Negative & Edge Cases

**Test Invalid Inputs**
- `test_invalid_stream_value_raises_error` - Pass `stream="invalid"`
- `test_stream_raw_with_empty_thread` - Handle edge case

**Test Error Conditions**  
- `test_raw_mode_handles_llm_error` - LiteLLM raises exception
- `test_raw_mode_handles_network_timeout` - Timeout during streaming
- `test_raw_mode_handles_malformed_chunk` - LiteLLM returns bad data

**Test Boundary Conditions**
- `test_raw_mode_single_chunk` - Only one chunk returned
- `test_raw_mode_empty_content` - Chunk with no content
- `test_raw_mode_large_response` - Many chunks (1000+)

### Performance Tests

**Benchmarks** (`tests/benchmarks/test_streaming_performance.py`)
```python
async def test_raw_mode_performance():
    # Target: Raw mode ≤ 110% of events mode duration
    raw_duration = await benchmark_raw_mode(iterations=100)
    events_duration = await benchmark_events_mode(iterations=100)
    assert raw_duration <= events_duration * 1.10
```

**Load Tests**
- Stream 100 concurrent requests in raw mode
- Verify no memory leaks
- Verify back-pressure handling

### CI Requirements
- All tests must pass before merge
- Type checking with mypy must pass
- Test coverage must be ≥ 85% for new code
- Performance benchmarks must not regress > 10%

## 11. Risks & Open Questions

### Known Risks

**Risk: Type Checker Confusion**
- **Description**: Union of bool and string literals might confuse some type checkers
- **Likelihood**: Low (tested with mypy)
- **Impact**: Medium (developers get unhelpful errors)
- **Mitigation**: Comprehensive overloads, clear documentation, examples

**Risk: LiteLLM Chunk Format Changes**
- **Description**: LiteLLM might change chunk structure in future versions
- **Likelihood**: Low (following OpenAI spec)
- **Impact**: High (breaks raw mode consumers)
- **Mitigation**: Pin LiteLLM version ranges, test with multiple versions, document supported versions

**Risk: Tool Call Reassembly Confusion**
- **Description**: Users expect Tyler to execute tools in raw mode
- **Likelihood**: Medium (misunderstanding docs)
- **Impact**: Medium (users frustrated)
- **Mitigation**: Clear documentation with warning, example showing tool call handling, FAQ entry

**Risk: Provider-Specific Differences**
- **Description**: Different providers may return slightly different chunk formats
- **Likelihood**: Medium (providers have quirks)
- **Impact**: Low (users building proxies need to handle this anyway)
- **Mitigation**: Document known differences, test with major providers (OpenAI, Anthropic, local)

### Open Questions

**Q1: Should we support tool execution in raw mode?**
- **FINAL DECISION**: YES! Raw mode executes tools and iterates.
- **Rationale**: Following OpenAI Agents SDK pattern, raw mode should be fully agentic. Without tool execution, it can't complete multi-step tasks and isn't truly an "agent."
- **Reference**: https://openai.github.io/openai-agents-python/streaming/
- **Implementation**: Silent tool execution between chunk streams (no events yielded)

**Q2: Should we validate chunk structure in raw mode?**
- **Proposed Answer**: No, pass through as-is. Let consumers handle malformed data.
- **Rationale**: Validation adds overhead and defeats "raw" nature
- **Alternative**: Add optional validation flag in future if users request it

**Q3: Should final usage chunk always be included?**
- **FINAL DECISION**: Yes, if LiteLLM provides it. Don't filter any chunks.
- **Rationale**: Users need token counts for billing/monitoring
- **Note**: Some providers might not send usage in stream (documented)
- **Implementation**: Usage chunk yielded at end of each LLM response

**Q4: How to handle Weave tracing in raw mode?**
- **Proposed Answer**: `@weave.op()` on `_go_stream_raw()`, log basic metrics (chunk count)
- **Rationale**: Still valuable to trace raw mode usage
- **Note**: Won't have rich event-level traces like events mode

## 12. Milestones / Plan (Post-Approval)

### Task 1: Update Agent.go() Signature & Overloads
**DoD:**
- [ ] Add new overload for `stream: Literal["raw"]`
- [ ] Add new overload for `stream: Union[Literal[True], Literal["events"]]`
- [ ] Update main `go()` signature to accept union type
- [ ] Add parameter validation
- [ ] Update docstring with new parameter docs
- [ ] Type checker (mypy) passes
- [ ] No lint errors

**Test:**
- `test_invalid_stream_value_raises_error` - Write first (should fail)

**Dependencies:** None

---

### Task 2: Implement `_go_stream_raw()` Method
**DoD:**
- [x] Create new `_go_stream_raw()` method with full iteration loop
- [x] Handle thread resolution (same as `_go_stream`)
- [x] Initialize iteration tracking
- [x] While loop for max_tool_iterations
- [x] Call LiteLLM with `stream=True` in each iteration
- [x] Yield raw chunks without transformation
- [x] Accumulate tool calls from chunk deltas
- [x] Execute tools silently after chunk stream ends
- [x] Add tool result messages to thread
- [x] Iterate until no more tool calls
- [x] Add debug logging
- [x] Tests pass for basic raw streaming

**Tests:**
- `test_raw_mode_yields_chunks_with_openai_fields` - ✅ Passing
- `test_raw_mode_includes_usage_in_final_chunk` - ✅ Passing

**Dependencies:** Task 1

---

### Task 3: Add Routing Logic in go()
**DoD:**
- [x] Normalize `True` → `"events"` internally
- [x] Route to `_go_complete`, `_go_stream`, or `_go_stream_raw` based on mode
- [x] Add debug log for mode selection
- [x] All routing tests pass

**Tests:**
- `test_stream_events_explicit` - ✅ Passing
- `test_stream_true_backward_compatibility` - ✅ Passing

**Dependencies:** Task 2

---

### Task 4: Handle Tool Calls in Raw Mode
**DoD:**
- [x] Accumulate tool calls from chunk deltas (same logic as _go_stream)
- [x] Execute tools after streaming completes (silently)
- [x] Add tool result messages to thread
- [x] Continue iteration for next LLM call
- [x] Ensure tool call chunks pass through unmodified
- [x] Test with mocked tool call responses
- [x] Update docstring to clarify tool execution happens

**Tests:**
- `test_raw_mode_tool_call_deltas` - ✅ Passing

**Implementation Note:**
Following OpenAI Agents SDK pattern - tools ARE executed, just silently between chunk streams.

**Dependencies:** Task 3

---

### Task 5: Integration Tests with Real Providers
**DoD:**
- [ ] Test with OpenAI API (requires API key)
- [ ] Test with Anthropic API (requires API key)
- [ ] Verify chunk format matches OpenAI spec
- [ ] Document any provider-specific differences
- [ ] All integration tests pass

**Tests:**
- `test_raw_mode_with_openai_api` - Write first
- `test_raw_mode_with_anthropic_api` - Write first

**Dependencies:** Task 4

---

### Task 6: Create Examples & Documentation
**DoD:**
- [ ] Create `examples/005_raw_streaming.py`
- [ ] Show basic raw mode usage
- [ ] Show SSE serialization pattern
- [ ] Show tool call handling in raw mode
- [ ] Update API reference docs
- [ ] Update streaming guide
- [ ] Add FAQ entry
- [ ] All examples run successfully

**Tests:**
- Run example scripts manually
- Verify docs build without errors

**Dependencies:** Task 5

---

### Task 7: Performance Benchmarks
**DoD:**
- [ ] Create benchmark comparing raw vs events mode
- [ ] Verify raw mode is ≤ 110% of events mode duration
- [ ] Document results
- [ ] Add benchmark to CI (optional)

**Tests:**
- `test_raw_mode_performance_vs_events_mode` - Create benchmark

**Dependencies:** Task 6

---

### Task 8: Final Polish & Review
**DoD:**
- [ ] All tests passing (unit, integration, contract)
- [ ] Type checking passes (mypy)
- [ ] No linter errors
- [ ] Code coverage ≥ 85% for new code
- [ ] All examples run successfully
- [ ] Documentation complete
- [ ] CHANGELOG updated
- [ ] Ready for PR review

**Dependencies:** All previous tasks

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved in the PR.

