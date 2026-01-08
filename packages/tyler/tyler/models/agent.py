"""Agent model implementation"""
import os
import weave
from weave import Prompt
from pydantic import BaseModel, Field, PrivateAttr
import json
import types
import logging
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Tuple, Callable, Awaitable, overload, Literal, Type
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
from tyler.models.agent_prompt import AgentPrompt, _weave_stream_accumulator
from tyler.models.agent_helpers import AgentHelpersMixin
from tyler.models.agent_tools import AgentToolsMixin
from tyler.models.agent_streaming import AgentStreamingMixin
from tyler.models.agent_structured_output import AgentStructuredOutputMixin
import asyncio
from functools import partial


class Agent(
    AgentHelpersMixin,
    AgentToolsMixin,
    AgentStreamingMixin,
    AgentStructuredOutputMixin,
    BaseModel
):
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
    _pending_output_type: Optional[Type[BaseModel]] = PrivateAttr(default=None)
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
