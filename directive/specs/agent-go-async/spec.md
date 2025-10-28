# Spec (per PR)

**Feature name**: Split Agent.go() into .go() and .stream() Methods  
**One-line summary**: Separate non-streaming and streaming execution into distinct async methods for clearer API semantics and better developer experience  

---

## Problem

The `Agent.go()` method currently handles both non-streaming and streaming execution through a single overloaded method with a `stream` parameter. This creates several developer experience issues:

1. **Overloaded API semantics** - One method with vastly different behaviors based on a boolean parameter
2. **Python async limitations** - Cannot mix `return value` and `yield` in same async function (syntax error)
3. **Violates single responsibility** - One method does two completely different things (return result vs stream events)
4. **Unclear intent** - `agent.go(thread, stream=True)` doesn't clearly indicate you're getting an iterator
5. **Industry anti-pattern** - Successful async libraries separate these concerns (httpx, aiohttp, FastAPI)

This also causes observable issues with tooling (like Weave) that expect async generators to come from async functions.

Current overloaded API:
```python
# Same method, completely different usage patterns
result = await agent.go(thread)  # Get final result
async for event in agent.go(thread, stream=True)  # Iterate events

# Confusing: stream=True changes everything about how you use it
```

## Goal

Split into two distinct async methods that each do one thing well, following industry best practices and Python async patterns.

## Success Criteria

- [x] `Agent.go()` is `async def` for non-streaming execution only
- [x] `Agent.stream()` is `async def` for streaming execution (events or raw)
- [x] Each method has single, clear responsibility
- [x] Both methods properly async (no Python syntax limitations)
- [x] Type signatures are clear and unambiguous
- [x] Observability tooling (like Weave) works correctly
- [x] Breaking change is clearly documented with migration guide
- [x] Follows industry patterns (httpx, aiohttp, FastAPI)

## User Story

As a **developer using Tyler agents**, I want **clear, focused methods for different execution modes**, so that **I can write more readable, maintainable code with proper async semantics**.

## Flow / States

### Happy Path - Non-Streaming (.go)
1. User calls `result = await agent.go(thread)`
2. Agent executes completion loop
3. Returns `AgentResult` object
4. Weave logs complete execution trace

### Happy Path - Event Streaming (.stream)
1. User calls `async for event in agent.stream(thread)`
2. Agent yields `ExecutionEvent` objects as they occur
3. Iteration completes when agent finishes
4. Weave logs execution trace with all events

### Happy Path - Raw Streaming (.stream)
1. User calls `async for chunk in agent.stream(thread, mode="raw")`
2. Agent yields raw LiteLLM chunks
3. Iteration completes when agent finishes

### Edge Case - Invalid Stream Mode
1. User calls `async for event in agent.stream(thread, mode="invalid")`
2. Method raises `ValueError` with clear message

## UX Links

N/A - This is an internal API change with no visual UX component.

## Requirements

### Must
- Create `Agent.go()` as `async def` for non-streaming execution only
  - Returns `AgentResult` (no streaming modes)
  - Uses `return await self._go_complete(...)`
- Create `Agent.stream()` as `async def` for streaming execution
  - Yields `ExecutionEvent` or raw chunks based on `mode` parameter
  - Uses `async for ... yield` pattern
  - Supports `mode="events"` (default) and `mode="raw"`
- Both methods have clear, focused type signatures (no Union return types)
- Preserve all existing functionality (tool execution, iteration limits, error handling)
- Follow Python async best practices (no return/yield mixing)
- Follow industry patterns (separate methods like httpx, aiohttp)

### Must Not
- Keep overloaded `.go()` method with `stream` parameter
- Mix `return` and `yield` in same function (Python limitation)
- Change return types, event structures, or execution logic
- Add unnecessary complexity beyond the method split

## Acceptance Criteria

### Non-Streaming Mode - Clear, Focused Method
- **Given** a thread with user messages, **when** calling `await agent.go(thread)`, **then** returns `AgentResult` with correct content

### Event Streaming Mode - Separate Method
- **Given** a thread with user messages, **when** calling `async for event in agent.stream(thread)`, **then** yields `ExecutionEvent` objects in real-time

### Raw Streaming Mode - Same Method, Different Mode
- **Given** a thread with user messages, **when** calling `async for chunk in agent.stream(thread, mode="raw")`, **then** yields raw LiteLLM chunks

### API Clarity - Single Responsibility
- **Given** a developer using the API, **when** they see `.go()` vs `.stream()`, **then** the intent is immediately clear (get result vs iterate events)

### Type Safety - No Union Types
- **Given** type checking with mypy, **when** calling `.go()`, **then** type is clearly `AgentResult` (not Union)
- **Given** type checking with mypy, **when** calling `.stream()`, **then** type is clearly `AsyncGenerator[ExecutionEvent]`

### Invalid Stream Mode (Negative Case)
- **Given** an invalid stream mode, **when** calling `agent.stream(thread, mode="invalid")`, **then** raises `ValueError` with helpful message

### Observability Tooling Works (Validation)
- **Given** any execution mode with Weave initialized, **when** agent executes, **then** observability tools correctly capture execution traces

### Breaking Change - Clear Migration Path
- **Given** streaming usage, **when** users update code, **then** they change `agent.go(thread, stream=True)` to `agent.stream(thread)` (simple find/replace)

## Non-Goals

- Changing the internal implementation of `_go_complete()`, `_go_stream()`, or `_go_stream_raw()` (these already work correctly)
- Adding new streaming modes beyond `events` and `raw`
- Changing the `ExecutionEvent` or `AgentResult` data structures
- Modifying how tools are executed or how iteration limits work
- Providing backward compatibility for old `stream=True` parameter (intentional breaking change for better DX)
- Creating a unified method that handles both modes (tried this, Python doesn't allow it)
- Fixing or optimizing observability beyond what naturally comes from proper async design

