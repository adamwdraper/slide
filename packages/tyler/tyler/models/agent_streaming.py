"""Agent streaming methods mixin."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple, Union

import weave

from narrator import Thread, Message

from tyler.models.agent_prompt import _weave_stream_accumulator
from tyler.models.execution import EventType, ExecutionEvent


class AgentStreamingMixin:
    """Mixin providing streaming methods for Agent.
    
    This mixin expects the following attributes/methods on the class:
    - model_name: str
    - temperature: float
    - max_tool_iterations: int
    - tool_context: Optional[Dict[str, Any]]
    - thread_store: Optional[ThreadStore]
    - file_store: Optional[FileStore]
    - message_factory: MessageFactory
    - completion_handler: CompletionHandler
    - _processed_tools: List[Dict]
    - _system_prompt: str
    - _iteration_count: int
    - _tool_attributes_cache: Dict[str, Optional[Dict[str, Any]]]
    - _tool_context: Optional[Dict[str, Any]]
    - _response_format: Optional[str]
    - _last_step_stream_had_tool_calls: bool
    - _last_step_stream_should_continue: bool
    - _get_thread(thread_or_id) -> Thread
    - _get_completion(**params) -> Any
    - _create_error_message(error_msg, source=None) -> Message
    - _create_assistant_source(include_version=True) -> Dict
    - _handle_tool_execution(tool_call, progress_callback=None) -> dict
    - _process_tool_result(result, tool_call, tool_name) -> Tuple[Message, bool]
    """

    @weave.op(accumulator=_weave_stream_accumulator)
    async def stream(
        self,
        thread_or_id: Union[Thread, str],
        mode: Literal["events", "raw"] = "events",
        tool_context: Optional[Dict[str, Any]] = None
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
            tool_context: Optional dictionary of dependencies to inject into tools.
                         Tools that have 'ctx' or 'context' as their first parameter
                         will receive this context.
            
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
            ToolContextError: If a tool requires context but tool_context was not provided
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
            if mode == "events":
                logging.getLogger(__name__).debug("Agent.stream() called with mode='events'")
                async for event in self._stream_events_step_stream(thread_or_id):
                    yield event
            elif mode == "raw":
                logging.getLogger(__name__).debug("Agent.stream() called with mode='raw'")
                async for chunk in self._stream_raw_step_stream(thread_or_id):
                    yield chunk
            else:
                raise ValueError(
                    f"Invalid mode: {mode}. Must be 'events' or 'raw'"
                )
        finally:
            # Clear tool context after execution
            self._tool_context = None
    
    @weave.op(accumulator=_weave_stream_accumulator)
    async def step_stream(
        self,
        thread: Thread,
        mode: Literal["events", "raw"] = "events",
    ) -> AsyncGenerator[Union[ExecutionEvent, Any], None]:
        """Execute a single streaming step (one LLM streamed completion + resulting tool execution).

        This is the streaming equivalent of `step()` for `run()`: tool execution happens
        *inside* this generator so tool ops appear as children of the step span in Weave.
        """
        # Reset per-step flags
        self._last_step_stream_had_tool_calls = False
        self._last_step_stream_should_continue = False

        if mode == "events":
            async for event in self._step_stream_events_impl(thread):
                yield event
        elif mode == "raw":
            async for chunk in self._step_stream_raw_impl(thread):
                yield chunk
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'events' or 'raw'")

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

    async def _stream_events_step_stream(
        self, thread_or_id: Union[Thread, str]
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """Event streaming orchestrator that emits per-iteration step_stream spans."""
        thread = await self._get_thread(thread_or_id)

        self._iteration_count = 0
        self._tool_attributes_cache.clear()
        start_time = datetime.now(timezone.utc)
        total_tokens = 0

        while self._iteration_count < self.max_tool_iterations:
            # Yield iteration start (outer orchestration event)
            yield ExecutionEvent(
                type=EventType.ITERATION_START,
                timestamp=datetime.now(timezone.utc),
                data={
                    "iteration_number": self._iteration_count,
                    "max_iterations": self.max_tool_iterations,
                },
            )

            async for event in self.step_stream(thread, mode="events"):
                if event.type == EventType.LLM_RESPONSE:
                    toks = (event.data or {}).get("tokens") or {}
                    if isinstance(toks, dict):
                        total_tokens += int(toks.get("total_tokens", 0) or 0)
                yield event

            if not self._last_step_stream_should_continue:
                break

            self._iteration_count += 1

        # If we hit max iterations, emit limit message/events
        if self._iteration_count >= self.max_tool_iterations:
            message = self.message_factory.create_max_iterations_message()
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            yield ExecutionEvent(
                type=EventType.ITERATION_LIMIT,
                timestamp=datetime.now(timezone.utc),
                data={"iterations_used": self._iteration_count},
            )
            if self.thread_store:
                await self.thread_store.save(thread)

        # Emit execution complete
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        yield ExecutionEvent(
            type=EventType.EXECUTION_COMPLETE,
            timestamp=datetime.now(timezone.utc),
            data={"duration_ms": duration_ms, "total_tokens": total_tokens},
        )

    async def _stream_raw_step_stream(
        self, thread_or_id: Union[Thread, str]
    ) -> AsyncGenerator[Any, None]:
        """Raw streaming orchestrator that emits per-iteration step_stream spans."""
        thread = await self._get_thread(thread_or_id)

        self._iteration_count = 0
        self._tool_attributes_cache.clear()

        while self._iteration_count < self.max_tool_iterations:
            async for chunk in self.step_stream(thread, mode="raw"):
                yield chunk

            if not self._last_step_stream_should_continue:
                break

            self._iteration_count += 1

        # If we hit max iterations, persist a max-iterations message (no events in raw mode)
        if self._iteration_count >= self.max_tool_iterations:
            logging.getLogger(__name__).warning(f"Hit max iterations ({self.max_tool_iterations})")
            message = self.message_factory.create_max_iterations_message()
            thread.add_message(message)
            if self.thread_store:
                await self.thread_store.save(thread)

    async def _step_stream_events_impl(
        self, thread: Thread
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """One streaming step that yields ExecutionEvents and executes tools inside the step span."""
        # Yield LLM request event
        yield ExecutionEvent(
            type=EventType.LLM_REQUEST,
            timestamp=datetime.now(timezone.utc),
            data={
                "message_count": len(thread.messages),
                "model": self.model_name,
                "temperature": self.temperature,
            },
        )

        try:
            streaming_response, metrics = await self._get_streaming_completion(thread)
        except Exception as e:
            error_msg = f"Completion failed: {str(e)}"
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            )
            message = self._create_error_message(error_msg)
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            if self.thread_store:
                await self.thread_store.save(thread)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        if not streaming_response:
            error_msg = "No response received from chat completion"
            logging.getLogger(__name__).error(error_msg)
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": "NoResponse", "message": error_msg},
            )
            message = self._create_error_message(error_msg)
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            if self.thread_store:
                await self.thread_store.save(thread)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        # Helper: initialize per-tool_call argument buffer only once
        def _init_tool_arg_buffer(
            tool_call_id: str, initial_value: Optional[str], buffers: Dict[str, str]
        ) -> None:
            if tool_call_id not in buffers:
                buffers[tool_call_id] = initial_value or ""

        current_content: list[str] = []
        current_thinking: list[str] = []
        current_tool_calls: list[dict] = []
        current_tool_call: Optional[dict] = None
        current_tool_args: Dict[str, str] = {}

        try:
            async for chunk in streaming_response:
                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Content chunks
                if hasattr(delta, "content") and delta.content is not None:
                    current_content.append(delta.content)
                    yield ExecutionEvent(
                        type=EventType.LLM_STREAM_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"content_chunk": delta.content},
                    )

                # Thinking/reasoning chunks
                thinking_content = None
                thinking_type = None
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    thinking_content = delta.reasoning_content
                    thinking_type = "reasoning"
                elif hasattr(delta, "thinking") and delta.thinking is not None:
                    thinking_content = delta.thinking
                    thinking_type = "thinking"
                elif hasattr(delta, "extended_thinking") and delta.extended_thinking is not None:
                    thinking_content = delta.extended_thinking
                    thinking_type = "extended_thinking"

                if thinking_content:
                    thinking_text = str(thinking_content)
                    current_thinking.append(thinking_text)
                    yield ExecutionEvent(
                        type=EventType.LLM_THINKING_CHUNK,
                        timestamp=datetime.now(timezone.utc),
                        data={"thinking_chunk": thinking_text, "thinking_type": thinking_type},
                    )

                # Tool call deltas
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        if isinstance(tool_call, dict):
                            if "id" in tool_call and tool_call["id"]:
                                current_tool_call = {
                                    "id": str(tool_call["id"]),
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.get("function", {}).get("name", ""),
                                        "arguments": tool_call.get("function", {}).get("arguments", "") or "",
                                    },
                                }
                                _init_tool_arg_buffer(
                                    current_tool_call["id"],
                                    current_tool_call["function"]["arguments"],
                                    current_tool_args,
                                )
                                if current_tool_call not in current_tool_calls:
                                    current_tool_calls.append(current_tool_call)
                            elif current_tool_call and "function" in tool_call:
                                if (
                                    "name" in tool_call["function"]
                                    and tool_call["function"]["name"]
                                ):
                                    current_tool_call["function"]["name"] = tool_call["function"]["name"]
                                if "arguments" in tool_call["function"]:
                                    buf_id = current_tool_call["id"]
                                    current_tool_args.setdefault(buf_id, "")
                                    current_tool_args[buf_id] += tool_call["function"]["arguments"] or ""
                                    current_tool_call["function"]["arguments"] = current_tool_args[buf_id]
                        else:
                            if hasattr(tool_call, "id") and tool_call.id:
                                current_tool_call = {
                                    "id": str(tool_call.id),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(tool_call.function, "name", ""),
                                        "arguments": getattr(tool_call.function, "arguments", "") or "",
                                    },
                                }
                                _init_tool_arg_buffer(
                                    current_tool_call["id"],
                                    current_tool_call["function"]["arguments"],
                                    current_tool_args,
                                )
                                if current_tool_call not in current_tool_calls:
                                    current_tool_calls.append(current_tool_call)
                            elif current_tool_call and hasattr(tool_call, "function"):
                                if hasattr(tool_call.function, "name") and tool_call.function.name:
                                    current_tool_call["function"]["name"] = tool_call.function.name
                                if hasattr(tool_call.function, "arguments"):
                                    buf_id = current_tool_call["id"]
                                    current_tool_args.setdefault(buf_id, "")
                                    current_tool_args[buf_id] += getattr(tool_call.function, "arguments", "") or ""
                                    current_tool_call["function"]["arguments"] = current_tool_args[buf_id]

                # Usage updates (if provided on chunk)
                if hasattr(chunk, "usage"):
                    metrics["usage"] = {
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                    }
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            )
            message = self._create_error_message(error_msg)
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            if self.thread_store:
                await self.thread_store.save(thread)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        # After stream ends, create assistant message + response event
        content = "".join(current_content)
        reasoning_content = "".join(current_thinking) if current_thinking else None

        yield ExecutionEvent(
            type=EventType.LLM_RESPONSE,
            timestamp=datetime.now(timezone.utc),
            data={
                "content": content,
                "tool_calls": current_tool_calls if current_tool_calls else None,
                "tokens": metrics.get("usage", {}),
                "latency_ms": metrics.get("timing", {}).get("latency", 0),
            },
        )

        assistant_message = Message(
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=current_tool_calls if current_tool_calls else None,
            source=self._create_assistant_source(include_version=True),
            metrics=metrics,
        )
        thread.add_message(assistant_message)
        yield ExecutionEvent(
            type=EventType.MESSAGE_CREATED,
            timestamp=datetime.now(timezone.utc),
            data={"message": assistant_message},
        )

        # No tools -> done
        if not current_tool_calls:
            if self.thread_store:
                await self.thread_store.save(thread)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        self._last_step_stream_had_tool_calls = True

        # Process tool calls inside this step span
        should_break = False
        try:
            # Yield tool selected events
            for tool_call in current_tool_calls:
                tool_name = tool_call["function"]["name"]
                args = tool_call["function"]["arguments"]
                try:
                    if isinstance(args, str) and args.strip():
                        parsed_args = json.loads(args)
                    elif isinstance(args, dict):
                        parsed_args = args
                    else:
                        parsed_args = {}
                except json.JSONDecodeError:
                    parsed_args = {}
                tool_call["function"]["arguments"] = json.dumps(parsed_args)
                yield ExecutionEvent(
                    type=EventType.TOOL_SELECTED,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "tool_name": tool_name,
                        "arguments": parsed_args,
                        "tool_call_id": tool_call["id"],
                    },
                )

            # Execute tools in parallel with timing + progress streaming
            tool_start_times: Dict[str, datetime] = {}
            tool_tasks: list[asyncio.Task] = []

            progress_queue: asyncio.Queue[Optional[ExecutionEvent]] = asyncio.Queue()

            for tool_call in current_tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_start_times[tool_id] = datetime.now(timezone.utc)

                def make_progress_callback(t_name: str, t_id: str, queue: asyncio.Queue):
                    async def progress_cb(
                        progress: float,
                        total: Optional[float] = None,
                        message: Optional[str] = None,
                    ):
                        await queue.put(
                            ExecutionEvent(
                                type=EventType.TOOL_PROGRESS,
                                timestamp=datetime.now(timezone.utc),
                                data={
                                    "tool_name": t_name,
                                    "progress": progress,
                                    "total": total,
                                    "message": message,
                                    "tool_call_id": t_id,
                                },
                            )
                        )

                    return progress_cb

                progress_callback = make_progress_callback(tool_name, tool_id, progress_queue)
                tool_tasks.append(
                    asyncio.create_task(
                        self._handle_tool_execution(tool_call, progress_callback=progress_callback)
                    )
                )

            async def run_tools_and_signal_done():
                results = await asyncio.gather(*tool_tasks, return_exceptions=True)
                await progress_queue.put(None)
                return results

            results_task = asyncio.create_task(run_tools_and_signal_done())

            while True:
                progress_event = await progress_queue.get()
                if progress_event is None:
                    break
                yield progress_event

            tool_results = await results_task

            for i, result in enumerate(tool_results):
                tool_call = current_tool_calls[i]
                tool_name = tool_call["function"]["name"]
                tool_id = tool_call["id"]
                tool_end_time = datetime.now(timezone.utc)
                tool_duration_ms = (
                    tool_end_time - tool_start_times[tool_id]
                ).total_seconds() * 1000

                if isinstance(result, Exception):
                    yield ExecutionEvent(
                        type=EventType.TOOL_ERROR,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "error": str(result),
                            "tool_call_id": tool_id,
                        },
                    )
                else:
                    if isinstance(result, tuple) and len(result) >= 1:
                        result_content = str(result[0])
                    else:
                        result_content = str(result)
                    yield ExecutionEvent(
                        type=EventType.TOOL_RESULT,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "tool_name": tool_name,
                            "result": result_content,
                            "tool_call_id": tool_id,
                            "duration_ms": tool_duration_ms,
                        },
                    )

                tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                thread.add_message(tool_message)
                yield ExecutionEvent(
                    type=EventType.MESSAGE_CREATED,
                    timestamp=datetime.now(timezone.utc),
                    data={"message": tool_message},
                )
                if break_iteration:
                    should_break = True

            if self.thread_store:
                await self.thread_store.save(thread)

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            yield ExecutionEvent(
                type=EventType.EXECUTION_ERROR,
                timestamp=datetime.now(timezone.utc),
                data={"error_type": type(e).__name__, "message": error_msg},
            )
            message = self._create_error_message(error_msg)
            thread.add_message(message)
            yield ExecutionEvent(
                type=EventType.MESSAGE_CREATED,
                timestamp=datetime.now(timezone.utc),
                data={"message": message},
            )
            if self.thread_store:
                await self.thread_store.save(thread)
            should_break = True

        # Continue only if tools were called and we didn't hit an interrupt
        self._last_step_stream_should_continue = bool(current_tool_calls) and not should_break

    async def _step_stream_raw_impl(self, thread: Thread) -> AsyncGenerator[Any, None]:
        """One streaming step that yields raw chunks and executes tools inside the step span."""
        try:
            streaming_response, metrics = await self._get_streaming_completion(thread)
        except Exception as e:
            logging.getLogger(__name__).error(f"Completion failed: {e}")
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        if not streaming_response:
            error_msg = "No response received from chat completion"
            logging.getLogger(__name__).error(error_msg)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        # Helper: initialize per-tool_call argument buffer only once
        def _init_tool_arg_buffer(
            tool_call_id: str, initial_value: Optional[str], buffers: Dict[str, str]
        ) -> None:
            if tool_call_id not in buffers:
                buffers[tool_call_id] = initial_value or ""

        current_content: list[str] = []
        current_tool_calls: list[dict] = []
        current_tool_call: Optional[dict] = None
        current_tool_args: Dict[str, str] = {}

        try:
            async for chunk in streaming_response:
                # Yield raw chunk
                yield chunk

                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if hasattr(delta, "content") and delta.content is not None:
                    current_content.append(delta.content)

                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        if isinstance(tool_call, dict):
                            if "id" in tool_call and tool_call["id"]:
                                current_tool_call = {
                                    "id": str(tool_call["id"]),
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.get("function", {}).get("name", ""),
                                        "arguments": tool_call.get("function", {}).get("arguments", "") or "",
                                    },
                                }
                                _init_tool_arg_buffer(
                                    current_tool_call["id"],
                                    current_tool_call["function"]["arguments"],
                                    current_tool_args,
                                )
                                if current_tool_call not in current_tool_calls:
                                    current_tool_calls.append(current_tool_call)
                            elif current_tool_call and "function" in tool_call:
                                if (
                                    "name" in tool_call["function"]
                                    and tool_call["function"]["name"]
                                ):
                                    current_tool_call["function"]["name"] = tool_call["function"]["name"]
                                if "arguments" in tool_call["function"]:
                                    buf_id = current_tool_call["id"]
                                    current_tool_args.setdefault(buf_id, "")
                                    current_tool_args[buf_id] += tool_call["function"]["arguments"] or ""
                                    current_tool_call["function"]["arguments"] = current_tool_args[buf_id]
                        else:
                            if hasattr(tool_call, "id") and tool_call.id:
                                current_tool_call = {
                                    "id": str(tool_call.id),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(tool_call.function, "name", ""),
                                        "arguments": getattr(tool_call.function, "arguments", "") or "",
                                    },
                                }
                                _init_tool_arg_buffer(
                                    current_tool_call["id"],
                                    current_tool_call["function"]["arguments"],
                                    current_tool_args,
                                )
                                if current_tool_call not in current_tool_calls:
                                    current_tool_calls.append(current_tool_call)
                            elif current_tool_call and hasattr(tool_call, "function"):
                                if hasattr(tool_call.function, "name") and tool_call.function.name:
                                    current_tool_call["function"]["name"] = tool_call.function.name
                                if hasattr(tool_call.function, "arguments"):
                                    buf_id = current_tool_call["id"]
                                    current_tool_args.setdefault(buf_id, "")
                                    current_tool_args[buf_id] += getattr(tool_call.function, "arguments", "") or ""
                                    current_tool_call["function"]["arguments"] = current_tool_args[buf_id]

                if hasattr(chunk, "usage"):
                    metrics["usage"] = {
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                    }
        except Exception as e:
            logging.getLogger(__name__).error(f"Stream error: {e}")
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        # After stream ends, create assistant message
        content = "".join(current_content)
        assistant_message = Message(
            role="assistant",
            content=content,
            tool_calls=current_tool_calls if current_tool_calls else None,
            source=self._create_assistant_source(include_version=True),
            metrics=metrics,
        )
        thread.add_message(assistant_message)

        if not current_tool_calls:
            if self.thread_store:
                await self.thread_store.save(thread)
            self._last_step_stream_had_tool_calls = False
            self._last_step_stream_should_continue = False
            return

        self._last_step_stream_had_tool_calls = True

        # Execute tools silently (no events yielded)
        should_break = False
        try:
            for tool_call in current_tool_calls:
                args = tool_call["function"]["arguments"]
                try:
                    if isinstance(args, str) and args.strip():
                        parsed_args = json.loads(args)
                    elif isinstance(args, dict):
                        parsed_args = args
                    else:
                        parsed_args = {}
                except json.JSONDecodeError:
                    parsed_args = {}
                tool_call["function"]["arguments"] = json.dumps(parsed_args)

            tool_tasks = [self._handle_tool_execution(tc) for tc in current_tool_calls]
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

            for i, result in enumerate(tool_results):
                tool_call = current_tool_calls[i]
                tool_name = tool_call["function"]["name"]
                tool_message, break_iteration = self._process_tool_result(result, tool_call, tool_name)
                thread.add_message(tool_message)
                if break_iteration:
                    should_break = True

            if self.thread_store:
                await self.thread_store.save(thread)
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logging.getLogger(__name__).error(error_msg)
            message = self._create_error_message(error_msg)
            thread.add_message(message)
            if self.thread_store:
                await self.thread_store.save(thread)
            should_break = True

        self._last_step_stream_should_continue = bool(current_tool_calls) and not should_break
