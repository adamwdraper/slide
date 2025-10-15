# Spec: Reasoning Content as Top-Level Message Field

**Feature name**: Move Reasoning Content to Top-Level Message Field  
**One-line summary**: Make reasoning content a first-class field on Message instead of buried in metrics, and unify reasoning parameters into a single API.

---

## Problem

Thinking tokens were just merged (PR #71) but have two design issues before release:

### Issue 1: Reasoning Hidden in Metrics
Currently, reasoning content is stored in `message.metrics['reasoning_content']`, which is:
- **Semantically wrong** - Reasoning IS content (user-visible), not system metrics (timing, tokens)
- **Poor DX** - UI developers have to dig into metrics dict to find reasoning
- **Inconsistent with standards** - OpenAI/LiteLLM use `message.reasoning_content` (top-level)
- **Hard to discover** - Not visible in type hints, schema, or autocomplete

### Issue 2: Dual Reasoning Parameters
Agent has TWO parameters for reasoning:
- `reasoning_effort: str` - For most providers
- `thinking: Dict` - Anthropic-specific

This violates framework's "provider-agnostic" principle and creates confusion.

**Why fix now:**
- ✅ Haven't released thinking tokens yet (no breaking changes)
- ✅ Better to fix architecture before external use
- ✅ Simple changes (1-2 days)

## Goal

Reasoning content should be a top-level field on Message that:
1. Is semantically correct (content, not metrics)
2. Is easy for UI developers to access
3. Mirrors OpenAI/LiteLLM API structure
4. Works consistently across all providers

Agent should have ONE unified `reasoning` parameter that works with all providers.

## Success Criteria

- [ ] Message has `reasoning_content` as top-level optional field
- [ ] Database schema supports storing `reasoning_content` column
- [ ] Agent has single `reasoning` parameter (removes `reasoning_effort` and `thinking`)
- [ ] CompletionHandler maps `reasoning` to provider-specific formats automatically
- [ ] All existing tests still pass
- [ ] UI developers can access `message.reasoning_content` directly

## User Story

**As a** UI developer building a chat interface with Tyler  
**I want** `message.reasoning_content` to be a top-level field  
**So that** I can easily display model thinking without digging through metrics

**As a** Tyler user configuring an agent  
**I want** one `reasoning` parameter that works for all models  
**So that** I don't need to learn provider-specific syntax

## Flow / States

### Happy Path: Message with Reasoning

1. Developer creates Agent with `reasoning="low"`
2. Agent streams response with thinking tokens
3. Tyler creates Message with:
   - `content="The answer is 42"`
   - `reasoning_content="Let me calculate..."` ← Top-level!
4. Message saved to ThreadStore
5. UI developer retrieves message
6. UI displays: `{message.reasoning_content}` and `{message.content}`
7. Clean, obvious API

### Edge Case: No Reasoning

1. Agent uses non-reasoning model (e.g., GPT-4)
2. Message created with `reasoning_content=None`
3. UI checks `if message.reasoning_content:` → skips display
4. Works seamlessly

## UX Links

- Current implementation: PR #71 (merged)
- Analysis: `/directive/specs/thinking-tokens-streaming/`
- LiteLLM docs: https://docs.litellm.ai/docs/reasoning_content

## Requirements

### Must
- Add `reasoning_content: Optional[str]` field to Narrator Message model
- Add `reasoning_content` column to database (SQLite + PostgreSQL)
- Remove `reasoning_effort` and `thinking` from Agent
- Add single `reasoning: Optional[Union[str, Dict]]` parameter to Agent
- Map `reasoning` to provider-specific formats in CompletionHandler
- Update Tyler to save reasoning in top-level field (not metrics)
- Support simple string format: `reasoning="low"`
- Support advanced dict formats for power users
- Update all tests to use new API
- Update documentation to show new field/parameter

### Must Not
- Break any Message serialization/deserialization
- Lose any reasoning data during migration
- Require UI developers to handle provider differences
- Make reasoning parameter complex or confusing
- Add Anthropic-specific fields to Message (keep provider-agnostic)

## Acceptance Criteria

### AC1: Message Has Top-Level reasoning_content
**Given** a Message object  
**When** I access `message.reasoning_content`  
**Then** I get the reasoning content string (or None)  
**And** I don't need to access `message.metrics`

### AC2: Database Stores reasoning_content
**Given** a Message with reasoning_content  
**When** saved to ThreadStore (SQLite or PostgreSQL)  
**Then** reasoning_content is stored in its own column  
**And** retrieving the message returns reasoning_content correctly

### AC3: Single reasoning Parameter
**Given** I want to enable thinking tokens  
**When** I create an Agent with `reasoning="low"`  
**Then** thinking tokens are enabled for any supported model  
**And** I don't need different syntax for Anthropic vs others

### AC4: Anthropic Advanced Config
**Given** I want fine-grained control for Anthropic  
**When** I use `reasoning={"type": "enabled", "budget_tokens": 2048}`  
**Then** the `thinking` parameter is passed to LiteLLM  
**And** Anthropic models use the advanced config

### AC5: Provider-Agnostic Storage
**Given** reasoning from any provider (Anthropic, DeepSeek, etc.)  
**When** saved to Message  
**Then** it's stored as plain text in `reasoning_content`  
**And** no provider-specific fields exist on Message

### AC6: Backward Compatible Serialization
**Given** old Messages without reasoning_content field  
**When** loaded from database  
**Then** reasoning_content defaults to None  
**And** no errors occur

### Negative Case: Invalid reasoning Format
**Given** Agent created with `reasoning=123` (invalid type)  
**When** validation occurs  
**Then** clear error message about valid formats  
**Or** gracefully ignore and log warning

## Non-Goals

**Not in scope for this refactor:**
- Structured thinking blocks parsing (keep as plain text)
- Anthropic-specific `thinking_blocks` field on Message
- Reasoning in chat completion context (still don't send back to LLM)
- Migration of existing metrics data (no data exists yet, pre-release)
- UI components for displaying reasoning
- Cost tracking for reasoning tokens separately
- Reasoning token limits or budgets

