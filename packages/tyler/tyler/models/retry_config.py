"""Retry configuration for structured output validation."""
from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    """Configuration for structured output validation retry.
    
    When using structured outputs with `response_type`, validation failures
    can be automatically retried with error feedback sent back to the LLM.
    
    Example:
        ```python
        from tyler import Agent, RetryConfig
        from pydantic import BaseModel
        
        class Invoice(BaseModel):
            total: float
            items: list[str]
        
        agent = Agent(
            name="extractor",
            model_name="gpt-4.1",
            retry_config=RetryConfig(max_retries=3)
        )
        
        result = await agent.run(thread, response_type=Invoice)
        ```
    
    Attributes:
        max_retries: Maximum number of retry attempts on validation failure.
            Set to 0 to disable retry (fail immediately on first validation error).
        retry_on_validation_error: Whether to retry when Pydantic validation fails.
            If False, validation errors raise immediately without retry.
        backoff_base_seconds: Base delay between retries. Actual delay is
            `backoff_base_seconds * attempt_number` (linear backoff).
    """
    max_retries: int = Field(
        default=3, 
        ge=0, 
        le=10,
        description="Maximum retry attempts on validation failure (0-10)"
    )
    retry_on_validation_error: bool = Field(
        default=True,
        description="Whether to retry on Pydantic validation errors"
    )
    backoff_base_seconds: float = Field(
        default=0.5, 
        ge=0,
        description="Base delay between retries in seconds"
    )
    
    model_config = {
        "frozen": True  # Immutable once created
    }

