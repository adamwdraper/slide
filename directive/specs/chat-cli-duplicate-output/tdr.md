# Technical Decision Record: Fix Chat CLI Duplicate Output

## Decision
Remove redundant `console.print()` calls added in commit `b3afbf2` that cause duplicate output. Trust that Rich's `Live.stop()` preserves the final rendered content in the terminal.

## Context
Commit `b3afbf2` (Oct 29, 2025) added explicit `console.print()` calls after stopping Live displays to "preserve full content" under the assumption that Live widgets truncate or lose content when stopped. This created a bug where:
- Messages without tool calls appear **2x** (Live + print)
- Messages with tool calls appear **3x** (Live + print + format_message)
- Thinking blocks appear **2x** (Live + print)

## Options Considered

### Option 1: Remove Duplicate Prints ✅ CHOSEN
- Remove `console.print()` calls after `Live.stop()` (lines 479-482, 489-492)
- Remove duplicate content panel from `format_message()` for tool calls (lines 308-314)
- Trust Rich's Live to preserve content

**Pros:**
- Simplest, cleanest solution
- Minimal code changes (~15 lines removed)
- No additional complexity

**Cons:**
- If Rich's Live does truncate very long content, we'd lose it
- Unverified assumption about Live behavior

### Option 2: Increase Live Panel Height
- Keep Live but configure for taller content
- Remove duplicates but handle truncation proactively

**Rejected:** More complex than needed; can add later if truncation is confirmed

### Option 3: Detect Truncation & Conditionally Reprint
- Check content length and only reprint if truncated

**Rejected:** Hacky detection logic; user preference for clean solutions

### Option 4: Different Display Strategy
- Use scrollable/paged output for long content

**Rejected:** Too complex for a bug fix; changes UX significantly

## Technical Design

### Changes to `handle_stream_update()` function

**Remove lines 479-482 (thinking content reprint):**
```python
# DELETE THIS:
thinking_content = ''.join(handle_stream_update.thinking)
if thinking_content.strip():
    console.print(create_thinking_panel(thinking_content))
```

**Remove lines 489-492 (agent response reprint):**
```python
# DELETE THIS:
full_content = ''.join(handle_stream_update.content)
if full_content.strip():
    console.print(create_agent_panel(full_content))
```

### Changes to `format_message()` method

**Modify lines 307-314 to NOT include content panel for tool calls:**
```python
# Current (creates duplicate):
if message.content and message.content.strip():
    panels.append(Panel(
        Markdown(message.content),
        title=f"[blue]Agent[/]",
        border_style="blue",
        box=box.ROUNDED
    ))

# Change to (skip content, it's already visible from Live):
# Don't create content panel - Live already displayed it
```

### Flow After Changes

**For messages WITHOUT tool calls:**
1. Stream thinking → Live panel updates in real-time
2. Stream response → Live panel updates in real-time
3. MESSAGE_CREATED event → Live.stop() leaves content visible ✅
4. No duplicate prints ✅

**For messages WITH tool calls:**
1. Stream thinking → Live panel updates
2. Stream response → Live panel updates
3. MESSAGE_CREATED event:
   - Live.stop() leaves content visible ✅
   - format_message() creates ONLY tool call panels (no content panel) ✅
4. No duplicates ✅

## Implementation Plan

### Files to Modify
- `packages/tyler/tyler/cli/chat.py`

### Code Changes
1. In `handle_stream_update()` (lines 475-494):
   - Keep `Live.stop()` calls
   - Remove `console.print()` calls after stopping
   - Keep attribute cleanup (delattr)

2. In `format_message()` (lines 303-327):
   - Remove content panel creation for messages with tool calls (lines 308-314)
   - Keep tool call panel creation (lines 316-325)

### Testing Strategy
1. **Short responses** - verify no duplicates
2. **Long responses** (>100 lines) - verify no truncation and no duplicates
3. **Messages with tool calls** - verify content once, tool calls once
4. **Multiple turns** - verify consistent behavior
5. **Error conditions** - verify cleanup works

### Rollback Plan
If truncation issues appear:
1. Revert changes (restore commit `b3afbf2` state)
2. Implement Option 2 (increase Live height limits)

## Assumptions
- Rich's `Live.stop()` preserves the final rendered content in the terminal
- Terminal height is sufficient for most responses (can be addressed later if needed)
- Users prefer clean, non-duplicate output over potential edge case handling

## Risks & Mitigation

### Risk: Content Truncation
**Likelihood:** Low (Rich's Live likely preserves content)
**Impact:** Medium (users miss long responses)
**Mitigation:** 
- Test with long content during implementation
- Can add height limits if needed
- Can monitor for user reports

### Risk: Breaking Existing Behavior
**Likelihood:** Very Low (this is a bug fix)
**Impact:** Low (restoring expected behavior)
**Mitigation:** Manual testing before commit

## Success Criteria
- ✅ Zero duplicate output in terminal
- ✅ All content visible (no truncation)
- ✅ Clean streaming experience
- ✅ Tool calls display correctly
- ✅ No regression in chat functionality

## Open Questions
None - decision is clear and implementation is straightforward.

## Timeline
- Implementation: 15 minutes
- Testing: 30 minutes
- Total: 45 minutes

## Decision Rationale
Choosing Option 1 because:
1. **Simplicity**: Cleanest solution with minimal code changes
2. **User preference**: Explicitly requested "no hacky" solutions
3. **Low risk**: Easy to adjust if issues arise
4. **Correct behavior**: Rich's Live is designed to preserve content on stop
5. **Bug fix**: Reverting problematic code from commit `b3afbf2`

