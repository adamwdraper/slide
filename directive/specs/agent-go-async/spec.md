# Spec (per PR)

**Feature name**: Async Agent.go() Method  
**One-line summary**: Make `Agent.go()` an async method to provide a clearer, more semantically correct API that properly expresses async behavior  

---

## Problem

The `Agent.go()` method is currently a synchronous function that returns async generators and performs async operations internally. This creates several developer experience issues:

1. **Misleading API semantics** - The method appears synchronous but performs async database operations, network calls, and tool execution
2. **Inconsistent with implementation** - All internal methods (`_go_complete()`, `_go_stream()`, `_go_stream_raw()`, `step()`, `connect_mcp()`) are async
3. **Violates async best practices** - Async generators should come from async functions, not sync functions that return them
4. **Hidden complexity** - Developers can't tell from the signature that async work is happening

This also causes observable issues with tooling (like Weave) that expect async generators to come from async functions.

Current misleading API:
```python
# Looks sync but does async work
result = agent.go(thread)  # Hides async operations!

# Streaming requires async context but method isn't async
async for event in agent.go(thread, stream=True)  # Confusing mixed signals
```

## Goal

Convert `Agent.go()` to an async method that accurately represents its async nature, providing developers with a clear, semantically correct API that makes async operations explicit.

## Success Criteria

- [x] `Agent.go()` is declared as `async def`, making async behavior explicit
- [x] API signature clearly indicates async operations are happening
- [x] All three modes (non-streaming, event streaming, raw streaming) work correctly
- [x] Existing tests pass with minimal updates (just adding `await`)
- [x] Observability tooling (like Weave) works correctly as a validation of proper async design
- [x] Breaking change is clearly documented with migration guide

## User Story

As a **developer using Tyler agents**, I want **a clear, semantically correct API**, so that **I can immediately understand that async operations are happening and write more predictable, maintainable code**.

## Flow / States

### Happy Path - Non-Streaming
1. User calls `result = await agent.go(thread)`
2. Agent executes completion loop
3. Returns `AgentResult` object
4. Weave logs complete execution trace

### Happy Path - Event Streaming
1. User calls `async for event in agent.go(thread, stream=True)`
2. Agent yields `ExecutionEvent` objects as they occur
3. Iteration completes when agent finishes
4. Weave logs execution trace with all events

### Edge Case - Stream Parameter Validation
1. User calls `agent.go(thread, stream="invalid")`
2. Method raises `ValueError` with clear message
3. Weave logs the error

## UX Links

N/A - This is an internal API change with no visual UX component.

## Requirements

### Must
- Make `Agent.go()` an async method (`async def`) to accurately represent its async nature
- For non-streaming mode: use `return await` to return the result
- For streaming modes: use `async for ... yield` to delegate to internal generators
- Maintain identical type signatures and overloads (except adding `async`)
- Maintain identical return types for all three modes
- Preserve all existing functionality (tool execution, iteration limits, error handling)
- Make the API semantically correct and self-documenting
- Follow Python async best practices (async functions for async work)

### Must Not
- Change the streaming API behavior (users still call `async for event in agent.go(...)`)
- Change return types, event structures, or execution logic
- Break backward compatibility for streaming usage (still `async for`, not `await` then iterate)
- Add unnecessary complexity or indirection

## Acceptance Criteria

### Non-Streaming Mode - Clear Async Semantics
- **Given** a thread with user messages, **when** calling `await agent.go(thread)`, **then** returns `AgentResult` with correct content and the `async def` signature clearly indicates async work is happening

### Event Streaming Mode - Consistent Async Pattern
- **Given** a thread with user messages, **when** calling `async for event in agent.go(thread, stream=True)`, **then** yields `ExecutionEvent` objects in real-time with proper async generator semantics

### Raw Streaming Mode - Consistent Async Pattern
- **Given** a thread with user messages, **when** calling `async for chunk in agent.go(thread, stream="raw")`, **then** yields raw LiteLLM chunks with proper async generator semantics

### API Clarity - Developer Can See Async Nature
- **Given** a developer looking at the method signature, **when** they see `async def go(...)`, **then** they immediately understand async operations are involved and `await` is required

### Invalid Stream Parameter (Negative Case)
- **Given** an invalid stream parameter, **when** calling `await agent.go(thread, stream="invalid")`, **then** raises `ValueError` with helpful message

### Observability Tooling Works (Validation)
- **Given** any execution mode with Weave initialized, **when** agent executes, **then** observability tools correctly capture execution traces (validating proper async design)

### Breaking Change - Clear Error Message
- **Given** non-streaming usage, **when** users forget `await`, **then** they get Python's standard async/await error which clearly indicates the fix needed

## Non-Goals

- Changing the internal implementation of `_go_complete()`, `_go_stream()`, or `_go_stream_raw()` (these already work correctly)
- Adding new streaming modes or features beyond making existing ones properly async
- Changing the `ExecutionEvent` or `AgentResult` data structures
- Modifying how tools are executed or how iteration limits work
- Providing backward compatibility for synchronous usage (this is an intentional breaking change for better DX)
- Fixing or optimizing observability beyond what naturally comes from proper async design

