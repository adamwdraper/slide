"""CompletionHandler for managing LLM communication.

This module handles all LLM completion logic, including parameter building,
model-specific adjustments, and response processing.
"""
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, UTC
import copy
import weave
from litellm import acompletion
from narrator import Thread
from tyler.utils.logging import get_logger

logger = get_logger(__name__)


class CompletionHandler:
    """Handles LLM completion requests and response processing.
    
    This class centralizes all logic related to communicating with LLMs,
    including parameter preparation, model-specific adjustments, and
    metric collection.
    
    Attributes:
        model_name: Name of the LLM model to use
        temperature: Temperature setting for completions
        api_base: Optional custom API base URL
        api_key: Optional API key for the model provider
        extra_headers: Optional additional headers
        drop_params: Whether to drop unsupported parameters
    """
    
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.7,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        drop_params: bool = True,
        reasoning: Optional[Any] = None
    ):
        """Initialize the CompletionHandler.
        
        Args:
            model_name: Name of the LLM model
            temperature: Temperature for completions
            api_base: Optional custom API base URL
            api_key: Optional API key for the model provider
            extra_headers: Optional additional headers
            drop_params: Whether to drop unsupported parameters
            reasoning: Unified reasoning config (string or dict)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.api_base = api_base
        self.api_key = api_key
        self.extra_headers = extra_headers
        self.drop_params = drop_params
        self.reasoning = reasoning
    
    @weave.op()
    async def get_completion(
        self,
        system_prompt: str,
        thread_messages: List[Dict],
        tools: List[Dict],
        stream: bool = False
    ) -> Tuple[Any, Dict]:
        """Get a completion from the LLM.
        
        Args:
            system_prompt: System prompt to prepend
            thread_messages: List of thread messages
            tools: List of tool definitions
            stream: Whether to stream the response
            
        Returns:
            Tuple of (response, metrics dict)
        """
        # Create completion messages with system prompt
        completion_messages = [{"role": "system", "content": system_prompt}] + thread_messages
        
        # Build parameters
        completion_params = self._build_completion_params(
            completion_messages,
            tools,
            stream
        )
        
        # Track API call time
        api_start_time = datetime.now(UTC)
        
        try:
            # Get completion with weave call tracking
            response, call = await self._get_completion_with_tracking(**completion_params)
            
            # Create metrics dict
            metrics = self._build_metrics(api_start_time, response, call)
            
            return response, metrics
            
        except Exception as e:
            logger.error(f"Completion failed: {e}")
            raise
    
    def _build_completion_params(
        self,
        messages: List[Dict],
        tools: List[Dict],
        stream: bool
    ) -> Dict[str, Any]:
        """Build parameters for completion request.
        
        Args:
            messages: List of messages including system prompt
            tools: List of tool definitions
            stream: Whether to stream
            
        Returns:
            Dict of completion parameters
        """
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "stream": stream,
            "drop_params": self.drop_params
        }
        
        # Add custom API base URL if specified
        if self.api_base:
            params["api_base"] = self.api_base
        
        # Add API key if specified
        if self.api_key:
            params["api_key"] = self.api_key
        
        # Add extra headers if specified
        if self.extra_headers:
            params["extra_headers"] = self.extra_headers
        
        # Add tools if provided
        if len(tools) > 0:
            # Handle Gemini-specific tool modifications
            if "gemini" in self.model_name.lower():
                params["tools"] = self._modify_tools_for_gemini(tools)
            else:
                params["tools"] = tools
        
        # Add reasoning parameters if specified (for thinking/reasoning tokens)
        if self.reasoning:
            reasoning_params = self._map_reasoning_to_provider_params(self.reasoning)
            params.update(reasoning_params)
        
        return params
    
    def _map_reasoning_to_provider_params(self, reasoning: Any) -> Dict[str, Any]:
        """Map unified reasoning parameter to provider-specific format.
        
        Args:
            reasoning: String ('low'/'medium'/'high') or Dict (advanced config)
            
        Returns:
            Dict with provider-specific parameter(s)
        """
        if isinstance(reasoning, str):
            # Simple string format → use reasoning_effort (most providers)
            return {"reasoning_effort": reasoning}
        
        elif isinstance(reasoning, dict):
            # Dict format - check what it contains
            if "type" in reasoning:
                # Anthropic format: {"type": "enabled", "budget_tokens": 1024}
                return {"thinking": reasoning}
            elif "effort" in reasoning:
                # Alternative dict format: {"effort": "low"}
                return {"reasoning_effort": reasoning["effort"]}
            else:
                # Unknown format - try reasoning_effort as most compatible
                return {"reasoning": reasoning}
        
        # Fallback: empty dict (no reasoning params)
        return {}
    
    def _modify_tools_for_gemini(self, tools: List[Dict]) -> List[Dict]:
        """Modify tools for Gemini compatibility.
        
        Gemini doesn't support additionalProperties in tool parameters,
        so we need to remove them.
        
        Args:
            tools: Original tool definitions
            
        Returns:
            Modified tool definitions for Gemini
        """
        # Create a deep copy to avoid modifying originals
        modified_tools = copy.deepcopy(tools)
        
        # Remove additionalProperties from all tool parameters
        for tool in modified_tools:
            if "function" in tool and "parameters" in tool["function"]:
                params = tool["function"]["parameters"]
                if "properties" in params:
                    for prop_name, prop in params["properties"].items():
                        if isinstance(prop, dict) and "additionalProperties" in prop:
                            del prop["additionalProperties"]
        
        return modified_tools
    
    @weave.op()
    async def _get_completion_with_tracking(self, **completion_params) -> Tuple[Any, Any]:
        """Get completion from LLM with weave tracking.
        
        Args:
            **completion_params: Parameters for acompletion
            
        Returns:
            Tuple of (response, weave_call). If called outside of weave's .call() context,
            weave_call will be None. This is a compatibility workaround to ensure the return
            type is always a tuple, matching the expected interface for downstream consumers
            (Agent.step() expects a tuple and extracts call info from the second element).
        """
        response = await acompletion(**completion_params)
        # When called with .call(), weave returns (response, call_info).
        # If not called within weave's .call() context, call_info is unavailable.
        # For compatibility, we return (response, None) to maintain a consistent tuple return type.
        return response, None
    
    def _build_metrics(
        self,
        api_start_time: datetime,
        response: Any,
        call: Any
    ) -> Dict[str, Any]:
        """Build metrics dictionary from completion response.
        
        Args:
            api_start_time: Time when API call started
            response: LLM response
            call: Weave call object (may be None)
            
        Returns:
            Metrics dictionary with timing, usage, and weave info
        """
        metrics = {
            "model": self.model_name,
            "timing": {
                "started_at": api_start_time.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "latency": (datetime.now(UTC) - api_start_time).total_seconds() * 1000
            }
        }
        
        # Add weave-specific metrics if available
        try:
            if call and hasattr(call, 'id') and call.id:
                metrics["weave_call"] = {
                    "id": str(call.id),
                    "ui_url": str(call.ui_url)
                }
        except (AttributeError, ValueError):
            pass
        
        # Get usage metrics if available
        if hasattr(response, 'usage'):
            metrics["usage"] = {
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0)
            }
        
        return metrics

