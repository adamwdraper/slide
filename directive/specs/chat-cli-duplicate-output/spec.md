# Specification: Fix Chat CLI Duplicate Output

## Overview
The Tyler chat CLI currently displays assistant responses and thinking blocks 2-3 times due to redundant printing logic in the streaming handler. This regression was introduced in commit `b3afbf2` (Oct 29, 2025) which attempted to fix content truncation but instead created duplicate output.

## Problem Statement
When using the `tyler chat` command, each response from the agent is displayed twice:
1. First during the Live streaming display (real-time updates)
2. Again after the MESSAGE_CREATED event (static print)

This creates a confusing user experience with duplicate content appearing in the terminal.

## Current Behavior

### For messages WITHOUT tool calls:
1. Agent streams thinking tokens → displayed in Live panel
2. MESSAGE_CREATED event fires → Live stops, thinking content printed again (**duplicate**)
3. Agent streams response → displayed in Live panel  
4. MESSAGE_CREATED event fires → Live stops, response content printed again (**duplicate**)
5. Result: Everything appears **twice**

### For messages WITH tool calls:
1. Agent streams thinking tokens → displayed in Live panel
2. Agent streams response → displayed in Live panel
3. MESSAGE_CREATED event fires:
   - Live stops, thinking content printed again (**duplicate #1**)
   - Response content printed again (**duplicate #2**)
   - `format_message()` creates panels including content (**duplicate #3**)
   - Tool call panels printed (correct)
4. Result: Thinking appears **twice**, response content appears **three times**

## Desired Behavior

### For messages WITHOUT tool calls:
1. Agent streams thinking tokens → displayed in Live panel
2. MESSAGE_CREATED event fires → Live panel stops, content remains visible
3. Agent streams response → displayed in Live panel
4. MESSAGE_CREATED event fires → Live panel stops, content remains visible
5. Result: Each piece of content appears **exactly once**

### For messages WITH tool calls:
1. Agent streams thinking tokens → displayed in Live panel
2. Agent streams response → displayed in Live panel
3. MESSAGE_CREATED event fires:
   - Live panels stop, content remains visible
   - Tool call panels printed (no content duplication)
4. Result: Thinking appears **once**, response appears **once**, tool calls appear **once**

## Acceptance Criteria
1. ✅ Agent responses display exactly once in the terminal
2. ✅ Thinking/reasoning blocks display exactly once in the terminal
3. ✅ Live streaming continues to work correctly during content generation
4. ✅ Tool call outputs are not affected and continue to display correctly
5. ✅ Error messages continue to clean up Live displays properly
6. ✅ Existing chat functionality (commands, thread switching, etc.) remains unchanged

## Non-Goals
- Changing the Live display behavior during streaming
- Modifying how tool calls are displayed
- Altering the MESSAGE_CREATED event handling logic beyond removing duplicate prints

## Technical Notes
The issue is in `packages/tyler/tyler/cli/chat.py`:

### In `handle_stream_update` function:
- **Lines 477-484**: After stopping thinking Live display, prints content again (unnecessary)
- **Lines 486-494**: After stopping agent Live display, prints content again (unnecessary)
- **Lines 498-504**: Calls `format_message()` for tool calls, which also includes content

### In `format_message` method:
- **Lines 307-314**: For messages with tool calls, creates a panel with the content
- This creates a third instance when combined with the Live display and line 492 print

### Root Cause:
Commit `b3afbf2` added `console.print()` calls after `Live.stop()` to "preserve full content" under the assumption that Live truncates or loses content. However, Rich's `Live.stop()` already leaves the last rendered content visible and permanent in the terminal. The explicit `console.print()` calls are redundant and cause duplicates. For messages with tool calls, `format_message()` also re-creates the content panel, adding a third duplicate.

### Why the Original Fix Was Wrong:
The commit attempted to solve potential content truncation by always reprinting. A better approach would be:
- Only reprint if truncation is detected
- Increase Live display height limits
- Or use a different display strategy for very long content

The current implementation blindly reprints everything, causing the duplication bug.

## Success Metrics
- Zero duplicate output in terminal
- Smooth, single-display streaming experience
- No regression in existing chat features

