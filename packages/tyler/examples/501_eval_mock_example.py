#!/usr/bin/env python3
"""
Example showing how to mock any tool in Tyler evaluations.

This demonstrates mocking both Lye tools and custom tools with simple, user-defined responses.
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
    Expectation,
    ToolUsageScorer,
    mock_success,
    mock_error,
    mock_from_args
)
# Namespace-based imports - cleaner and avoids collisions
from lye import web, files

# Initialize weave
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("slide")
except Exception as e:
    print(f"Failed to initialize weave tracing: {e}. Continuing without weave.")


# Example custom tool
async def book_flight(destination: str, date: str, return_date: str) -> dict:
    """Book a flight to the specified destination"""
    # This would normally make real API calls!
    return {
        "confirmation": "FL123456",
        "destination": destination,
        "price": "$450"
    }


async def main():
    print("=== Tyler Mock Tools Example ===\n")
    
    # Create an agent to evaluate
    agent = Agent(
        name="travel_assistant", 
        model_name="gpt-4o",
        purpose="To help users plan and book travel arrangements",
        tools=[web.fetch_page, files.write_file, book_flight],  # Namespace + custom tool!
        temperature=0.7
    )
    
    # Create evaluation
    eval = AgentEval(
        name="travel_agent_eval",
        conversations=[
            Conversation(
                id="search_flights",
                user="Find flights to Paris for next Friday",
                expect=Expectation(
                    uses_tools=["web-fetch_page"],
                    mentions=["Paris", "Friday"],
                )
            ),
            Conversation(
                id="book_flight",
                user="Book the cheapest flight to Tokyo on March 15th",
                expect=Expectation(
                    uses_tools=["web-fetch_page", "book_flight"],
                    completes_task=True
                )
            ),
            Conversation(
                id="save_itinerary",
                user="Save my flight details to a file",
                expect=Expectation(
                    uses_tools=["files-write_file"],
                    mentions=["saved", "file"]
                )
            )
        ],
        scorers=[ToolUsageScorer()]
    )
    
    # Method 1: Simple static responses
    eval.mock_registry.register(
        web.fetch_page,
        response={
            "success": True,
            "status_code": 200,
            "content": "Flight Results:\n1. Flight to Paris - $500\n2. Flight to Paris - $450",
            "content_type": "text"
        }
    )
    
    # Method 2: Using helper functions
    eval.mock_registry.register(
        files.write_file,
        response=mock_success("File saved successfully", path="/mock/itinerary.txt")
    )
    
    # Method 3: Dynamic responses based on input
    def mock_booking(destination: str, date: str, **kwargs):
        return {
            "success": True,
            "booking_id": f"MOCK-{destination.upper()}-{date.replace(' ', '')}",
            "message": f"Flight to {destination} on {date} booked successfully",
            "price": "$450",
            "airline": "Mock Airlines"
        }
    
    eval.mock_registry.register(book_flight, response=mock_booking)
    
    # Run evaluation
    print("Running evaluation with mocked tools...")
    results = await eval.run(agent)
    
    print("\n" + "="*60)
    print(results.summary())
    print("="*60)
    
    # Inspect tool calls
    print("\nTool calls made during evaluation:")
    for tool_name, mock in eval.mock_registry.mocks.items():
        if mock.was_called():
            print(f"\n{tool_name}: called {mock.call_count} time(s)")
            for i, call in enumerate(mock.call_history):
                print(f"  Call {i+1}: {call['kwargs']}")
    
    # Example: Testing error scenarios
    print("\n\n=== Testing Error Handling ===")
    
    error_eval = AgentEval(
        name="error_handling_eval",
        conversations=[
            Conversation(
                id="handle_fetch_error",
                user="Get information from https://example.com",
                expect=Expectation(
                    uses_tools=["web-fetch_page"],
                    mentions_any=["error", "problem", "try again"],
                    completes_task=False
                )
            )
        ],
        scorers=[ToolUsageScorer()]
    )
    
    # Mock an error response
    error_eval.mock_registry.register(
        web.fetch_page,
        response=mock_error("Connection timeout")
    )
    
    print("Testing error handling...")
    error_results = await error_eval.run(agent)
    
    print("\n✅ All examples completed!")
    print("\nKey takeaways:")
    print("1. Direct tool imports make mocking clearer")
    print("2. You can mock any tool with simple responses")
    print("3. Test both success and error scenarios")
    print("4. Inspect tool calls to verify agent behavior")


if __name__ == "__main__":
    asyncio.run(main()) 