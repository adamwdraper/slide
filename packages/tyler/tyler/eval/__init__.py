"""Tyler Agent Evaluation Framework

A simple, agent-focused API for evaluating Tyler agents using Weave under the hood.
"""

from .expectations import Expectation
from .conversations import Turn, Conversation
from .agent_eval import AgentEval
from .scorers import (
    ToolUsageScorer,
    ToneScorer,
    TaskCompletionScorer,
    ConversationFlowScorer
)
from .results import EvalResults, ConversationResult, Score
from .mock_tools import (
    MockTool, 
    MockToolRegistry, 
    mock_success,
    mock_error,
    mock_from_args
)

__all__ = [
    # Core evaluation classes
    "AgentEval",
    "Conversation",
    "Turn",
    "Expectation",
    
    # Scorers
    "ToolUsageScorer",
    "ToneScorer", 
    "TaskCompletionScorer",
    "ConversationFlowScorer",
    
    # Results
    "EvalResults",
    "ConversationResult",
    "Score",
    
    # Mock tools for safe evaluation
    "MockTool",
    "MockToolRegistry",
    "mock_success",
    "mock_error",
    "mock_from_args"
] 