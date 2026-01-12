"""Agent model implementation"""
import weave
from weave import Prompt
from pydantic import BaseModel, Field, PrivateAttr
import json
import types
import logging
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Tuple, Callable, Awaitable, Literal, Type
from datetime import datetime, timezone
from litellm import acompletion

# Direct imports to avoid circular dependency
from narrator import Thread, Message, Attachment, ThreadStore, FileStore

from tyler.utils.tool_runner import tool_runner, ToolContext
from tyler.models.execution import (
    EventType, ExecutionEvent,
    AgentResult, StructuredOutputError, ToolContextError
)
from tyler.models.retry_config import RetryConfig
from tyler.models.tool_manager import ToolManager
from tyler.models.message_factory import MessageFactory
from tyler.models.completion_handler import CompletionHandler
import asyncio


def _weave_stream_accumulator(state: Any | None, value: Any) -> dict:
    """Accumulate yields from Agent.stream() into a compact, serializable summary.

    This is only for Weave tracing output; it does not change what `stream()` yields.
    Handles both `mode="events"` (ExecutionEvent yields) and `mode="openai"` (provider chunks).
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

    # --- OpenAI mode (best-effort) ---
    state["mode"] = state.get("mode") or "openai"
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

    def system_prompt(self, purpose: Union[str, Prompt], name: str, model_name: str, tools: List[Dict], notes: Union[str, Prompt] = "") -> str:
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

class Agent(BaseModel):
    """Tyler Agent model for AI-powered assistants.
    
    The Agent class provides a flexible interface for creating AI agents with tool use,
    delegation capabilities, and conversation management.
    
    Note: You can use either 'api_base' or 'base_url' to specify a custom API endpoint.
    'base_url' will be automatically mapped to 'api_base' for compatibility with litellm.
    """
    model_name: str = Field(default="gpt-4.1")
    api_base: Optional[str] = Field(default=None, description="Custom API base URL for the model provider (e.g., for using alternative inference services). You can also use 'base_url' as an alias.")
    api_key: Optional[str] = Field(default=None, description="API key for the model provider. If not provided, LiteLLM will use environment variables.")
    extra_headers: Optional[Dict[str, str]] = Field(default=None, description="Additional headers to include in API requests (e.g., for authentication or tracking)")
    temperature: float = Field(default=0.7)
    drop_params: bool = Field(default=True, description="Whether to drop unsupported parameters for specific models (e.g., O-series models only support temperature=1)")
    reasoning: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="""Enable reasoning/thinking tokens for supported models.
        - String: 'low', 'medium', 'high' (recommended for most use cases)
        - Dict: Provider-specific config (e.g., {'type': 'enabled', 'budget_tokens': 1024} for Anthropic)
        """
    )
    name: str = Field(default="Tyler")
    purpose: Union[str, Prompt] = Field(default_factory=lambda: weave.StringPrompt("To be a helpful assistant."))
    notes: Union[str, Prompt] = Field(default_factory=lambda: weave.StringPrompt(""))
    version: str = Field(default="1.0.0")
    tools: List[Union[str, Dict, Callable, types.ModuleType]] = Field(default_factory=list, description="List of tools available to the agent. Can include: 1) Direct tool function references (callables), 2) Tool module namespaces (modules like web, files), 3) Built-in tool module names (strings), 4) Custom tool definitions (dicts with 'definition', 'implementation', and optional 'attributes' keys). For module names, you can specify specific tools using 'module:tool1,tool2'.")
    max_tool_iterations: int = Field(default=10)
    agents: List["Agent"] = Field(default_factory=list, description="List of agents that this agent can delegate tasks to.")
    thread_store: Optional[ThreadStore] = Field(default=None, description="Thread store instance for managing conversation threads", exclude=True)
    file_store: Optional[FileStore] = Field(default=None, description="File store instance for managing file attachments", exclude=True)
    mcp: Optional[Dict[str, Any]] = Field(default=None, description="MCP server configuration. Same structure as YAML config. Call connect_mcp() after creating agent to connect to servers.")
    retry_config: Optional[RetryConfig] = Field(
        default=None, 
        description="Configuration for structured output validation retry. When set, the agent will retry on validation failures up to max_retries times."
    )
    response_type: Optional[Type[BaseModel]] = Field(
        default=None,
        description="Default Pydantic model for structured output. When set, agent.run() will return validated structured data. Can be overridden per-run via agent.run(response_type=...)."
    )
    tool_context: Optional[Dict[str, Any]] = Field(
        default=None,
        exclude=True,  # Non-serializable objects like DB connections
        description="Default tool context for dependency injection. Contains static dependencies (database clients, API clients, config) that are passed to tools. Can be extended per-run via agent.run(tool_context=...) which merges with and overrides agent-level context."
    )
    
    # Helper objects excluded from serialization (recreated on deserialization)
    message_factory: Optional[MessageFactory] = Field(default=None, exclude=True, description="Factory for creating standardized messages (excluded from serialization)")
    completion_handler: Optional[CompletionHandler] = Field(default=None, exclude=True, description="Handler for LLM completions (excluded from serialization)")
    
    _prompt: AgentPrompt = PrivateAttr(default_factory=AgentPrompt)
    _iteration_count: int = PrivateAttr(default=0)
    _processed_tools: List[Dict] = PrivateAttr(default_factory=list)
    _system_prompt: str = PrivateAttr(default="")
    _tool_attributes_cache: Dict[str, Optional[Dict[str, Any]]] = PrivateAttr(default_factory=dict)
    _mcp_connected: bool = PrivateAttr(default=False)
    _mcp_disconnect: Optional[Callable[[], Awaitable[None]]] = PrivateAttr(default=None)
    _tool_context: Optional[Dict[str, Any]] = PrivateAttr(default=None)
    _response_format: Optional[str] = PrivateAttr(default=None)
    _last_step_stream_had_tool_calls: bool = PrivateAttr(default=False)
    _last_step_stream_should_continue: bool = PrivateAttr(default=False)
    step_errors_raise: bool = Field(default=False, description="If True, step() will raise exceptions instead of returning an error message tuple for backward compatibility.")

    model_config = {
        "arbitrary_types_allowed": True,
        "extra": "allow"
    }

    def __init__(self, **data):
        # Handle base_url as an alias for api_base (since litellm uses api_base)
        if 'base_url' in data and 'api_base' not in data:
            data['api_base'] = data.pop('base_url')
            
        super().__init__(**data)
        
        # Validate MCP config schema immediately (fail fast!)
        if self.mcp:
            from tyler.mcp.config_loader import _validate_mcp_config
            _validate_mcp_config(self.mcp)
        
        # Note: Helper initialization happens in model_post_init(), which is
        # automatically called by Pydantic after __init__ completes. This ensures
        # helpers are initialized both for fresh instances and after deserialization.
    
    def _initialize_helpers(self):
        """Initialize or reinitialize helper objects and internal state.
        
        This method is called during __init__ and can be called after deserialization
        to ensure all helper objects are properly initialized. It preserves any
        user-provided helper objects (e.g., custom message_factory or completion_handler).
        """
        # Generate system prompt once at initialization
        self._prompt = AgentPrompt()
        # Initialize the tool attributes cache
        self._tool_attributes_cache = {}
        
        # Initialize MessageFactory only if not provided by user
        if self.message_factory is None:
            self.message_factory = MessageFactory(self.name, self.model_name)
        
        # Initialize CompletionHandler only if not provided by user
        if self.completion_handler is None:
            self.completion_handler = CompletionHandler(
                model_name=self.model_name,
                temperature=self.temperature,
                api_base=self.api_base,
                api_key=self.api_key,
                extra_headers=self.extra_headers,
                drop_params=self.drop_params,
                reasoning=self.reasoning
            )
        
        # Use ToolManager to register all tools and delegation
        tool_manager = ToolManager(tools=self.tools, agents=self.agents)
        self._processed_tools = tool_manager.register_all_tools()

        # Create default stores if not provided
        if self.thread_store is None:
            logging.getLogger(__name__).info(f"Creating default in-memory thread store for agent {self.name}")
            self.thread_store = ThreadStore()  # Uses in-memory backend by default
            
        if self.file_store is None:
            logging.getLogger(__name__).info(f"Creating default file store for agent {self.name}")
            self.file_store = FileStore()  # Uses default settings

        # Now generate the system prompt including the tools
        self._system_prompt = self._prompt.system_prompt(
            self.purpose, 
            self.name, 
            self.model_name, 
            self._processed_tools, 
            self.notes
        )
    
    def model_post_init(self, __context: Any) -> None:
        """Pydantic v2 hook called after model initialization.
        
        This method initializes all helper objects and internal state. It's called
        automatically by Pydantic after __init__() completes, ensuring helpers are
        properly initialized for both:
        - Fresh Agent instances (helpers start as None with default values)
        - Deserialized instances (helpers excluded from serialization, so they're None)
        
        The _initialize_helpers() method preserves any user-provided helpers, so it's
        safe to call unconditionally.
        
        Args:
            __context: Pydantic context (unused)
        """
        # Always initialize - the method preserves user-provided helpers
        self._initialize_helpers()
    
    @classmethod
    def from_config(
        cls,
        config_path: Optional[str] = None,
        **overrides
    ) -> "Agent":
        """Create an Agent from a YAML configuration file.
        
        Loads a Tyler config file (same format as tyler-chat CLI) and creates
        an Agent instance with those settings. Allows the same configuration
        to be used in both CLI and Python code.
        
        Args:
            config_path: Path to YAML config file (.yaml or .yml).
                        If None, searches standard locations:
                        1. ./tyler-chat-config.yaml (current directory)
                        2. ~/.tyler/chat-config.yaml (user home)
                        3. /etc/tyler/chat-config.yaml (system-wide)
            **overrides: Override any config values. These replace (not merge)
                        config file values using shallow dict update semantics.
                        
                        Examples:
                        - tools=["web"] replaces entire tools list
                        - temperature=0.9 replaces temperature value
                        - mcp={...} replaces entire mcp dict (not merged)
        
        Returns:
            Agent instance initialized with config values and overrides
        
        Raises:
            FileNotFoundError: If config_path specified but doesn't exist
            ValueError: If no config found in standard locations (path=None)
                       or if file extension is not .yaml/.yml
            yaml.YAMLError: If YAML syntax is invalid
            ValidationError: If config contains invalid Agent parameters
        
        Example:
            >>> # Auto-discover config
            >>> agent = Agent.from_config()
            
            >>> # Explicit config path
            >>> agent = Agent.from_config("./my-config.yaml")
            
            >>> # With overrides
            >>> agent = Agent.from_config(
            ...     "config.yaml",
            ...     temperature=0.9,
            ...     model_name="gpt-4o"
            ... )
            
            >>> # Then use normally
            >>> await agent.connect_mcp()  # If MCP servers configured
            >>> result = await agent.go(thread)
        """
        from tyler.config import load_config
        
        # Load config from file
        logging.getLogger(__name__).info(f"Creating agent from config: {config_path or 'auto-discovered'}")
        config = load_config(config_path)
        
        # Apply overrides (replacement semantics - dict.update replaces)
        if overrides:
            logging.getLogger(__name__).debug(f"Config overrides: {list(overrides.keys())}")
            config.update(overrides)
        
        # Create agent using standard __init__
        return cls(**config)

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now(timezone.utc).isoformat()
    
    def _get_tool_attributes(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool attributes with caching."""
        if tool_name not in self._tool_attributes_cache:
            self._tool_attributes_cache[tool_name] = tool_runner.get_tool_attributes(tool_name)
        return self._tool_attributes_cache[tool_name]

    def _normalize_tool_call(self, tool_call):
        """Ensure tool_call has a consistent format for tool_runner without modifying the original."""
        if isinstance(tool_call, dict):
            # Create a minimal wrapper that provides the expected interface
            class ToolCallWrapper:
                def __init__(self, tool_dict):
                    self.id = tool_dict.get('id')
                    self.type = tool_dict.get('type', 'function')
                    self.function = type('obj', (object,), {
                        'name': tool_dict.get('function', {}).get('name', ''),
                        'arguments': tool_dict.get('function', {}).get('arguments', '{}') or '{}'
                    })
            return ToolCallWrapper(tool_call)
        else:
            # For objects, ensure arguments is not empty
            if not tool_call.function.arguments or tool_call.function.arguments.strip() == "":
                # Create a copy to avoid modifying the original
                class ToolCallCopy:
                    def __init__(self, original):
                        self.id = original.id
                        self.type = getattr(original, 'type', 'function')
                        self.function = type('obj', (object,), {
                            'name': original.function.name,
                            'arguments': '{}'
                        })
                return ToolCallCopy(tool_call)
            return tool_call

    async def _handle_tool_execution(self, tool_call, progress_callback=None) -> dict:
        """
        Execute a single tool call and format the result message
        
        Args:
            tool_call: The tool call object from the model response
            progress_callback: Optional async callback for progress updates.
                Signature: async (progress: float, total: float | None, message: str | None) -> None
                Used by MCP tools to emit progress notifications during long-running operations.
        
        Returns:
            dict: Formatted tool result message
        """
        normalized_tool_call = self._normalize_tool_call(tool_call)
        
        # Build rich ToolContext with metadata if user provided tool_context
        if self._tool_context is not None:
            # Extract tool_name and tool_call_id from the normalized tool_call
            tool_name = getattr(normalized_tool_call.function, 'name', None)
            tool_call_id = getattr(normalized_tool_call, 'id', None)
            
            # Shallow copy deps to prevent direct mutations from affecting other tool calls.
            # Note: Nested mutable objects (dicts within dicts) are still shared references.
            # We intentionally avoid deepcopy as it would fail for non-picklable objects
            # like database connections and API clients which are common deps.
            deps_copy = dict(self._tool_context)
            
            # Handle progress callbacks - combine if both parameter and tool_context have one
            # This allows streaming mode to emit TOOL_PROGRESS events while also calling
            # a user's custom callback
            user_callback = deps_copy.pop('progress_callback', None)
            
            if progress_callback is not None and user_callback is not None:
                # Both exist - create composite that calls both (best-effort)
                async def composite_callback(progress, total, message):
                    # Call both callbacks, continuing even if one fails
                    # Progress callbacks are informational, so we don't want
                    # one failure to prevent the other from being called
                    try:
                        await progress_callback(progress, total, message)
                    except Exception:
                        pass  # Progress callback failure shouldn't stop execution
                    try:
                        await user_callback(progress, total, message)
                    except Exception:
                        pass  # Progress callback failure shouldn't stop execution
                effective_progress_callback = composite_callback
            elif progress_callback is not None:
                effective_progress_callback = progress_callback
            else:
                effective_progress_callback = user_callback
            
            rich_context = ToolContext(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                deps=deps_copy,
                progress_callback=effective_progress_callback,
            )
        else:
            # Create minimal context just for progress callback if provided
            if progress_callback is not None:
                tool_name = getattr(normalized_tool_call.function, 'name', None)
                tool_call_id = getattr(normalized_tool_call, 'id', None)
                rich_context = ToolContext(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    progress_callback=progress_callback,
                )
            else:
                rich_context = None
        
        return await tool_runner.execute_tool_call(normalized_tool_call, context=rich_context)
    
    async def _get_completion(self, **completion_params) -> Any:
        """Get a completion from the LLM with weave tracing.
        
        This is a thin wrapper around acompletion for backward compatibility
        with tests that mock this method.
        
        Returns:
            Any: The completion response.
        """
        response = await acompletion(**completion_params)
        return response
    
    @weave.op()
    async def step(
        self, 
        thread: Thread, 
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        tool_choice: Optional[str] = None,
        execute_tools: bool = False,
    ) -> Tuple[Any, Dict]:
        """Execute a single step of the agent's processing.
        
        A step consists of:
        1. Getting a completion from the LLM
        2. Collecting metrics about the completion
        3. (Optional) Executing any tool calls produced by the completion
        
        Args:
            thread: The thread to process
            stream: Whether to stream the response. Defaults to False.
            tools: Optional tools override. If None, uses self._processed_tools.
            system_prompt: Optional system prompt override. If None, uses self._system_prompt.
            tool_choice: Optional tool_choice parameter for LLM. Use "required" to force
                tool calls (used for structured output), "auto" for default behavior.
            execute_tools: If True, execute any tool calls produced by this completion
                *within* the step (so tool ops nest under this step in traces). Tool
                execution results are returned in `metrics["_tool_execution_results"]`.
            
        Returns:
            Tuple[Any, Dict]: The completion response and metrics.
        """
        # Get thread messages (these won't include system messages as they're filtered out)
        thread_messages = await thread.get_messages_for_chat_completion(file_store=self.file_store)
        
        # Use provided overrides or defaults
        effective_tools = tools if tools is not None else self._processed_tools
        effective_system_prompt = system_prompt if system_prompt is not None else self._system_prompt
        
        # Use CompletionHandler to build parameters
        completion_messages = [{"role": "system", "content": effective_system_prompt}] + thread_messages
        completion_params = self.completion_handler._build_completion_params(
            messages=completion_messages,
            tools=effective_tools,
            stream=stream
        )
        
        # Add response_format if set (for simple JSON mode)
        if self._response_format == "json":
            completion_params["response_format"] = {"type": "json_object"}
        
        # Add tool_choice if specified (used for structured output to force tool calls)
        if tool_choice is not None and effective_tools:
            completion_params["tool_choice"] = tool_choice
        
        # Track API call time
        api_start_time = datetime.now(timezone.utc)
        
        try:
            # Backward-compatible behavior:
            # - If tests/users patch `_get_completion` with an object that exposes `.call(...)`,
            #   use it to get `(response, call)` for metrics.
            # - Otherwise call the coroutine directly and treat call info as unavailable.
            if hasattr(self._get_completion, "call"):
                response, call = await self._get_completion.call(self, **completion_params)
            else:
                response = await self._get_completion(**completion_params)
                call = None
            
            # Use CompletionHandler to build metrics
            metrics = self.completion_handler._build_metrics(api_start_time, response, call)

            # Optionally execute tool calls
            if execute_tools or getattr(self, "_execute_tools_in_step", False):
                tool_calls = None
                try:
                    if response and hasattr(response, "choices") and response.choices:
                        assistant_message = response.choices[0].message
                        tool_calls = getattr(assistant_message, "tool_calls", None)
                except Exception:
                    tool_calls = None

                tool_results_by_id: Dict[str, Any] = {}
                tool_durations_ms_by_id: Dict[str, float] = {}
                if tool_calls:
                    # Execute all tools concurrently (restore pre-refactor behavior).
                    async def _run_one_tool(tc: Any) -> Tuple[Optional[str], Any, float]:
                        try:
                            tc_id_local = tc.id if hasattr(tc, "id") else tc.get("id")
                        except Exception:
                            tc_id_local = None
                        if not tc_id_local:
                            return None, None, 0.0

                        start = datetime.now(timezone.utc)
                        try:
                            # _handle_tool_execution reads `self._tool_context` internally.
                            res = await self._handle_tool_execution(tc)
                        except Exception as tool_exc:
                            res = tool_exc
                        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                        return str(tc_id_local), res, duration_ms

                    tasks = [_run_one_tool(tc) for tc in tool_calls]
                    results = await asyncio.gather(*tasks, return_exceptions=False)
                    for tc_id, res, dur in results:
                        if not tc_id:
                            continue
                        tool_results_by_id[tc_id] = res
                        tool_durations_ms_by_id[tc_id] = dur

                if tool_results_by_id:
                    metrics["_tool_execution_results"] = tool_results_by_id
                    metrics["_tool_execution_durations_ms"] = tool_durations_ms_by_id
            
            return response, metrics
        except Exception as e:
            if self.step_errors_raise:
                raise
            # Backward-compatible behavior: append error message and return (thread, [error_message])
            error_text = f"I encountered an error: {str(e)}"
            error_msg = Message(
                role='assistant', 
                content=error_text,
                source={
                    "id": self.name,
                    "name": self.name,
                    "type": "agent",
                    "attributes": {
                        "model": self.model_name,
                        "purpose": str(self.purpose)
                    }
                }
            )
            error_msg.metrics = {"error": str(e)}
            thread.add_message(error_msg)
            return thread, [error_msg]

    async def _get_thread(self, thread_or_id: Union[str, Thread]) -> Thread:
        """Get thread object from ID or return the thread object directly."""
        if isinstance(thread_or_id, str):
            if not self.thread_store:
                raise ValueError("Thread store is required when passing thread ID")
            thread = await self.thread_store.get(thread_or_id)
            if not thread:
                raise ValueError(f"Thread with ID {thread_or_id} not found")
            return thread
        return thread_or_id

    def _serialize_tool_calls(self, tool_calls: Optional[List[Any]]) -> Optional[List[Dict]]:
        """Serialize tool calls to a list of dictionaries.

        Args:
            tool_calls: List of tool calls to serialize, or None

        Returns:
            Optional[List[Dict]]: Serialized tool calls, or None if input is None
        """
        if tool_calls is None:
            return None
            
        serialized = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                # Ensure ID is present
                if not tool_call.get('id'):
                    continue
                serialized.append(tool_call)
            else:
                # Ensure ID is present
                if not hasattr(tool_call, 'id') or not tool_call.id:
                    continue
                serialized.append({
                    "id": str(tool_call.id),
                    "type": str(tool_call.type),
                    "function": {
                        "name": str(tool_call.function.name),
                        "arguments": str(tool_call.function.arguments)
                    }
                })
        return serialized if serialized else None

    @weave.op()
    async def run(
        self, 
        thread_or_id: Union[Thread, str],
        response_type: Optional[Type[BaseModel]] = None,
        response_format: Optional[Literal["json"]] = None,
        tool_context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute the agent and return the complete result.
        
        This method runs the agent to completion, handling tool calls,
        managing conversation flow, and returning the final result with
        all messages and execution details.
        
        Args:
            thread_or_id: Thread object or thread ID to process. The thread will be
                         modified in-place with new messages.
            response_type: Optional Pydantic model class for structured output.
                          When provided, overrides the agent's default response_type.
                          The agent will instruct the LLM to respond in JSON matching
                          this schema, and the response will be validated and returned
                          in result.structured_data. If None, uses the agent's default.
            response_format: Optional format for the response. Currently supports:
                            - "json": Forces the LLM to respond with valid JSON (any structure).
                              Unlike response_type, this doesn't validate against a schema.
                              Tools still work in this mode.
            tool_context: Optional dictionary of dependencies to inject into tools.
                         Tools that have 'ctx' or 'context' as their first parameter
                         will receive this context. Enables dependency injection for
                         databases, API clients, user info, etc.
            
        Returns:
            AgentResult containing the updated thread, new messages,
            final output, and complete execution details. When response_type
            is provided, result.structured_data contains the validated Pydantic model.
        
        Raises:
            ValueError: If thread_id is provided but thread is not found
            StructuredOutputError: If response_type is provided and validation fails
                                  after all retry attempts
            ToolContextError: If a tool requires context but tool_context was not provided
            Exception: Re-raises any unhandled exceptions during execution,
                      but execution details are still available in the result
                      
        Example:
            # Basic usage
            result = await agent.run(thread)
            print(f"Response: {result.content}")
            
            # With structured output
            class Invoice(BaseModel):
                total: float
                items: list[str]
            
            result = await agent.run(thread, response_type=Invoice)
            invoice = result.structured_data  # Validated Invoice instance
            
            # Simple JSON mode (any valid JSON, tools still work)
            result = await agent.run(thread, response_format="json")
            data = json.loads(result.content)  # Parse the JSON yourself
            
            # With tool context
            result = await agent.run(
                thread, 
                tool_context={"db": database, "user_id": current_user.id}
            )
        """
        logging.getLogger(__name__).debug("Agent.run() called (non-streaming mode)")
        
        # Use provided response_type, or fall back to agent's default
        effective_response_type = response_type if response_type is not None else self.response_type
        
        # Validate that response_type and response_format are not both specified
        if effective_response_type is not None and response_format is not None:
            raise ValueError(
                "Cannot specify both response_type and response_format. "
                "Use response_type for Pydantic-validated structured output, "
                "or response_format='json' for simple JSON mode without validation."
            )
        
        # Merge agent-level and run-level tool contexts
        # Run-level context overrides agent-level context
        if self.tool_context is not None or tool_context is not None:
            merged_context = {}
            if self.tool_context:
                merged_context.update(self.tool_context)
            if tool_context:
                merged_context.update(tool_context)
            self._tool_context = merged_context
        else:
            self._tool_context = None
        
        # Store response_format for use by step()
        self._response_format = response_format
        
        try:
            if effective_response_type is not None:
                return await self._run_with_structured_output(thread_or_id, effective_response_type)
            else:
                return await self._run_complete(thread_or_id)
        finally:
            # Clear tool context and response_format after execution
            self._tool_context = None
            self._response_format = None
    
    # Backwards compatibility alias
    go = run
    
    def _create_output_tool(self, response_type: Type[BaseModel]) -> Dict[str, Any]:
        """Create an output tool definition from a Pydantic model.
        
        This tool is used internally to get structured output while still
        allowing other tools to work. The model calls this tool when it's
        ready to provide its final answer.
        
        Args:
            response_type: Pydantic model class defining the output schema
            
        Returns:
            Tool definition dict in OpenAI format
        """
        schema = response_type.model_json_schema()
        schema_name = response_type.__name__
        
        return {
            "type": "function",
            "function": {
                "name": f"__{schema_name}_output__",
                "description": (
                    f"Submit your final {schema_name} response. "
                    f"Call this tool ONLY when you have gathered all necessary information "
                    f"and are ready to provide your structured answer. "
                    f"The arguments must match the {schema_name} schema exactly."
                ),
                "parameters": schema
            }
        }
    
    async def _run_with_structured_output(
        self,
        thread_or_id: Union[Thread, str],
        response_type: Type[BaseModel]
    ) -> AgentResult:
        """Run agent expecting structured output matching response_type schema.
        
        This method uses the output-tool pattern:
        1. Creates an output tool from the Pydantic schema
        2. Runs the normal tool loop (agent can use all tools)
        3. When the model calls the output tool, validates and returns
        4. Retries on validation failure if retry_config is set
        
        This approach allows tools and structured output to work together.
        
        Args:
            thread_or_id: Thread object or thread ID to process
            response_type: Pydantic model class defining the expected output schema
            
        Returns:
            AgentResult with structured_data containing the validated model instance
            
        Raises:
            StructuredOutputError: If validation fails after all retry attempts
        """
        from pydantic import ValidationError
        
        # Get the thread
        thread = await self._get_thread(thread_or_id)
        
        # Create output tool
        output_tool = self._create_output_tool(response_type)
        output_tool_name = output_tool["function"]["name"]
        schema_name = response_type.__name__
        
        # Create tools list with output tool added (don't mutate instance state)
        tools_with_output = self._processed_tools + [output_tool]
        
        # Create system prompt with output tool instruction (don't mutate instance state)
        output_instruction = (
            f"\n\n<structured_output_instruction>\n"
            f"IMPORTANT: When you have gathered all necessary information and are ready to "
            f"provide your final answer, you MUST call the `{output_tool_name}` tool with "
            f"your response matching the {schema_name} schema. Do NOT respond with plain text "
            f"for your final answer - use the output tool instead.\n"
            f"</structured_output_instruction>"
        )
        system_prompt_with_output = self._system_prompt + output_instruction
        
        # Determine max retries
        max_retries = 0
        if self.retry_config and self.retry_config.retry_on_validation_error:
            max_retries = self.retry_config.max_retries
        
        retry_count = 0
        last_validation_errors = []
        last_response = None
        retry_history = []
        new_messages = []
        
        try:
            # Reset iteration count
            self._iteration_count = 0
            
            while self._iteration_count < self.max_tool_iterations:
                # Get completion with tools, system prompt, and tool_choice overrides
                # tool_choice="required" forces the model to call a tool (like Pydantic AI does)
                response, metrics = await self.step(
                    thread, 
                    tools=tools_with_output,
                    system_prompt=system_prompt_with_output,
                    tool_choice="required"
                )
                
                if not response or not hasattr(response, 'choices') or not response.choices:
                    raise StructuredOutputError(
                        "No response received from LLM",
                        validation_errors=[],
                        last_response=None
                    )
                
                # Process response
                assistant_message = response.choices[0].message
                content = assistant_message.content or ""
                tool_calls = getattr(assistant_message, 'tool_calls', None)
                has_tool_calls = tool_calls is not None and len(tool_calls) > 0
                
                # Create and add assistant message if there's content or tool calls
                if content or has_tool_calls:
                    message = Message(
                        role="assistant",
                        content=content,
                        tool_calls=self._serialize_tool_calls(tool_calls) if has_tool_calls else None,
                        source=self._create_assistant_source(include_version=True),
                        metrics=metrics
                    )
                    thread.add_message(message)
                    new_messages.append(message)
                
                if has_tool_calls:
                    # Separate output tool call from regular tool calls
                    # Store (tool_call, tool_name) tuples to avoid re-extracting names
                    output_tool_call = None
                    regular_tool_calls = []  # List of (tool_call, tool_name) tuples
                    
                    for tool_call in tool_calls:
                        tool_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call['function']['name']
                        if tool_name == output_tool_name:
                            output_tool_call = tool_call
                        else:
                            regular_tool_calls.append((tool_call, tool_name))
                    
                    # Process regular tool calls first
                    should_break = False
                    for tool_call, tool_name in regular_tool_calls:
                        result = await self._handle_tool_execution(tool_call)
                        tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                        thread.add_message(tool_message)
                        new_messages.append(tool_message)
                        if break_iteration:
                            should_break = True
                    
                    # If an interrupt tool was called, save and continue to next iteration
                    if should_break and not output_tool_call:
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        self._iteration_count += 1
                        continue
                    
                    # Now process the output tool call if present
                    if output_tool_call:
                        tool_id = output_tool_call.id if hasattr(output_tool_call, 'id') else output_tool_call.get('id')
                        args_str = output_tool_call.function.arguments if hasattr(output_tool_call, 'function') else output_tool_call['function']['arguments']
                        
                        # Parse and validate the output
                        try:
                            raw_json = json.loads(args_str) if isinstance(args_str, str) else args_str
                            last_response = raw_json
                            
                            validated_data = response_type.model_validate(raw_json)
                            
                            # Success! Create the tool response message
                            tool_message = Message(
                                role="tool",
                                name=output_tool_name,
                                content=json.dumps({"status": "success", "message": "Output accepted"}),
                                tool_call_id=tool_id,
                                source=self._create_tool_source(output_tool_name)
                            )
                            thread.add_message(tool_message)
                            new_messages.append(tool_message)
                            
                            # Build result metrics
                            result_metrics = {}
                            if retry_count > 0:
                                result_metrics["structured_output"] = {
                                    "validation_retries": retry_count,
                                    "retry_history": retry_history
                                }
                            
                            # Save thread if store is configured
                            if self.thread_store:
                                await self.thread_store.save(thread)
                            
                            return AgentResult(
                                thread=thread,
                                new_messages=new_messages,
                                content=json.dumps(raw_json),
                                structured_data=validated_data,
                                validation_retries=retry_count,
                                retry_history=retry_history if retry_history else None
                            )
                            
                        except json.JSONDecodeError as e:
                            last_validation_errors = [{"type": "json_error", "msg": str(e)}]
                            retry_count += 1
                            retry_history.append({
                                "attempt": retry_count,
                                "error_type": "json_parse_error",
                                "errors": last_validation_errors,
                                "response_preview": str(args_str)[:500]
                            })
                            
                            if retry_count > max_retries:
                                raise StructuredOutputError(
                                    f"Failed to parse output tool arguments after {retry_count} attempts: {e}",
                                    validation_errors=last_validation_errors,
                                    last_response=args_str
                                )
                            
                            # Add error message to prompt retry
                            error_msg = Message(
                                role="tool",
                                name=output_tool_name,
                                content=json.dumps({
                                    "status": "error",
                                    "message": f"Invalid JSON: {e}. Please try again with valid JSON."
                                }),
                                tool_call_id=tool_id,
                                source=self._create_tool_source(output_tool_name)
                            )
                            thread.add_message(error_msg)
                            new_messages.append(error_msg)
                            
                            if self.retry_config:
                                await asyncio.sleep(self.retry_config.backoff_base_seconds * retry_count)
                                
                        except ValidationError as e:
                            last_validation_errors = e.errors()
                            retry_count += 1
                            
                            response_str = json.dumps(raw_json) if isinstance(raw_json, dict) else str(raw_json)
                            retry_history.append({
                                "attempt": retry_count,
                                "error_type": "validation_error",
                                "errors": last_validation_errors,
                                "response_preview": response_str[:500]
                            })
                            
                            logging.getLogger(__name__).warning(
                                f"Structured output validation failed (attempt {retry_count}/{max_retries + 1}): {e}"
                            )
                            
                            if retry_count > max_retries:
                                raise StructuredOutputError(
                                    f"Validation failed after {retry_count} attempts",
                                    validation_errors=last_validation_errors,
                                    last_response=raw_json
                                )
                            
                            # Add validation error message to prompt retry
                            error_msg = Message(
                                role="tool",
                                name=output_tool_name,
                                content=json.dumps({
                                    "status": "error",
                                    "message": f"Validation failed: {e}. Please correct and try again.",
                                    "errors": [{"loc": list(err.get("loc", [])), "msg": err.get("msg", "")} for err in last_validation_errors[:5]]
                                }),
                                tool_call_id=tool_id,
                                source=self._create_tool_source(output_tool_name)
                            )
                            thread.add_message(error_msg)
                            new_messages.append(error_msg)
                            
                            if self.retry_config:
                                await asyncio.sleep(self.retry_config.backoff_base_seconds * retry_count)
                    
                    # Save after processing tool calls
                    if self.thread_store:
                        await self.thread_store.save(thread)
                else:
                    # No tool calls - model responded with plain text instead of using output tool
                    # Add a system reminder message to prompt the model to use the output tool
                    reminder = Message(
                        role="system",
                        content=(
                            f"REMINDER: You must provide your response by calling the `{output_tool_name}` tool. "
                            f"Do not respond with plain text. Use the output tool with arguments "
                            f"matching the {schema_name} schema."
                        ),
                        source={
                            "type": "agent",
                            "id": self.name,
                            "name": "structured_output_reminder"
                        }
                    )
                    thread.add_message(reminder)
                    new_messages.append(reminder)
                    
                    if self.thread_store:
                        await self.thread_store.save(thread)
                    
                    # If this is the last iteration, we'll fall through and raise an error
                    if self._iteration_count >= self.max_tool_iterations - 1:
                        break
                
                self._iteration_count += 1
            
            # Max iterations reached without output tool being called
            raise StructuredOutputError(
                f"Model did not call output tool within {self.max_tool_iterations} iterations. "
                f"Ensure the model understands it must use the {output_tool_name} tool to provide structured output.",
                validation_errors=[{"type": "no_output_tool_call", "msg": "Output tool was never called"}],
                last_response=last_response
            )
            
        except StructuredOutputError:
            raise
        except Exception as e:
            raise StructuredOutputError(
                f"Unexpected error during structured output: {e}",
                validation_errors=[{"type": "unexpected_error", "msg": str(e)}],
                last_response=last_response
            )
    
    @weave.op(accumulator=_weave_stream_accumulator)
    async def stream(
        self,
        thread_or_id: Union[Thread, str],
        mode: Literal["events", "openai", "vercel", "vercel_objects"] = "events",
        tool_context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Union[ExecutionEvent, Any, str], None]:
        """
        Stream agent execution events or raw chunks in real-time.
        
        This method yields events as the agent executes, providing
        real-time visibility into the agent's reasoning, tool usage,
        and message generation.
        
        Args:
            thread_or_id: Thread object or thread ID to process. The thread will be
                         modified in-place with new messages.
            mode: Streaming mode:
                  - "events" (default): Yields ExecutionEvent objects with detailed telemetry
                  - "openai": Yields raw LiteLLM chunks in OpenAI-compatible format
                  - "vercel": Yields SSE strings in Vercel AI SDK Data Stream Protocol format
                  - "vercel_objects": Yields chunk dicts for Vercel AI SDK (for marimo, etc.)
            tool_context: Optional dictionary of dependencies to inject into tools.
                         Tools that have 'ctx' or 'context' as their first parameter
                         will receive this context.
            
        Yields:
            If mode="events":
                ExecutionEvent objects including LLM_REQUEST, LLM_RESPONSE, 
                TOOL_SELECTED, TOOL_RESULT, MESSAGE_CREATED, and EXECUTION_COMPLETE events.
            
            If mode="openai":
                Raw LiteLLM chunk objects passed through unmodified for direct
                integration with OpenAI-compatible clients.
            
            If mode="vercel":
                SSE-formatted strings compatible with Vercel AI SDK's useChat hook.
                See: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol#data-stream-protocol
            
            If mode="vercel_objects":
                Chunk dictionaries (without SSE wrapping) for frameworks like marimo's
                mo.ui.chat(vercel_messages=True) that consume Vercel chunks directly.
        
        Raises:
            ValueError: If thread_id is provided but thread is not found, or
                       if an invalid mode is provided
            ToolContextError: If a tool requires context but tool_context was not provided
            Exception: Re-raises any unhandled exceptions during execution
                      
        Example:
            # Event streaming (observability)
            async for event in agent.stream(thread):
                if event.type == EventType.MESSAGE_CREATED:
                    print(f"New message: {event.data['message'].content}")
            
            # OpenAI-compatible chunk streaming
            async for chunk in agent.stream(thread, mode="openai"):
                if hasattr(chunk.choices[0].delta, 'content'):
                    print(chunk.choices[0].delta.content, end="")
            
            # Vercel AI SDK streaming (for React/Next.js frontends)
            async for sse_chunk in agent.stream(thread, mode="vercel"):
                yield sse_chunk  # Send directly to HTTP response
            
            # marimo mo.ui.chat() integration
            async for chunk in agent.stream(thread, mode="vercel_objects"):
                yield chunk  # Chunk dicts for vercel_messages=True
        """
        # Merge agent-level and run-level tool contexts
        # Run-level context overrides agent-level context
        if self.tool_context is not None or tool_context is not None:
            merged_context = {}
            if self.tool_context:
                merged_context.update(self.tool_context)
            if tool_context:
                merged_context.update(tool_context)
            self._tool_context = merged_context
        else:
            self._tool_context = None
        
        try:
            # Resolve thread from ID if needed
            thread = await self._get_thread(thread_or_id)
            
            # Get the streaming mode and delegate
            from tyler.streaming import get_stream_mode
            stream_mode = get_stream_mode(mode)
            
            logging.getLogger(__name__).debug(f"Agent.stream() called with mode='{mode}'")
            async for item in stream_mode.stream(self, thread):
                yield item
        finally:
            # Clear tool context after execution
            self._tool_context = None
    
    @weave.op(accumulator=_weave_stream_accumulator)
    async def step_stream(
        self,
        thread: Thread,
        mode: Literal["events", "openai", "vercel", "vercel_objects"] = "events",
    ) -> AsyncGenerator[Union[ExecutionEvent, Any, str], None]:
        """Execute a single streaming step (one LLM streamed completion + resulting tool execution).

        This is the streaming equivalent of `step()` for `run()`: tool execution happens
        *inside* this generator so tool ops appear as children of the step span in Weave.
        
        Note: For most use cases, use `stream()` which handles multi-step iteration.
        This method is for advanced use cases where you need step-by-step control.
        """
        # Reset per-step flags
        self._last_step_stream_had_tool_calls = False
        self._last_step_stream_should_continue = False

        if mode == "events":
            from tyler.streaming.events import events_stream_mode
            async for event in events_stream_mode._step_stream(self, thread):
                yield event
        elif mode == "openai":
            from tyler.streaming.openai import openai_stream_mode
            async for chunk in openai_stream_mode._step_stream(self, thread):
                yield chunk
        elif mode == "vercel":
            from tyler.streaming.vercel import vercel_stream_mode
            async for sse in vercel_stream_mode._step_stream(self, thread):
                yield sse
        elif mode == "vercel_objects":
            from tyler.streaming.vercel_objects import vercel_objects_stream_mode
            async for chunk in vercel_objects_stream_mode._step_stream(self, thread):
                yield chunk
        else:
            raise ValueError(
                f"Invalid streaming mode: '{mode}'. Must be one of: 'events', 'openai', 'vercel', 'vercel_objects'"
            )

    async def _get_streaming_completion(
        self,
        thread: Thread,
        *,
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        tool_choice: Optional[str] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Get a streaming completion and initial metrics without creating an `Agent.step` span.

        We intentionally do not call `self.step(stream=True)` here because `step` is a traced op.
        Streaming traces should look like:
            Agent.stream -> Agent.step_stream -> openai.chat.completions.create -> tool ops
        """
        # Backward-compat for tests/user code that patches `agent.step` to simulate failures.
        # `unittest.mock` objects often report `hasattr(x, "resolve_fn") == True` due to dynamic attrs,
        # so we detect mocks by type instead of attribute presence.
        patched_step = getattr(self, "step", None)
        if patched_step is not None:
            try:
                from unittest.mock import Mock  # type: ignore
            except Exception:  # pragma: no cover
                Mock = ()  # type: ignore
            if isinstance(patched_step, Mock):  # type: ignore[arg-type]
                return await patched_step(thread, stream=True)

        thread_messages = await thread.get_messages_for_chat_completion(file_store=self.file_store)

        effective_tools = tools if tools is not None else self._processed_tools
        effective_system_prompt = system_prompt if system_prompt is not None else self._system_prompt

        completion_messages = [{"role": "system", "content": effective_system_prompt}] + thread_messages
        completion_params = self.completion_handler._build_completion_params(
            messages=completion_messages,
            tools=effective_tools,
            stream=True,
        )

        if self._response_format == "json":
            completion_params["response_format"] = {"type": "json_object"}

        if tool_choice is not None and effective_tools:
            completion_params["tool_choice"] = tool_choice

        api_start_time = datetime.now(timezone.utc)

        # Backward-compatible behavior for tests that patch `_get_completion` with `.call(...)`
        if hasattr(self._get_completion, "call"):
            response, call = await self._get_completion.call(self, **completion_params)
        else:
            response = await self._get_completion(**completion_params)
            call = None

        metrics = self.completion_handler._build_metrics(api_start_time, response, call)
        return response, metrics

    async def _run_complete(self, thread_or_id: Union[Thread, str]) -> AgentResult:
        """Non-streaming implementation that collects all events and returns AgentResult."""
        # Initialize execution tracking
        events = []
        start_time = datetime.now(timezone.utc)
        new_messages = []
        
        # Helper to record events
        def record_event(event_type: EventType, data: Dict[str, Any], attributes=None):
            events.append(ExecutionEvent(
                type=event_type,
                timestamp=datetime.now(timezone.utc),
                data=data,
                attributes=attributes
            ))
            
        # Reset iteration count at the beginning of each go call
        self._iteration_count = 0
        # Clear tool attributes cache for fresh request
        self._tool_attributes_cache.clear()
            
        thread = None
        try:
            # Get thread
            try:
                thread = await self._get_thread(thread_or_id)
            except ValueError:
                raise  # Re-raise ValueError for thread not found
            
            # Record iteration start
            record_event(EventType.ITERATION_START, {
                "iteration_number": 0,
                "max_iterations": self.max_tool_iterations
            })
            
            # Check if we've already hit max iterations
            if self._iteration_count >= self.max_tool_iterations:
                message = Message(
                    role="assistant",
                    content="Maximum tool iteration count reached. Stopping further tool calls.",
                    source=self._create_assistant_source(include_version=False)
                )
                thread.add_message(message)
                new_messages.append(message)
                record_event(EventType.MESSAGE_CREATED, {"message": message})
                record_event(EventType.ITERATION_LIMIT, {"iterations_used": self._iteration_count})
                if self.thread_store:
                    await self.thread_store.save(thread)
                # Nothing else to do; avoid duplicate saves and return immediately.
                return AgentResult(
                    thread=thread,
                    new_messages=new_messages,
                    content=message.content,
                )
            
            else:
                # Main iteration loop
                while self._iteration_count < self.max_tool_iterations:
                    try:
                        # Record LLM request
                        record_event(EventType.LLM_REQUEST, {
                            "message_count": len(thread.messages),
                            "model": self.model_name,
                            "temperature": self.temperature
                        })
                        
                        # Get completion (+ execute resulting tools *inside the step* so tool
                        # ops nest under the step span for tracing). We use an internal flag
                        # rather than a kwarg so tests that patch `step()` with a side_effect
                        # (without accepting extra kwargs) keep working.
                        self._execute_tools_in_step = True
                        try:
                            response, metrics = await self.step(thread)
                        finally:
                            self._execute_tools_in_step = False

                        # Backward-compatible step error behavior: some callers/tests expect
                        # `step()` to append an assistant error message and return
                        # `(thread, [error_message])` instead of raising.
                        if isinstance(response, Thread):
                            thread = response
                            if isinstance(metrics, list):
                                for msg in metrics:
                                    new_messages.append(msg)
                                    record_event(EventType.MESSAGE_CREATED, {"message": msg})
                            record_event(EventType.EXECUTION_ERROR, {
                                "error_type": "StepError",
                                "message": metrics[-1].content if isinstance(metrics, list) and metrics else "Step error"
                            })
                            if self.thread_store:
                                await self.thread_store.save(thread)
                            break
                        
                        if not response or not hasattr(response, 'choices') or not response.choices:
                            error_msg = "No response received from chat completion"
                            logging.getLogger(__name__).error(error_msg)
                            record_event(EventType.EXECUTION_ERROR, {
                                "error_type": "NoResponse",
                                "message": error_msg
                            })
                            message = self._create_error_message(error_msg)
                            thread.add_message(message)
                            new_messages.append(message)
                            record_event(EventType.MESSAGE_CREATED, {"message": message})
                            if self.thread_store:
                                await self.thread_store.save(thread)
                            break
                        
                        # Process response
                        assistant_message = response.choices[0].message
                        content = assistant_message.content or ""
                        tool_calls = getattr(assistant_message, 'tool_calls', None)
                        has_tool_calls = tool_calls is not None and len(tool_calls) > 0

                        # Record LLM response
                        record_event(EventType.LLM_RESPONSE, {
                            "content": content,
                            "tool_calls": self._serialize_tool_calls(tool_calls) if has_tool_calls else None,
                            "tokens": metrics.get("usage", {}),
                            "latency_ms": metrics.get("timing", {}).get("latency", 0)
                        })
                        
                        # Create assistant message
                        if content or has_tool_calls:
                            message = Message(
                                role="assistant",
                                content=content,
                                tool_calls=self._serialize_tool_calls(tool_calls) if has_tool_calls else None,
                                source=self._create_assistant_source(include_version=True),
                                metrics=metrics
                            )
                            thread.add_message(message)
                            new_messages.append(message)
                            record_event(EventType.MESSAGE_CREATED, {"message": message})

                        # Process tool calls
                        should_break = False
                        if has_tool_calls:
                            tool_execution_results = metrics.get("_tool_execution_results", {}) or {}
                            tool_execution_durations_ms = metrics.get("_tool_execution_durations_ms", {}) or {}

                            # Backward-compatibility: if step() did not execute tools (e.g. because
                            # it was patched in a test), execute them here so behavior matches the
                            # pre-refactor run loop.
                            if not tool_execution_results:
                                tool_execution_results = {}
                                tool_execution_durations_ms = {}
                                for tc in tool_calls:
                                    try:
                                        tc_id = tc.id if hasattr(tc, "id") else tc.get("id")
                                    except Exception:
                                        tc_id = None
                                    if not tc_id:
                                        continue
                                    try:
                                        # _handle_tool_execution reads `self._tool_context` internally.
                                        start = datetime.now(timezone.utc)
                                        tool_execution_results[str(tc_id)] = await self._handle_tool_execution(tc)
                                        tool_execution_durations_ms[str(tc_id)] = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                                    except Exception as tool_exc:
                                        tool_execution_results[str(tc_id)] = tool_exc
                                        tool_execution_durations_ms[str(tc_id)] = (datetime.now(timezone.utc) - start).total_seconds() * 1000

                            # Record tool selections
                            for tool_call in tool_calls:
                                tool_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call['function']['name']
                                tool_id = tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id')
                                args = tool_call.function.arguments if hasattr(tool_call, 'function') else tool_call['function']['arguments']
                                
                                # Parse arguments
                                try:
                                    parsed_args = json.loads(args) if isinstance(args, str) else args
                                except (json.JSONDecodeError, TypeError, AttributeError):
                                    parsed_args = {}
                                
                                record_event(EventType.TOOL_SELECTED, {
                                    "tool_name": tool_name,
                                    "arguments": parsed_args,
                                    "tool_call_id": tool_id
                                })
                            
                            # Process results (tools were executed inside step)
                            for tool_call in tool_calls:
                                tool_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call['function']['name']
                                tool_id = tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id')
                                
                                key = str(tool_id) if tool_id is not None else None
                                duration_ms = tool_execution_durations_ms.get(key) if key else None

                                # Distinguish "missing result" from "tool returned None":
                                # - Missing: tool call id not present in results mapping
                                # - Present: tool executed; its return value may legitimately be None
                                if not key or key not in tool_execution_results:
                                    result = RuntimeError("Tool result missing")
                                    record_event(EventType.TOOL_ERROR, {
                                        "tool_name": tool_name,
                                        "error": "Tool result missing",
                                        "tool_call_id": tool_id
                                    })
                                else:
                                    result = tool_execution_results.get(key)
                                if isinstance(result, Exception):
                                    record_event(EventType.TOOL_ERROR, {
                                        "tool_name": tool_name,
                                        "error": str(result),
                                        "tool_call_id": tool_id
                                    })
                                else:
                                        # Extract result content (None is a valid successful return)
                                    if isinstance(result, tuple) and len(result) >= 1:
                                        result_content = str(result[0])
                                    else:
                                        result_content = str(result)
                                    
                                    record_event(EventType.TOOL_RESULT, {
                                        "tool_name": tool_name,
                                        "result": result_content,
                                        "tool_call_id": tool_id,
                                            "duration_ms": duration_ms
                                    })
                                
                                # Process tool result into message
                                tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                                thread.add_message(tool_message)
                                new_messages.append(tool_message)
                                record_event(EventType.MESSAGE_CREATED, {"message": tool_message})
                                
                                if break_iteration:
                                    should_break = True
                                
                        # Save after processing all tool calls but before next completion
                        if self.thread_store:
                            await self.thread_store.save(thread)
                            
                        if should_break:
                            break
                    
                        # If no tool calls, we are done
                        if not has_tool_calls:
                            break
                        
                        self._iteration_count += 1

                    except Exception as e:
                        error_msg = f"Error during chat completion: {str(e)}"
                        logging.getLogger(__name__).error(error_msg)
                        record_event(EventType.EXECUTION_ERROR, {
                            "error_type": type(e).__name__,
                            "message": error_msg,
                            "traceback": None  # Could add traceback if needed
                        })
                        message = self._create_error_message(error_msg)
                        thread.add_message(message)
                        new_messages.append(message)
                        record_event(EventType.MESSAGE_CREATED, {"message": message})
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                
                # Check for max iterations
                if self._iteration_count >= self.max_tool_iterations:
                    message = self.message_factory.create_max_iterations_message()
                    thread.add_message(message)
                    new_messages.append(message)
                    record_event(EventType.MESSAGE_CREATED, {"message": message})
                    record_event(EventType.ITERATION_LIMIT, {"iterations_used": self._iteration_count})
                
            # Final save
            if self.thread_store:
                await self.thread_store.save(thread)
                
            # Record completion
            end_time = datetime.now(timezone.utc)
            total_tokens = sum(
                event.data.get("tokens", {}).get("total_tokens", 0)
                for event in events
                if event.type == EventType.LLM_RESPONSE
            )
            
            record_event(EventType.EXECUTION_COMPLETE, {
                "duration_ms": (end_time - start_time).total_seconds() * 1000,
                "total_tokens": total_tokens
            })
            
            # Extract final output
            output = None
            for msg in reversed(new_messages):
                if msg.role == "assistant" and msg.content:
                    output = msg.content
                    break
            
            return AgentResult(
                thread=thread,
                new_messages=new_messages,
                content=output
            )

        except ValueError:
            # Re-raise ValueError for thread not found
            raise
        except Exception as e:
            error_msg = f"Error processing thread: {str(e)}"
            logging.getLogger(__name__).error(error_msg)
            message = self._create_error_message(error_msg)
            
            if isinstance(thread_or_id, Thread):
                # If we were passed a Thread object directly, use it
                thread = thread_or_id
            elif thread is None:
                # If thread creation failed, create a new one
                thread = Thread()
                
            thread.add_message(message)
            new_messages.append(message)
            
            # Still try to return a result with error information
            if events is None:
                events = []
            record_event(EventType.EXECUTION_ERROR, {
                "error_type": type(e).__name__,
                "message": error_msg
            })
            
            if self.thread_store:
                await self.thread_store.save(thread)
            
            # Build result even with error
            end_time = datetime.now(timezone.utc)
            
            return AgentResult(
                thread=thread,
                new_messages=new_messages,
                content=None
            )

    def _create_tool_source(self, tool_name: str) -> Dict:
        """Creates a standardized source entity dict for tool messages."""
        return {
            "id": tool_name,
            "name": tool_name,
            "type": "tool",
            "attributes": {
                "agent_id": self.name
            }
        }

    def _create_assistant_source(self, include_version: bool = True) -> Dict:
        """Creates a standardized source entity dict for assistant messages."""
        attributes = {
            "model": self.model_name
        }
        
        return {
            "id": self.name,
            "name": self.name,
            "type": "agent",
            "attributes": attributes
        } 

    def _create_error_message(self, error_msg: str, source: Optional[Dict] = None) -> Message:
        """Create a standardized error message."""
        return self.message_factory.create_error_message(error_msg, source=source)
    
    def _process_tool_result(self, result: Any, tool_call: Any, tool_name: str) -> Tuple[Message, bool]:
        """
        Process a tool execution result and create a message.
        
        Returns:
            Tuple[Message, bool]: The tool message and whether to break iteration
        """
        timestamp = self._get_timestamp()
        
        # Handle exceptions in tool execution
        if isinstance(result, Exception):
            error_msg = f"Tool execution failed: {str(result)}"
            tool_message = Message(
                role="tool",
                name=tool_name,
                content=error_msg,
                tool_call_id=tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                source=self._create_tool_source(tool_name),
                metrics={
                    "timing": {
                        "started_at": timestamp,
                        "ended_at": timestamp,
                        "latency": 0
                    }
                }
            )
            return tool_message, False
        
        # Process successful result
        content = None
        files = []
        
        if isinstance(result, tuple):
            # Handle tuple return (content, files)
            content = str(result[0])
            if len(result) >= 2:
                files = result[1]
        else:
            # Handle any content type - just convert to string
            content = str(result)
            
        # Create tool message
        tool_message = Message(
            role="tool",
            name=tool_name,
            content=content,
            tool_call_id=tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
            source=self._create_tool_source(tool_name),
            metrics={
                "timing": {
                    "started_at": timestamp,
                    "ended_at": timestamp,
                    "latency": 0
                }
            }
        )
        
        # Add any files as attachments
        if files:
            logging.getLogger(__name__).debug(f"Processing {len(files)} files from tool result")
            for file_info in files:
                logging.getLogger(__name__).debug(f"Creating attachment for {file_info.get('filename')} with mime type {file_info.get('mime_type')}")
                attachment = Attachment(
                    filename=file_info["filename"],
                    content=file_info["content"],
                    mime_type=file_info["mime_type"]
                )
                tool_message.attachments.append(attachment)
        
        # Check if tool wants to break iteration
        tool_attributes = self._get_tool_attributes(tool_name)
        should_break = tool_attributes and tool_attributes.get('type') == 'interrupt'
        
        return tool_message, should_break
    
    async def connect_mcp(self) -> None:
        """
        Connect to MCP servers configured in the mcp field.
        
        Call this after creating an Agent with mcp config and before using it.
        Connects to servers, discovers tools, and registers them.
        
        Raises:
            ValueError: If connection fails and fail_silent=False for a server
        
        Example:
            agent = Agent(mcp={"servers": [...]})
            await agent.connect_mcp()  # Fails immediately if server unreachable
            result = await agent.go(thread)
        """
        if not self.mcp:
            logging.getLogger(__name__).warning("connect_mcp() called but no mcp config provided")
            return
        
        if self._mcp_connected:
            logging.getLogger(__name__).debug("MCP already connected, skipping")
            return
        
        logging.getLogger(__name__).info("Connecting to MCP servers...")
        
        from tyler.mcp.config_loader import _load_mcp_config
        
        # Connect and get tools (fails fast if server unreachable)
        mcp_tools, disconnect_callback = await _load_mcp_config(self.mcp)
        
        # Store disconnect callback
        self._mcp_disconnect = disconnect_callback
        
        # Merge MCP tools
        if not isinstance(self.tools, list):
            self.tools = list(self.tools) if self.tools else []
        self.tools.extend(mcp_tools)
        
        # Re-process tools with ToolManager
        from tyler.models.tool_manager import ToolManager
        tool_manager = ToolManager(tools=self.tools, agents=self.agents)
        self._processed_tools = tool_manager.register_all_tools()
        
        # Regenerate system prompt with new tools
        self._system_prompt = self._prompt.system_prompt(
            self.purpose, 
            self.name, 
            self.model_name, 
            self._processed_tools, 
            self.notes
        )
        
        self._mcp_connected = True
        logging.getLogger(__name__).info(f"MCP connected with {len(mcp_tools)} tools")
    
    async def cleanup(self) -> None:
        """
        Cleanup MCP connections and resources.
        
        Call this when done with the agent to properly close MCP connections.
        Agent can be reused by calling connect_mcp() again if needed.
        """
        if self._mcp_disconnect:
            await self._mcp_disconnect()
            self._mcp_disconnect = None
            self._mcp_connected = False 
