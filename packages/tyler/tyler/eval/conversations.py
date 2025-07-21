"""Conversation and Turn definitions for agent evaluations"""
from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass, field
from .expectations import Expectation


@dataclass
class Turn:
    """Represents a single turn in a conversation.
    
    A turn can be from either the user or the assistant, and can have
    expectations about what the assistant should do/say.
    """
    role: str  # "user" or "assistant"
    content: Optional[str] = None
    expect: Optional[Expectation] = None
    
    def __post_init__(self):
        if self.role not in ["user", "assistant"]:
            raise ValueError(f"Role must be 'user' or 'assistant', got '{self.role}'")
        
        if self.role == "user" and self.expect is not None:
            raise ValueError("User turns cannot have expectations")
            
        if self.role == "assistant" and self.content is not None:
            raise ValueError("Assistant turns should not have pre-defined content in evaluations")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert turn to dictionary"""
        result = {"role": self.role}
        
        if self.content is not None:
            result["content"] = self.content
            
        if self.expect is not None:
            result["expect"] = self.expect.to_dict()
            
        return result


@dataclass
class Conversation:
    """Represents a test conversation for evaluation.
    
    Can be either:
    1. A simple single-turn conversation (user message + expectations)
    2. A multi-turn conversation with multiple turns
    """
    # Conversation identifier
    id: Optional[str] = None
    
    # For single-turn conversations
    user: Optional[str] = None
    expect: Optional[Expectation] = None
    
    # For multi-turn conversations
    turns: Optional[List[Turn]] = None
    
    # Metadata
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Validate that we have either single-turn or multi-turn, not both
        has_single = self.user is not None
        has_multi = self.turns is not None
        
        if has_single and has_multi:
            raise ValueError("Cannot specify both 'user' and 'turns' - use one or the other")
            
        if not has_single and not has_multi:
            raise ValueError("Must specify either 'user' (for single-turn) or 'turns' (for multi-turn)")
            
        # For single-turn, create the turns list
        if has_single:
            self._turns = [
                Turn(role="user", content=self.user),
                Turn(role="assistant", expect=self.expect)
            ]
        else:
            self._turns = self.turns
            
        # Validate turns
        self._validate_turns()
        
        # Auto-generate ID if not provided
        if self.id is None:
            if self.user:
                # Use first few words of user message
                self.id = "_".join(self.user.split()[:3]).lower().replace("?", "")
            else:
                self.id = f"conversation_{id(self)}"
    
    def _validate_turns(self):
        """Validate the conversation turns"""
        if not self._turns:
            raise ValueError("Conversation must have at least one turn")
            
        # First turn should be from user
        if self._turns[0].role != "user":
            raise ValueError("First turn must be from user")
            
        # Alternating turns (simple validation)
        for i in range(1, len(self._turns)):
            if self._turns[i].role == self._turns[i-1].role:
                raise ValueError(f"Turns must alternate between user and assistant (turn {i})")
    
    @property
    def all_turns(self) -> List[Turn]:
        """Get all turns in the conversation"""
        return self._turns
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary for Weave dataset"""
        result = {
            "conversation_id": self.id,
            "messages": []
        }
        
        # Build message list
        for turn in self._turns:
            if turn.role == "user":
                result["messages"].append({
                    "role": "user",
                    "content": turn.content
                })
        
        # Collect all expectations
        expectations = []
        for i, turn in enumerate(self._turns):
            if turn.expect is not None:
                expectations.append({
                    "turn_index": i,
                    "expectations": turn.expect.to_dict()
                })
        
        result["expectations"] = expectations
        
        # Add metadata
        if self.description:
            result["description"] = self.description
        if self.tags:
            result["tags"] = self.tags
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result
    
    def get_user_messages(self) -> List[str]:
        """Get all user messages in order"""
        return [turn.content for turn in self._turns if turn.role == "user"]
    
    def get_expectations(self) -> List[Expectation]:
        """Get all expectations in the conversation"""
        return [turn.expect for turn in self._turns if turn.expect is not None] 