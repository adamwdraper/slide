"""Expectation definitions for agent evaluations"""
from typing import List, Optional, Callable, Any, Dict, Union
from dataclasses import dataclass, field


@dataclass
class Expectation:
    """Define expectations for agent behavior in conversations.
    
    This class allows you to specify what you expect from an agent's response
    in a flexible and intuitive way.
    """
    
    # Tool usage expectations
    uses_tools: Optional[List[str]] = None
    uses_any_tool: Optional[List[str]] = None
    uses_tools_in_order: Optional[List[str]] = None
    does_not_use_tools: Optional[List[str]] = None
    
    # Content expectations
    mentions: Optional[List[str]] = None
    mentions_any: Optional[List[str]] = None
    mentions_none: Optional[List[str]] = None
    
    # Behavioral expectations
    asks_clarification: Optional[bool] = None
    confirms_details: Optional[List[str]] = None
    offers_alternatives: Optional[bool] = None
    refuses_request: Optional[bool] = None
    offers_help: Optional[bool] = None
    
    # Tone/style expectations
    tone: Optional[str] = None
    sentiment: Optional[str] = None
    is_helpful: Optional[bool] = None
    
    # Task completion
    completes_task: Optional[bool] = None
    partially_completes: Optional[bool] = None
    
    # Custom validation function
    custom: Optional[Callable[[Any], bool]] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert expectation to dictionary for serialization"""
        result = {}
        
        # Include all non-None, non-custom fields
        for key, value in self.__dict__.items():
            if value is not None and key not in ['custom', 'metadata']:
                result[key] = value
                
        # Add metadata
        if self.metadata:
            result['metadata'] = self.metadata
            
        # Note if custom validation exists
        if self.custom:
            result['has_custom_validation'] = True
            
        return result
    
    def validate_against(self, agent_response: Dict[str, Any]) -> Dict[str, bool]:
        """Validate an agent response against these expectations.
        
        Returns a dictionary of expectation_name -> passed (bool)
        """
        results = {}
        
        # Extract relevant data from response
        tool_calls = agent_response.get('tool_calls', [])
        content = agent_response.get('content', '').lower()
        
        # Tool usage checks
        if self.uses_tools is not None:
            used_tools = [tc.get('name') for tc in tool_calls]
            results['uses_tools'] = set(self.uses_tools) == set(used_tools)
            
        if self.uses_any_tool is not None:
            used_tools = [tc.get('name') for tc in tool_calls]
            results['uses_any_tool'] = any(tool in used_tools for tool in self.uses_any_tool)
            
        if self.uses_tools_in_order is not None:
            used_tools = [tc.get('name') for tc in tool_calls]
            results['uses_tools_in_order'] = used_tools == self.uses_tools_in_order
            
        if self.does_not_use_tools is not None:
            used_tools = [tc.get('name') for tc in tool_calls]
            results['does_not_use_tools'] = not any(tool in used_tools for tool in self.does_not_use_tools)
        
        # Content checks
        if self.mentions is not None:
            results['mentions'] = all(term.lower() in content for term in self.mentions)
            
        if self.mentions_any is not None:
            results['mentions_any'] = any(term.lower() in content for term in self.mentions_any)
            
        if self.mentions_none is not None:
            results['mentions_none'] = not any(term.lower() in content for term in self.mentions_none)
        
        # Behavioral checks (these would need more sophisticated analysis in practice)
        if self.asks_clarification is not None:
            # Simple heuristic - look for question marks and clarifying phrases
            clarifying_phrases = ['could you', 'can you', 'what', 'when', 'where', 'which', '?']
            has_clarification = any(phrase in content for phrase in clarifying_phrases)
            results['asks_clarification'] = has_clarification == self.asks_clarification
            
        if self.confirms_details is not None:
            results['confirms_details'] = all(detail.lower() in content for detail in self.confirms_details)
        
        # Custom validation
        if self.custom is not None:
            try:
                results['custom'] = self.custom(agent_response)
            except Exception as e:
                results['custom'] = False
                results['custom_error'] = str(e)
        
        return results 