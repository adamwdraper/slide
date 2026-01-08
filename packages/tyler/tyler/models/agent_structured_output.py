"""Agent structured output methods mixin."""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from narrator import Thread, Message

from tyler.models.execution import AgentResult, StructuredOutputError


class AgentStructuredOutputMixin:
    """Mixin providing structured output methods for Agent.
    
    This mixin expects the following attributes/methods on the class:
    - name: str
    - max_tool_iterations: int
    - retry_config: Optional[RetryConfig]
    - thread_store: Optional[ThreadStore]
    - message_factory: MessageFactory
    - _processed_tools: List[Dict]
    - _system_prompt: str
    - _iteration_count: int
    - _get_thread(thread_or_id) -> Thread
    - step(thread, tools=None, system_prompt=None, tool_choice=None) -> Tuple[Any, Dict]
    - _create_tool_source(tool_name) -> Dict
    - _create_assistant_source(include_version=True) -> Dict
    - _serialize_tool_calls(tool_calls) -> Optional[List[Dict]]
    - _handle_tool_execution(tool_call) -> Any
    - _process_tool_result(result, tool_call, tool_name) -> Tuple[Message, bool]
    """
    
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
