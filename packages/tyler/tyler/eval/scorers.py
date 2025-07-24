"""Scorer implementations for agent evaluations"""
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import weave
from litellm import acompletion
import json


class BaseScorer(ABC):
    """Base class for all scorers"""
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    async def score(self, 
                   agent_response: Dict[str, Any], 
                   conversation: Dict[str, Any],
                   expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score an agent response.
        
        Args:
            agent_response: The agent's response including content and tool calls
            conversation: The full conversation context
            expectations: List of expectations for this conversation
            
        Returns:
            Dictionary with score results
        """
        pass
    
    def to_weave_scorer(self):
        """Convert to a Weave scorer function"""
        @weave.op(name=f"{self.name}_scorer")
        async def scorer(output: Dict[str, Any], 
                        conversation_id: str,
                        messages: List[Dict[str, Any]],
                        expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
            # Build conversation context
            conversation = {
                "conversation_id": conversation_id,
                "messages": messages
            }
            return await self.score(output, conversation, expectations)
        
        return scorer


class ToolUsageScorer(BaseScorer):
    """Scores whether the agent used tools correctly based on expectations"""
    
    def __init__(self, strict: bool = True):
        super().__init__("tool_usage")
        self.strict = strict
    
    async def score(self, 
                   agent_response: Dict[str, Any], 
                   conversation: Dict[str, Any],
                   expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score tool usage against expectations"""
        
        tool_calls = agent_response.get('tool_calls', [])
        used_tools = [tc.get('name') for tc in tool_calls]
        
        results = {
            "score": 1.0,
            "passed": True,
            "details": {}
        }
        
        # Check each expectation
        for exp_data in expectations:
            exp = exp_data.get('expectations', {})
            
            # Check uses_tools
            if 'uses_tools' in exp:
                expected = set(exp['uses_tools'])
                actual = set(used_tools)
                passed = expected == actual
                results['details']['uses_tools'] = {
                    'passed': passed,
                    'expected': list(expected),
                    'actual': list(actual)
                }
                if not passed:
                    results['passed'] = False
                    results['score'] *= 0.5
            
            # Check uses_any_tool
            if 'uses_any_tool' in exp:
                allowed = exp['uses_any_tool']
                passed = any(tool in used_tools for tool in allowed)
                results['details']['uses_any_tool'] = {
                    'passed': passed,
                    'allowed': allowed,
                    'actual': used_tools
                }
                if not passed:
                    results['passed'] = False
                    results['score'] *= 0.7
            
            # Check does_not_use_tools
            if 'does_not_use_tools' in exp:
                forbidden = exp['does_not_use_tools']
                passed = not any(tool in used_tools for tool in forbidden)
                results['details']['does_not_use_tools'] = {
                    'passed': passed,
                    'forbidden': forbidden,
                    'actual': used_tools
                }
                if not passed:
                    results['passed'] = False
                    results['score'] = 0.0  # Critical failure
            
            # Check uses_tools_in_order
            if 'uses_tools_in_order' in exp:
                expected_order = exp['uses_tools_in_order']
                passed = used_tools == expected_order
                results['details']['uses_tools_in_order'] = {
                    'passed': passed,
                    'expected_order': expected_order,
                    'actual_order': used_tools
                }
                if not passed:
                    results['passed'] = False
                    results['score'] *= 0.6
        
        return results


class ToneScorer(BaseScorer):
    """Scores the tone of agent responses using an LLM judge"""
    
    def __init__(self, 
                 acceptable_tones: Optional[List[str]] = None,
                 model: str = "gpt-4.1"):
        super().__init__("tone")
        self.acceptable_tones = acceptable_tones or ["professional", "friendly", "helpful"]
        self.model = model
    
    async def score(self, 
                   agent_response: Dict[str, Any], 
                   conversation: Dict[str, Any],
                   expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score tone using LLM judge"""
        
        content = agent_response.get('content', '')
        
        # Check if there's a specific tone expectation
        expected_tone = None
        for exp_data in expectations:
            exp = exp_data.get('expectations', {})
            if 'tone' in exp:
                expected_tone = exp['tone']
                break
        
        # Prepare prompt for LLM judge
        prompt = f"""Analyze the tone of this AI assistant response and determine if it matches expectations.

Assistant Response: {content}

Expected Tone: {expected_tone or f"One of: {', '.join(self.acceptable_tones)}"}

Respond with a JSON object containing:
- "tone": The detected tone (e.g., "professional", "friendly", "casual", "formal")
- "matches_expected": true/false whether it matches the expected tone
- "score": 0.0 to 1.0 rating of how well it matches
- "reasoning": Brief explanation
"""
        
        try:
            response = await acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "score": result.get("score", 0.0),
                "passed": result.get("matches_expected", False),
                "details": {
                    "detected_tone": result.get("tone"),
                    "expected_tone": expected_tone or self.acceptable_tones,
                    "reasoning": result.get("reasoning")
                }
            }
        except Exception as e:
            return {
                "score": 0.0,
                "passed": False,
                "error": str(e)
            }


class TaskCompletionScorer(BaseScorer):
    """Scores whether the agent completed the requested task"""
    
    def __init__(self, model: str = "gpt-4.1"):
        super().__init__("task_completion")
        self.model = model
    
    async def score(self, 
                   agent_response: Dict[str, Any], 
                   conversation: Dict[str, Any],
                   expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score task completion using LLM judge"""
        
        # Build conversation history
        messages = conversation.get('messages', [])
        messages_str = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        # Add agent response
        agent_content = agent_response.get('content', '')
        tool_calls = agent_response.get('tool_calls', [])
        
        # Check expectations
        expects_completion = False
        for exp_data in expectations:
            exp = exp_data.get('expectations', {})
            if exp.get('completes_task') is True:
                expects_completion = True
                break
        
        prompt = f"""Analyze whether the AI assistant completed the requested task.

Conversation:
{messages_str}

Assistant Response: {agent_content}

Tools Used: {[tc.get('name') for tc in tool_calls]}

Expected: {"Task should be completed" if expects_completion else "Assess if task was completed"}

Respond with a JSON object containing:
- "completed": true/false whether the task was completed
- "partially_completed": true/false if some progress was made
- "score": 0.0 to 1.0 rating (1.0 = fully complete, 0.5 = partial, 0.0 = no progress)
- "reasoning": Brief explanation
"""
        
        try:
            response = await acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            passed = result.get("completed", False)
            if expects_completion:
                passed = result.get("completed", False)
            
            return {
                "score": result.get("score", 0.0),
                "passed": passed,
                "details": {
                    "completed": result.get("completed"),
                    "partially_completed": result.get("partially_completed"),
                    "reasoning": result.get("reasoning")
                }
            }
        except Exception as e:
            return {
                "score": 0.0,
                "passed": False,
                "error": str(e)
            }


class ConversationFlowScorer(BaseScorer):
    """Scores the natural flow and coherence of the conversation"""
    
    def __init__(self, model: str = "gpt-4.1"):
        super().__init__("conversation_flow")
        self.model = model
    
    async def score(self, 
                   agent_response: Dict[str, Any], 
                   conversation: Dict[str, Any],
                   expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Score conversation flow using LLM judge"""
        
        # Build full conversation including agent response
        messages = conversation.get('messages', [])
        messages_str = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        agent_content = agent_response.get('content', '')
        
        # Check for specific flow expectations
        flow_expectations = []
        for exp_data in expectations:
            exp = exp_data.get('expectations', {})
            if exp.get('asks_clarification'):
                flow_expectations.append("Should ask for clarification")
            if exp.get('confirms_details'):
                flow_expectations.append(f"Should confirm details: {exp['confirms_details']}")
            if exp.get('offers_alternatives'):
                flow_expectations.append("Should offer alternatives")
        
        prompt = f"""Analyze the conversation flow and determine if the assistant's response is natural and appropriate.

Conversation:
{messages_str}

Assistant Response: {agent_content}

Flow Expectations: {flow_expectations or ["Natural, coherent conversation"]}

Respond with a JSON object containing:
- "natural_flow": true/false whether the conversation flows naturally
- "appropriate_response": true/false whether the response is appropriate for the context
- "meets_expectations": true/false whether specific flow expectations are met
- "score": 0.0 to 1.0 rating
- "reasoning": Brief explanation
"""
        
        try:
            response = await acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "score": result.get("score", 0.0),
                "passed": result.get("meets_expectations", True) and result.get("natural_flow", True),
                "details": {
                    "natural_flow": result.get("natural_flow"),
                    "appropriate_response": result.get("appropriate_response"),
                    "reasoning": result.get("reasoning")
                }
            }
        except Exception as e:
            return {
                "score": 0.0,
                "passed": False,
                "error": str(e)
            } 