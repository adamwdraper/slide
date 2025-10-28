# Agent API Split: .go() and .stream()

## Overview

This spec proposes splitting `Agent.go()` into two focused methods for v5.0.0:
- `agent.go(thread)` - Non-streaming execution (returns `AgentResult`)
- `agent.stream(thread, mode="events")` - Streaming execution (yields events or chunks)

## Why Split Instead of Making `.go()` Async?

We initially planned to make `.go()` async while keeping the `stream` parameter, but discovered a **Python limitation**:

```python
# This causes SyntaxError!
async def go(self, thread, stream=False):
    if not stream:
        return await self._go_complete(thread)  # return with value
    else:
        async for event in self._go_stream(thread):
            yield event  # yield

# Error: 'return' with value in async generator
```

**Python does not allow mixing `return value` and `yield` in the same function.**

After exploring alternatives (yield-once pattern, smart wrapper objects, etc.), we determined that **splitting into two methods** is:
- Industry standard (httpx, aiohttp, FastAPI)
- Better design (single responsibility)
- Clearer for developers
- No Python limitations

## Design

### New API (v5.0.0)

```python
# Non-streaming - Get final result
result = await agent.go(thread)
print(result.content)

# Event streaming - Watch execution in real-time
async for event in agent.stream(thread):
    if event.type == EventType.MESSAGE_CREATED:
        print(event.data['message'].content)

# Raw streaming - OpenAI-compatible chunks
async for chunk in agent.stream(thread, mode="raw"):
    print(chunk.choices[0].delta.content, end="")
```

### Implementation

```python
@weave.op()
async def go(self, thread_or_id: Union[Thread, str]) -> AgentResult:
    """Execute agent and return complete result"""
    return await self._go_complete(thread_or_id)

@weave.op()
async def stream(
    self,
    thread_or_id: Union[Thread, str],
    mode: Literal["events", "raw"] = "events"
) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
    """Stream agent execution events or raw chunks"""
    if mode == "events":
        async for event in self._go_stream(thread_or_id):
            yield event
    else:
        async for chunk in self._go_stream_raw(thread_or_id):
            yield chunk
```

## Migration from v4.x

### Pattern 1: Non-streaming (add await)
```python
# v4.x
result = agent.go(thread)

# v5.0.0
result = await agent.go(thread)
```

### Pattern 2: Event streaming (change method)
```python
# v4.x
async for event in agent.go(thread, stream=True):
    print(event)

# v5.0.0
async for event in agent.stream(thread):
    print(event)
```

### Pattern 3: Raw streaming (change method + parameter)
```python
# v4.x
async for chunk in agent.go(thread, stream="raw"):
    process(chunk)

# v5.0.0
async for chunk in agent.stream(thread, mode="raw"):
    process(chunk)
```

### Automated Migration (Regex)

```
1. .go\((.*?), stream=True\)     → .stream(\1)
2. .go\((.*?), stream="events"\) → .stream(\1)
3. .go\((.*?), stream="raw"\)    → .stream(\1, mode="raw")
4. = agent\.go\(                 → = await agent.go(
5. .go\((.*?), stream=False\)    → .go(\1)
```

## Impact

### Files Affected
- **Core**: 1 file (agent.py)
- **Tests**: ~13 files, ~100+ functions
- **Examples**: ~30 files
- **Docs**: ~14 files, ~80+ samples
- **Integrations**: 2 files (CLI, Space Monkey)

**Total**: ~60 files, ~250+ call sites

### Timeline
- **Implementation**: ~31 hours (~4 days)
- **Review & Release**: ~10 hours (1.5 days)
- **Total**: ~39 hours (~5 days)

## Benefits

1. **Clear Intent**: Method names are self-documenting
2. **Single Responsibility**: Each method does one thing well
3. **Type Safety**: No Union return types
4. **Industry Standard**: Matches successful async libraries
5. **No Python Limitations**: Both methods work perfectly
6. **Better Observability**: Weave tracing works correctly
7. **Simpler Code**: ~45 lines less in agent.py

## Documents

- ✅ `spec.md` - Requirements and acceptance criteria
- ✅ `impact.md` - Comprehensive impact analysis
- ✅ `tdr.md` - Technical design and implementation plan
- ✅ `PIVOT_NOTES.md` - Design decision rationale
- ✅ `README.md` (this file) - Quick reference

## Status

**Branch**: `agent-go-async`  
**Commits**: 5 (spec, impact, TDR, pivot notes, README)  
**State**: Ready for implementation pending approval  
**Version**: Tyler v5.0.0 (major breaking change)

## Next Steps

1. Review and approve TDR
2. Begin implementation (Milestone 1: Core)
3. Update all tests and examples
4. Update documentation
5. Release v5.0.0

