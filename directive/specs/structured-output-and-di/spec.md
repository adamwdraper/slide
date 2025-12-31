# Spec — Structured Output & Dependency Injection

**Feature name**: Structured Output, Validation Retry, and Dependency Injection  
**One-line summary**: Add Pydantic-validated structured outputs, automatic retry on validation failure, and tool context injection to close feature gaps with Pydantic AI.

---

## Problem
Developers choosing between AI agent frameworks often select Pydantic AI specifically for its:
1. **Type-safe structured outputs** - LLM responses validated against Pydantic models
2. **Automatic retry** - Self-healing when LLM output doesn't match schema
3. **Dependency injection** - Clean way to pass runtime context (DB, user info) to tools

Slide/Tyler currently lacks these features, making it less attractive for use cases requiring structured data extraction, data pipelines, or multi-tenant applications.

## Goal
Add three opt-in, non-breaking features to Tyler:
1. `response_type` parameter for Pydantic-validated structured outputs
2. `retry_config` for automatic retry on validation failures
3. `tool_context` for dependency injection into tools

## Success Criteria
- [ ] Users can pass a Pydantic model as `response_type` and receive validated structured data
- [ ] Validation failures trigger automatic retry with error feedback to the LLM
- [ ] Tools can declare a `ctx` parameter to receive injected dependencies
- [ ] All existing code continues to work unchanged (100% backward compatible)
- [ ] Unit tests cover all three features with edge cases

## User Story
As a developer building a data extraction pipeline, I want my agent to return validated Pydantic models so that I can trust the output structure without manual parsing.

As a developer building a multi-tenant app, I want to inject user-specific context (like DB connections, user ID) into my tools so that tools don't need hardcoded dependencies.

## Flow / States

### Structured Output Flow
1. User creates `Agent` with optional `response_type=MyModel`
2. User calls `agent.run(thread, response_type=MyModel)` (can override agent default)
3. Agent adds JSON schema instruction to system prompt
4. Agent calls LLM with `response_format={"type": "json_schema", ...}`
5. Agent parses response and validates with Pydantic
6. On success: returns `AgentResult` with `structured_data` populated
7. On failure: retries (if configured) or raises `StructuredOutputError`

### Tool Context Flow
1. User defines tool with `ctx: ToolContext` as first parameter
2. User calls `agent.run(thread, tool_context={"db": db, "user_id": "123"})`
3. Tool runner inspects function signature
4. If `ctx` parameter exists, injects context as first argument
5. Tool executes with access to dependencies

## Requirements
- Must be 100% backward compatible (all parameters optional with `None` defaults)
- Must work with any Pydantic v2 BaseModel
- Must support both agent-level and per-run `response_type` overrides
- Must provide clear error messages on validation failure
- Must not affect streaming behavior for non-structured outputs
- Must not require changes to existing tool definitions

## Acceptance Criteria

### Structured Output
- Given an agent with `response_type=Invoice`, when `run()` completes, then `result.structured_data` is a validated `Invoice` instance
- Given an agent without `response_type`, when `run()` completes, then `result.structured_data` is `None` (existing behavior)
- Given an LLM response that doesn't match the schema, when `retry_config` is not set, then `StructuredOutputError` is raised
- Given an LLM response that doesn't match the schema, when `retry_config.max_retries=2`, then the agent retries up to 2 times with error feedback

### Tool Context
- Given a tool with `ctx: ToolContext` parameter, when `tool_context` is provided, then the tool receives the context
- Given a tool without `ctx` parameter, when `tool_context` is provided, then the tool is called without context (backward compatible)
- Given a tool with `ctx` parameter, when `tool_context` is `None`, then `ToolContextError` is raised

### Retry
- Given `retry_config=RetryConfig(max_retries=3)`, when validation fails, then up to 3 retry attempts are made
- Given `retry_config=None` (default), when validation fails, then error is raised immediately

## Non-Goals
- Full generic typing like `RunContext[T]` (can add later, start with dict-based)
- Streaming structured outputs (structured output requires complete response)
- Automatic schema inference from tool return types

