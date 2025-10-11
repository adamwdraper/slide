"""Tests for MessageFactory."""
import pytest
from datetime import datetime, UTC, timedelta
from narrator import Message, Attachment
from tyler.models.message_factory import MessageFactory


class TestMessageFactoryInit:
    """Test MessageFactory initialization."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        factory = MessageFactory(agent_name="TestAgent", model_name="gpt-4")
        
        assert factory.agent_name == "TestAgent"
        assert factory.model_name == "gpt-4"


class TestCreateAssistantMessage:
    """Test creating assistant messages."""
    
    def test_create_basic(self):
        """Test creating basic assistant message."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_assistant_message("Hello, world!")
        
        assert message.role == "assistant"
        assert message.content == "Hello, world!"
        assert message.tool_calls is None
        assert message.source["name"] == "TestAgent"
        assert message.source["type"] == "agent"
        assert message.source["attributes"]["model"] == "gpt-4"
    
    def test_create_with_tool_calls(self):
        """Test creating assistant message with tool calls."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": "{}"}
            }
        ]
        
        message = factory.create_assistant_message(
            content="Let me check that for you.",
            tool_calls=tool_calls
        )
        
        assert message.role == "assistant"
        assert message.content == "Let me check that for you."
        assert message.tool_calls == tool_calls
        assert len(message.tool_calls) == 1
    
    def test_create_with_metrics(self):
        """Test creating assistant message with metrics."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        metrics = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            },
            "timing": {"latency": 250}
        }
        
        message = factory.create_assistant_message(
            content="Response",
            metrics=metrics
        )
        
        assert message.metrics == metrics
        assert message.metrics["usage"]["total_tokens"] == 150


class TestCreateToolMessage:
    """Test creating tool messages."""
    
    def test_create_basic(self):
        """Test creating basic tool message."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_tool_message(
            tool_name="get_weather",
            content="Temperature is 72°F",
            tool_call_id="call_123"
        )
        
        assert message.role == "tool"
        assert message.name == "get_weather"
        assert message.content == "Temperature is 72°F"
        assert message.tool_call_id == "call_123"
        assert message.source["name"] == "get_weather"
        assert message.source["type"] == "tool"
        assert message.source["attributes"]["agent_id"] == "TestAgent"
    
    def test_create_with_attachments(self):
        """Test creating tool message with attachments."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        attachment = Attachment(
            filename="result.txt",
            content=b"Test content",
            mime_type="text/plain"
        )
        
        message = factory.create_tool_message(
            tool_name="generate_file",
            content="File generated",
            tool_call_id="call_456",
            attachments=[attachment]
        )
        
        assert len(message.attachments) == 1
        assert message.attachments[0].filename == "result.txt"
    
    def test_create_with_metrics(self):
        """Test creating tool message with metrics."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        metrics = {
            "timing": {
                "started_at": "2025-01-11T10:00:00Z",
                "ended_at": "2025-01-11T10:00:01Z",
                "latency": 1000
            }
        }
        
        message = factory.create_tool_message(
            tool_name="slow_tool",
            content="Done",
            tool_call_id="call_789",
            metrics=metrics
        )
        
        assert message.metrics == metrics
        assert message.metrics["timing"]["latency"] == 1000
    
    def test_create_with_multiple_attachments(self):
        """Test creating tool message with multiple attachments."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        attachments = [
            Attachment(filename="file1.txt", content=b"1", mime_type="text/plain"),
            Attachment(filename="file2.txt", content=b"2", mime_type="text/plain")
        ]
        
        message = factory.create_tool_message(
            tool_name="multi_file_tool",
            content="Files generated",
            tool_call_id="call_multi",
            attachments=attachments
        )
        
        assert len(message.attachments) == 2
        assert message.attachments[0].filename == "file1.txt"
        assert message.attachments[1].filename == "file2.txt"


class TestCreateErrorMessage:
    """Test creating error messages."""
    
    def test_create_basic(self):
        """Test creating basic error message."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_error_message("Something went wrong")
        
        assert message.role == "assistant"
        assert "I encountered an error" in message.content
        assert "Something went wrong" in message.content
        assert "Please try again" in message.content
        assert message.source["name"] == "TestAgent"
        assert message.metrics is not None
        assert "timing" in message.metrics
    
    def test_create_without_preamble(self):
        """Test creating error message without preamble."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_error_message(
            "Error occurred",
            include_preamble=False
        )
        
        assert message.content == "Error occurred"
        assert "I encountered an error" not in message.content
    
    def test_create_with_custom_source(self):
        """Test creating error message with custom source."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        custom_source = {
            "id": "custom",
            "name": "Custom Source",
            "type": "agent"  # Must be valid type: 'user', 'agent', or 'tool'
        }
        
        message = factory.create_error_message(
            "Error",
            source=custom_source
        )
        
        assert message.source == custom_source
        assert message.source["name"] == "Custom Source"
    
    def test_error_message_has_zero_latency(self):
        """Test that error messages have zero latency."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_error_message("Test error")
        
        assert message.metrics["timing"]["latency"] == 0


class TestCreateSystemMessage:
    """Test creating system messages."""
    
    def test_create_basic(self):
        """Test creating basic system message."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_system_message("System prompt here")
        
        assert message.role == "system"
        assert message.content == "System prompt here"
        assert message.source["name"] == "TestAgent"
    
    def test_create_with_custom_source(self):
        """Test creating system message with custom source."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        custom_source = {"id": "system", "name": "System", "type": "agent"}  # Must be valid type
        
        message = factory.create_system_message(
            "Custom system message",
            source=custom_source
        )
        
        assert message.source == custom_source


class TestCreateMaxIterationsMessage:
    """Test creating max iterations message."""
    
    def test_create(self):
        """Test creating max iterations message."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        message = factory.create_max_iterations_message()
        
        assert message.role == "assistant"
        assert "Maximum tool iteration count reached" in message.content
        assert message.source["name"] == "TestAgent"


class TestSourceCreation:
    """Test source dict creation methods."""
    
    def test_agent_source(self):
        """Test agent source creation."""
        factory = MessageFactory("MyAgent", "gpt-4.1")
        
        source = factory._create_agent_source()
        
        assert source["id"] == "MyAgent"
        assert source["name"] == "MyAgent"
        assert source["type"] == "agent"
        assert source["attributes"]["model"] == "gpt-4.1"
    
    def test_tool_source(self):
        """Test tool source creation."""
        factory = MessageFactory("MyAgent", "gpt-4")
        
        source = factory._create_tool_source("my_tool")
        
        assert source["id"] == "my_tool"
        assert source["name"] == "my_tool"
        assert source["type"] == "tool"
        assert source["attributes"]["agent_id"] == "MyAgent"


class TestTimingMetrics:
    """Test timing metrics creation."""
    
    def test_create_with_end_time(self):
        """Test creating timing metrics with explicit end time."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        start = datetime(2025, 1, 11, 10, 0, 0, tzinfo=UTC)
        end = datetime(2025, 1, 11, 10, 0, 1, tzinfo=UTC)  # 1 second later
        
        metrics = factory.create_tool_timing_metrics(start, end)
        
        assert "timing" in metrics
        assert metrics["timing"]["latency"] == 1000  # 1000ms
        assert metrics["timing"]["started_at"] == start.isoformat()
        assert metrics["timing"]["ended_at"] == end.isoformat()
    
    def test_create_without_end_time(self):
        """Test creating timing metrics without end time (uses current time)."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        start = datetime.now(UTC) - timedelta(milliseconds=500)
        
        metrics = factory.create_tool_timing_metrics(start)
        
        assert "timing" in metrics
        # Should be approximately 500ms (with some tolerance for execution time)
        assert 450 <= metrics["timing"]["latency"] <= 600
    
    def test_timing_format(self):
        """Test timing metrics format."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        start = datetime.now(UTC)
        end = start + timedelta(milliseconds=250)
        
        metrics = factory.create_tool_timing_metrics(start, end)
        
        assert isinstance(metrics, dict)
        assert "timing" in metrics
        assert "started_at" in metrics["timing"]
        assert "ended_at" in metrics["timing"]
        assert "latency" in metrics["timing"]
        assert isinstance(metrics["timing"]["latency"], (int, float))


class TestMessageConsistency:
    """Test that all messages have consistent structure."""
    
    def test_all_messages_have_source(self):
        """Test that all message types have source."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        assistant = factory.create_assistant_message("test")
        tool = factory.create_tool_message("tool", "result", "call_1")
        error = factory.create_error_message("error")
        system = factory.create_system_message("system")
        max_iter = factory.create_max_iterations_message()
        
        for msg in [assistant, tool, error, system, max_iter]:
            assert msg.source is not None
            assert "name" in msg.source
            assert "type" in msg.source
    
    def test_agent_messages_have_consistent_source(self):
        """Test that agent messages have consistent source."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        msg1 = factory.create_assistant_message("test1")
        msg2 = factory.create_error_message("error")
        msg3 = factory.create_system_message("system")
        
        # All agent messages should have same base source structure
        assert msg1.source["id"] == msg2.source["id"] == msg3.source["id"]
        assert msg1.source["name"] == msg2.source["name"] == msg3.source["name"]
        assert msg1.source["type"] == msg2.source["type"] == msg3.source["type"]


class TestFactoryReuse:
    """Test that factory can be reused for multiple messages."""
    
    def test_create_multiple_messages(self):
        """Test creating multiple messages with same factory."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        messages = [
            factory.create_assistant_message(f"Message {i}")
            for i in range(5)
        ]
        
        assert len(messages) == 5
        for i, msg in enumerate(messages):
            assert msg.content == f"Message {i}"
            assert msg.source["name"] == "TestAgent"
    
    def test_factory_state_not_shared(self):
        """Test that messages don't share mutable state."""
        factory = MessageFactory("TestAgent", "gpt-4")
        
        msg1 = factory.create_assistant_message("First")
        msg2 = factory.create_assistant_message("Second")
        
        # Messages should be independent
        assert msg1.content != msg2.content
        # But sources should have same values (different objects)
        assert msg1.source["name"] == msg2.source["name"]

