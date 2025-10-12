# Impact Analysis — Raw Streaming Mode for OpenAI Compatibility

## Modules/packages likely touched
- **`packages/tyler/tyler/models/agent.py`**
  - The `go()` method signature and overloads
  - The `_go_stream()` method (or new `_go_stream_raw()` method)
  - Type hints and return type annotations
  - Method documentation/docstrings

- **`packages/tyler/tyler/__init__.py`** (potentially)
  - May need to export new types/literals if we create them

- **`packages/tyler/examples/`**
  - New example file demonstrating `stream="raw"` usage
  - Example showing SSE serialization pattern

- **Documentation (`docs/`)**
  - API reference for `agent.go()`
  - Guide on streaming modes
  - Migration notes for understanding the new parameter

- **Tests (`packages/tyler/tests/`)**
  - `tests/models/test_agent_streaming.py` - new tests for raw mode
  - `tests/models/test_agent_observability.py` - ensure backward compat tests pass
  - Integration tests with actual LiteLLM providers

## Contracts to update (APIs, events, schemas, migrations)

### API Changes
**`Agent.go()` method signature:**
```python
# Before (current)
def go(
    self,
    thread_or_id: Union[Thread, str],
    stream: bool = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None]]

# After (proposed)
def go(
    self,
    thread_or_id: Union[Thread, str],
    stream: Union[bool, Literal["events", "raw"]] = False
) -> Union[AgentResult, AsyncGenerator[ExecutionEvent, None], AsyncGenerator[Any, None]]
```

**Type overloads needed:**
```python
@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal[False] = False) -> AgentResult: ...

@overload
def go(self, thread_or_id: Union[Thread, str], stream: Union[Literal[True], Literal["events"]]) -> AsyncGenerator[ExecutionEvent, None]: ...

@overload
def go(self, thread_or_id: Union[Thread, str], stream: Literal["raw"]) -> AsyncGenerator[Any, None]: ...
```

### Internal Changes
- New private method `_go_stream_raw()` with full iteration loop
- Parameter normalization: convert `True` → `"events"` early in the method
- Tool execution logic duplicated from `_go_stream()` (yields chunks instead of events)
- Silent tool execution: no chunks during tool calls, matches OpenAI pattern

### No Breaking Changes
- Existing calls with `stream=True` or `stream=False` continue to work identically
- All existing type annotations remain valid
- No changes to `ExecutionEvent` or `AgentResult` classes

## Risks

### Security
- **Low Risk**: Raw chunks from LiteLLM don't contain more sensitive information than ExecutionEvents
- **Consideration**: Raw chunks expose the exact provider response format, which might leak provider-specific details (model IDs, internal fields)
- **Mitigation**: Document that `stream="raw"` exposes provider-specific data; users should sanitize before forwarding to untrusted clients

### Performance/Availability
- **Positive Impact**: Raw mode should be FASTER than events mode (no transformation overhead)
- **Low Risk**: No additional API calls or processing
- **Consideration**: Users might create large buffering if they don't handle chunks efficiently
- **Mitigation**: Add documentation best practices for handling high-volume chunk streams

### Data Integrity
- **Medium Risk**: Need to ensure ALL chunks are passed through across multiple iterations:
  - Content deltas from all LLM calls
  - Tool call deltas 
  - Usage/completion information
  - Error/finish reason
  - Chunks from iteration 1, then iteration 2, etc.
- **Mitigation**: 
  - Comprehensive tests comparing raw chunk content with ExecutionEvent content
  - Validate that final usage tokens match in both modes
  - Test with multiple providers (OpenAI, Anthropic, local models)
  - Test multi-iteration scenarios with tool calls

### Backward Compatibility
- **Critical**: Must not break existing code using `stream=True` or `stream=False`
- **Mitigation**:
  - Extensive backward compatibility tests
  - Type checker validation (mypy) to ensure existing annotations work
  - CI runs all existing streaming examples

### Type Safety
- **Low Risk**: The `Union[bool, Literal["events", "raw"]]` might be confusing for type checkers
- **Mitigation**: Use comprehensive `@overload` decorators to provide precise type hints for each mode

## Observability needs

### Logs
- **Add debug log** in `go()` method indicating which streaming mode is being used:
  ```python
  logger.debug(f"Agent.go() called with stream mode: {stream_mode}")
  ```
- **Log warning** if an unrecognized stream value is provided (for future extensibility)

### Metrics
- **Usage tracking** (if using Weave or similar):
  - Counter: `tyler.agent.go.stream_mode` with labels: `raw`, `events`, `none`
  - Track adoption of raw mode vs events mode
  - Monitor if anyone passes invalid stream values

- **Performance metrics** (optional but valuable):
  - Histogram: `tyler.agent.go.duration_ms` with label for stream mode
  - Compare performance of raw vs events mode
  - Track total chunks yielded per request

### Alerts
- **None required** - This is additive functionality that doesn't affect existing behavior
- **Optional**: Alert on unusually high error rates if we add validation for stream parameter values

### Tracing
- If using distributed tracing, add span attribute:
  - `tyler.stream_mode`: `"raw"` | `"events"` | `"none"`
- Helps debug streaming issues in production

## Dependencies

### No new dependencies required
- Uses existing LiteLLM streaming functionality
- Uses existing Python typing features (`Literal`, `Union`, `overload`)

### Version compatibility
- Requires Python 3.8+ for `Literal` type hints (already required by Tyler)
- No changes to LiteLLM version requirements

## Testing Strategy Summary

### Unit Tests
1. Test `stream="raw"` returns raw LiteLLM chunks
2. Test `stream="events"` returns ExecutionEvents
3. Test `stream=True` returns ExecutionEvents (backward compat)
4. Test `stream=False` returns AgentResult (backward compat)
5. Test invalid stream values raise appropriate errors

### Integration Tests
1. Test raw mode with actual OpenAI API
2. Test raw mode with tool calls
3. Test raw mode captures usage information
4. Compare content between raw and events mode (should be equivalent)

### Backward Compatibility Tests
1. Run all existing streaming examples unchanged
2. Verify type checker (mypy) passes on existing code
3. Ensure no deprecation warnings

## Migration Path for Users

### No migration required for existing users
- All existing code continues to work without changes

### Opt-in adoption
Users who want raw chunks can:
1. Change `stream=True` to `stream="raw"` in their code
2. Update their event handlers to work with raw chunk objects instead of ExecutionEvents
3. Implement SSE serialization if building an API endpoint

### Documentation updates needed
- Add new example: `examples/005_raw_streaming.py`
- Update streaming guide with comparison table
- Add FAQ: "When should I use raw mode vs events mode?"

