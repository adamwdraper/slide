# LiteLLM Reasoning Content & Streaming - Definitive Guide

## Key Finding: LiteLLM Standardizes Reasoning Content ✅

Based on [LiteLLM's official documentation](https://docs.litellm.ai/docs/reasoning_content) and their AI assistant:

### Non-Streaming Mode

LiteLLM **fully standardizes** reasoning content in non-streaming responses:

```python
response = litellm.completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    reasoning_effort="low",
    thinking={"type": "enabled", "budget_tokens": 1024}
)

# Standardized fields available in message:
response.choices[0].message.reasoning_content  # String - ALL providers
response.choices[0].message.thinking_blocks    # List[Dict] - Anthropic only
```

**Supported providers** (requires LiteLLM v1.63.0+):
- Deepseek (`deepseek/`)
- Anthropic API (`anthropic/`)
- Bedrock (Anthropic + Deepseek + GPT-OSS) (`bedrock/`)
- Vertex AI (Anthropic) (`vertexai/`)
- OpenRouter (`openrouter/`)
- XAI (`xai/`)
- Google AI Studio (`google/`)
- Perplexity (`perplexity/`)
- Mistral AI (Magistral models) (`mistral/`)
- Groq (`groq/`)

### Streaming Mode - Critical Question

The documentation shows:

```python
response = completion(
    model="gpt-3.5-turbo", 
    messages=messages, 
    stream=True
)

for chunk in response:
    print(chunk['choices'][0]['delta'])
```

**Question:** Does `delta` contain `reasoning_content` during streaming, or is reasoning only available in the final message?

## Implications for Tyler

### Scenario 1: If `delta.reasoning_content` Exists in Streaming

Tyler should check for standardized field:

```python
async for chunk in streaming_response:
    delta = chunk.choices[0].delta
    
    # Check LiteLLM standardized field
    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={"thinking_chunk": delta.reasoning_content, "thinking_type": "reasoning"}
        )
```

✅ **Simple implementation** - single field to check

### Scenario 2: If Reasoning Only in Final Message (Not in Delta)

Tyler would need to:
1. Accumulate all chunks
2. After streaming completes, check `message.reasoning_content`
3. Either emit as single event OR check provider-specific delta fields

```python
async for chunk in streaming_response:
    delta = chunk.choices[0].delta
    
    # Fall back to provider-specific fields during streaming
    if hasattr(delta, 'thinking'):  # Anthropic
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={"thinking_chunk": delta.thinking, "thinking_type": "thinking"}
        )
    elif hasattr(delta, 'reasoning_content'):  # If available in delta
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            data={"thinking_chunk": delta.reasoning_content, "thinking_type": "reasoning"}
        )

# After streaming completes
if hasattr(final_message, 'reasoning_content'):
    # reasoning_content available here for sure
    pass
```

⚠️ **More complex** - need to handle both delta and final message

## Recommended Tyler Implementation

Based on LiteLLM's design pattern, use a **defensive approach** that handles both cases:

```python
async for chunk in streaming_response:
    if not hasattr(chunk, 'choices') or not chunk.choices:
        continue
    
    delta = chunk.choices[0].delta
    
    # Handle regular content
    if hasattr(delta, 'content') and delta.content is not None:
        current_content.append(delta.content)
        yield ExecutionEvent(
            type=EventType.LLM_STREAM_CHUNK,
            timestamp=datetime.now(UTC),
            data={"content_chunk": delta.content}
        )
    
    # Handle thinking/reasoning - check multiple fields defensively
    thinking_content = None
    thinking_type = None
    
    # Priority 1: LiteLLM standardized field (v1.63.0+)
    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
        thinking_content = delta.reasoning_content
        thinking_type = "reasoning"
    
    # Priority 2: Provider-specific fields (fallback)
    elif hasattr(delta, 'thinking') and delta.thinking is not None:
        thinking_content = delta.thinking
        thinking_type = "thinking"
    
    elif hasattr(delta, 'extended_thinking') and delta.extended_thinking is not None:
        thinking_content = delta.extended_thinking
        thinking_type = "extended_thinking"
    
    # Emit thinking event if found
    if thinking_content:
        yield ExecutionEvent(
            type=EventType.LLM_THINKING_CHUNK,
            timestamp=datetime.now(UTC),
            data={
                "thinking_chunk": thinking_content,
                "thinking_type": thinking_type
            }
        )

# After streaming completes - check final message
if hasattr(final_message, 'reasoning_content') and final_message.reasoning_content:
    # Store in Message object for non-streaming compatibility
    metrics["reasoning_content"] = final_message.reasoning_content

if hasattr(final_message, 'thinking_blocks') and final_message.thinking_blocks:
    # Store structured thinking blocks (Anthropic)
    metrics["thinking_blocks"] = final_message.thinking_blocks
```

## Testing Strategy

To determine the actual behavior, Tyler should test with real streaming responses:

### Test 1: Anthropic Claude with Streaming
```python
import litellm
litellm._turn_on_debug()

response = litellm.completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    reasoning_effort="low",
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    print(f"Delta fields: {dir(delta)}")
    if hasattr(delta, 'reasoning_content'):
        print(f"FOUND: delta.reasoning_content = {delta.reasoning_content}")
    if hasattr(delta, 'thinking'):
        print(f"FOUND: delta.thinking = {delta.thinking}")
```

### Test 2: Deepseek with Streaming
```python
response = litellm.completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "What is 2+2?"}],
    reasoning_effort="low",
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    if hasattr(delta, 'reasoning_content'):
        print(f"Deepseek: delta.reasoning_content = {delta.reasoning_content}")
```

## Example Response Structure

According to LiteLLM docs, the response structure is:

```json
{
  "message": {
    "content": "The answer is 42",
    "reasoning_content": "Let me think step by step...",
    "thinking_blocks": [
      {
        "type": "thinking",
        "thinking": "Let me think step by step...",
        "signature": "EqoBCkgIARABGAIiQL2UoU0b1OHYi+..."
      }
    ]
  }
}
```

**In streaming:**
- `delta.content` appears chunk by chunk ✅ (confirmed)
- `delta.reasoning_content` - **needs verification** 🔍
- `delta.thinking` - **provider-specific, needs verification** 🔍

## Tool Calls + Reasoning

LiteLLM supports combining tool calls with reasoning:

```python
response = litellm.completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    messages=messages,
    tools=tools,
    tool_choice="auto",
    reasoning_effort="low",  # Enable reasoning
    stream=True
)

# Chunks will contain both tool_calls and reasoning content
for chunk in response:
    delta = chunk.choices[0].delta
    
    # Tool calls
    if hasattr(delta, 'tool_calls'):
        # Process tool calls
        pass
    
    # Reasoning (if available in delta)
    if hasattr(delta, 'reasoning_content'):
        # Process reasoning
        pass
```

This is exactly what Tyler needs for agentic workflows!

## Recommended Next Steps

1. **Quick Test** (30 minutes):
   - Write a simple test script to check if `delta.reasoning_content` exists in streaming
   - Test with Anthropic and Deepseek models
   - Document findings

2. **Implementation** (based on test results):
   - If `delta.reasoning_content` works: Use standardized field ✅
   - If not: Fall back to provider-specific fields + final message

3. **Tyler Integration**:
   - Add `EventType.LLM_THINKING_CHUNK`
   - Update `_go_stream` to check reasoning fields
   - Add `reasoning_content` and `thinking_blocks` to Message metrics

## Comparison Summary

| Feature | LiteLLM Standardization | Tyler Current | Tyler Needs |
|---------|------------------------|---------------|-------------|
| **Non-streaming reasoning** | ✅ `reasoning_content` | ❌ Not captured | Add to Message |
| **Streaming reasoning** | 🔍 Need to verify | ❌ Not captured | Test & implement |
| **Thinking blocks** | ✅ `thinking_blocks` (Anthropic) | ❌ Not captured | Add to Message |
| **Tool calls** | ✅ Standardized | ✅ Works great | Keep as-is |
| **Content streaming** | ✅ Standardized | ✅ Works great | Keep as-is |

## Conclusion

**Good news:** LiteLLM does standardize reasoning content across providers! ✅

**Action required:** 
1. Test streaming behavior to confirm if `delta.reasoning_content` exists
2. Implement defensive approach that handles both standardized and provider-specific fields
3. Capture `reasoning_content` and `thinking_blocks` in Tyler's Message object

**Estimated effort:** 
- Testing: 30 minutes
- Implementation: 1-2 days (if streaming works as expected)
- Edge cases: +1 day (if need to handle provider-specific fields)

**Total: 2-3 days for full thinking token support** 🎯

