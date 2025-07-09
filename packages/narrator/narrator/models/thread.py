from typing import List, Dict, Optional, Literal, Any
from datetime import datetime, UTC
from pydantic import BaseModel, Field, field_validator
from narrator.models.message import Message
from narrator.storage.file_store import FileStore
import uuid
from narrator.utils.logging import get_logger

logger = get_logger(__name__)

class Thread(BaseModel):
    """Represents a thread containing multiple messages"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = Field(default="Untitled Thread")
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attributes: Dict = Field(default_factory=dict)
    platforms: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="References to where this thread exists on external platforms. Maps platform name to platform-specific identifiers."
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "thread-123",
                    "title": "Example Thread",
                    "messages": [],
                    "created_at": "2024-02-07T00:00:00+00:00",
                    "updated_at": "2024-02-07T00:00:00+00:00",
                    "attributes": {},
                    "platforms": {
                        "slack": {
                        "channel": "C123",
                        "thread_ts": "1234567890.123"
                        }
                    }
                }
            ]
        }
    }
    
    @field_validator("created_at", "updated_at", mode="before")
    def ensure_timezone(cls, value: datetime) -> datetime:
        """Ensure all datetime fields are timezone-aware UTC"""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        """Convert thread to a dictionary suitable for JSON serialization
        
        Args:
            mode: Serialization mode, either "json" or "python". 
                 "json" converts datetimes to ISO strings (default).
                 "python" keeps datetimes as datetime objects.
        """
        return {
            "id": self.id,
            "title": self.title,
            "messages": [msg.model_dump(mode=mode) for msg in self.messages],
            "created_at": self.created_at.isoformat() if mode == "json" else self.created_at,
            "updated_at": self.updated_at.isoformat() if mode == "json" else self.updated_at,
            "attributes": self.attributes,
            "platforms": self.platforms
        }
    
    def add_message(self, message: Message, same_turn: bool = False) -> None:
        """Add a new message to the thread and update analytics
        
        Args:
            message: The message to add
            same_turn: If True, assign the same turn as the last message (for grouping related messages)
        """
        # Set message sequence - system messages always get 0, others get next available number starting at 1
        if message.role == "system":
            message.sequence = 0
            message.turn = 0  # System messages always get turn 0
            # Insert at beginning to maintain system message first
            self.messages.insert(0, message)
        else:
            # Find highest sequence number and increment
            max_sequence = max((m.sequence for m in self.messages if m.role != "system"), default=0)
            message.sequence = max_sequence + 1
            self.messages.append(message)
        
        # Handle turn assignment for non-system messages
        if message.role != "system":
            if same_turn and self.messages and len(self.messages) > 1:
                # Use same turn as last message (excluding the one we just added)
                last_message = self.messages[-2]  # Get second-to-last since we just appended
                if last_message.role != "system":
                    message.turn = last_message.turn
                else:
                    # If last message was system, get next turn
                    max_turn = max((m.turn for m in self.messages if m.turn is not None and m.role != "system"), default=0)
                    message.turn = max_turn + 1
            else:
                # Get next turn number
                max_turn = max((m.turn for m in self.messages if m.turn is not None and m.role != "system"), default=0)
                message.turn = max_turn + 1
        
        self.updated_at = datetime.now(UTC)

    def add_messages_batch(self, messages: List[Message]) -> None:
        """Add multiple messages as a batch (all get the same turn number)
        
        Args:
            messages: List of messages to add as a group
        """
        if not messages:
            return
        
        # Get the next turn number for all messages in the batch
        max_turn = max((m.turn for m in self.messages if m.turn is not None and m.role != "system"), default=0)
        batch_turn = max_turn + 1
        
        # Add each message with the same turn number
        for i, message in enumerate(messages):
            if message.role == "system":
                # System messages handled separately
                message.sequence = 0
                message.turn = 0
                self.messages.insert(0, message)
            else:
                # Set sequence and turn for non-system messages
                max_sequence = max((m.sequence for m in self.messages if m.role != "system"), default=0)
                message.sequence = max_sequence + 1
                message.turn = batch_turn
                self.messages.append(message)
        
        self.updated_at = datetime.now(UTC)

    async def get_messages_for_chat_completion(self, file_store: Optional[FileStore] = None) -> List[Dict[str, Any]]:
        """Return messages in the format expected by chat completion APIs
        
        Note: This excludes system messages as they are injected by agents at completion time.
        
        Args:
            file_store: Optional FileStore instance to pass to messages for file URL access
        """
        # Only include non-system messages from the thread - system messages are injected by agents
        return [msg.to_chat_completion_message(file_store=file_store) for msg in self.messages if msg.role != "system"]

    def clear_messages(self) -> None:
        """Clear all messages from the thread"""
        self.messages = []
        self.updated_at = datetime.now(UTC)

    def get_last_message_by_role(self, role: Literal["user", "assistant", "system", "tool"]) -> Optional[Message]:
        """Return the last message with the specified role, or None if no messages exist with that role"""
        messages = [m for m in self.messages if m.role == role]
        return messages[-1] if messages else None
        
    def generate_title(self) -> str:
        """Generate a simple title for the thread based on first message"""
        if not self.messages:
            return "Empty Thread"
        
        # Use first user message content for title
        user_messages = [msg for msg in self.messages if msg.role == "user"]
        if user_messages:
            first_content = user_messages[0].content
            if isinstance(first_content, str):
                # Take first 50 characters and add ellipsis if needed
                title = first_content[:50]
                if len(first_content) > 50:
                    title += "..."
                self.title = title
                self.updated_at = datetime.now(UTC)
                return title
        
        return "Untitled Thread"

    def get_total_tokens(self) -> Dict[str, Any]:
        """Get total token usage across all messages in the thread
        
        Returns:
            Dictionary containing:
            - overall: Total token counts across all models
            - by_model: Token counts broken down by model
        """
        overall = {
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "total_tokens": 0
        }
        
        by_model = {}
        
        for message in self.messages:
            metrics = message.metrics
            if not metrics:
                continue
                
            # Update overall counts
            if "usage" in metrics:
                overall["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                overall["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                overall["total_tokens"] += metrics["usage"].get("total_tokens", 0)
            
            # Update per-model counts
            model = metrics.get("model")
            if model:
                if model not in by_model:
                    by_model[model] = {
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "total_tokens": 0
                    }
                
                if "usage" in metrics:
                    by_model[model]["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                    by_model[model]["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                    by_model[model]["total_tokens"] += metrics["usage"].get("total_tokens", 0)
            
        return {
            "overall": overall,
            "by_model": by_model
        }

    def get_model_usage(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a specific model or all models
        
        Args:
            model_name: Optional name of model to get stats for. If None, returns all models.
            
        Returns:
            Dictionary containing model usage statistics
        """
        model_usage = {}
        
        for message in self.messages:
            metrics = message.metrics
            if not metrics or not metrics.get("model"):
                continue
                
            model = metrics["model"]
            if model not in model_usage:
                model_usage[model] = {
                    "calls": 0,
                    "completion_tokens": 0,
                    "prompt_tokens": 0,
                    "total_tokens": 0
                }
            
            model_usage[model]["calls"] += 1
            if "usage" in metrics:
                model_usage[model]["completion_tokens"] += metrics["usage"].get("completion_tokens", 0)
                model_usage[model]["prompt_tokens"] += metrics["usage"].get("prompt_tokens", 0)
                model_usage[model]["total_tokens"] += metrics["usage"].get("total_tokens", 0)
        
        if model_name:
            return model_usage.get(model_name, {
                "calls": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0
            })
            
        return model_usage

    def get_message_timing_stats(self) -> Dict[str, Any]:
        """Calculate timing statistics across all messages
        
        Returns:
            Dictionary containing:
            - total_latency: Total processing time across all messages (in milliseconds)
            - average_latency: Average processing time per message (in milliseconds)
            - message_count: Total number of messages with timing data
        """
        total_latency = 0
        message_count = 0
        
        for message in self.messages:
            if message.metrics and message.metrics.get("timing", {}).get("latency"):
                total_latency += message.metrics["timing"]["latency"]
                message_count += 1
        
        return {
            "total_latency": total_latency,
            "average_latency": total_latency / message_count if message_count > 0 else 0,
            "message_count": message_count
        }

    def get_message_counts(self) -> Dict[str, int]:
        """Get count of messages by role
        
        Returns:
            Dictionary with counts for each role (system, user, assistant, tool)
        """
        counts = {
            "system": 0,
            "user": 0,
            "assistant": 0,
            "tool": 0
        }
        
        for message in self.messages:
            counts[message.role] += 1
            
        return counts

    def get_tool_usage(self) -> Dict[str, Any]:
        """Get count of tool function calls in the thread
        
        Returns:
            Dictionary containing:
            - tools: Dictionary of tool names and their call counts
            - total_calls: Total number of tool calls made
        """
        tool_counts = {}  # {"tool_name": count}
        
        for message in self.messages:
            if message.role == "assistant" and message.tool_calls:
                for call in message.tool_calls:
                    if isinstance(call, dict):
                        tool_name = call.get("function", {}).get("name")
                    else:
                        # Handle OpenAI tool call objects
                        tool_name = getattr(call.function, "name", None)
                        
                    if tool_name:
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        return {
            "tools": tool_counts,
            "total_calls": sum(tool_counts.values())
        }

    def get_system_message(self) -> Optional[Message]:
        """Get the system message from the thread if it exists"""
        for message in self.messages:
            if message.role == "system":
                return message
        return None

    def get_messages_in_sequence(self) -> List[Message]:
        """Get messages sorted by sequence number"""
        return sorted(self.messages, key=lambda m: m.sequence if m.sequence is not None else float('inf'))

    def get_messages_by_turn(self, turn: int) -> List[Message]:
        """Get all messages in a specific turn
        
        Args:
            turn: The turn number to retrieve messages for
            
        Returns:
            List of messages in the specified turn, sorted by sequence
        """
        turn_messages = [m for m in self.messages if m.turn == turn]
        return sorted(turn_messages, key=lambda m: m.sequence if m.sequence is not None else float('inf'))

    def get_current_turn(self) -> int:
        """Get the current turn number (highest turn number in the thread)
        
        Returns:
            Current turn number, or 0 if no messages
        """
        if not self.messages:
            return 0
        
        # Exclude system messages when determining current turn
        non_system_messages = [m for m in self.messages if m.role != "system"]
        if not non_system_messages:
            return 0
            
        return max(m.turn for m in non_system_messages if m.turn is not None)

    def get_turns_summary(self) -> Dict[int, Dict[str, Any]]:
        """Get a summary of all turns in the thread
        
        Returns:
            Dictionary mapping turn numbers to turn information
        """
        turns = {}
        
        for message in self.messages:
            if message.turn is None or message.role == "system":
                continue
                
            turn = message.turn
            if turn not in turns:
                turns[turn] = {
                    "turn": turn,
                    "message_count": 0,
                    "roles": {},
                    "first_message_time": message.timestamp,
                    "last_message_time": message.timestamp
                }
            
            turns[turn]["message_count"] += 1
            turns[turn]["roles"][message.role] = turns[turn]["roles"].get(message.role, 0) + 1
            
            # Update timestamps
            if message.timestamp < turns[turn]["first_message_time"]:
                turns[turn]["first_message_time"] = message.timestamp
            if message.timestamp > turns[turn]["last_message_time"]:
                turns[turn]["last_message_time"] = message.timestamp
        
        return turns

    def get_message_by_id(self, message_id: str) -> Optional[Message]:
        """Return the message with the specified ID, or None if no message exists with that ID"""
        for message in self.messages:
            if message.id == message_id:
                return message
        return None

    def add_reaction(self, message_id: str, emoji: str, user_id: str) -> bool:
        """Add a reaction to a message in the thread
        
        Args:
            message_id: ID of the message to react to
            emoji: Emoji shortcode (e.g., ":thumbsup:")
            user_id: ID of the user adding the reaction
            
        Returns:
            True if reaction was added, False if it wasn't (message not found or already reacted)
        """
        message = self.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Thread.add_reaction (thread_id={self.id}): Message with ID '{message_id}' not found.")
            return False
        
        result = message.add_reaction(emoji, user_id)
        if result:
            self.updated_at = datetime.now(UTC) # Ensure thread update time is changed
            logger.info(f"Thread.add_reaction (thread_id={self.id}): Message '{message_id}' reactions updated. Thread updated_at: {self.updated_at}")
        return result
    
    def remove_reaction(self, message_id: str, emoji: str, user_id: str) -> bool:
        """Remove a reaction from a message in the thread
        
        Args:
            message_id: ID of the message to remove reaction from
            emoji: Emoji shortcode (e.g., ":thumbsup:")
            user_id: ID of the user removing the reaction
            
        Returns:
            True if reaction was removed, False if it wasn't (message or reaction not found)
        """
        message = self.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Thread.remove_reaction (thread_id={self.id}): Message with ID '{message_id}' not found.")
            return False
            
        result = message.remove_reaction(emoji, user_id)
        if result:
            self.updated_at = datetime.now(UTC) # Ensure thread update time is changed
            logger.info(f"Thread.remove_reaction (thread_id={self.id}): Message '{message_id}' reactions updated. Thread updated_at: {self.updated_at}")
        return result
    
    def get_reactions(self, message_id: str) -> Dict[str, List[str]]:
        """Get all reactions for a message in the thread
        
        Args:
            message_id: ID of the message to get reactions for
            
        Returns:
            Dictionary mapping emoji to list of user IDs, or empty dict if message not found
        """
        message = self.get_message_by_id(message_id)
        if not message:
            return {}
            
        return message.get_reactions()