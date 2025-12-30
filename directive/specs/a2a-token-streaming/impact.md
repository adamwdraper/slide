# Impact Analysis — A2A Token-Level Streaming

**Updated**: 2024-12-30 — Simplified design (always stream internally)

## Modules/packages touched
- `packages/tyler/tyler/a2a/server.py` — Modified `TylerAgentExecutor.execute()` to always use `agent.stream()`. Removed dispatch logic.
- `packages/tyler/tests/a2a/test_streaming.py` — New tests for streaming behavior (6 tests)

## Contracts updated (APIs, events, schemas, migrations)
- **A2A Event Contract**: No protocol changes—we're implementing existing A2A spec behavior:
  - `TaskArtifactUpdateEvent` with `append=True` for intermediate chunks
  - `TaskArtifactUpdateEvent` with `lastChunk=True` for final chunk
- **A2AServer Constructor**: No new parameters (simplified design)
- **Behavioral change**: Executor always streams internally; SDK handles delivery mode
- **No database migrations**: Feature is stateless
- **No breaking changes**: SDK aggregates events for `message/send` clients automatically

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
- **Logs** (implemented): 
  - DEBUG: `Starting execution for task {task_id}`
  - DEBUG: `Execution complete for task {task_id}: {chunk_count} chunks`
  - INFO: `Completed task {task_id}: {chunk_count} chunks, {total_bytes} bytes`
  - ERROR: `Execution error for task {task_id}: {error_msg}`
  
- **Metrics** (future, not required for MVP):
  - `a2a_stream_chunks_total` — Counter of chunks emitted
  - `a2a_stream_latency_ms` — Time from LLM chunk to SSE emission
  
- **Alerts**: None required for MVP—use existing A2A server health alerts

