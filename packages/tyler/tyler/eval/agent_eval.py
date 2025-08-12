"""Main AgentEval class for orchestrating evaluations"""
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, UTC
import weave
from weave import Evaluation
import copy

from tyler import Agent
from .conversations import Conversation
from .scorers import BaseScorer
from .results import EvalResults, ConversationResult, Score
from .mock_tools import MockToolRegistry
from narrator import Thread, Message


class AgentEval:
    """Tyler-specific evaluation framework for agents.
    
    This class provides a simple, agent-focused API for evaluating Tyler agents
    while using Weave evaluations under the hood.
    """
    
    def __init__(self,
                 name: str,
                 conversations: List[Conversation],
                 scorers: List[BaseScorer],
                 description: Optional[str] = None,
                 trials: int = 1,
                 use_mock_tools: bool = True):
        """Initialize an agent evaluation.
        
        Args:
            name: Name for this evaluation
            conversations: List of test conversations
            scorers: List of scorers to apply
            description: Optional description
            trials: Number of times to run each conversation (default: 1)
            use_mock_tools: Whether to use mock tools for safety (default: True)
        """
        self.name = name
        self.conversations = conversations
        self.scorers = scorers
        self.description = description
        self.trials = trials
        self.use_mock_tools = use_mock_tools
        self.mock_registry = MockToolRegistry()
        
        # Store results during evaluation
        self._current_results = []
        
        # Validate conversations
        if not conversations:
            raise ValueError("Must provide at least one conversation")
        
        # Validate scorers
        if not scorers:
            raise ValueError("Must provide at least one scorer")
    
    def _create_weave_dataset(self) -> List[Dict[str, Any]]:
        """Convert conversations to Weave dataset format"""
        dataset = []
        for conv in self.conversations:
            dataset.append(conv.to_dict())
        return dataset
    
    def _create_weave_scorers(self) -> List:
        """Convert scorers to Weave scorer functions"""
        return [scorer.to_weave_scorer() for scorer in self.scorers]
    
    def _create_safe_agent(self, agent: Agent) -> Agent:
        """Create a copy of the agent with mocked tools if needed"""
        if not self.use_mock_tools:
            return agent
            
        # Create a copy of the agent with mocked tools
        safe_agent = copy.copy(agent)
        
        # Replace tools with mocks
        if hasattr(agent, 'tools') and agent.tools:
            mock_tools = self.mock_registry.get_mock_tools(agent.tools)
            safe_agent.tools = mock_tools
            
        return safe_agent
    
    async def _run_single_conversation(self, 
                                     agent: Agent, 
                                     conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run agent on a single conversation and return response.
        
        This is the function that Weave will call for each example.
        """
        messages = conversation_data['messages']
        conversation_id = conversation_data['conversation_id']
        expectations = conversation_data.get('expectations', [])
        
        # Create a safe copy of the agent with mock tools
        safe_agent = self._create_safe_agent(agent)
        
        # Create a new thread for this conversation
        thread = Thread()
        
        # Add all user messages to thread
        for msg in messages:
            if msg['role'] == 'user':
                thread.add_message(Message(
                    role="user",
                    content=msg['content']
                ))
        
        # Run agent on the thread
        result = await safe_agent.go(thread)
        
        # Extract agent response
        agent_messages = [m for m in result.new_messages if m.role == "assistant"]
        if not agent_messages:
            return {
                "content": "",
                "tool_calls": [],
                "error": "No assistant response generated",
                "mock_tools_used": self.use_mock_tools
            }
        
        last_message = agent_messages[-1]
        
        # Format response for scorers
        response = {
            "content": last_message.content or "",
            "tool_calls": last_message.tool_calls or [],
            "all_messages": [{"role": m.role, "content": m.content} for m in result.new_messages],
            "thread_id": result.thread.id,
            "mock_tools_used": self.use_mock_tools
        }
        
        # Format tool calls for scorers (extract names)
        if last_message.tool_calls:
            formatted_tool_calls = []
            for tc in last_message.tool_calls:
                if hasattr(tc, 'function'):
                    formatted_tool_calls.append({
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    })
                elif isinstance(tc, dict) and 'function' in tc:
                    formatted_tool_calls.append({
                        'name': tc['function']['name'],
                        'arguments': tc['function'].get('arguments', {})
                    })
            response["tool_calls"] = formatted_tool_calls
        
        # Add mock tool call history if using mocks
        if self.use_mock_tools:
            response["mock_tool_calls"] = {
                name: mock.call_history 
                for name, mock in self.mock_registry.mocks.items()
                if mock.was_called()
            }
        
        # Store the response with expectations for later processing
        self._current_results.append({
            'conversation_id': conversation_id,
            'response': response,
            'expectations': expectations,
            'messages': messages  # Add messages for scorer context
        })
            
        return response
    
    async def run(self, 
                  agent: Union[Agent, Any],
                  display_name: Optional[str] = None,
                  use_mock_tools: Optional[bool] = None) -> EvalResults:
        """Run the evaluation against an agent.
        
        Args:
            agent: The Tyler agent to evaluate
            display_name: Optional display name for this run
            use_mock_tools: Override the default mock tools setting for this run
            
        Returns:
            EvalResults with detailed results
        """
        if not isinstance(agent, Agent):
            raise TypeError(f"Expected Tyler Agent, got {type(agent)}")
        
        # Override mock tools setting if specified
        if use_mock_tools is not None:
            original_use_mock = self.use_mock_tools
            self.use_mock_tools = use_mock_tools
        
        try:
            # Reset mock tool histories
            self.mock_registry.reset_all()
            
            # Clear previous results
            self._current_results = []
            
            # Create Weave evaluation
            dataset = self._create_weave_dataset()
            weave_scorers = self._create_weave_scorers()
            
            # Create a wrapper function for the agent
            @weave.op(name=f"tyler_agent_{agent.name}")
            async def agent_predict(conversation_id: str,
                                  messages: List[Dict[str, Any]],
                                  expectations: List[Dict[str, Any]]) -> Dict[str, Any]:
                conversation_data = {
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "expectations": expectations
                }
                return await self._run_single_conversation(agent, conversation_data)
            
            # Create Weave evaluation
            weave_eval = Evaluation(
                dataset=dataset,
                scorers=weave_scorers,
                evaluation_name=self.name,
                trials=self.trials
            )
            
            # Run evaluation
            start_time = datetime.now(UTC)
            eval_result = await weave_eval.evaluate(
                agent_predict,
                __weave={"display_name": display_name or f"{self.name}_{agent.name}"}
            )
            
            # Process results into Tyler format
            conversation_results = []
            
            # Process the results we stored during evaluation
            for i, result_data in enumerate(self._current_results):
                conv_id = result_data['conversation_id']
                agent_response = result_data['response']
                expectations = result_data['expectations']
                
                # Run scorers on this conversation
                scores = []
                for scorer in self.scorers:
                    conversation = {
                        'conversation_id': conv_id,
                        'messages': [msg for msg in result_data.get('messages', [])]
                    }
                    
                    try:
                        score_result = await scorer.score(
                            agent_response,
                            conversation,
                            expectations
                        )
                        
                        scores.append(Score(
                            name=scorer.name,
                            score=score_result.get('score', 0.0),
                            passed=score_result.get('passed', False),
                            details=score_result.get('details', {}),
                            error=score_result.get('error')
                        ))
                    except Exception as e:
                        scores.append(Score(
                            name=scorer.name,
                            score=0.0,
                            passed=False,
                            details={},
                            error=str(e)
                        ))
                
                conversation_results.append(ConversationResult(
                    conversation_id=conv_id,
                    scores=scores,
                    agent_response=agent_response
                ))
            
            # Create final results
            results = EvalResults(
                evaluation_name=self.name,
                agent_name=agent.name,
                timestamp=start_time,
                conversations=conversation_results,
                weave_run_id=getattr(eval_result, 'id', None),
                metadata={
                    "description": self.description,
                    "trials": self.trials,
                    "scorer_names": [s.name for s in self.scorers],
                    "mock_tools_used": self.use_mock_tools
                }
            )
            
            # Add warning if real tools were used
            if not self.use_mock_tools:
                print("\n⚠️  WARNING: This evaluation used REAL tools - actual API calls may have been made!")
            
            return results
            
        finally:
            # Restore original mock tools setting
            if use_mock_tools is not None:
                self.use_mock_tools = original_use_mock
    
    async def evaluate(self, agent: Agent, **kwargs) -> EvalResults:
        """Alias for run() method for consistency with Weave API"""
        return await self.run(agent, **kwargs) 