# Impact Analysis — A2A Token-Level Streaming

## Modules/packages likely touched
- `packages/tyler/tyler/a2a/server.py` — Primary change: modify `TylerAgentExecutor.execute()` to use `agent.stream()` instead of `agent.run()`
- `packages/tyler/tyler/a2a/__init__.py` — May need to export new config options
- `packages/tyler/tests/a2a/` — New/updated tests for streaming behavior

## Contracts to update (APIs, events, schemas, migrations)
- **A2A Event Contract**: No protocol changes—we're implementing existing A2A spec behavior:
  - `TaskArtifactUpdateEvent` with `append=True` for intermediate chunks
  - `TaskArtifactUpdateEvent` with `lastChunk=True` for final chunk
- **A2AServer Constructor**: Add optional `streaming: bool = True` parameter
- **No database migrations**: Feature is stateless
- **No breaking changes**: Existing non-streaming behavior preserved

## Risks
- **Security**: None identified. Token streaming doesn't expose additional data—same content, different delivery timing.
  
- **Performance/Availability**: 
  - *Risk*: High-frequency event emission could overwhelm slow clients or the event queue
  - *Mitigation*: A2A SDK's `EventQueue` handles backpressure; SSE is designed for this pattern
  - *Future*: Consider optional batching (e.g., emit every 50ms or N tokens) if issues arise
  
- **Data integrity**: 
  - *Risk*: Partial artifacts if connection drops mid-stream
  - *Mitigation*: Clients can use `tasks/get` to fetch complete state; `lastChunk=True` signals completion
  - *Risk*: Token ordering in multi-tool-call scenarios
  - *Mitigation*: Sequential event emission within each LLM response; new artifact ID per response cycle

## Observability needs
- **Logs**: 
  - DEBUG: Log chunk count and total bytes streamed per task
  - INFO: Log streaming mode enabled/disabled on server start
  - ERROR: Log streaming failures with task ID
  
- **Metrics** (future, not required for MVP):
  - `a2a_stream_chunks_total` — Counter of chunks emitted
  - `a2a_stream_latency_ms` — Time from LLM chunk to SSE emission
  
- **Alerts**: None required for MVP—use existing A2A server health alerts

