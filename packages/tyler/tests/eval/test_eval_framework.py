import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tyler import Agent
from tyler.eval import (
    AgentEval,
    Conversation,
    Turn,
    Expectation,
    ToolUsageScorer,
    ToneScorer,
    TaskCompletionScorer,
    ConversationFlowScorer,
    MockTool,
    MockToolRegistry,
    mock_success,
    mock_error,
    mock_from_args
)


@pytest.fixture
def mock_weave():
    """Mock weave to prevent initialization"""
    with patch('weave.init'):
        with patch('tyler.eval.agent_eval.Evaluation') as mock_eval:
            mock_eval_instance = MagicMock()
            mock_eval_instance.evaluate = AsyncMock()
            mock_eval.return_value = mock_eval_instance
            yield mock_eval, mock_eval_instance


@pytest.fixture
def simple_agent():
    """Create a simple agent for testing"""
    with patch('litellm.acompletion') as mock:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock(
            content="Test response", 
            tool_calls=None
        )
        mock.return_value = mock_response
        
        agent = Agent(
            name="test_agent",
            model_name="gpt-4",
            purpose="Test agent for evaluation",
            notes="Test notes",
            tools=[]
        )
        return agent


class TestExpectations:
    """Test the Expectation class"""
    
    def test_expectation_creation(self):
        """Test creating expectations with various conditions"""
        expect = Expectation(
            uses_tools=["tool1", "tool2"],
            mentions=["keyword1", "keyword2"],
            tone="friendly",
            completes_task=True
        )
        
        assert expect.uses_tools == ["tool1", "tool2"]
        assert expect.mentions == ["keyword1", "keyword2"]
        assert expect.tone == "friendly"
        assert expect.completes_task == True
    
    def test_expectation_to_dict(self):
        """Test serialization of expectations"""
        expect = Expectation(
            mentions=["test"],
            custom=lambda r: "test" in r.get("content", "")
        )
        
        result = expect.to_dict()
        assert result["mentions"] == ["test"]
        assert result.get("has_custom_validation") == True  # Custom is marked as present
    
    def test_expectation_validate_tool_usage(self):
        """Test validating tool usage expectations"""
        expect = Expectation(
            uses_tools=["tool1"],
            does_not_use_tools=["tool2"],
            uses_tools_in_order=["tool1", "tool3"]
        )
        
        # Mock response with tool calls  
        response = {
            "tool_calls": [
                {"name": "tool1"},  # Changed from tool_name to name
                {"name": "tool3"}
            ]
        }
        
        results = expect.validate_against(response)
        
        # validate_against returns a dict of check_name -> bool
        assert isinstance(results, dict)
        # Should pass uses_tools check (exact match)
        assert results.get("uses_tools") == False  # False because we have tool3 but not in uses_tools
        # Should pass does_not_use_tools check
        assert results.get("does_not_use_tools") == True  # tool2 not used
        # Should pass uses_tools_in_order check
        assert results.get("uses_tools_in_order") == True  # tool1, tool3 in correct order


class TestConversations:
    """Test the Conversation and Turn classes"""
    
    def test_single_turn_conversation(self):
        """Test creating a single-turn conversation"""
        conv = Conversation(
            id="test_conv",
            user="Hello",
            expect=Expectation(mentions=["Hello"])
        )
        
        assert conv.id == "test_conv"
        assert len(conv._turns) == 2  # User + assistant (internal attribute)
        assert conv._turns[0].content == "Hello"
        assert conv._turns[1].expect.mentions == ["Hello"]
    
    def test_multi_turn_conversation(self):
        """Test creating a multi-turn conversation"""
        turns = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", expect=Expectation(mentions=["Hi"])),
            Turn(role="user", content="How are you?"),
            Turn(role="assistant", expect=Expectation(tone="friendly"))
        ]
        
        conv = Conversation(
            id="multi_turn",
            turns=turns
        )
        
        assert len(conv._turns) == 4
        # Just check that turns is not None to confirm it's multi-turn
        assert conv.turns is not None
    
    def test_conversation_validation(self):
        """Test conversation validation"""
        # Invalid: starts with assistant
        with pytest.raises(ValueError):
            Conversation(
                id="invalid",
                turns=[Turn(role="assistant", content="Hello")]
            )
        
        # Invalid: consecutive same roles
        with pytest.raises(ValueError):
            Conversation(
                id="invalid",
                turns=[
                    Turn(role="user", content="Hello"),
                    Turn(role="user", content="Hello again")
                ]
            )
    
    def test_conversation_to_dict(self):
        """Test conversation serialization for Weave"""
        conv = Conversation(
            id="test",
            user="Hello",
            expect=Expectation(mentions=["greeting"])
        )
        
        result = conv.to_dict()
        assert result["conversation_id"] == "test"  # Changed from 'id' to 'conversation_id'
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == "Hello"
        assert "expectations" in result


class TestScorers:
    """Test the scorer implementations"""
    
    @pytest.mark.asyncio
    async def test_tool_usage_scorer(self):
        """Test ToolUsageScorer"""
        scorer = ToolUsageScorer()
        
        # Test with matching tool usage
        agent_response = {
            "content": "I'll help you with that",
            "tool_calls": [{"tool_name": "tool1"}]
        }
        conversation = {
            "messages": [
                {"role": "user", "content": "Do something with tool1"}
            ]
        }
        expectations = [{
            "uses_tools": ["tool1"]
        }]
        
        score = await scorer.score(agent_response, conversation, expectations)
        assert score["passed"] == True
        assert score["score"] > 0
    
    @pytest.mark.asyncio
    async def test_tone_scorer(self):
        """Test ToneScorer with LLM judge"""
        scorer = ToneScorer()
        
        # Mock the LLM response
        with patch('tyler.eval.scorers.acompletion', new_callable=AsyncMock) as mock_completion:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"matches_expected": true, "score": 1.0, "tone": "friendly", "reasoning": "Friendly tone"}'
            mock_completion.return_value = mock_response
            
            agent_response = {"content": "Hi there! I'd be happy to help!"}
            conversation = {"messages": []}
            expectations = [{"expectations": {"tone": "friendly"}}]
            
            score = await scorer.score(agent_response, conversation, expectations)
            assert score["passed"] == True
    
    def test_scorer_to_weave(self):
        """Test converting scorers to Weave format"""
        scorer = ToolUsageScorer()
        weave_scorer = scorer.to_weave_scorer()
        
        # Should be a callable
        assert callable(weave_scorer)


class TestMockTools:
    """Test the mock tool system"""
    
    @pytest.mark.asyncio
    async def test_mock_tool_creation(self):
        """Test creating mock tools"""
        mock = MockTool("test_tool", {"result": "success"})
        
        result = await mock(param="value")
        assert result == {"result": "success"}
        assert mock.was_called()
        assert mock.call_count == 1
    
    @pytest.mark.asyncio
    async def test_mock_tool_with_function(self):
        """Test mock tool with dynamic response"""
        def dynamic_response(**kwargs):
            return f"Received: {kwargs.get('input', 'nothing')}"
        
        mock = MockTool("test_tool", dynamic_response)
        
        result = await mock(input="test")
        assert result == "Received: test"
    
    def test_mock_registry(self):
        """Test MockToolRegistry"""
        registry = MockToolRegistry()
        
        # Mock function
        def test_func():
            return "original"
        
        # Register mock
        registry.register(test_func, response="mocked")
        
        # Get mock
        mocks = registry.get_mock_tools([test_func])
        assert len(mocks) == 1
        mock = mocks[0]
        assert mock is not None
    
    def test_mock_helpers(self):
        """Test mock helper functions"""
        # Test mock_success
        success = mock_success("It worked!", extra="data")
        assert success["success"] == True
        assert success["message"] == "It worked!"
        assert success["extra"] == "data"
        
        # Test mock_error
        error = mock_error("It failed!")
        assert error["success"] == False
        assert error["error"] == "It failed!"
        
        # Test mock_from_args
        template = mock_from_args({
            "result": "Processed {input}",
            "count": "{count}"
        })
        result = template(input="test", count=5)
        assert result["result"] == "Processed test"
        assert result["count"] == "5"


class TestAgentEval:
    """Test the main AgentEval class"""
    
    @pytest.mark.asyncio
    async def test_agent_eval_creation(self, simple_agent):
        """Test creating an AgentEval"""
        conversations = [
            Conversation(
                id="test1",
                user="Hello",
                expect=Expectation(mentions=["greeting"])
            )
        ]
        
        eval = AgentEval(
            name="test_eval",
            conversations=conversations,
            scorers=[ToolUsageScorer()]
        )
        
        assert eval.name == "test_eval"
        assert len(eval.conversations) == 1
        assert len(eval.scorers) == 1
    
    @pytest.mark.asyncio
    async def test_agent_eval_with_mocks(self, simple_agent, mock_weave):
        """Test running evaluation with mocked tools"""
        mock_eval_class, mock_eval_instance = mock_weave
        
        # Create a mock tool
        def mock_tool(param: str) -> str:
            return f"Mocked: {param}"
        
        # Create evaluation
        eval = AgentEval(
            name="mock_test",
            conversations=[
                Conversation(
                    id="test1",
                    user="Use the tool",
                    expect=Expectation(uses_tools=["mock_tool"])
                )
            ],
            scorers=[ToolUsageScorer()]
        )
        
        # Register mock
        eval.mock_registry.register(mock_tool, response="Mocked response")
        
        # Mock the evaluation results
        mock_result = MagicMock()
        mock_result.rows = [
            {
                "conversation_id": "test1",
                "output": {"content": "Using tool", "tool_calls": [{"name": "mock_tool"}]},
                "tool_usage_scorer": {"score": 1.0, "passed": True}
            }
        ]
        mock_result.id = "test-run-id"
        
        # Mock the evaluate method to actually call the agent_predict function
        async def mock_evaluate(agent_predict_fn, **kwargs):
            # Call the agent_predict function for each conversation
            for conv in eval.conversations:
                conv_data = conv.to_dict()
                await agent_predict_fn(
                    conversation_id=conv_data['conversation_id'],
                    messages=conv_data['messages'],
                    expectations=conv_data['expectations']
                )
            return mock_result
        
        mock_eval_instance.evaluate = mock_evaluate
        
        # Mock the agent's go method to return tool usage
        from narrator import Message
        from tyler import AgentResult, ExecutionDetails
        import uuid
        from datetime import datetime, UTC
        async def mock_go(thread):
            # Return a response that uses the mock_tool
            assistant_msg = Message(
                role="assistant",
                content="Using tool",
                tool_calls=[{
                    'id': str(uuid.uuid4()),
                    'type': 'function',
                    'function': {
                        'name': 'mock_tool',
                        'arguments': '{"param": "test"}'
                    }
                }]
            )
            thread.add_message(assistant_msg)
            
            # Create mock execution details
            execution = ExecutionDetails(
                events=[],
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                total_iterations=1
            )
            
            return AgentResult(
                thread=thread,
                messages=[assistant_msg],
                output="Using tool",
                execution=execution
            )
        
        # Run evaluation with mocked go method
        with patch.object(simple_agent, 'tools', [mock_tool]):
            with patch.object(simple_agent, 'go', mock_go):
                results = await eval.run(simple_agent)
        
        # Check results structure
        assert results.total_conversations == 1
        assert results.passed_conversations == 1
    
    @pytest.mark.asyncio  
    async def test_eval_results_summary(self, simple_agent, mock_weave):
        """Test evaluation results summary"""
        mock_eval_class, mock_eval_instance = mock_weave
        
        eval = AgentEval(
            name="summary_test",
            conversations=[
                Conversation(id="test1", user="Hello"),
                Conversation(
                    id="test2", 
                    user="Hi",
                    expect=Expectation(uses_tools=["some_tool"])  # This will fail since no tools are used
                )
            ],
            scorers=[ToolUsageScorer()]
        )
        
        # Mock mixed results
        mock_result = MagicMock()
        mock_result.rows = [
            {
                "conversation_id": "test1",
                "output": {"content": "Hello", "tool_calls": []},
                "tool_usage_scorer": {"score": 1.0, "passed": True}
            },
            {
                "conversation_id": "test2",
                "output": {"content": "Hi", "tool_calls": []},
                "tool_usage_scorer": {"score": 0.0, "passed": False}
            }
        ]
        mock_result.id = "test-run-id"
        
        # Mock the evaluate method to actually call the agent_predict function
        async def mock_evaluate(agent_predict_fn, **kwargs):
            # Call the agent_predict function for each conversation
            for conv in eval.conversations:
                conv_data = conv.to_dict()
                await agent_predict_fn(
                    conversation_id=conv_data['conversation_id'],
                    messages=conv_data['messages'],
                    expectations=conv_data['expectations']
                )
            return mock_result
        
        mock_eval_instance.evaluate = mock_evaluate
        
        results = await eval.run(simple_agent)
        
        # Test summary
        summary = results.summary()
        assert "(50%)" in summary  # Pass rate
        assert "test2: tool_usage: failed" in summary  # Failed test shows in summary 