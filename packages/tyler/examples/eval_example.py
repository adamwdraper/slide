#!/usr/bin/env python3
"""
Example demonstrating Tyler's agent evaluation framework.

This shows how to create and run evaluations for your agents with
agent-focused expectations and scoring.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import weave
from tyler import Agent
from tyler.eval import (
    AgentEval, 
    Conversation, 
    Turn,
    Expectation,
    ToolUsageScorer,
    ToneScorer,
    TaskCompletionScorer,
    ConversationFlowScorer
)
# Namespace-based imports - avoids name collisions!
from lye import web, files

# Initialize weave
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-eval-example")
except Exception as e:
    print(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


async def main():
    print("=== Tyler Agent Evaluation Example ===\n")
    print("NOTE: By default, evaluations use MOCK tools for safety.")
    print("No real API calls will be made or flights booked!\n")
    
    # Create an agent to evaluate
    agent = Agent(
        name="travel_assistant",
        model_name="gpt-4.1",
        purpose="To help users plan and book travel arrangements",
        tools=[web.fetch_page, files.write_file],  # Namespace-based references!
        temperature=0.7
    )
    
    # IMPORTANT: Tool naming in expectations
    # When referencing tools in expectations, use their registered names:
    # - "web-fetch_page" (not "web.fetch_page" or "fetch_page")
    # - "files-read_file" (not "files.read_file" or "read_file")
    # - "files-write_file" (not "files.write_file" or "write_file") 
    # - "audio-text_to_speech" (not "audio.text_to_speech")
    # All Lye tools follow the pattern: "module-method_name"
    
    # Define test conversations
    conversations = [
        # Simple single-turn conversation
        Conversation(
            id="simple_flight_booking",
            user="Book me a flight to Paris next Friday",
            expect=Expectation(
                mentions=["Paris", "Friday"],
                tone="helpful",
                completes_task=False,  # Should ask for more details
                asks_clarification=True
            ),
            description="Test if agent asks for clarification on incomplete request"
        ),
        
        # Test that agent doesn't use tools without enough info
        Conversation(
            id="vague_request",
            user="I need to travel somewhere warm",
            expect=Expectation(
                does_not_use_tools=["web-fetch_page"],  # Use actual tool name
                asks_clarification=True,
                mentions_any=["destination", "where", "location", "dates", "when"],
                tone="friendly"
            )
        ),
        
        # Multi-turn conversation
        Conversation(
            id="complete_booking_flow",
            turns=[
                Turn(role="user", content="Hi, I need help booking a flight"),
                Turn(role="assistant", expect=Expectation(
                    offers_help=True,
                    tone="friendly",
                    asks_clarification=True
                )),
                Turn(role="user", content="I want to fly from NYC to London"),
                Turn(role="assistant", expect=Expectation(
                    confirms_details=["NYC", "London"],
                    mentions_any=["date", "when", "departure"],
                    does_not_use_tools=["web-fetch_page"]  # Still needs dates
                )),
                Turn(role="user", content="Next Tuesday, returning the following Sunday"),
                Turn(role="assistant", expect=Expectation(
                    uses_tools=["web-fetch_page"],  # Now it should search (mock!)
                    mentions=["Tuesday", "Sunday"],
                    completes_task=True
                ))
            ],
            description="Test complete booking flow with proper information gathering"
        ),
        
        # Test edge case - conflicting request
        Conversation(
            id="conflicting_dates",
            user="Book a flight for yesterday",
            expect=Expectation(
                refuses_request=True,
                mentions_any=["past", "cannot", "unable", "yesterday"],
                tone="helpful",
                offers_alternatives=True
            )
        ),
        
        # Test tool usage and file creation
        Conversation(
            id="save_search_results", 
            user="Search for flights to Tokyo next month and save the results",
            expect=Expectation(
                uses_tools_in_order=["web-fetch_page", "files-write_file"],
                mentions=["Tokyo", "save"],
                completes_task=True,
                custom=lambda response: "saved" in response.get("content", "").lower()
            )
        )
    ]
    
    # Create evaluation with multiple scorers
    # use_mock_tools=True by default for safety!
    eval = AgentEval(
        name="travel_agent_comprehensive",
        description="Comprehensive evaluation of travel booking agent",
        conversations=conversations,
        scorers=[
            ToolUsageScorer(strict=True),
            ToneScorer(acceptable_tones=["friendly", "helpful", "professional"]),
            TaskCompletionScorer(),
            ConversationFlowScorer()
        ],
        trials=1,  # Run each conversation once
        use_mock_tools=True  # This is the default, shown for clarity
    )
    
    # Run the evaluation (safely with mock tools)
    print("Running evaluation with MOCK tools...")
    results = await eval.run(agent)
    
    # Display results
    print("\n" + "="*60)
    print(results.summary())
    print("="*60)
    
    # Show that mock tools were used
    print("\n✅ Mock tools were used - no real API calls were made!")
    
    # Detailed analysis of failed conversations
    if results.failed_conversations:
        print("\nDetailed failure analysis:")
        for conv in results.get_failed_conversations():
            print(f"\n{conv.conversation_id}:")
            print(f"  Agent response: {conv.agent_response.get('content', '')[:100]}...")
            
            # Show mock tool calls if any
            mock_calls = conv.agent_response.get('mock_tool_calls', {})
            if mock_calls:
                print(f"  Mock tools called: {list(mock_calls.keys())}")
            
            for score in conv.get_failed_scores():
                print(f"  ❌ {score.name}: {score.details}")
    
    # Access specific scores
    print("\n\nScore breakdown by category:")
    for scorer_name, stats in results.score_summary().items():
        print(f"{scorer_name}: {stats['average_score']:.2f} "
              f"({stats['passed']}/{stats['total']} passed)")
    
    # Example of accessing individual conversation results
    simple_result = results.get_conversation("simple_flight_booking")
    if simple_result:
        print(f"\n\nSimple flight booking result:")
        print(f"  Passed: {simple_result.passed}")
        print(f"  Tool usage score: {simple_result.get_score('tool_usage')}")
        print(f"  Agent asked for clarification: "
              f"{simple_result.agent_response.get('content', '')}")
    
    # DANGEROUS: Example of running with REAL tools (not recommended!)
    print("\n\n" + "="*60)
    print("⚠️  DANGER ZONE: Running with REAL tools")
    print("="*60)
    
    dangerous_eval = AgentEval(
        name="dangerous_real_tools_eval",
        conversations=[
            Conversation(
                id="real_search",
                user="What's the weather in NYC?",
                expect=Expectation(uses_tools=["web.search"])
            )
        ],
        scorers=[ToolUsageScorer()],
        use_mock_tools=False  # ⚠️  REAL TOOLS!
    )
    
    # Uncomment to run with real tools (at your own risk!)
    # results = await dangerous_eval.run(agent)
    print("☝️  Uncomment the line above to run with real tools (not recommended!)")


if __name__ == "__main__":
    asyncio.run(main()) 