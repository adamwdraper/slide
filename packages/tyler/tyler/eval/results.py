"""Result classes for agent evaluations"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Score:
    """Individual score result from a scorer"""
    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    @property
    def failed(self) -> bool:
        return not self.passed


@dataclass
class ConversationResult:
    """Result of evaluating a single conversation"""
    conversation_id: str
    scores: List[Score]
    agent_response: Dict[str, Any]
    passed: bool = True
    
    def __post_init__(self):
        # Conversation passes if all scores pass
        self.passed = all(score.passed for score in self.scores)
    
    @property
    def failed(self) -> bool:
        return not self.passed
    
    @property
    def average_score(self) -> float:
        """Calculate average score across all scorers"""
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)
    
    def get_score(self, scorer_name: str) -> Optional[Score]:
        """Get score by scorer name"""
        for score in self.scores:
            if score.name == scorer_name:
                return score
        return None
    
    def get_failed_scores(self) -> List[Score]:
        """Get all failed scores"""
        return [s for s in self.scores if s.failed]


@dataclass 
class EvalResults:
    """Complete results from an evaluation run"""
    evaluation_name: str
    agent_name: str
    timestamp: datetime
    conversations: List[ConversationResult]
    weave_run_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_conversations(self) -> int:
        return len(self.conversations)
    
    @property
    def passed_conversations(self) -> int:
        return sum(1 for c in self.conversations if c.passed)
    
    @property
    def failed_conversations(self) -> int:
        return sum(1 for c in self.conversations if c.failed)
    
    @property
    def pass_rate(self) -> float:
        """Overall pass rate (0.0 to 1.0)"""
        if not self.conversations:
            return 0.0
        return self.passed_conversations / self.total_conversations
    
    @property
    def average_score(self) -> float:
        """Average score across all conversations"""
        if not self.conversations:
            return 0.0
        return sum(c.average_score for c in self.conversations) / len(self.conversations)
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationResult]:
        """Get result for specific conversation"""
        for conv in self.conversations:
            if conv.conversation_id == conversation_id:
                return conv
        return None
    
    def get_failed_conversations(self) -> List[ConversationResult]:
        """Get all failed conversations"""
        return [c for c in self.conversations if c.failed]
    
    def score_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary statistics by scorer"""
        scorer_stats = {}
        
        for conv in self.conversations:
            for score in conv.scores:
                if score.name not in scorer_stats:
                    scorer_stats[score.name] = {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "scores": [],
                        "pass_rate": 0.0,
                        "average_score": 0.0
                    }
                
                stats = scorer_stats[score.name]
                stats["total"] += 1
                stats["scores"].append(score.score)
                
                if score.passed:
                    stats["passed"] += 1
                else:
                    stats["failed"] += 1
        
        # Calculate aggregates
        for name, stats in scorer_stats.items():
            stats["pass_rate"] = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
            stats["average_score"] = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0.0
            del stats["scores"]  # Remove raw scores from summary
            
        return scorer_stats
    
    def summary(self) -> str:
        """Generate human-readable summary"""
        lines = [
            f"{self.evaluation_name} Results:",
            f"{'✅' if self.pass_rate >= 0.8 else '❌'} {self.passed_conversations}/{self.total_conversations} tests passed ({self.pass_rate*100:.0f}%)",
            "",
            "By Category:"
        ]
        
        scorer_stats = self.score_summary()
        for scorer_name, stats in scorer_stats.items():
            emoji = "✅" if stats["pass_rate"] >= 0.8 else "❌"
            lines.append(
                f"- {scorer_name}: {stats['passed']}/{stats['total']} "
                f"({stats['pass_rate']*100:.0f}%) avg: {stats['average_score']:.2f}"
            )
        
        if self.failed_conversations:
            lines.extend(["", "Failed Tests:"])
            for conv in self.get_failed_conversations():
                failed_scores = conv.get_failed_scores()
                reasons = ", ".join([f"{s.name}: {s.details.get('reasoning', 'failed')}" 
                                   for s in failed_scores][:2])  # Show first 2 reasons
                lines.append(f"- {conv.conversation_id}: {reasons}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "evaluation_name": self.evaluation_name,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "total_conversations": self.total_conversations,
            "passed_conversations": self.passed_conversations,
            "failed_conversations": self.failed_conversations,
            "pass_rate": self.pass_rate,
            "average_score": self.average_score,
            "score_summary": self.score_summary(),
            "failed_conversations": [
                {
                    "id": c.conversation_id,
                    "failed_scores": [s.name for s in c.get_failed_scores()]
                }
                for c in self.get_failed_conversations()
            ],
            "weave_run_id": self.weave_run_id,
            "metadata": self.metadata
        } 