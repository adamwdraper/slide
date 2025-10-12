# Spec (per PR)

**Feature name**: Raw Streaming Mode for OpenAI Compatibility  
**One-line summary**: Add `stream="raw"` mode to expose raw LiteLLM SSE chunks in OpenAI-compatible format for direct integration with OpenAI-compatible clients.

---

## Problem
Currently, Tyler's streaming API transforms LiteLLM streaming chunks into Tyler-specific `ExecutionEvent` objects. While this provides a rich observability model, developers building OpenAI-compatible applications or integrations need access to the raw OpenAI SSE (Server-Sent Events) chunk format that LiteLLM provides. This is particularly important for:

1. Building drop-in replacements for OpenAI API endpoints
2. Integrating with existing OpenAI-compatible streaming clients
3. Building proxy or gateway services that need to pass through raw chunks
4. Debugging and comparing behavior with OpenAI's API directly

## Goal
Tyler agents should support a `stream="raw"` mode that exposes raw LiteLLM streaming chunks in OpenAI-compatible SSE format while maintaining backward compatibility with the existing ExecutionEvent streaming model (`stream=True` or `stream="events"`).

## Success Criteria
- [ ] Developers can receive raw OpenAI-compatible streaming chunks from Tyler agents
- [ ] The raw chunk format matches OpenAI's SSE format (can be consumed by OpenAI SDKs)
- [ ] Existing streaming behavior remains unchanged (backward compatible)
- [ ] Documentation shows how to use both streaming modes
- [ ] Performance overhead is minimal (raw chunks should be fast)

## User Story
As a developer building an OpenAI-compatible agent service, I want to use `stream="raw"` to receive raw SSE chunks from Tyler agents, so that I can pass them directly to OpenAI-compatible clients without transformation overhead.

## Flow / States

### Happy Path
1. Developer calls `agent.go(thread, stream="raw")`
2. Agent yields raw LiteLLM chunk objects directly from the LLM provider
3. Developer serializes chunks to SSE format for their client
4. Client receives OpenAI-compatible stream

### Edge Case - Backward Compatibility
1. Developer calls `agent.go(thread, stream=True)` (existing code)
2. Agent interprets `stream=True` as `stream="events"` for backward compatibility
3. Agent yields `ExecutionEvent` objects as before
4. Existing code continues to work unchanged

## UX Links
- Designs: N/A (API-only feature)
- Prototype: N/A
- Copy/Content: Will need documentation examples showing:
  - How to use `stream="raw"` vs `stream="events"` (or `stream=True`)
  - How to format raw chunks as SSE
  - Side-by-side comparison of both streaming modes

## Requirements
- Must accept `stream` parameter with values: `False` (default), `True`, `"events"`, `"raw"`
- Must expose raw LiteLLM chunks when `stream="raw"`
- Must yield ExecutionEvents when `stream=True` or `stream="events"`
- Must treat `stream=True` as equivalent to `stream="events"` for backward compatibility
- Must not transform or filter the chunks in raw mode
- Must include usage/completion information when available in raw chunks
- Must work with all LiteLLM-supported providers that support streaming
- Must maintain type hints with overloads for each stream mode

## Acceptance Criteria
- Given an agent with `stream="raw"`, when processing a simple text generation request, then raw LiteLLM chunk objects are yielded containing `id`, `object`, `created`, `model`, `choices` fields
- Given an agent with `stream="raw"`, when the LLM completes generation, then a final chunk with `usage` information is included
- Given an agent with `stream="raw"` using tool calls, when the LLM calls a tool, then the raw chunks containing tool call deltas are passed through unmodified
- Given an agent with `stream=True` (backward compatibility), when processing a request, then `ExecutionEvent` objects are yielded as before
- Given an agent with `stream="events"`, when processing a request, then `ExecutionEvent` objects are yielded (same as `stream=True`)
- Given an agent with `stream=False` or no stream parameter, when processing a request, then an `AgentResult` is returned (existing behavior)

## Non-Goals
- Converting ExecutionEvents back to raw chunks (one direction only)
- Supporting `stream="raw"` with non-async iteration
- Adding SSE serialization utilities (developers handle serialization)
- Providing a middleware/proxy server (out of scope for this PR)
- Modifying the chunk format or adding Tyler-specific metadata to raw chunks
- Removing or deprecating `stream=True` (maintaining full backward compatibility)
- Adding ExecutionEvents for tool execution in raw mode (raw chunks only)

## Important Note on Tool Execution

Raw mode DOES execute tools and iterate like a full agent. This matches the pattern from [OpenAI's Agents SDK](https://openai.github.io/openai-agents-python/streaming/) where:
- Raw response events are LLM chunks
- Tools are executed silently between LLM responses
- Frontend sees `finish_reason: "tool_calls"` to know tools are running
- More chunks arrive after tool execution completes

