# Tyler Streaming API - Quick Comparison

## Architecture Comparison

### OpenAI Agents SDK
```
Runner.run_streamed()
    └── result.stream_events()
        ├── RawResponsesStreamEvent
        │   ├── response.created
        │   ├── response.output_text.delta
        │   └── response.output_text.done
        ├── RunItemStreamEvent
        │   ├── tool_call_item
        │   ├── tool_call_output_item
        │   └── message_output_item
        └── AgentUpdatedStreamEvent
```

### Tyler (Current)
```
agent.go(thread, stream="events")
    └── ExecutionEvent
        ├── LLM_REQUEST
        ├── LLM_STREAM_CHUNK ← content only
        ├── LLM_RESPONSE
        ├── TOOL_SELECTED
        ├── TOOL_RESULT
        ├── MESSAGE_CREATED
        └── EXECUTION_COMPLETE

agent.go(thread, stream="raw")
    └── Raw LiteLLM chunks
        └── Passes through all fields (including thinking)
```

### Tyler (Recommended)
```
agent.go(thread, stream="events")
    └── ExecutionEvent
        ├── LLM_REQUEST
        ├── LLM_STREAM_CHUNK ← content
        ├── LLM_THINKING_CHUNK ← NEW: reasoning/thinking
        ├── LLM_FINISH ← NEW: finish_reason
        ├── LLM_RESPONSE
        ├── TOOL_SELECTED
        ├── TOOL_RESULT
        ├── MESSAGE_CREATED
        ├── AGENT_UPDATED ← NEW: handoffs
        └── EXECUTION_COMPLETE

agent.go(thread, stream="raw")
    └── Raw LiteLLM chunks (unchanged)
        └── All provider-specific fields preserved
```

---

## What's Missing: Visual Guide

### Current Flow (Tyler)
```
User Message
    ↓
[LLM_REQUEST event]
    ↓
Model generates: "Let me think... 🤔 The answer is 42"
                  ↑ thinking ↑    ↑ content ↑
    ↓
[LLM_STREAM_CHUNK: "Let me think..."]  ← MIXED! 
[LLM_STREAM_CHUNK: "The answer is 42"] ← No distinction
    ↓
[LLM_RESPONSE: complete]
```

### Recommended Flow (Tyler + Thinking)
```
User Message
    ↓
[LLM_REQUEST event]
    ↓
Model generates: "Let me think... 🤔 The answer is 42"
                  ↑ thinking ↑    ↑ content ↑
    ↓
[LLM_THINKING_CHUNK: "Let me think..."] ← Separated!
[LLM_STREAM_CHUNK: "The answer is 42"]  ← Clean content
    ↓
[LLM_FINISH: "stop"]                    ← NEW
    ↓
[LLM_RESPONSE: complete]
```

### OpenAI Agents SDK Flow
```
User Message
    ↓
[raw_response_event: response.created]
    ↓
[raw_response_event: response.output_text.delta] ← Token-by-token
[raw_response_event: response.output_text.delta]
[raw_response_event: response.output_text.delta]
    ↓
[raw_response_event: response.output_text.done]
    ↓
[run_item_stream_event: message_output_item] ← Higher-level
```

---

## Delta Fields: What Tyler Handles

### Currently Handled ✅
```javascript
{
  choices: [{
    delta: {
      content: "text",           ✅ → LLM_STREAM_CHUNK
      tool_calls: [{...}],       ✅ → TOOL_SELECTED
      role: "assistant"          ✅ (internal)
    },
    finish_reason: "stop"        ✅ (tracked but not evented)
  }],
  usage: {                       ✅ (final chunk only)
    total_tokens: 100
  }
}
```

### NOT Handled ❌
```javascript
{
  choices: [{
    delta: {
      thinking: "reasoning...",           ❌ → Should be LLM_THINKING_CHUNK
      reasoning_content: "step by step", ❌ → Should be LLM_THINKING_CHUNK
      extended_thinking: "deep think",    ❌ → Should be LLM_THINKING_CHUNK
    }
  }],
  thinking_blocks: [{                     ❌ → Should be structured events
    type: "planning",
    content: "..."
  }]
}
```

---

## Provider-Specific Thinking Fields

### Anthropic Claude
```python
# Current: Lost in event mode, passed in raw mode
# Recommended: Explicit event

for chunk in stream:
    if chunk.choices[0].delta.thinking:
        # Event mode:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={
                "thinking_chunk": chunk.choices[0].delta.thinking,
                "thinking_type": "thinking"
            }
        )
```

**Example:**
```json
{
  "choices": [{
    "delta": {
      "thinking": "Let me break this down: First, I need to..."
    }
  }]
}
```

### OpenAI o1
```python
# Current: Lost in event mode, passed in raw mode
# Recommended: Explicit event

for chunk in stream:
    if chunk.choices[0].delta.reasoning_content:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={
                "thinking_chunk": chunk.choices[0].delta.reasoning_content,
                "thinking_type": "reasoning"
            }
        )
```

**Example:**
```json
{
  "choices": [{
    "delta": {
      "reasoning_content": "Step 1: Analyze the input. Step 2: ..."
    }
  }]
}
```

### Extended Thinking (Various Providers)
```python
# Current: Not accessible
# Recommended: Pass in Agent init, emit events

agent = Agent(
    name="deep-thinker",
    model_name="claude-3-7-sonnet-20250219",
    stream_options={"extended_thinking": True}  # NEW
)

# Then in stream:
for chunk in stream:
    if chunk.choices[0].delta.extended_thinking:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={
                "thinking_chunk": chunk.choices[0].delta.extended_thinking,
                "thinking_type": "extended_thinking"
            }
        )
```

---

## Tool Usage: Tyler is Good! ✅

Tyler already handles tool usage well in streaming:

```python
async for event in agent.go(thread, stream=True):
    if event.type == EventType.TOOL_SELECTED:
        # Tyler emits this ✅
        print(f"Tool: {event.data['tool_name']}")
        print(f"Args: {event.data['arguments']}")
        print(f"ID: {event.data['tool_call_id']}")
    
    elif event.type == EventType.TOOL_RESULT:
        # Tyler emits this ✅
        print(f"Result: {event.data['result']}")
        print(f"Duration: {event.data['duration_ms']}ms")
```

**OpenAI Agents SDK equivalent:**
```python
async for event in result.stream_events():
    if event.type == "run_item_stream_event":
        if event.item.type == "tool_call_item":
            print(f"Tool: {event.item.name}")
        elif event.item.type == "tool_call_output_item":
            print(f"Output: {event.item.output}")
```

Tyler's approach is actually more granular and developer-friendly! ✅

---

## Usage Information

### Current (Tyler)
```python
# Only available at the end in LLM_RESPONSE event
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_RESPONSE:
        tokens = event.data['tokens']  # ← At the end only
        print(f"Used {tokens['total_tokens']} tokens")
```

### Recommended (Tyler + stream_options)
```python
agent = Agent(
    name="test",
    model_name="gpt-4o",
    stream_options={"include_usage": True}  # NEW
)

async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_RESPONSE:
        tokens = event.data['tokens']  # ← Earlier in stream!
        print(f"Used {tokens['total_tokens']} tokens")
```

### LiteLLM Standard
```python
response = completion(
    model="gpt-4",
    messages=messages,
    stream=True,
    stream_options={"include_usage": True}
)

for chunk in response:
    # Usage arrives before [DONE] message
    if hasattr(chunk, 'usage'):
        print(f"Tokens: {chunk.usage.total_tokens}")
```

---

## Side-by-Side: Real Example

### User Query
```
"What is 123 * 456? Show your thinking."
```

### OpenAI o1 Response
```
[reasoning_content]: "Let me calculate this step by step.
                     123 * 456 = 123 * (400 + 50 + 6)
                     = 123 * 400 + 123 * 50 + 123 * 6
                     = 49,200 + 6,150 + 738
                     = 56,088"

[content]: "The answer is 56,088."
```

### Tyler Current (Event Mode)
```python
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_STREAM_CHUNK:
        # Prints: "Let me calculate this step by step. ..."
        #         "The answer is 56,088."
        # ❌ No distinction between reasoning and answer!
        print(event.data['content_chunk'], end="")
```

**Output:**
```
Let me calculate this step by step. 123 * 456 = ...The answer is 56,088.
```

### Tyler Recommended (Event Mode)
```python
async for event in agent.go(thread, stream=True):
    if event.type == EventType.LLM_THINKING_CHUNK:
        # Reasoning content
        print(f"[💭 {event.data['thinking_chunk']}]", end="")
    
    elif event.type == EventType.LLM_STREAM_CHUNK:
        # Regular content
        print(event.data['content_chunk'], end="")
```

**Output:**
```
[💭 Let me calculate this step by step. 123 * 456 = ...]
The answer is 56,088.
```

### Tyler Current (Raw Mode)
```python
async for chunk in agent.go(thread, stream="raw"):
    delta = chunk.choices[0].delta
    
    # This technically works but is undocumented
    if hasattr(delta, 'reasoning_content'):
        print(f"[Reasoning: {delta.reasoning_content}]")
    
    if hasattr(delta, 'content'):
        print(delta.content, end="")
```

**Output:**
```
[Reasoning: Let me calculate this step by step. 123 * 456 = ...]
The answer is 56,088.
```

✅ Raw mode actually preserves everything, just undocumented!

---

## Summary Table

| Feature | Tyler Current | Tyler Needs | Standard |
|---------|---------------|-------------|----------|
| **Content Streaming** | ✅ Yes | ✅ Keep | Both |
| **Thinking Tokens** | ❌ No (event) / 🟡 Yes (raw, undoc) | ✅ Add event type | Both |
| **Tool Tracking** | ✅ Yes (excellent) | ✅ Keep | Both |
| **Finish Reasons** | 🟡 Tracked, not evented | ✅ Add event | OpenAI SDK |
| **Agent Changes** | ❌ No | ✅ Add event | OpenAI SDK |
| **Usage in Stream** | 🟡 Final chunk only | ✅ Add stream_options | LiteLLM |
| **Provider Support** | ✅ Yes (via LiteLLM) | ✅ Keep | LiteLLM |
| **Event Hierarchy** | ❌ Flat | 🟡 Optional categories | OpenAI SDK |

---

## Code Changes Needed

### 1. Add Event Type (tyler/models/execution.py)
```python
class EventType(Enum):
    # ... existing ...
    LLM_THINKING_CHUNK = "llm_thinking_chunk"  # NEW
    LLM_FINISH = "llm_finish"                  # NEW
    AGENT_UPDATED = "agent_updated"            # NEW
```

### 2. Add Agent Parameter (tyler/models/agent.py)
```python
class Agent(Model):
    # ... existing fields ...
    stream_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Options for streaming responses"
    )
```

### 3. Emit Thinking Events (tyler/models/agent.py - _go_stream)
```python
async for chunk in streaming_response:
    delta = chunk.choices[0].delta
    
    # Existing content handling
    if hasattr(delta, 'content') and delta.content:
        yield ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(UTC),
            data={"content_chunk": delta.content}
        )
    
    # NEW: Thinking handling
    thinking = None
    thinking_type = None
    
    if hasattr(delta, 'thinking'):
        thinking = delta.thinking
        thinking_type = "thinking"
    elif hasattr(delta, 'reasoning_content'):
        thinking = delta.reasoning_content
        thinking_type = "reasoning"
    
    if thinking:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(UTC),
            data={
                "thinking_chunk": thinking,
                "thinking_type": thinking_type
            }
        )
```

### 4. Update Documentation
- Add thinking token examples
- Document raw mode preserves all fields
- Add examples for o1 and Claude
- Update streaming guide

---

## Quick Win: Document Raw Mode

Tyler's raw mode already works with thinking tokens! Just need to:

1. **Document it**
```markdown
### Raw Streaming with Thinking Tokens

Tyler's raw streaming mode preserves ALL fields from LiteLLM:

```python
async for chunk in agent.go(thread, stream="raw"):
    delta = chunk.choices[0].delta
    
    # Anthropic thinking
    if hasattr(delta, 'thinking'):
        print(f"[Thinking: {delta.thinking}]")
    
    # OpenAI o1 reasoning
    if hasattr(delta, 'reasoning_content'):
        print(f"[Reasoning: {delta.reasoning_content}]")
    
    # Regular content
    if hasattr(delta, 'content'):
        print(delta.content, end="")
```
```

2. **Add example**
```python
# examples/006_thinking_tokens.py
```

3. **Add test**
```python
# tests/models/test_thinking_tokens.py
```

This gives users a workaround TODAY while full event support is added!

---

## Conclusion

**Tyler is close to standard compliance!** Key gaps:

1. ❌ **Thinking tokens in event mode** (works in raw mode, undocumented)
2. ❌ **stream_options parameter**
3. ❌ **Finish reason events**
4. ❌ **Agent state change events**

**Recommendation:** Implement in phases:
- **Phase 1:** Add thinking events + document raw mode (2-3 days)
- **Phase 2:** Add stream_options + finish events (2-3 days)
- **Phase 3:** Add agent events + polish (3-5 days)

**Total effort:** ~1-2 weeks for full compliance

