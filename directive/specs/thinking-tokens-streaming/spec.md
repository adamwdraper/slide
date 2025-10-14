# Spec: Thinking Tokens in Streaming

**Feature name**: Thinking Tokens Support in Tyler Streaming API  
**One-line summary**: Enable developers to see model reasoning/thinking process in real-time during streaming responses.

---

## Problem

Models like OpenAI o1 and Anthropic Claude emit their reasoning process as separate "thinking tokens" alongside the actual response content. Tyler's streaming API currently mixes thinking and response content together in `LLM_STREAM_CHUNK` events, making it impossible for developers to:

1. **Distinguish reasoning from response** - Can't separate "Let me think..." from the actual answer
2. **Display thinking differently** - Can't show reasoning in a different UI element (e.g., collapsible section)
3. **Build transparent AI apps** - Users can't see how the AI arrived at decisions
4. **Debug agent behavior** - Developers can't trace the model's reasoning process
5. **Optimize costs** - Can't distinguish between reasoning tokens and output tokens for billing

**Why now?**
- OpenAI o1 and Anthropic Claude 3.7 Sonnet (with extended thinking) are production-ready
- LiteLLM v1.63.0+ standardizes reasoning content across providers
- Developers are requesting thinking token visibility for transparency and debugging

## Goal

Tyler's streaming API should expose thinking/reasoning tokens as separate events from content tokens, leveraging LiteLLM's standardized `reasoning_content` field.

## Success Criteria

- [ ] Developers can distinguish thinking tokens from response tokens in event streaming mode
- [ ] Raw streaming mode preserves all reasoning fields from LiteLLM unchanged
- [ ] Works across all LiteLLM-supported providers (Anthropic, Deepseek, OpenAI o1, etc.)
- [ ] Zero breaking changes to existing streaming code
- [ ] Thinking tokens are captured in Message objects for later analysis

## User Story

**As a** Tyler developer building an AI application  
**I want** to receive thinking/reasoning tokens separately from response content during streaming  
**So that** I can display the model's reasoning process to end users and debug agent decisions

## Flow / States

### Happy Path: Event Streaming with Thinking Tokens

1. Developer creates agent with reasoning-capable model (e.g., `claude-3-7-sonnet-20250219`)
2. Developer calls `agent.go(thread, stream=True)` to start streaming
3. Tyler yields `ExecutionEvent` objects:
   - `LLM_REQUEST` - Request sent
   - `LLM_THINKING_CHUNK` - **NEW** - Reasoning tokens as they arrive
   - `LLM_STREAM_CHUNK` - Regular content tokens as they arrive
   - `LLM_RESPONSE` - Complete response with both content and reasoning
   - `MESSAGE_CREATED` - Message added to thread with reasoning metadata
   - `EXECUTION_COMPLETE` - Done
4. Developer displays thinking in collapsible UI, content in main chat
5. Both thinking and content are preserved in thread history

### Edge Case: Model Without Thinking Support

1. Developer uses model without thinking support (e.g., `gpt-4o`)
2. Tyler yields normal events (no `LLM_THINKING_CHUNK` events)
3. Everything works as before - backward compatible

### Edge Case: Raw Streaming Mode

1. Developer uses `stream="raw"` for OpenAI compatibility
2. Tyler passes through raw chunks unchanged (including `reasoning_content` if present)
3. Developer handles reasoning fields manually
4. Tool execution still happens (agentic behavior preserved)

## UX Links

- Analysis docs: `/directive/specs/streaming-analysis.md`
- Comparison: `/directive/specs/streaming-comparison.md`
- Quick reference: `/directive/specs/streaming-quick-reference.md`
- LiteLLM clarification: `/directive/specs/streaming-litellm-clarification.md`
- LiteLLM docs: https://docs.litellm.ai/docs/reasoning_content

## Requirements

### Must
- Add new `EventType.LLM_THINKING_CHUNK` event type
- Emit thinking chunk events during `_go_stream` when reasoning content is detected
- Check for LiteLLM's standardized `reasoning_content` field in delta
- Fall back to provider-specific fields (`thinking`, `extended_thinking`) if needed
- Preserve `reasoning_content` and `thinking_blocks` in Message object after streaming
- Display thinking tokens in Tyler CLI (`tyler chat`) when present
- Show thinking in a visually distinct way from regular content in CLI
- Maintain full backward compatibility - existing code must work unchanged
- Work with all LiteLLM-supported reasoning providers
- Document thinking token support in streaming guide

### Must Not
- Break existing streaming code
- Change the format of existing event types
- Require developers to update their code to handle thinking tokens
- Lose thinking tokens - they must be captured somewhere (events + Message)
- Change raw streaming behavior (except passing through new fields)

## Acceptance Criteria

### AC1: Event Streaming Emits Thinking Chunks
**Given** an agent using a reasoning-capable model (e.g., Anthropic Claude)  
**When** the developer streams a response with `agent.go(thread, stream=True)`  
**Then** the stream yields `LLM_THINKING_CHUNK` events with reasoning content  
**And** the stream yields `LLM_STREAM_CHUNK` events with regular content  
**And** thinking and content are clearly separated

### AC2: Thinking Stored in Message Object
**Given** streaming completes with thinking tokens  
**When** the assistant Message is created  
**Then** the Message contains `reasoning_content` in its metadata/metrics  
**And** the Message contains `thinking_blocks` if available (Anthropic)  
**And** this data is persisted to thread storage

### AC3: Backward Compatibility
**Given** existing Tyler code that handles streaming  
**When** the developer runs the same code after this update  
**Then** all existing events still work identically  
**And** no errors occur from new event types (they're simply ignored if not handled)  
**And** existing tests pass without modification

### AC4: Raw Streaming Passes Through Reasoning
**Given** an agent in raw streaming mode (`stream="raw"`)  
**When** the model emits reasoning tokens  
**Then** the raw chunks contain `reasoning_content` or provider-specific fields  
**And** no transformation or standardization happens beyond LiteLLM's  
**And** developers can access reasoning fields directly from chunks

### AC5: Non-Reasoning Models Work Unchanged
**Given** an agent using a non-reasoning model (e.g., GPT-4)  
**When** streaming a response  
**Then** no `LLM_THINKING_CHUNK` events are emitted  
**And** regular `LLM_STREAM_CHUNK` events work as before  
**And** no errors or warnings occur

### AC6: Tool Calls + Thinking Work Together
**Given** an agent with tools and reasoning enabled  
**When** the model uses thinking and calls tools  
**Then** both thinking events and tool events are emitted  
**And** the sequence is: thinking → tool_selected → tool_result → thinking → response  
**And** both reasoning and tool results are preserved in messages

### AC7: CLI Displays Thinking Tokens
**Given** a user runs `tyler chat` with a reasoning-capable model  
**When** the agent emits thinking tokens during streaming  
**Then** the CLI displays thinking in a visually distinct panel or format  
**And** thinking is shown separately from the response content  
**And** the user can see the model's reasoning process in real-time

### Negative Case: Malformed Reasoning Content
**Given** LiteLLM returns malformed reasoning data  
**When** Tyler processes the chunks  
**Then** Tyler gracefully skips the malformed thinking  
**And** regular content streaming continues normally  
**And** an error is logged but execution continues

## Non-Goals

**Not in scope for this PR:**
- UI components for displaying thinking tokens
- Agent-to-agent handoff events (separate feature)
- Finish reason events (separate feature)
- `stream_options` parameter support (separate feature)
- Event categorization/hierarchy (separate feature)
- Structured thinking block parsing beyond what LiteLLM provides
- Custom thinking token formatting or transformation
- Thinking token cost tracking or analytics
- Compatibility with LiteLLM versions < 1.63.0
- Support for providers not listed in LiteLLM docs

