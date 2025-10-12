"""Tests for ToolCall value object."""
import pytest
import json
from tyler.models.tool_call import (
    ToolCall, 
    normalize_tool_calls, 
    serialize_tool_calls
)


class TestToolCallFromDict:
    """Test ToolCall.from_llm_response() with dict format."""
    
    def test_from_dict_basic(self):
        """Test creating ToolCall from dict with basic arguments."""
        tool_call_dict = {
            'id': 'call_123',
            'type': 'function',
            'function': {
                'name': 'get_weather',
                'arguments': '{"location": "San Francisco"}'
            }
        }
        
        tool_call = ToolCall.from_llm_response(tool_call_dict)
        
        assert tool_call.id == 'call_123'
        assert tool_call.name == 'get_weather'
        assert tool_call.arguments == {'location': 'San Francisco'}
    
    def test_from_dict_empty_arguments(self):
        """Test dict with empty arguments string."""
        tool_call_dict = {
            'id': 'call_456',
            'function': {
                'name': 'no_args_tool',
                'arguments': ''
            }
        }
        
        tool_call = ToolCall.from_llm_response(tool_call_dict)
        
        assert tool_call.id == 'call_456'
        assert tool_call.name == 'no_args_tool'
        assert tool_call.arguments == {}
    
    def test_from_dict_null_arguments(self):
        """Test dict with None/null arguments."""
        tool_call_dict = {
            'id': 'call_789',
            'function': {
                'name': 'another_tool',
                'arguments': None
            }
        }
        
        tool_call = ToolCall.from_llm_response(tool_call_dict)
        
        assert tool_call.id == 'call_789'
        assert tool_call.arguments == {}
    
    def test_from_dict_complex_arguments(self):
        """Test dict with complex nested arguments."""
        tool_call_dict = {
            'id': 'call_complex',
            'function': {
                'name': 'complex_tool',
                'arguments': json.dumps({
                    'params': {
                        'nested': {
                            'value': 42,
                            'list': [1, 2, 3]
                        }
                    },
                    'flag': True
                })
            }
        }
        
        tool_call = ToolCall.from_llm_response(tool_call_dict)
        
        assert tool_call.arguments == {
            'params': {
                'nested': {
                    'value': 42,
                    'list': [1, 2, 3]
                }
            },
            'flag': True
        }
    
    def test_from_dict_missing_id(self):
        """Test that missing id raises ValueError."""
        tool_call_dict = {
            'function': {
                'name': 'test_tool',
                'arguments': '{}'
            }
        }
        
        with pytest.raises(ValueError, match="missing 'id'"):
            ToolCall.from_llm_response(tool_call_dict)
    
    def test_from_dict_missing_function(self):
        """Test that missing function raises ValueError."""
        tool_call_dict = {
            'id': 'call_123'
        }
        
        with pytest.raises(ValueError, match="missing 'function'"):
            ToolCall.from_llm_response(tool_call_dict)
    
    def test_from_dict_missing_name(self):
        """Test that missing name raises ValueError."""
        tool_call_dict = {
            'id': 'call_123',
            'function': {
                'arguments': '{}'
            }
        }
        
        with pytest.raises(ValueError, match="missing 'function.name'"):
            ToolCall.from_llm_response(tool_call_dict)
    
    def test_from_dict_invalid_json_arguments(self):
        """Test that invalid JSON in arguments is handled gracefully."""
        tool_call_dict = {
            'id': 'call_bad_json',
            'function': {
                'name': 'test_tool',
                'arguments': '{invalid json'
            }
        }
        
        # Should not raise, but log warning and use empty dict
        tool_call = ToolCall.from_llm_response(tool_call_dict)
        assert tool_call.arguments == {}


class TestToolCallFromObject:
    """Test ToolCall.from_llm_response() with object format."""
    
    def test_from_object_basic(self):
        """Test creating ToolCall from object with basic arguments."""
        class MockFunction:
            name = 'get_weather'
            arguments = '{"location": "New York"}'
        
        class MockToolCall:
            id = 'call_obj_123'
            function = MockFunction()
        
        tool_call = ToolCall.from_llm_response(MockToolCall())
        
        assert tool_call.id == 'call_obj_123'
        assert tool_call.name == 'get_weather'
        assert tool_call.arguments == {'location': 'New York'}
    
    def test_from_object_empty_arguments(self):
        """Test object with empty arguments string."""
        class MockFunction:
            name = 'no_args_tool'
            arguments = ''
        
        class MockToolCall:
            id = 'call_obj_456'
            function = MockFunction()
        
        tool_call = ToolCall.from_llm_response(MockToolCall())
        
        assert tool_call.arguments == {}
    
    def test_from_object_none_arguments(self):
        """Test object with None arguments."""
        class MockFunction:
            name = 'tool'
            arguments = None
        
        class MockToolCall:
            id = 'call_obj_789'
            function = MockFunction()
        
        tool_call = ToolCall.from_llm_response(MockToolCall())
        
        assert tool_call.arguments == {}
    
    def test_from_object_missing_id(self):
        """Test that missing id raises ValueError."""
        class MockFunction:
            name = 'test_tool'
            arguments = '{}'
        
        class MockToolCall:
            function = MockFunction()
        
        with pytest.raises(ValueError, match="missing 'id'"):
            ToolCall.from_llm_response(MockToolCall())
    
    def test_from_object_missing_function(self):
        """Test that missing function raises ValueError."""
        class MockToolCall:
            id = 'call_123'
        
        with pytest.raises(ValueError, match="missing 'function'"):
            ToolCall.from_llm_response(MockToolCall())
    
    def test_from_object_missing_name(self):
        """Test that missing name raises ValueError."""
        class MockFunction:
            arguments = '{}'
        
        class MockToolCall:
            id = 'call_123'
            function = MockFunction()
        
        with pytest.raises(ValueError, match="missing 'function.name'"):
            ToolCall.from_llm_response(MockToolCall())


class TestToolCallSerialization:
    """Test ToolCall serialization methods."""
    
    def test_to_message_format(self):
        """Test converting ToolCall to message format."""
        tool_call = ToolCall(
            id='call_123',
            name='get_weather',
            arguments={'location': 'Boston'}
        )
        
        message_format = tool_call.to_message_format()
        
        assert message_format == {
            'id': 'call_123',
            'type': 'function',
            'function': {
                'name': 'get_weather',
                'arguments': '{"location": "Boston"}'
            }
        }
    
    def test_to_message_format_empty_args(self):
        """Test message format with empty arguments."""
        tool_call = ToolCall(
            id='call_456',
            name='no_args_tool',
            arguments={}
        )
        
        message_format = tool_call.to_message_format()
        
        assert message_format['function']['arguments'] == '{}'
    
    def test_to_execution_format(self):
        """Test converting ToolCall to execution format."""
        tool_call = ToolCall(
            id='call_789',
            name='test_tool',
            arguments={'param': 'value'}
        )
        
        exec_format = tool_call.to_execution_format()
        
        # Should return self
        assert exec_format is tool_call
    
    def test_get_arguments_json(self):
        """Test getting arguments as JSON string."""
        tool_call = ToolCall(
            id='call_123',
            name='tool',
            arguments={'key': 'value', 'number': 42}
        )
        
        args_json = tool_call.get_arguments_json()
        
        # Parse to verify it's valid JSON
        parsed = json.loads(args_json)
        assert parsed == {'key': 'value', 'number': 42}


class TestBatchNormalization:
    """Test batch normalization helper functions."""
    
    def test_normalize_tool_calls_list(self):
        """Test normalizing a list of tool calls."""
        tool_calls = [
            {
                'id': 'call_1',
                'function': {'name': 'tool1', 'arguments': '{"a": 1}'}
            },
            {
                'id': 'call_2',
                'function': {'name': 'tool2', 'arguments': '{"b": 2}'}
            }
        ]
        
        normalized = normalize_tool_calls(tool_calls)
        
        assert len(normalized) == 2
        assert all(isinstance(tc, ToolCall) for tc in normalized)
        assert normalized[0].name == 'tool1'
        assert normalized[1].name == 'tool2'
    
    def test_normalize_tool_calls_none(self):
        """Test normalizing None returns None."""
        assert normalize_tool_calls(None) is None
    
    def test_normalize_tool_calls_empty(self):
        """Test normalizing empty list."""
        assert normalize_tool_calls([]) is None
    
    def test_normalize_tool_calls_with_invalid(self):
        """Test normalizing list with some invalid calls."""
        tool_calls = [
            {
                'id': 'call_1',
                'function': {'name': 'tool1', 'arguments': '{}'}
            },
            {
                # Missing id - should be skipped
                'function': {'name': 'tool2', 'arguments': '{}'}
            },
            {
                'id': 'call_3',
                'function': {'name': 'tool3', 'arguments': '{}'}
            }
        ]
        
        normalized = normalize_tool_calls(tool_calls)
        
        # Should skip the invalid one
        assert len(normalized) == 2
        assert normalized[0].id == 'call_1'
        assert normalized[1].id == 'call_3'
    
    def test_serialize_tool_calls(self):
        """Test serializing a list of ToolCall instances."""
        tool_calls = [
            ToolCall(id='call_1', name='tool1', arguments={'a': 1}),
            ToolCall(id='call_2', name='tool2', arguments={'b': 2})
        ]
        
        serialized = serialize_tool_calls(tool_calls)
        
        assert len(serialized) == 2
        assert all(isinstance(tc, dict) for tc in serialized)
        assert serialized[0]['id'] == 'call_1'
        assert serialized[1]['id'] == 'call_2'
    
    def test_serialize_tool_calls_none(self):
        """Test serializing None returns None."""
        assert serialize_tool_calls(None) is None


class TestToolCallRepr:
    """Test ToolCall string representation."""
    
    def test_repr_basic(self):
        """Test basic repr."""
        tool_call = ToolCall(
            id='call_123',
            name='test_tool',
            arguments={'key': 'value'}
        )
        
        repr_str = repr(tool_call)
        
        assert 'call_123' in repr_str
        assert 'test_tool' in repr_str
        assert 'key' in repr_str
    
    def test_repr_long_arguments(self):
        """Test repr with long arguments gets truncated."""
        tool_call = ToolCall(
            id='call_456',
            name='tool',
            arguments={'very': 'long' * 100}  # Long string
        )
        
        repr_str = repr(tool_call)
        
        # Should be truncated with ...
        assert '...' in repr_str
        assert len(repr_str) < 200  # Reasonable length


class TestRoundTripConversion:
    """Test round-trip conversions (dict -> ToolCall -> dict)."""
    
    def test_roundtrip_dict_format(self):
        """Test dict -> ToolCall -> dict maintains data."""
        original = {
            'id': 'call_rt_123',
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'arguments': '{"param1": "value1", "param2": 42}'
            }
        }
        
        # Convert to ToolCall
        tool_call = ToolCall.from_llm_response(original)
        
        # Convert back to dict
        result = tool_call.to_message_format()
        
        # Should match original
        assert result['id'] == original['id']
        assert result['function']['name'] == original['function']['name']
        
        # Arguments should parse to same values
        original_args = json.loads(original['function']['arguments'])
        result_args = json.loads(result['function']['arguments'])
        assert result_args == original_args
    
    def test_roundtrip_preserves_data_integrity(self):
        """Test that complex data survives round-trip."""
        complex_args = {
            'nested': {
                'list': [1, 2, {'inner': 'value'}],
                'flag': True,
                'none_val': None
            },
            'unicode': '你好世界'
        }
        
        # Create ToolCall
        tool_call = ToolCall(
            id='call_complex',
            name='complex_tool',
            arguments=complex_args
        )
        
        # Serialize and deserialize
        serialized = tool_call.to_message_format()
        deserialized = ToolCall.from_llm_response(serialized)
        
        # Arguments should match
        assert deserialized.arguments == complex_args

