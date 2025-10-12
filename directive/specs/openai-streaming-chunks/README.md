# OpenAI-Compatible Raw Streaming Chunks

This spec adds support for exposing raw LiteLLM SSE chunks in OpenAI-compatible format through Tyler's Agent API.

## Quick Links

- **Spec**: [spec.md](./spec.md) - Feature requirements and acceptance criteria
- **Impact Analysis**: [impact.md](./impact.md) - Modules affected, risks, and observability needs
- **Technical Design Review**: [tdr.md](./tdr.md) - Detailed design, test strategy, and implementation plan

## Overview

**Feature**: Add `stream="raw"` mode to `Agent.go()` method

**Problem**: Tyler currently transforms all LiteLLM streaming chunks into ExecutionEvent objects. While great for observability, this prevents direct integration with OpenAI-compatible clients.

**Solution**: Extend the `stream` parameter to accept string literals in addition to booleans:
- `stream=False` → AgentResult (non-streaming)
- `stream=True` or `stream="events"` → ExecutionEvent streaming (current behavior)
- `stream="raw"` → Raw LiteLLM chunk streaming (new)

## API Example

```python
# Current behavior (unchanged)
result = await agent.go(thread)  # AgentResult
async for event in agent.go(thread, stream=True):  # ExecutionEvent
    if event.type == EventType.LLM_STREAM_CHUNK:
        print(event.data["content_chunk"])

# New raw mode
async for chunk in agent.go(thread, stream="raw"):
    # chunk is raw LiteLLM object
    if hasattr(chunk.choices[0].delta, 'content'):
        content = chunk.choices[0].delta.content
        print(content)
```

## Status

- [x] Spec created
- [x] Impact Analysis created
- [x] TDR created
- [ ] TDR approved
- [ ] Implementation started
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Ready for merge

## Key Decisions

1. **Single parameter approach**: Use `stream` parameter with multiple values instead of adding a second `raw_chunks` flag
2. **No tool execution in raw mode**: Raw mode is pass-through only; consumers handle tool calls
3. **No validation**: Pass chunks as-is from LiteLLM without structure validation
4. **100% backward compatible**: All existing code continues to work unchanged

## Implementation Notes

- Main changes in `packages/tyler/tyler/models/agent.py`
- New private method: `_go_stream_raw()`
- Type-safe with overloads for each stream mode
- Comprehensive tests for backward compatibility
- Examples showing SSE serialization patterns

## Testing Strategy

- Unit tests for all stream modes
- Integration tests with OpenAI, Anthropic APIs
- Backward compatibility validation
- Performance benchmarks (raw should be ~10-15% faster)
- Type checker validation (mypy)

## Use Cases

1. Building OpenAI API proxies or gateways
2. Drop-in replacements for OpenAI endpoints
3. Debugging provider-specific behavior
4. Integration with existing OpenAI-compatible tools
5. Performance-critical applications needing minimal overhead

