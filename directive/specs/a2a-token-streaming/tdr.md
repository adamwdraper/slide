# Technical Design Review (TDR) — A2A Token-Level Streaming

**Author**: Agent  
**Date**: 2024-12-30  
**Links**: [Spec](spec.md), [Impact](impact.md)

---

## 1. Summary

This TDR describes the implementation of real-time token streaming for Tyler agents exposed via the A2A protocol. Currently, the `TylerAgentExecutor` uses `agent.run()` which waits for complete execution before emitting results. We will modify it to use `agent.stream()` and emit `TaskArtifactUpdateEvent`s for each token chunk, providing A2A clients with real-time response visibility.

Tyler already has robust streaming infrastructure via `agent.stream()` that yields `ExecutionEvent` objects including `LLM_STREAM_CHUNK`. This TDR focuses on wiring that infrastructure into the A2A server's event queue.

## 2. Decision Drivers & Non-Goals

**Drivers:**
- Protocol compliance: A2A spec explicitly supports streaming via SSE
- User experience: Real-time feedback for long-running responses
- Low implementation effort: Tyler streaming already exists

**Non-Goals:**
- Batching/throttling optimization (future enhancement if needed)
- Streaming tool execution progress (would require separate events)
- Push notification streaming (already handled by SDK infrastructure)
- Client-side changes (client already supports streaming)

## 3. Current State — Codebase Map

### Key Modules

| Module | Purpose |
|--------|---------|
| `tyler/a2a/server.py` | A2A server with `TylerAgentExecutor` |
| `tyler/models/agent.py` | Agent with `run()` and `stream()` methods |
| `tyler/models/streaming.py` | `ExecutionEvent`, `EventType` definitions |

### Current A2A Executor Flow

```python
# server.py - TylerAgentExecutor.execute()
async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
    # ...
    result = await self.agent.run(tyler_thread)  # Blocks until complete
    # ...
    await event_queue.enqueue_event(TaskArtifactUpdateEvent(...))  # Single artifact
```

### Tyler Streaming Events

The `agent.stream()` method yields these relevant `ExecutionEvent` types:

| EventType | Data | Use |
|-----------|------|-----|
| `LLM_STREAM_CHUNK` | `{"content_chunk": str}` | Token content |
| `LLM_THINKING_CHUNK` | `{"thinking_chunk": str}` | Reasoning tokens |
| `TOOL_SELECTED` | `{"tool_name": str, ...}` | Tool invocation |
| `TOOL_RESULT` | `{"result": str, ...}` | Tool completion |
| `EXECUTION_COMPLETE` | `{"duration_ms": float, ...}` | Final event |
| `EXECUTION_ERROR` | `{"message": str, ...}` | Error handling |

### Existing Observability
- Tyler agent emits structured logs for streaming events
- A2A server logs task lifecycle events

## 4. Proposed Design

### High-Level Approach

Replace `agent.run()` with `agent.stream()` in `TylerAgentExecutor.execute()` and map Tyler's `ExecutionEvent`s to A2A's `TaskArtifactUpdateEvent`s.

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `TylerAgentExecutor` | Consume Tyler stream, emit A2A events |
| `EventQueue` (SDK) | Buffer and deliver SSE events to clients |
| `A2AServer` | Configuration (streaming enabled/disabled) |

### Proposed Interface Changes

```python
class A2AServer:
    def __init__(
        self,
        agent,
        agent_card: Optional[Dict[str, Any]] = None,
        authentication: Optional[Dict[str, Any]] = None,
        push_signing_secret: Optional[str] = None,
        streaming: bool = True,  # NEW: Enable token streaming
    ):
        ...
        self._streaming_enabled = streaming
```

### Event Mapping

| Tyler Event | A2A Event | Notes |
|-------------|-----------|-------|
| `LLM_STREAM_CHUNK` | `TaskArtifactUpdateEvent(append=True)` | Token chunk |
| `LLM_THINKING_CHUNK` | (skip or separate artifact) | Optional |
| `TOOL_SELECTED` | `TaskStatusUpdateEvent(working)` | Status update |
| `EXECUTION_COMPLETE` | `TaskArtifactUpdateEvent(lastChunk=True)` + `TaskStatusUpdateEvent(completed)` | Final events |
| `EXECUTION_ERROR` | `TaskStatusUpdateEvent(failed)` | Error handling |

### Streaming Execute Implementation

```python
async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
    task_id = context.task_id
    context_id = context.context_id
    
    # ... setup thread ...
    
    # Send working status
    await event_queue.enqueue_event(TaskStatusUpdateEvent(
        taskId=task_id,
        status=TaskStatus(state=TaskState.working),
        final=False,
    ))
    
    artifact_id = str(uuid.uuid4())
    content_buffer = []
    
    async for event in self.agent.stream(tyler_thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            chunk = event.data.get("content_chunk", "")
            if chunk:
                content_buffer.append(chunk)
                await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                    taskId=task_id,
                    contextId=context_id or task_id,
                    artifact=A2AArtifact(
                        artifactId=artifact_id,
                        name=f"Task {task_id[:8]} Result",
                        parts=[Part(root=TextPart(text=chunk))],
                    ),
                    append=True,
                    lastChunk=False,
                ))
                
        elif event.type == EventType.TOOL_SELECTED:
            # Optionally emit status update for tool use
            pass
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            # Send final artifact event
            await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                artifact=A2AArtifact(
                    artifactId=artifact_id,
                    name=f"Task {task_id[:8]} Result",
                    parts=[],  # Empty parts for final marker
                ),
                append=False,
                lastChunk=True,
            ))
            
            # Send completion status
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            ))
            
        elif event.type == EventType.EXECUTION_ERROR:
            # Handle error
            await event_queue.enqueue_event(TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[Part(root=TextPart(text=event.data.get("message", "Unknown error")))],
                    ),
                ),
                final=True,
            ))
```

### Error Handling

- **LLM errors**: Emit `TaskStatusUpdateEvent(failed)` with error message
- **Connection drops**: SDK handles SSE cleanup; clients use `tasks/get` for final state
- **Tool errors**: Continue streaming after tool error (Tyler handles gracefully)

### Backward Compatibility

When `streaming=False`:
```python
if not self._streaming_enabled:
    # Use existing non-streaming path
    result = await self.agent.run(tyler_thread)
    # ... emit single artifact as before ...
```

## 5. Alternatives Considered

### Option A: Batch chunks (emit every N tokens or T milliseconds)
- **Pros**: Reduces event frequency, lower overhead
- **Cons**: Adds latency, more complex implementation
- **Decision**: Skip for MVP; add if performance issues arise

### Option B: Stream via separate endpoint
- **Pros**: Clean separation of concerns
- **Cons**: Doesn't leverage A2A protocol's built-in streaming
- **Decision**: Rejected—use protocol-native approach

### Option C: Stream only final content, not tokens
- **Pros**: Simpler implementation
- **Cons**: No real-time feedback; defeats purpose of streaming
- **Decision**: Rejected—token streaming is the goal

**Chosen**: Direct token streaming via `agent.stream()` mapped to A2A events.

## 6. Data Model & Contract Changes

### API Changes

| Change | Type | Backward Compatible |
|--------|------|---------------------|
| `A2AServer(streaming=True)` | New optional parameter | Yes (defaults to True) |
| `TaskArtifactUpdateEvent.append` | Existing A2A field | N/A (protocol-defined) |
| `TaskArtifactUpdateEvent.lastChunk` | Existing A2A field | N/A (protocol-defined) |

### No Database Changes
Feature is stateless; no migrations required.

## 7. Security, Privacy, Compliance

- **No new attack surface**: Same data, different delivery timing
- **No PII changes**: Content flows same as before
- **AuthN/AuthZ**: Unchanged—handled by SDK infrastructure

## 8. Observability & Operations

### Logs to Add

```python
# On streaming start
logger.debug(f"Starting streaming execution for task {task_id}")

# On chunk emission (throttled)
logger.debug(f"Emitted {chunk_count} chunks for task {task_id}")

# On completion
logger.info(f"Completed streaming task {task_id}: {total_chunks} chunks, {total_bytes} bytes")
```

### Metrics (Future)
- `a2a_stream_chunks_total{task_id}` — Chunks emitted per task
- `a2a_stream_latency_ms` — LLM chunk to SSE emission latency

### No New Alerts Required
Existing A2A server health monitoring is sufficient.

## 9. Rollout & Migration

### Feature Flag
```python
A2AServer(agent, streaming=True)  # Default enabled
A2AServer(agent, streaming=False)  # Opt-out
```

### Rollout Plan
1. Deploy with `streaming=True` default
2. Monitor for issues in staging
3. Promote to production
4. No data migration required

### Revert Plan
Set `streaming=False` in server configuration.

## 10. Test Strategy & Spec Coverage (TDD)

### Spec → Test Mapping

| Acceptance Criterion | Test ID |
|---------------------|---------|
| Tokens arrive within 100ms | `test_streaming_latency` |
| Non-streaming clients work | `test_non_streaming_fallback` |
| Streaming disabled config | `test_streaming_disabled_config` |
| Tool calls resume streaming | `test_streaming_with_tool_calls` |
| Error handling | `test_streaming_error_handling` |

### Test Tiers

**Unit Tests** (`tests/a2a/test_streaming.py`):
- `test_streaming_executor_emits_chunks` — Verify chunks emitted for each `LLM_STREAM_CHUNK`
- `test_streaming_executor_final_event` — Verify `lastChunk=True` on completion
- `test_streaming_disabled_uses_run` — Verify fallback to `agent.run()`
- `test_streaming_error_emits_failed_status` — Verify error handling

**Integration Tests**:
- `test_streaming_e2e_with_mock_agent` — Full flow with mocked Tyler agent
- `test_streaming_with_tool_calls` — Multi-iteration streaming

### Negative/Edge Cases
- LLM returns empty response → Emit completion with no chunks
- Connection drops mid-stream → Verify no server crash
- Agent raises exception → Emit failed status

## 11. Risks & Open Questions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| High chunk frequency overwhelms client | Low | Medium | SDK handles backpressure; add batching later if needed |
| Artifact reassembly issues | Low | Low | A2A protocol defines `append` semantics clearly |

### Open Questions
1. **Should we stream thinking tokens?** — Propose: Skip for MVP; add as separate artifact type later
2. **Batching threshold?** — Propose: No batching for MVP; monitor and add if needed

## 12. Milestones / Plan (post-approval)

| Task | DoD | Estimate |
|------|-----|----------|
| Add `streaming` param to `A2AServer` | Tests pass, param works | 15 min |
| Refactor `execute()` to use `agent.stream()` | Chunks emitted, tests pass | 1 hour |
| Handle tool call iterations | Multi-turn streaming works | 30 min |
| Add unit tests | All test IDs implemented, CI green | 1 hour |
| Update docstrings | Docs reflect new behavior | 15 min |

**Total estimate**: ~3 hours

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved.

