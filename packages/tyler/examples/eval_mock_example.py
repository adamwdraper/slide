#!/usr/bin/env python3
"""
Example showing how to mock any tool in Tyler evaluations.

This demonstrates mocking both Lye tools and custom tools with simple, user-defined responses.
"""
from dotenv import load_dotenv
load_dotenv()

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
from lye import web, files

# Initialize weave
weave.init("tyler-eval-mocking")


# Example custom tool
@weave.op()
async def book_flight(destination: str, date: str) -> dict:
    """Book a flight to the specified destination"""
    # In reality, this would call a booking API
    pass


async def main():
    print("=== Tyler Tool Mocking Example ===\n")
    
    # Create agent with Lye tools and custom tools
    agent = Agent(
        name="travel_assistant",
        model_name="gpt-4.1",
        purpose="To help users with travel planning",
        tools=[web.search, files.write, book_flight],
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
                    uses_tools=["web.search"],
                    mentions=["Paris", "Friday"],
                )
            ),
            Conversation(
                id="book_flight",
                user="Book the cheapest flight to Tokyo on March 15th",
                expect=Expectation(
                    uses_tools=["web.search", "book_flight"],
                    completes_task=True
                )
            ),
            Conversation(
                id="save_itinerary",
                user="Save my flight details to a file",
                expect=Expectation(
                    uses_tools=["files.write"],
                    mentions=["saved", "file"]
                )
            )
        ],
        scorers=[ToolUsageScorer()]
    )
    
    # Method 1: Simple static responses
    eval.mock_registry.register(
        web.search,
        response={
            "success": True,
            "results": [
                {"title": "Flight Option 1", "price": "$500", "airline": "United"},
                {"title": "Flight Option 2", "price": "$450", "airline": "Delta"}
            ]
        }
    )
    
    # Method 2: Using helper functions
    eval.mock_registry.register(
        files.write,
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
    
    # Method 4: Using mock_from_args for template-based responses
    # This is useful when you want the response to include the input
    eval.mock_registry.register(
        web.search,
        response=mock_from_args({
            "success": True,
            "query": "{query}",  # Will be filled with actual query
            "results": [
                {"title": "Result for: {query}", "url": "https://example.com"}
            ]
        })
    )
    
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
                id="handle_search_error",
                user="Search for available flights",
                expect=Expectation(
                    uses_tools=["web.search"],
                    mentions_any=["error", "problem", "try again"],
                    completes_task=False
                )
            )
        ],
        scorers=[ToolUsageScorer()]
    )
    
    # Mock an error response
    error_eval.mock_registry.register(
        web.search,
        response=mock_error("Search service temporarily unavailable")
    )
    
    print("Testing error handling...")
    error_results = await error_eval.run(agent)
    
    # Example: Async mock functions
    print("\n\n=== Async Mock Functions ===")
    
    async def async_file_reader(file_url: str, **kwargs):
        """Example async mock that could simulate delays or complex logic"""
        await asyncio.sleep(0.1)  # Simulate IO
        return (
            {"success": True, "file_url": file_url},
            [{"content": f"Mock content from {file_url}", "filename": "mock.txt"}]
        )
    
    # You can register async functions as mocks too
    async_eval = AgentEval(
        name="async_mock_eval",
        conversations=[
            Conversation(
                id="read_file",
                user="Read the flight details from saved_flights.txt",
                expect=Expectation(uses_tools=["files.read_file"])
            )
        ],
        scorers=[ToolUsageScorer()]
    )
    
    # Assuming files.read_file exists (or you have a custom read function)
    # async_eval.mock_registry.register(files.read_file, response=async_file_reader)
    
    print("\n✅ All examples completed!")
    print("\nKey takeaways:")
    print("1. Mock any tool (Lye or custom) with simple responses")
    print("2. Use static responses, functions, or template-based mocks")
    print("3. Test both success and error scenarios")
    print("4. Inspect tool calls to verify agent behavior")


if __name__ == "__main__":
    asyncio.run(main()) 