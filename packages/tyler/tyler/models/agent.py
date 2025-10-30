"""Agent model implementation"""
import os
import weave
from weave import Model, Prompt
import json
import types
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Tuple, Callable, Awaitable, overload, Literal
from datetime import datetime, UTC
from pydantic import Field, PrivateAttr
from litellm import acompletion

# Direct imports to avoid circular dependency
from narrator import Thread, Message, Attachment, ThreadStore, FileStore

from tyler.utils.tool_runner import tool_runner
from tyler.utils.logging import get_logger
from tyler.models.execution import (
    EventType, ExecutionEvent,
    AgentResult
)
from tyler.models.tool_manager import ToolManager
from tyler.models.message_factory import MessageFactory
from tyler.models.completion_handler import CompletionHandler
import asyncio
from functools import partial

# Get configured logger
logger = get_logger(__name__)



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

    @weave.op()
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

class Agent(Model):
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
    
    _prompt: AgentPrompt = PrivateAttr(default_factory=AgentPrompt)
    _iteration_count: int = PrivateAttr(default=0)
    _processed_tools: List[Dict] = PrivateAttr(default_factory=list)
    _system_prompt: str = PrivateAttr(default="")
    _tool_attributes_cache: Dict[str, Optional[Dict[str, Any]]] = PrivateAttr(default_factory=dict)
    _mcp_connected: bool = PrivateAttr(default=False)
    _mcp_disconnect: Optional[Callable[[], Awaitable[None]]] = PrivateAttr(default=None)
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
        
        # Generate system prompt once at initialization
        self._prompt = AgentPrompt()
        # Initialize the tool attributes cache
        self._tool_attributes_cache = {}
        
        # Initialize MessageFactory for creating standardized messages
        self.message_factory = MessageFactory(self.name, self.model_name)
        
        # Initialize CompletionHandler for LLM communication
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
            logger.info(f"Creating default in-memory thread store for agent {self.name}")
            self.thread_store = ThreadStore()  # Uses in-memory backend by default
            
        if self.file_store is None:
            logger.info(f"Creating default file store for agent {self.name}")
            self.file_store = FileStore()  # Uses default settings

        # Now generate the system prompt including the tools
        self._system_prompt = self._prompt.system_prompt(
            self.purpose, 
            self.name, 
            self.model_name, 
            self._processed_tools, 
            self.notes
        )
    
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
        logger.info(f"Creating agent from config: {config_path or 'auto-discovered'}")
        config = load_config(config_path)
        
        # Apply overrides (replacement semantics - dict.update replaces)
        if overrides:
            logger.debug(f"Config overrides: {list(overrides.keys())}")
            config.update(overrides)
        
        # Create agent using standard __init__
        return cls(**config)

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now(UTC).isoformat()
    
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

    @weave.op()
    async def _handle_tool_execution(self, tool_call) -> dict:
        """
        Execute a single tool call and format the result message
        
        Args:
            tool_call: The tool call object from the model response
        
        Returns:
            dict: Formatted tool result message
        """
        normalized_tool_call = self._normalize_tool_call(tool_call)
        return await tool_runner.execute_tool_call(normalized_tool_call)
    
    @weave.op()
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
    async def step(self, thread: Thread, stream: bool = False) -> Tuple[Any, Dict]:
        """Execute a single step of the agent's processing.
        
        A step consists of:
        1. Getting a completion from the LLM
        2. Collecting metrics about the completion
        3. Processing any tool calls if present
        
        Args:
            thread: The thread to process
            stream: Whether to stream the response. Defaults to False.
            
        Returns:
            Tuple[Any, Dict]: The completion response and metrics.
        """
        # Get thread messages (these won't include system messages as they're filtered out)
        thread_messages = await thread.get_messages_for_chat_completion(file_store=self.file_store)
        
        # Use CompletionHandler to build parameters
        completion_messages = [{"role": "system", "content": self._system_prompt}] + thread_messages
        completion_params = self.completion_handler._build_completion_params(
            messages=completion_messages,
            tools=self._processed_tools,
            stream=stream
        )
        
        # Track API call time
        api_start_time = datetime.now(UTC)
        
        try:
            # Get completion with weave call tracking (kept for backward compatibility)
            response, call = await self._get_completion.call(self, **completion_params)
            
            # Use CompletionHandler to build metrics
            metrics = self.completion_handler._build_metrics(api_start_time, response, call)
            
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
                        "purpose": self.purpose
                    }
                }
            )
            error_msg.metrics = {"error": str(e)}
            thread.add_message(error_msg)
            return thread, [error_msg]

    @weave.op()
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
    async def _process_tool_call(self, tool_call, thread: Thread, new_messages: List[Message]) -> bool:
        """Process a single tool call and return whether to break the iteration."""
        # Get tool name based on tool_call type
        tool_name = tool_call['function']['name'] if isinstance(tool_call, dict) else tool_call.function.name

        logger.debug(f"Processing tool call: {tool_name}")
        
        # Get tool attributes before execution
        tool_attributes = self._get_tool_attributes(tool_name)

        # Execute the tool
        tool_start_time = datetime.now(UTC)
        try:
            result = await self._handle_tool_execution(tool_call)
            
            # Handle both tuple returns and single values
            content = None
            files = []
            
            if isinstance(result, tuple):
                # Handle tuple return (content, files)
                content = str(result[0])  # Simply convert first item to string
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
                tool_call_id=tool_call.get('id') if isinstance(tool_call, dict) else tool_call.id,
                source=self._create_tool_source(tool_name),
                metrics={
                    "timing": {
                        "started_at": tool_start_time.isoformat(),
                        "ended_at": datetime.now(UTC).isoformat(),
                        "latency": (datetime.now(UTC) - tool_start_time).total_seconds() * 1000
                    }
                }
            )
            
            # Add any files as attachments
            if files:
                logger.debug(f"Processing {len(files)} files from tool result")
                for file_info in files:
                    logger.debug(f"Creating attachment for {file_info.get('filename')} with mime type {file_info.get('mime_type')}")
                    attachment = Attachment(
                        filename=file_info["filename"],
                        content=file_info["content"],
                        mime_type=file_info["mime_type"]
                    )
                    tool_message.attachments.append(attachment)
            
            # Add message to thread and new_messages
            thread.add_message(tool_message)
            new_messages.append(tool_message)
            
            # Check if tool wants to break iteration
            if tool_attributes and tool_attributes.get('type') == 'interrupt':
                return True
            
            return False
        
        except Exception as e:
            # Handle tool execution error
            error_msg = f"Tool execution failed: {str(e)}"
            error_message = Message(
                role="tool",
                name=tool_name,
                content=f"Error: {e}",
                tool_call_id=tool_call.get('id') if isinstance(tool_call, dict) else tool_call.id,
                source=self._create_tool_source(tool_name),
                metrics={
                    "timing": {
                        "started_at": datetime.now(UTC).isoformat(),
                        "ended_at": datetime.now(UTC).isoformat(),
                        "latency": (datetime.now(UTC) - tool_start_time).total_seconds() * 1000
                    }
                }
            )
            # Add error message to thread and new_messages
            thread.add_message(error_message)
            new_messages.append(error_message)
            return False

    @weave.op()
    async def _handle_max_iterations(self, thread: Thread, new_messages: List[Message]) -> Tuple[Thread, List[Message]]:
        """Handle the case when max iterations is reached."""
        message = self.message_factory.create_max_iterations_message()
        thread.add_message(message)
        new_messages.append(message)
        if self.thread_store:
            await self.thread_store.save(thread)
        return thread, [m for m in new_messages if m.role != "user"]

    @weave.op()
    async def run(
        self, 
        thread_or_id: Union[Thread, str]
    ) -> AgentResult:
        """
        Execute the agent and return the complete result.
        
        This method runs the agent to completion, handling tool calls,
        managing conversation flow, and returning the final result with
        all messages and execution details.
        
        Args:
            thread_or_id: Thread object or thread ID to process. The thread will be
                         modified in-place with new messages.
            
        Returns:
            AgentResult containing the updated thread, new messages,
            final output, and complete execution details.
        
        Raises:
            ValueError: If thread_id is provided but thread is not found
            Exception: Re-raises any unhandled exceptions during execution,
                      but execution details are still available in the result
                      
        Example:
            result = await agent.run(thread)
            print(f"Response: {result.content}")
            print(f"New messages: {len(result.new_messages)}")
        """
        logger.debug("Agent.run() called (non-streaming mode)")
        return await self._run_complete(thread_or_id)
    
    # Backwards compatibility alias
    go = run
    
    @weave.op()
    async def stream(
        self,
        thread_or_id: Union[Thread, str],
        mode: Literal["events", "raw"] = "events"
    ) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
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
                  - "raw": Yields raw LiteLLM chunks in OpenAI-compatible format
            
        Yields:
            If mode="events":
                ExecutionEvent objects including LLM_REQUEST, LLM_RESPONSE, 
                TOOL_SELECTED, TOOL_RESULT, MESSAGE_CREATED, and EXECUTION_COMPLETE events.
            
            If mode="raw":
                Raw LiteLLM chunk objects passed through unmodified for direct
                integration with OpenAI-compatible clients.
        
        Raises:
            ValueError: If thread_id is provided but thread is not found, or
                       if an invalid mode is provided
            Exception: Re-raises any unhandled exceptions during execution
                      
        Example:
            # Event streaming (observability)
            async for event in agent.stream(thread):
                if event.type == EventType.MESSAGE_CREATED:
                    print(f"New message: {event.data['message'].content}")
            
            # Raw chunk streaming (OpenAI compatibility)
            async for chunk in agent.stream(thread, mode="raw"):
                if hasattr(chunk.choices[0].delta, 'content'):
                    print(chunk.choices[0].delta.content, end="")
        """
        if mode == "events":
            logger.debug("Agent.stream() called with mode='events'")
            async for event in self._stream_events(thread_or_id):
                yield event
        elif mode == "raw":
            logger.debug("Agent.stream() called with mode='raw'")
            async for chunk in self._stream_raw(thread_or_id):
                yield chunk
        else:
            raise ValueError(
                f"Invalid mode: {mode}. Must be 'events' or 'raw'"
            )
    
    @weave.op()
    async def _run_complete(self, thread_or_id: Union[Thread, str]) -> AgentResult:
        """Non-streaming implementation that collects all events and returns AgentResult."""
        # Initialize execution tracking
        events = []
        start_time = datetime.now(UTC)
        new_messages = []
        
        # Helper to record events
        def record_event(event_type: EventType, data: Dict[str, Any], attributes=None):
            events.append(ExecutionEvent(
                type=event_type,
                timestamp=datetime.now(UTC),
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
                        
                        # Get completion
                        response, metrics = await self.step(thread)
                        
                        if not response or not hasattr(response, 'choices') or not response.choices:
                            error_msg = "No response received from chat completion"
                            logger.error(error_msg)
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
                            
                            # Execute tools in parallel with timing
                            tool_start_times = {}
                            tool_tasks = []
                            
                            for tool_call in tool_calls:
                                tool_id = tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id')
                                tool_start_times[tool_id] = datetime.now(UTC)
                                tool_tasks.append(self._handle_tool_execution(tool_call))
                            
                            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
                            
                            # Process results
                            should_break = False
                            for i, result in enumerate(tool_results):
                                tool_call = tool_calls[i]
                                tool_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call['function']['name']
                                tool_id = tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id')
                                
                                # Calculate duration
                                tool_end_time = datetime.now(UTC)
                                tool_duration_ms = (tool_end_time - tool_start_times[tool_id]).total_seconds() * 1000
                                
                                # Record tool result or error
                                if isinstance(result, Exception):
                                    record_event(EventType.TOOL_ERROR, {
                                        "tool_name": tool_name,
                                        "error": str(result),
                                        "tool_call_id": tool_id
                                    })
                                else:
                                    # Extract result content
                                    if isinstance(result, tuple) and len(result) >= 1:
                                        result_content = str(result[0])
                                    else:
                                        result_content = str(result)
                                    
                                    record_event(EventType.TOOL_RESULT, {
                                        "tool_name": tool_name,
                                        "result": result_content,
                                        "tool_call_id": tool_id,
                                        "duration_ms": tool_duration_ms
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
                        logger.error(error_msg)
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
            end_time = datetime.now(UTC)
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
            logger.error(error_msg)
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
            end_time = datetime.now(UTC)
            
            return AgentResult(
                thread=thread,
                new_messages=new_messages,
                content=None
            )

    @weave.op()
    async def _stream_events(self, thread_or_id: Union[Thread, str]) -> AsyncGenerator[ExecutionEvent, None]:
        """Streaming implementation that yields ExecutionEvent objects in real-time."""
        try:
            # Get thread
            thread = await self._get_thread(thread_or_id)
            
            # Initialize tracking
            self._iteration_count = 0
            self._tool_attributes_cache.clear()
            current_content = []
            current_tool_calls = []
            current_tool_call = None
            current_tool_args: Dict[str, str] = {}
            start_time = datetime.now(UTC)
            new_messages = []
            
            # Helper: initialize per-tool_call argument buffer only once
            def _init_tool_arg_buffer(tool_call_id: str, initial_value: Optional[str], buffers: Dict[str, str]) -> None:
                if tool_call_id not in buffers:
                    buffers[tool_call_id] = initial_value or ""

            # Yield iteration start
            yield ExecutionEvent(
                type=EventType.ITERATION_START,
                timestamp=datetime.now(UTC),
                data={
                    "iteration_number": 0,
                    "max_iterations": self.max_tool_iterations
                }
            )
            
            # Check if we've already hit max iterations
            if self._iteration_count >= self.max_tool_iterations:
                message = self.message_factory.create_max_iterations_message()
                thread.add_message(message)
                new_messages.append(message)
                yield ExecutionEvent(
                    type=EventType.MESSAGE_CREATED,
                    timestamp=datetime.now(UTC),
                    data={"message": message}
                )
                yield ExecutionEvent(
                    type=EventType.ITERATION_LIMIT,
                    timestamp=datetime.now(UTC),
                    data={"iterations_used": self._iteration_count}
                )
                if self.thread_store:
                    await self.thread_store.save(thread)
                return
            
            # Main iteration loop
            while self._iteration_count < self.max_tool_iterations:
                try:
                    # Yield LLM request event
                    yield ExecutionEvent(
                        type=EventType.LLM_REQUEST,
                        timestamp=datetime.now(UTC),
                        data={
                            "message_count": len(thread.messages),
                            "model": self.model_name,
                            "temperature": self.temperature
                        }
                    )
                    
                    # Get streaming response
                    streaming_response, metrics = await self.step(thread, stream=True)
                    
                    if not streaming_response:
                        error_msg = "No response received from chat completion"
                        logger.error(error_msg)
                        yield ExecutionEvent(
                            type=EventType.EXECUTION_ERROR,
                            timestamp=datetime.now(UTC),
                            data={
                                "error_type": "NoResponse",
                                "message": error_msg
                            }
                        )
                        message = self._create_error_message(error_msg)
                        thread.add_message(message)
                        new_messages.append(message)
                        yield ExecutionEvent(
                            type=EventType.MESSAGE_CREATED,
                            timestamp=datetime.now(UTC),
                            data={"message": message}
                        )
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                    
                    # Process streaming chunks
                    current_content = []
                    current_thinking = []  # Track thinking/reasoning tokens
                    current_tool_calls = []
                    current_tool_call = None
                    
                    async for chunk in streaming_response:
                        if not hasattr(chunk, 'choices') or not chunk.choices:
                            continue
                        
                        delta = chunk.choices[0].delta
                        
                        # Handle content chunks
                        if hasattr(delta, 'content') and delta.content is not None:
                            current_content.append(delta.content)
                            yield ExecutionEvent(
                                type=EventType.LLM_STREAM_CHUNK,
                                timestamp=datetime.now(UTC),
                                data={"content_chunk": delta.content}
                            )
                        
                        # Handle thinking/reasoning chunks (LiteLLM v1.63.0+ standardization)
                        thinking_content = None
                        thinking_type = None
                        
                        # Check for LiteLLM standardized field (v1.63.0+)
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                            thinking_content = delta.reasoning_content
                            thinking_type = "reasoning"
                        # Fallback: Anthropic-specific field
                        elif hasattr(delta, 'thinking') and delta.thinking is not None:
                            thinking_content = delta.thinking
                            thinking_type = "thinking"
                        # Fallback: Extended thinking field
                        elif hasattr(delta, 'extended_thinking') and delta.extended_thinking is not None:
                            thinking_content = delta.extended_thinking
                            thinking_type = "extended_thinking"
                        
                        # Emit thinking chunk event if found
                        if thinking_content:
                            # Ensure thinking_content is a string for type safety
                            thinking_text = str(thinking_content)
                            current_thinking.append(thinking_text)
                            yield ExecutionEvent(
                                type=EventType.LLM_THINKING_CHUNK,
                                timestamp=datetime.now(UTC),
                                data={
                                    "thinking_chunk": thinking_text,
                                    "thinking_type": thinking_type
                                }
                            )
                        
                        # Process tool calls (same logic as legacy streaming)
                        if hasattr(delta, 'tool_calls') and delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                # Handle both dict and object formats
                                if isinstance(tool_call, dict):
                                    if 'id' in tool_call and tool_call['id']:
                                        # New tool call
                                        current_tool_call = {
                                            "id": str(tool_call['id']),
                                            "type": "function",
                                            "function": {
                                                "name": tool_call.get('function', {}).get('name', ''),
                                                "arguments": tool_call.get('function', {}).get('arguments', '') or ''
                                            }
                                        }
                                        # Initialize buffer for this tool_call id only once.
                                        _init_tool_arg_buffer(current_tool_call['id'], current_tool_call['function']['arguments'], current_tool_args)
                                        if current_tool_call not in current_tool_calls:
                                            current_tool_calls.append(current_tool_call)
                                    elif current_tool_call and 'function' in tool_call:
                                        # Update existing tool call
                                        if 'name' in tool_call['function'] and tool_call['function']['name']:
                                            current_tool_call['function']['name'] = tool_call['function']['name']
                                        if 'arguments' in tool_call['function']:
                                            buf_id = current_tool_call['id']
                                            # Append raw fragment; repair/parse later
                                            current_tool_args.setdefault(buf_id, "")
                                            current_tool_args[buf_id] += tool_call['function']['arguments'] or ''
                                            current_tool_call['function']['arguments'] = current_tool_args[buf_id]
                                else:
                                    # Handle object format
                                    if hasattr(tool_call, 'id') and tool_call.id:
                                        # New tool call
                                        current_tool_call = {
                                            "id": str(tool_call.id),
                                            "type": "function",
                                            "function": {
                                                "name": getattr(tool_call.function, 'name', ''),
                                                "arguments": getattr(tool_call.function, 'arguments', '') or ''
                                            }
                                        }
                                        # Initialize buffer for this tool_call id only once (object format).
                                        _init_tool_arg_buffer(current_tool_call['id'], current_tool_call['function']['arguments'], current_tool_args)
                                        if current_tool_call not in current_tool_calls:
                                            current_tool_calls.append(current_tool_call)
                                    elif current_tool_call and hasattr(tool_call, 'function'):
                                        # Update existing tool call
                                        if hasattr(tool_call.function, 'name') and tool_call.function.name:
                                            current_tool_call['function']['name'] = tool_call.function.name
                                        if hasattr(tool_call.function, 'arguments'):
                                            buf_id = current_tool_call['id']
                                            current_tool_args.setdefault(buf_id, "")
                                            current_tool_args[buf_id] += getattr(tool_call.function, 'arguments', '') or ''
                                            current_tool_call['function']['arguments'] = current_tool_args[buf_id]
                    
                    # After streaming completes, process the accumulated data
                    content = ''.join(current_content)
                    
                    # Add usage metrics if available
                    if hasattr(chunk, 'usage'):
                        metrics["usage"] = {
                            "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                            "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                            "total_tokens": getattr(chunk.usage, "total_tokens", 0)
                        }
                    
                    # Prepare reasoning content for Message (top-level field, not metrics)
                    reasoning_content = None
                    if current_thinking:
                        # Ensure all thinking chunks are strings before joining
                        reasoning_content = ''.join(map(str, current_thinking))
                    
                    yield ExecutionEvent(
                        type=EventType.LLM_RESPONSE,
                        timestamp=datetime.now(UTC),
                        data={
                            "content": content,
                            "tool_calls": current_tool_calls if current_tool_calls else None,
                            "tokens": metrics.get("usage", {}),
                            "latency_ms": metrics.get("timing", {}).get("latency", 0)
                        }
                    )
                    
                    # Create assistant message
                    assistant_message = Message(
                        role="assistant",
                        content=content,
                        reasoning_content=reasoning_content,  # Top-level field (not in metrics)
                        tool_calls=current_tool_calls if current_tool_calls else None,
                        source=self._create_assistant_source(include_version=True),
                        metrics=metrics
                    )
                    thread.add_message(assistant_message)
                    new_messages.append(assistant_message)
                    yield ExecutionEvent(
                        type=EventType.MESSAGE_CREATED,
                        timestamp=datetime.now(UTC),
                        data={"message": assistant_message}
                    )
                    
                    # If no tool calls, we're done
                    if not current_tool_calls:
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                    
                    # Process tool calls
                    try:
                        # Yield tool selected events
                        for tool_call in current_tool_calls:
                            tool_name = tool_call['function']['name']
                            args = tool_call['function']['arguments']
                            
                            # Parse arguments
                            # args may be a string (typical) or already a dict if upstream parsed it.
                            # Parse only when it's a non-empty string; otherwise use as-is or fallback to {}.
                            try:
                                if isinstance(args, str) and args.strip():
                                    parsed_args = json.loads(args)
                                elif isinstance(args, dict):
                                    parsed_args = args
                                else:
                                    parsed_args = {}
                            except json.JSONDecodeError:
                                # On invalid JSON, do not guess; fall back to empty dict
                                parsed_args = {}
                            
                            tool_call['function']['arguments'] = json.dumps(parsed_args)
                            
                            yield ExecutionEvent(
                                type=EventType.TOOL_SELECTED,
                                timestamp=datetime.now(UTC),
                                data={
                                    "tool_name": tool_name,
                                    "arguments": parsed_args,
                                    "tool_call_id": tool_call['id']
                                }
                            )
                        
                        # Execute tools in parallel with timing
                        tool_start_times = {}
                        tool_tasks = []
                        
                        for tool_call in current_tool_calls:
                            tool_id = tool_call['id']
                            tool_start_times[tool_id] = datetime.now(UTC)
                            tool_tasks.append(self._handle_tool_execution(tool_call))
                        
                        tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
                        
                        # Process results
                        should_break = False
                        for i, result in enumerate(tool_results):
                            tool_call = current_tool_calls[i]
                            tool_name = tool_call['function']['name']
                            tool_id = tool_call['id']
                            
                            # Calculate duration
                            tool_end_time = datetime.now(UTC)
                            tool_duration_ms = (tool_end_time - tool_start_times[tool_id]).total_seconds() * 1000
                            
                            # Yield result or error event
                            if isinstance(result, Exception):
                                yield ExecutionEvent(
                                    type=EventType.TOOL_ERROR,
                                    timestamp=datetime.now(UTC),
                                    data={
                                        "tool_name": tool_name,
                                        "error": str(result),
                                        "tool_call_id": tool_id
                                    }
                                )
                            else:
                                # Extract result content
                                if isinstance(result, tuple) and len(result) >= 1:
                                    result_content = str(result[0])
                                else:
                                    result_content = str(result)
                                
                                yield ExecutionEvent(
                                    type=EventType.TOOL_RESULT,
                                    timestamp=datetime.now(UTC),
                                    data={
                                        "tool_name": tool_name,
                                        "result": result_content,
                                        "tool_call_id": tool_id,
                                        "duration_ms": tool_duration_ms
                                    }
                                )
                            
                            # Process tool result into message
                            tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                            thread.add_message(tool_message)
                            new_messages.append(tool_message)
                            yield ExecutionEvent(
                                type=EventType.MESSAGE_CREATED,
                                timestamp=datetime.now(UTC),
                                data={"message": tool_message}
                            )
                            
                            if break_iteration:
                                should_break = True
                        
                        # Save after tool calls
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        
                        if should_break:
                            break
                    
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        yield ExecutionEvent(
                            type=EventType.EXECUTION_ERROR,
                            timestamp=datetime.now(UTC),
                            data={
                                "error_type": type(e).__name__,
                                "message": error_msg
                            }
                        )
                        message = self._create_error_message(error_msg)
                        thread.add_message(message)
                        yield ExecutionEvent(
                            type=EventType.MESSAGE_CREATED,
                            timestamp=datetime.now(UTC),
                            data={"message": message}
                        )
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                    
                    # Reset for next iteration
                    current_content = []
                    current_tool_calls = []
                    current_tool_call = None
                    self._iteration_count += 1
                    
                except Exception as e:
                    error_msg = f"Completion failed: {str(e)}"
                    yield ExecutionEvent(
                        type=EventType.EXECUTION_ERROR,
                        timestamp=datetime.now(UTC),
                        data={
                            "error_type": type(e).__name__,
                            "message": error_msg
                        }
                    )
                    message = self._create_error_message(error_msg)
                    thread.add_message(message)
                    new_messages.append(message)
                    yield ExecutionEvent(
                        type=EventType.MESSAGE_CREATED,
                        timestamp=datetime.now(UTC),
                        data={"message": message}
                    )
                    if self.thread_store:
                        await self.thread_store.save(thread)
                    break
            
            # Calculate total tokens
            total_tokens = sum(
                msg.metrics.get("usage", {}).get("total_tokens", 0)
                for msg in new_messages
                if msg.metrics and "usage" in msg.metrics
            )
            
            # Yield completion event
            yield ExecutionEvent(
                type=EventType.EXECUTION_COMPLETE,
                timestamp=datetime.now(UTC),
                data={
                    "duration_ms": (datetime.now(UTC) - start_time).total_seconds() * 1000,
                    "total_tokens": total_tokens
                }
            )
            
        except Exception as e:
            error_msg = f"Stream processing failed: {str(e)}"
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(UTC),
                data={
                    "error_type": type(e).__name__,
                    "message": error_msg
                }
            )
            if self.thread_store:
                await self.thread_store.save(thread)
            raise

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
            logger.debug(f"Processing {len(files)} files from tool result")
            for file_info in files:
                logger.debug(f"Creating attachment for {file_info.get('filename')} with mime type {file_info.get('mime_type')}")
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
    
    @weave.op()
    async def _stream_raw(self, thread_or_id: Union[Thread, str]) -> AsyncGenerator[Any, None]:
        """
        Raw streaming implementation that yields unmodified LiteLLM chunks while executing tools.
        
        This mode is designed for OpenAI compatibility and passes through raw chunks
        without transformation. Unlike event streaming mode, this yields raw LiteLLM
        chunks instead of ExecutionEvents, but DOES execute tools and iterate like
        a full agent.
        
        The pattern matches OpenAI's Agents SDK:
        - Stream raw chunks from LLM response
        - When finish_reason is "tool_calls", execute tools silently
        - Stream raw chunks from next LLM response
        - Continue until finish_reason is "stop" or max iterations
        
        Args:
            thread_or_id: Thread object or thread ID to process
            
        Yields:
            Raw LiteLLM chunk objects in OpenAI-compatible format
            
        Note:
            - Tools ARE executed (fully agentic behavior)
            - Multi-turn iteration supported
            - No ExecutionEvent telemetry (raw chunks only)
            - Silent during tool execution (no events yielded)
        """
        try:
            # Get thread
            thread = await self._get_thread(thread_or_id)
            
            # Initialize tracking
            self._iteration_count = 0
            self._tool_attributes_cache.clear()
            new_messages = []
            
            logger.debug(f"Starting raw streaming for thread {thread.id}")
            
            # Helper: initialize per-tool_call argument buffer only once
            def _init_tool_arg_buffer(tool_call_id: str, initial_value: Optional[str], buffers: Dict[str, str]) -> None:
                if tool_call_id not in buffers:
                    buffers[tool_call_id] = initial_value or ""
            
            # Main iteration loop (like _stream_events but yielding raw chunks)
            while self._iteration_count < self.max_tool_iterations:
                try:
                    # Get streaming response
                    streaming_response, metrics = await self.step(thread, stream=True)
                    
                    # Check if step() returned an error
                    if isinstance(streaming_response, Thread):
                        error_msg = "Error during LLM request"
                        if isinstance(metrics, list) and metrics:
                            error_msg = metrics[0].content if hasattr(metrics[0], 'content') else str(metrics[0])
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    if not streaming_response:
                        error_msg = "No response received from chat completion"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    # Verify we got an async generator
                    if not hasattr(streaming_response, '__aiter__'):
                        error_msg = f"Expected async generator from step(), got {type(streaming_response).__name__}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    # Yield all raw chunks and accumulate tool calls
                    current_content = []
                    current_tool_calls = []
                    current_tool_call = None
                    current_tool_args: Dict[str, str] = {}
                    
                    async for chunk in streaming_response:
                        # Yield raw chunk unmodified
                        yield chunk
                        
                        if not hasattr(chunk, 'choices') or not chunk.choices:
                            continue
                        
                        delta = chunk.choices[0].delta
                        
                        # Track content for message creation
                        if hasattr(delta, 'content') and delta.content is not None:
                            current_content.append(delta.content)
                        
                        # Track tool calls for execution (same logic as _stream_events)
                        if hasattr(delta, 'tool_calls') and delta.tool_calls:
                            for tool_call in delta.tool_calls:
                                # Handle both dict and object formats
                                if isinstance(tool_call, dict):
                                    if 'id' in tool_call and tool_call['id']:
                                        current_tool_call = {
                                            "id": str(tool_call['id']),
                                            "type": "function",
                                            "function": {
                                                "name": tool_call.get('function', {}).get('name', ''),
                                                "arguments": tool_call.get('function', {}).get('arguments', '') or ''
                                            }
                                        }
                                        _init_tool_arg_buffer(current_tool_call['id'], current_tool_call['function']['arguments'], current_tool_args)
                                        if current_tool_call not in current_tool_calls:
                                            current_tool_calls.append(current_tool_call)
                                    elif current_tool_call and 'function' in tool_call:
                                        if 'name' in tool_call['function'] and tool_call['function']['name']:
                                            current_tool_call['function']['name'] = tool_call['function']['name']
                                        if 'arguments' in tool_call['function']:
                                            buf_id = current_tool_call['id']
                                            current_tool_args.setdefault(buf_id, "")
                                            current_tool_args[buf_id] += tool_call['function']['arguments'] or ''
                                            current_tool_call['function']['arguments'] = current_tool_args[buf_id]
                                else:
                                    # Handle object format
                                    if hasattr(tool_call, 'id') and tool_call.id:
                                        current_tool_call = {
                                            "id": str(tool_call.id),
                                            "type": "function",
                                            "function": {
                                                "name": getattr(tool_call.function, 'name', ''),
                                                "arguments": getattr(tool_call.function, 'arguments', '') or ''
                                            }
                                        }
                                        _init_tool_arg_buffer(current_tool_call['id'], current_tool_call['function']['arguments'], current_tool_args)
                                        if current_tool_call not in current_tool_calls:
                                            current_tool_calls.append(current_tool_call)
                                    elif current_tool_call and hasattr(tool_call, 'function'):
                                        if hasattr(tool_call.function, 'name') and tool_call.function.name:
                                            current_tool_call['function']['name'] = tool_call.function.name
                                        if hasattr(tool_call.function, 'arguments'):
                                            buf_id = current_tool_call['id']
                                            current_tool_args.setdefault(buf_id, "")
                                            current_tool_args[buf_id] += getattr(tool_call.function, 'arguments', '') or ''
                                            current_tool_call['function']['arguments'] = current_tool_args[buf_id]
                        
                        # Add usage metrics if available
                        if hasattr(chunk, 'usage'):
                            metrics["usage"] = {
                                "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                                "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                                "total_tokens": getattr(chunk.usage, "total_tokens", 0)
                            }
                    
                    # After streaming completes, create assistant message
                    content = ''.join(current_content)
                    assistant_message = Message(
                        role="assistant",
                        content=content,
                        tool_calls=current_tool_calls if current_tool_calls else None,
                        source=self._create_assistant_source(include_version=True),
                        metrics=metrics
                    )
                    thread.add_message(assistant_message)
                    new_messages.append(assistant_message)
                    
                    # If no tool calls, we're done
                    if not current_tool_calls:
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                    
                    # Execute tools (silently - no events yielded)
                    try:
                        # Parse and validate tool call arguments
                        for tool_call in current_tool_calls:
                            args = tool_call['function']['arguments']
                            try:
                                if isinstance(args, str) and args.strip():
                                    parsed_args = json.loads(args)
                                elif isinstance(args, dict):
                                    parsed_args = args
                                else:
                                    parsed_args = {}
                            except json.JSONDecodeError:
                                parsed_args = {}
                            
                            tool_call['function']['arguments'] = json.dumps(parsed_args)
                        
                        # Execute tools in parallel
                        tool_tasks = [self._handle_tool_execution(tc) for tc in current_tool_calls]
                        tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
                        
                        # Process tool results into messages
                        should_break = False
                        for i, result in enumerate(tool_results):
                            tool_call = current_tool_calls[i]
                            tool_name = tool_call['function']['name']
                            
                            tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                            thread.add_message(tool_message)
                            new_messages.append(tool_message)
                            
                            if break_iteration:
                                should_break = True
                        
                        # Save after tool execution
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        
                        if should_break:
                            break
                    
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        logger.error(error_msg)
                        message = self._create_error_message(error_msg)
                        thread.add_message(message)
                        if self.thread_store:
                            await self.thread_store.save(thread)
                        break
                    
                    # Increment iteration count
                    self._iteration_count += 1
                
                except Exception as e:
                    error_msg = f"Completion failed: {str(e)}"
                    logger.error(error_msg)
                    raise
            
            # Check if we hit max iterations
            if self._iteration_count >= self.max_tool_iterations:
                logger.warning(f"Hit max iterations ({self.max_tool_iterations})")
                message = self.message_factory.create_max_iterations_message()
                thread.add_message(message)
                if self.thread_store:
                    await self.thread_store.save(thread)
            
            logger.debug(f"Raw streaming complete - {self._iteration_count} iterations")
            
        except ValueError:
            # Re-raise ValueError for thread not found
            raise
        except Exception as e:
            error_msg = f"Error in raw streaming mode: {str(e)}"
            logger.error(error_msg)
            raise
    
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
            logger.warning("connect_mcp() called but no mcp config provided")
            return
        
        if self._mcp_connected:
            logger.debug("MCP already connected, skipping")
            return
        
        logger.info("Connecting to MCP servers...")
        
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
        logger.info(f"MCP connected with {len(mcp_tools)} tools")
    
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
