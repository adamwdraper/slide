"""Example: Structured Output with Pydantic Models

This example demonstrates how to use response_type to get validated,
type-safe structured outputs from your agent.

Features shown:
- Agent-level default response_type (set once, used for all runs)
- Per-run response_type override
- Automatic validation of LLM responses
- Retry on validation failure with retry_config
- Accessing the validated structured_data

Prerequisites:
    pip install slide-tyler

Usage:
    export OPENAI_API_KEY=your-key
    python 600_structured_output.py
"""
import asyncio
from pydantic import BaseModel, Field
from typing import List, Literal

from tyler import Agent, Thread, Message, RetryConfig, StructuredOutputError


# Define your output schema using Pydantic
class MovieReview(BaseModel):
    """A structured movie review."""
    title: str = Field(description="The movie title")
    rating: float = Field(ge=0, le=10, description="Rating from 0 to 10")
    genre: Literal["action", "comedy", "drama", "horror", "sci-fi", "other"]
    pros: List[str] = Field(description="List of positive aspects")
    cons: List[str] = Field(description="List of negative aspects")
    recommended: bool = Field(description="Whether you recommend this movie")


class SupportTicket(BaseModel):
    """A classified support ticket."""
    priority: Literal["low", "medium", "high", "critical"]
    category: str
    summary: str = Field(max_length=200)
    requires_escalation: bool
    suggested_actions: List[str]


async def agent_level_response_type():
    """Example: Set response_type on the agent for all runs."""
    print("=" * 60)
    print("Agent-Level Response Type (Default for All Runs)")
    print("=" * 60)
    
    # Set response_type on the agent - all runs will use this schema
    agent = Agent(
        name="movie-reviewer",
        model_name="gpt-4.1",
        purpose="To provide detailed movie reviews",
        response_type=MovieReview  # Default for all runs
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Give me a review of The Matrix (1999)"
    ))
    
    # No need to pass response_type - uses agent's default
    result = await agent.run(thread)
    
    # Access the validated Pydantic model
    review: MovieReview = result.structured_data
    
    print(f"\nMovie: {review.title}")
    print(f"Rating: {review.rating}/10")
    print(f"Genre: {review.genre}")
    print(f"Recommended: {'Yes' if review.recommended else 'No'}")
    print(f"\nPros:")
    for pro in review.pros:
        print(f"  ✓ {pro}")
    print(f"\nCons:")
    for con in review.cons:
        print(f"  ✗ {con}")
    
    return review


async def per_run_response_type():
    """Example: Override response_type per-run for flexibility."""
    print("\n" + "=" * 60)
    print("Per-Run Response Type Override")
    print("=" * 60)
    
    # Agent with no default response_type
    agent = Agent(
        name="flexible-analyzer",
        model_name="gpt-4.1",
        purpose="To analyze and extract structured data"
    )
    
    # First run: extract a movie review
    thread1 = Thread()
    thread1.add_message(Message(
        role="user",
        content="Give me a review of Inception (2010)"
    ))
    result1 = await agent.run(thread1, response_type=MovieReview)
    print(f"\nExtracted MovieReview: {result1.structured_data.title}")
    
    # Second run: same agent, different schema
    thread2 = Thread()
    thread2.add_message(Message(
        role="user",
        content="User says: I can't log in and my subscription expired yesterday!"
    ))
    result2 = await agent.run(thread2, response_type=SupportTicket)
    print(f"Extracted SupportTicket: Priority={result2.structured_data.priority}")
    
    return result1.structured_data, result2.structured_data


async def structured_output_with_retry():
    """Example with retry configuration for more reliable outputs."""
    print("\n" + "=" * 60)
    print("Structured Output with Retry Example")
    print("=" * 60)
    
    # Configure retry behavior for validation failures
    agent = Agent(
        name="support-classifier",
        model_name="gpt-4.1",
        purpose="To classify and prioritize support tickets",
        retry_config=RetryConfig(
            max_retries=3,           # Retry up to 3 times on validation failure
            backoff_base_seconds=0.5  # Wait 0.5s * attempt between retries
        )
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="User report: My payment failed twice and now I can't access my account. This is urgent - I have a meeting in 30 minutes that requires this!"
    ))
    
    result = await agent.run(thread, response_type=SupportTicket)
    
    ticket: SupportTicket = result.structured_data
    
    print(f"\nTicket Classification:")
    print(f"  Priority: {ticket.priority.upper()}")
    print(f"  Category: {ticket.category}")
    print(f"  Summary: {ticket.summary}")
    print(f"  Escalation needed: {'Yes' if ticket.requires_escalation else 'No'}")
    print(f"\nSuggested Actions:")
    for i, action in enumerate(ticket.suggested_actions, 1):
        print(f"  {i}. {action}")
    
    if result.validation_retries > 0:
        print(f"\n(Note: Required {result.validation_retries} retry attempts)")
    
    return ticket


async def handling_validation_errors():
    """Example showing how to handle validation failures."""
    print("\n" + "=" * 60)
    print("Handling Validation Errors Example")
    print("=" * 60)
    
    # Agent without retry config - validation failures raise immediately
    agent = Agent(
        name="strict-extractor",
        model_name="gpt-4.1",
        purpose="To extract structured data"
        # No retry_config = fail immediately on validation error
    )
    
    thread = Thread()
    thread.add_message(Message(
        role="user",
        content="Review: It was okay I guess."  # Vague - might produce incomplete data
    ))
    
    try:
        result = await agent.run(thread, response_type=MovieReview)
        print(f"\nSuccessfully extracted: {result.structured_data.title}")
    except StructuredOutputError as e:
        print(f"\nValidation failed!")
        print(f"Errors: {e.validation_errors}")
        print(f"Last response: {e.last_response}")


async def main():
    """Run all examples."""
    # Agent-level default response_type
    await agent_level_response_type()
    
    # Per-run override for flexibility
    await per_run_response_type()
    
    # With retry for reliability
    await structured_output_with_retry()
    
    # Error handling
    await handling_validation_errors()
    
    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

