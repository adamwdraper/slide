# Design Pivot: From Async .go() to .go() + .stream()

## What Happened

We attempted to make `.go()` async while keeping the `stream` parameter, but discovered a fundamental Python limitation:

**You cannot mix `return value` and `yield` in the same function.**

```python
# This doesn't work in Python!
async def go(...):
    if not streaming:
        return await self._go_complete(...)  # return with value
    else:
        async for event in self._go_stream(...):
            yield event  # yield
# SyntaxError: 'return' with value in async generator
```

## Why We Pivoted

After brainstorming alternatives, we concluded that **splitting into two methods** is:
1. **Industry standard** - httpx, aiohttp, FastAPI all do this
2. **Better design** - Single responsibility principle
3. **Clearer intent** - `.go()` vs `.stream()` is self-documenting
4. **Type safe** - No Union return types
5. **No Python limitations** - Each method can be properly async

## New Design

### Before (v4.x)
```python
result = await agent.go(thread)  # Needs await added
async for event in agent.go(thread, stream=True)  # Parameter changes behavior
async for chunk in agent.go(thread, stream="raw")
```

### After (v5.0.0)
```python
# Two distinct methods
result = await agent.go(thread)  # Clear: returns result
async for event in agent.stream(thread)  # Clear: yields events  
async for chunk in agent.stream(thread, mode="raw")  # Clear: yields chunks
```

## Migration

Simple find/replace:
- `agent.go(thread)` → `await agent.go(thread)` (add await)
- `agent.go(thread, stream=True)` → `agent.stream(thread)`
- `agent.go(thread, stream="events")` → `agent.stream(thread)`
- `agent.go(thread, stream="raw")` → `agent.stream(thread, mode="raw")`

## Benefits

1. **Clearer API**: Method name indicates behavior
2. **Better types**: No Union[AgentResult, AsyncGenerator]
3. **Industry standard**: Matches successful async libraries
4. **No Python limitations**: Both methods work perfectly
5. **Single responsibility**: Each method does one thing well

## Documents Updated

- ✅ spec.md - Reflects new design
- ⏳ impact.md - Needs update
- ⏳ tdr.md - Needs complete rewrite
- ⏳ IMPLEMENTATION_NOTES.md - Needs update

Date: 2025-10-28
Decision: Approved by user after discussion

