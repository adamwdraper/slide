# Technical Design Review (TDR) — A2A Token-Level Streaming

**Author**: Agent  
**Date**: 2024-12-30  
**Updated**: 2024-12-30 — Simplified design (always stream internally)  
**Links**: [Spec](spec.md), [Impact](impact.md)

---

## 1. Summary

This TDR describes the implementation of real-time token streaming for Tyler agents exposed via the A2A protocol. The `TylerAgentExecutor` now uses `agent.stream()` internally for all requests, emitting `TaskArtifactUpdateEvent`s for each token chunk. The A2A SDK's `DefaultRequestHandler` handles delivery based on the client's request type:

- **`message/send`**: SDK aggregates events into a single response
- **`message/stream`**: SDK streams events via SSE in real-time

This follows the pattern documented in the A2A SDK: https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/

Tyler already has robust streaming infrastructure via `agent.stream()` that yields `ExecutionEvent` objects including `LLM_STREAM_CHUNK`. This TDR focuses on wiring that infrastructure into the A2A server's event queue.

## 2. Decision Drivers & Non-Goals

**Drivers:**
- Protocol compliance: A2A spec explicitly supports streaming via SSE
- User experience: Real-time feedback for long-running responses
- Low implementation effort: Tyler streaming already exists
- Simplicity: Single execution path (always stream) vs. dispatch logic

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
| `TylerAgentExecutor` | Always use `agent.stream()`, emit A2A events for each chunk |
| `DefaultRequestHandler` (SDK) | Route requests to executor, handle delivery mode |
| `EventQueue` (SDK) | Buffer events; aggregate for send, stream for SSE |
| `A2AServer` | Create executor and SDK infrastructure |

### Interface (Simplified)

No new configuration needed. The executor always streams internally:

```python
class TylerAgentExecutor(AgentExecutor):
    """Always uses streaming internally. SDK handles delivery mode."""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Always use agent.stream() - SDK handles aggregation for message/send
        async for event in self.agent.stream(tyler_thread):
            if event.type == EventType.LLM_STREAM_CHUNK:
                await event_queue.enqueue_event(TaskArtifactUpdateEvent(...))
```

### Event Mapping

| Tyler Event | A2A Event | Notes |
|-------------|-----------|-------|
| First `LLM_STREAM_CHUNK` | `TaskArtifactUpdateEvent(append=False)` | Creates artifact |
| Subsequent `LLM_STREAM_CHUNK` | `TaskArtifactUpdateEvent(append=True)` | Appends to artifact |
| `LLM_THINKING_CHUNK` | (skip or separate artifact) | Optional |
| `TOOL_SELECTED` | `TaskStatusUpdateEvent(working)` | Status update |
| `EXECUTION_COMPLETE` | `TaskArtifactUpdateEvent(append=True, lastChunk=True)` + `TaskStatusUpdateEvent(completed)` | Final events |
| `EXECUTION_ERROR` | `TaskStatusUpdateEvent(failed)` | Error handling |

**Important**: The first chunk must use `append=False` to create the artifact. The SDK's
`append_artifact_to_task` helper ignores events with `append=True` when no artifact exists.

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
    artifact_initialized = False
    
    async for event in self.agent.stream(tyler_thread):
        if event.type == EventType.LLM_STREAM_CHUNK:
            chunk = event.data.get("content_chunk", "")
            if chunk:
                content_buffer.append(chunk)
                
                # First chunk creates artifact (append=False)
                # Subsequent chunks append (append=True)
                is_first = not artifact_initialized
                if is_first:
                    artifact_initialized = True
                
                await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                    taskId=task_id,
                    contextId=context_id or task_id,
                    artifact=A2AArtifact(
                        artifactId=artifact_id,
                        name=f"Task {task_id[:8]} Result",
                        parts=[Part(root=TextPart(text=chunk))],
                    ),
                    append=not is_first,  # False for first, True for rest
                    lastChunk=False,
                ))
                
        elif event.type == EventType.TOOL_SELECTED:
            # Optionally emit status update for tool use
            pass
            
        elif event.type == EventType.EXECUTION_COMPLETE:
            # Send final artifact event - use append=True if artifact exists
            await event_queue.enqueue_event(TaskArtifactUpdateEvent(
                taskId=task_id,
                contextId=context_id or task_id,
                artifact=A2AArtifact(
                    artifactId=artifact_id,
                    name=f"Task {task_id[:8]} Result",
                    parts=[Part(root=TextPart(text="Task completed."))] if not artifact_initialized else [],
                ),
                append=artifact_initialized,  # True if artifact exists, False to create
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

The A2A SDK handles backward compatibility automatically:
- Clients calling `message/send` receive aggregated responses (no change)
- Clients calling `message/stream` receive real-time SSE events

No configuration flag needed—the executor always streams, SDK handles delivery.

## 5. Alternatives Considered

### Option A: Batch chunks (emit every N tokens or T milliseconds)
- **Pros**: Reduces event frequency, lower overhead
- **Cons**: Adds latency, more complex implementation
- **Decision**: Skip for MVP; add if performance issues arise

### Option B: Separate `execute()` and `stream()` methods in executor
- **Pros**: Explicit separation of streaming vs non-streaming
- **Cons**: A2A SDK routes both request types to `execute()`; would fight the framework
- **Decision**: Rejected—follow SDK design; always stream internally

### Option C: Configuration flag to enable/disable streaming
- **Pros**: Opt-in control
- **Cons**: Unnecessary complexity; SDK handles delivery mode automatically
- **Decision**: Rejected—simplified to always stream

### Option D: Stream only final content, not tokens
- **Pros**: Simpler implementation
- **Cons**: No real-time feedback; defeats purpose of streaming
- **Decision**: Rejected—token streaming is the goal

**Chosen**: Always stream internally via `agent.stream()`, let SDK handle delivery.

## 6. Data Model & Contract Changes

### API Changes

| Change | Type | Backward Compatible |
|--------|------|---------------------|
| `TylerAgentExecutor` now streams internally | Behavioral change | Yes (SDK handles delivery) |
| `TaskArtifactUpdateEvent.append` | Existing A2A field | N/A (protocol-defined) |
| `TaskArtifactUpdateEvent.lastChunk` | Existing A2A field | N/A (protocol-defined) |

**No new parameters added.** The simplified design removes the need for configuration.

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

### No Feature Flag Needed
The simplified design always streams internally. The A2A SDK handles delivery mode:
- `message/send` clients receive aggregated responses (existing behavior)
- `message/stream` clients receive real-time SSE events (new capability)

### Rollout Plan
1. Deploy updated executor
2. Monitor for issues in staging
3. Promote to production
4. No data migration required

### Revert Plan
Revert the code change to use `agent.run()` instead of `agent.stream()`.

## 10. Test Strategy & Spec Coverage (TDD)

### Spec → Test Mapping

| Acceptance Criterion | Test ID |
|---------------------|---------|
| Tokens arrive as generated | `test_streaming_executor_emits_chunks` |
| Executor always uses stream | `test_executor_always_uses_stream` |
| Final event has lastChunk | `test_streaming_executor_final_event_has_last_chunk` |
| Tool calls resume streaming | `test_streaming_with_tool_calls` |
| Error handling | `test_streaming_error_emits_failed_status` |
| Server creates executor | `test_server_creates_executor` |

### Test Tiers

**Unit Tests** (`tests/a2a/test_streaming.py`):
- `test_streaming_executor_emits_chunks` — Verify chunks emitted for each `LLM_STREAM_CHUNK`
- `test_streaming_executor_final_event_has_last_chunk` — Verify `lastChunk=True` on completion
- `test_executor_always_uses_stream` — Verify `agent.stream()` always called, not `run()`
- `test_streaming_with_tool_calls` — Verify streaming across tool call iterations
- `test_streaming_error_emits_failed_status` — Verify error handling
- `test_server_creates_executor` — Verify A2AServer creates TylerAgentExecutor

**Integration Tests** (future):
- `test_streaming_e2e_with_mock_agent` — Full flow with mocked Tyler agent
- `test_message_send_aggregates_response` — Verify SDK aggregation for message/send

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

| Task | DoD | Status |
|------|-----|--------|
| Refactor `execute()` to always use `agent.stream()` | Chunks emitted, tests pass | ✅ Complete |
| Map Tyler events to A2A events | All event types handled | ✅ Complete |
| Handle tool call iterations | Multi-turn streaming works | ✅ Complete |
| Add unit tests | All test IDs implemented, CI green | ✅ Complete (6 tests) |
| Update docstrings | Docs reflect new behavior | ✅ Complete |
| Simplify design (remove config flag) | Single execution path | ✅ Complete |

**Implementation complete**: Simplified design with always-streaming executor.

---

**Approval Gate**: ~~Do not start coding until this TDR is reviewed and approved.~~  
**Implementation Status**: Complete. See `tyler/a2a/server.py` and `tests/a2a/test_streaming.py`.

