# Final Design - Raw Streaming Mode

**Status**: ✅ Complete and Production Ready  
**Date**: 2025-10-12  
**PR**: #63

## Key Design Decision: Raw Mode is Fully Agentic

After researching [OpenAI's Agents SDK streaming pattern](https://openai.github.io/openai-agents-python/streaming/), we made a critical design decision:

**Raw mode executes tools and iterates like a full agent, not just a dumb proxy.**

## The Pattern (Matches OpenAI)

```
┌─────────────────────────────────────────────────┐
│ Frontend calls: agent.go(thread, stream="raw") │
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Iteration 1: LLM Call                           │
│ ├─ yield chunk: {"delta": {"content": "Let"}}  │
│ ├─ yield chunk: {"delta": {"content": " me"}}  │
│ ├─ yield chunk: {"delta": {"tool_calls": ...}} │
│ └─ yield chunk: {"finish_reason": "tool_calls"}│
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ SILENT: Tyler executes tools                    │
│ - Parse tool calls from accumulated chunks      │
│ - Execute tools in parallel                     │
│ - Add tool result messages to thread            │
│ - NO chunks yielded during this phase           │
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ Iteration 2: LLM Call (with tool results)       │
│ ├─ yield chunk: {"delta": {"content": "Based"}}│
│ ├─ yield chunk: {"delta": {"content": " on"}}  │
│ └─ yield chunk: {"finish_reason": "stop"}      │
└─────────────────────────────────────────────────┘
                     │
                     ▼
                  COMPLETE
```

## Why This Design is Better

### ❌ Original Design (Pass-Through Only)
```python
async for chunk in agent.go(thread, stream="raw"):
    # Only chunks from first LLM call
    # Tools NOT executed
    # Agent NOT agentic
    # Useless for real applications!
```

**Problems:**
- Can't complete multi-step tasks
- Not actually an "agent"
- Frontend would have to execute tools itself
- Defeats the purpose of Tyler

### ✅ Final Design (Fully Agentic)
```python
async for chunk in agent.go(thread, stream="raw"):
    # Chunks from ALL LLM iterations
    # Tools executed silently between chunk streams
    # finish_reason tells frontend what's happening
    # Fully agentic behavior!
```

**Benefits:**
- Multi-step reasoning works ✅
- Tools executed automatically ✅
- Frontend gets OpenAI-compatible chunks ✅
- Still fully agentic ✅
- Matches OpenAI's pattern ✅

## Frontend Integration Example

```python
# FastAPI endpoint for OpenAI-compatible streaming
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/v1/chat/completions")
async def openai_compatible_chat(messages: list):
    thread = Thread()
    for msg in messages:
        thread.add_message(Message(role=msg["role"], content=msg["content"]))
    
    async def generate():
        async for chunk in agent.go(thread, stream="raw"):
            # chunk has OpenAI format with finish_reason
            chunk_dict = {
                "id": chunk.id,
                "object": chunk.object,
                "created": chunk.created,
                "model": chunk.model,
                "choices": [{
                    "index": 0,
                    "delta": chunk.choices[0].delta,  
                    "finish_reason": chunk.choices[0].finish_reason  # Tells client about tool calls!
                }]
            }
            
            if hasattr(chunk, 'usage') and chunk.usage:
                chunk_dict["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
            
            yield f"data: {json.dumps(chunk_dict)}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Frontend Experience:**
```
data: {"id": "...", "choices": [{"delta": {"content": "Let me search"}, "finish_reason": null}]}
data: {"id": "...", "choices": [{"delta": {"tool_calls": [...]}, "finish_reason": "tool_calls"}]}

[Brief pause - Tyler executing web_search tool]

data: {"id": "...", "choices": [{"delta": {"content": "Based on"}, "finish_reason": null}]}
data: {"id": "...", "choices": [{"delta": {"content": " the results"}, "finish_reason": null}]}
data: {"id": "...", "choices": [{"delta": {}, "finish_reason": "stop"}]}
data: [DONE]
```

## What the Frontend Sees

### Indicators of Agent Activity

1. **Content Generation**: `finish_reason: null` + content delta
2. **Tool Execution Starting**: `finish_reason: "tool_calls"` + tool_calls delta
3. **Silent Gap**: Agent executing tools (expected pause)
4. **Resuming**: New chunks with content delta
5. **Completion**: `finish_reason: "stop"`

The frontend can show UI like:
- "🤖 Typing..." during content chunks
- "🔧 Using tools..." when finish_reason is "tool_calls"
- "✅ Complete!" when finish_reason is "stop"

## Comparison: Raw vs Events Mode

| Feature | Event Mode (`stream=True`) | Raw Mode (`stream="raw"`) |
|---------|---------------------------|--------------------------|
| Output Format | ExecutionEvent objects | Raw LiteLLM chunks |
| Tool Execution | ✅ Yes, with TOOL_SELECTED events | ✅ Yes, silently |
| Iterations | ✅ Yes, with ITERATION_START events | ✅ Yes, silently |
| Observability | ✅ Rich telemetry | ⚠️ Only via chunk finish_reason |
| OpenAI Compatible | ❌ No | ✅ Yes |
| Use Case | Internal apps, debugging | OpenAI-compatible frontends |

## Implementation Highlights

### Iteration Loop
```python
while self._iteration_count < self.max_tool_iterations:
    # 1. Get streaming response
    streaming_response, metrics = await self.step(thread, stream=True)
    
    # 2. Yield ALL raw chunks (including tool call deltas)
    current_tool_calls = []
    async for chunk in streaming_response:
        yield chunk  # Pass through unmodified!
        # Track tool calls for execution
        if delta.tool_calls:
            current_tool_calls.append(...)
    
    # 3. Create assistant message
    assistant_message = Message(
        content=content,
        tool_calls=current_tool_calls
    )
    thread.add_message(assistant_message)
    
    # 4. If no tool calls, done!
    if not current_tool_calls:
        break
    
    # 5. Execute tools (SILENTLY - no chunks yielded)
    tool_results = await asyncio.gather(*tool_tasks)
    for result in tool_results:
        tool_message = create_tool_message(result)
        thread.add_message(tool_message)
    
    # 6. Loop back for next LLM call
    self._iteration_count += 1
```

### Error Handling
- API errors detected and raised properly
- Thread/metrics type checking
- Graceful degradation in examples
- Matches behavior of event streaming mode

## Testing

All tests verify the agentic behavior:

| Test | What it Validates |
|------|------------------|
| `test_raw_mode_yields_chunks_with_openai_fields` | Chunk structure matches OpenAI format |
| `test_raw_mode_includes_usage_in_final_chunk` | Usage metrics passed through |
| `test_raw_mode_tool_call_deltas` | Tool calls in chunks (will be executed) |
| `test_stream_events_explicit` | Explicit `stream="events"` works |
| `test_stream_true_backward_compatibility` | Existing code unchanged |
| `test_invalid_stream_value_raises_error` | Parameter validation |

**Example test** (`005_raw_streaming.py`) demonstrates:
- Raw streaming with SSE serialization
- Mode comparison (raw vs events produce same content)
- Graceful error handling

## Documentation Updates

1. **API Reference** (`tyler-agent.mdx`)
   - Updated warnings: "Tools ARE executed"
   - Added finish_reason explanation
   - Links to OpenAI Agents SDK

2. **Streaming Guide** (`streaming-responses.mdx`)
   - New streaming modes table
   - Raw streaming section with examples
   - SSE serialization helper
   - FastAPI endpoint example

3. **Spec Package**
   - Updated with tool execution notes
   - References OpenAI pattern
   - Design rationale documented

## Conclusion

**Raw streaming mode is now a first-class agentic mode**, not just a pass-through proxy. It enables building OpenAI-compatible frontends while leveraging Tyler's full agent capabilities (tool execution, iteration, state management).

This aligns with OpenAI's Agents SDK design and provides the best of both worlds:
- ✅ OpenAI-compatible chunk format
- ✅ Full Tyler agent capabilities
- ✅ Simple, intuitive API

Perfect for building agentic applications with OpenAI-compatible UIs! 🚀

