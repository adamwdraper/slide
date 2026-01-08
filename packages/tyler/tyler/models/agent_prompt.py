"""Agent prompt generation and Weave stream accumulator."""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

import weave
from weave import Prompt
from pydantic import Field


def _weave_stream_accumulator(state: Any | None, value: Any) -> dict:
    """Accumulate yields from Agent.stream() into a compact, serializable summary.

    This is only for Weave tracing output; it does not change what `stream()` yields.
    Handles both `mode="events"` (ExecutionEvent yields) and `mode="raw"` (provider chunks).
    """
    if state is None or not isinstance(state, dict):
        state = {
            "mode": None,
            "content": "",
            "thinking": "",
            "events": {"counts": {}},
            "tools": [],
            "errors": [],
            "metrics": {},
        }

    def _bump(event_name: str) -> None:
        counts = state.setdefault("events", {}).setdefault("counts", {})
        counts[event_name] = int(counts.get(event_name, 0)) + 1

    # --- Events mode (Tyler ExecutionEvent) ---
    if hasattr(value, "type") and hasattr(value, "data"):
        try:
            event_type = getattr(value.type, "value", None) or str(value.type)
        except Exception:
            event_type = "unknown"

        state["mode"] = state.get("mode") or "events"
        _bump(event_type)

        data = getattr(value, "data", {}) or {}

        if event_type == "llm_stream_chunk":
            chunk = data.get("content_chunk")
            if chunk:
                state["content"] = (state.get("content") or "") + str(chunk)
        elif event_type == "llm_thinking_chunk":
            chunk = data.get("thinking_chunk")
            if chunk:
                state["thinking"] = (state.get("thinking") or "") + str(chunk)
        elif event_type == "tool_selected":
            state.setdefault("tools", []).append(
                {
                    "tool_name": data.get("tool_name"),
                    "tool_call_id": data.get("tool_call_id"),
                    "arguments": data.get("arguments"),
                    "status": "selected",
                }
            )
        elif event_type == "tool_result":
            state.setdefault("tools", []).append(
                {
                    "tool_name": data.get("tool_name"),
                    "tool_call_id": data.get("tool_call_id"),
                    "result": data.get("result"),
                    "duration_ms": data.get("duration_ms"),
                    "status": "result",
                }
            )
        elif event_type == "tool_error":
            state.setdefault("errors", []).append(
                {
                    "tool_name": data.get("tool_name"),
                    "tool_call_id": data.get("tool_call_id"),
                    "error": data.get("error"),
                }
            )
        elif event_type == "llm_response":
            tokens = data.get("tokens")
            if isinstance(tokens, dict) and tokens:
                state.setdefault("metrics", {})["tokens"] = tokens
            latency = data.get("latency_ms")
            if latency is not None:
                state.setdefault("metrics", {})["latency_ms"] = latency
            if data.get("tool_calls") is not None:
                state.setdefault("metrics", {})["tool_calls"] = data.get("tool_calls")
        elif event_type == "execution_complete":
            if "duration_ms" in data:
                state.setdefault("metrics", {})["duration_ms"] = data.get("duration_ms")
            if "total_tokens" in data:
                state.setdefault("metrics", {})["total_tokens"] = data.get("total_tokens")

        return state

    # --- Raw mode (best-effort) ---
    state["mode"] = state.get("mode") or "raw"
    try:
        choices = getattr(value, "choices", None)
        if choices:
            delta = getattr(choices[0], "delta", None)
            if delta is not None and hasattr(delta, "content"):
                content = getattr(delta, "content", None)
                if content:
                    state["content"] = (state.get("content") or "") + str(content)
    except Exception:
        # Chunk shapes vary by provider; keep tracing robust.
        pass

    return state


class AgentPrompt(Prompt):
    """Generates the system prompt for the Agent."""
    
    system_template: str = Field(default="""<agent_overview>
# Agent Identity
Your name is {name} and you are a {model_name} powered AI agent that can converse, answer questions, and when necessary, use tools to perform tasks.

Current date: {current_date}

# Core Purpose
Your purpose is:
```
{purpose}
```

# Supporting Notes
Here are some relevant notes to help you accomplish your purpose:
```
{notes}
```
</agent_overview>

<operational_routine>
# Operational Routine
Based on the user's input, follow this routine:
1. If the user makes a statement or shares information, respond appropriately with acknowledgment.
2. If the user's request is vague, incomplete, or missing information needed to complete the task, use the relevant notes to understand the user's request. If you don't find an answer in the notes, ask probing questions to understand the user's request deeper. You can ask a maximum of 3 probing questions.
3. If the request requires gathering information or performing actions beyond your knowledge you can use the tools available to you.
</operational_routine>

<tool_usage_guidelines>
# Tool Usage Guidelines

## Available Tools
You have access to the following tools:
{tools_description}

## Important Instructions for Using Tools
When you need to use a tool, you MUST FIRST write a brief message to the user summarizing the user's ask and what you're going to do. This message should be casual and conversational, like talking with a friend. After writing this message, then include your tool call.

For example:

User: "Can you create an image of a desert landscape?"
Assistant: "Sure, I can make that desert landscape for you. Give me a sec."
[Then you would use the image generation tool]

User: "What's the weather like in Chicago today?"
Assistant: "Let me check the Chicago weather for you."
[Then you would use the weather tool]

User: "Can you help me find information about electric cars?"
Assistant: "Yeah, I'll look up some current info on electric cars for you."
[Then you would use the search tool]

User: "Calculate 15% tip on a $78.50 restaurant bill"
Assistant: "Let me figure that out for you."
[Then you would use the calculator tool]

Remember: ALWAYS write a brief, conversational message to the user BEFORE using any tools. Never skip this step. The message should acknowledge what the user is asking for and let them know what you're going to do, but keep it casual and friendly.
</tool_usage_guidelines>

<file_handling_instructions>
# File Handling Instructions
Both user messages and tool responses may contain file attachments. 

File attachments are included in the message content in this format:
```
[File: files/path/to/file.ext (mime/type)]
```

When referencing files in your responses, ALWAYS use the exact file path as shown in the file reference. For example:

Instead of: "I've created an audio summary. You can listen to it [here](sandbox:/mnt/data/speech_ef3b8be3a702416494d9f20593d4b38f.mp3)."

Use: "I've created an audio summary. You can listen to it [here](files/path/to/stored/file.mp3)."

This ensures the user can access the file correctly.
</file_handling_instructions>""")

    def system_prompt(
        self, 
        purpose: Union[str, Prompt], 
        name: str, 
        model_name: str, 
        tools: List[Dict], 
        notes: Union[str, Prompt] = ""
    ) -> str:
        """Generate the system prompt for the agent.
        
        Args:
            purpose: The agent's purpose (string or Prompt)
            name: The agent's name
            model_name: The model being used
            tools: List of tool definitions
            notes: Additional notes for the agent
            
        Returns:
            The formatted system prompt string
        """
        # Use cached tools description if available and tools haven't changed
        cache_key = f"{len(tools)}_{id(tools)}"
        if not hasattr(self, '_tools_cache') or self._tools_cache.get('key') != cache_key:
            # Format tools description
            tools_description_lines = []
            for tool in tools:
                if tool.get('type') == 'function' and 'function' in tool:
                    tool_func = tool['function']
                    tool_name = tool_func.get('name', 'N/A')
                    description = tool_func.get('description', 'No description available.')
                    tools_description_lines.append(f"- `{tool_name}`: {description}")
            
            tools_description_str = "\n".join(tools_description_lines) if tools_description_lines else "No tools available."
            self._tools_cache = {'key': cache_key, 'description': tools_description_str}
        else:
            tools_description_str = self._tools_cache['description']

        # Handle both string and Prompt types
        if isinstance(purpose, Prompt):
            formatted_purpose = str(purpose)  # StringPrompt has __str__ method
        else:
            formatted_purpose = purpose
            
        if isinstance(notes, Prompt):
            formatted_notes = str(notes)  # StringPrompt has __str__ method
        else:
            formatted_notes = notes

        return self.system_template.format(
            current_date=datetime.now().strftime("%Y-%m-%d %A"),
            purpose=formatted_purpose,
            name=name,
            model_name=model_name,
            tools_description=tools_description_str,
            notes=formatted_notes
        )
