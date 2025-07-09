"""
Configuration management for Space Monkey bot framework
"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

class Config(BaseModel):
    """Configuration for Space Monkey bot"""
    
    # Slack configuration
    slack_bot_token: str = Field(..., description="Slack bot token (xoxb-)")
    slack_app_token: str = Field(..., description="Slack app token (xapp-)")
    
    # Database configuration
    database_url: Optional[str] = Field(None, description="Database URL for thread storage")
    
    # File storage configuration
    file_storage_path: Optional[str] = Field(None, description="Path for file storage")
    max_file_size: int = Field(50 * 1024 * 1024, description="Maximum file size (50MB)")
    max_storage_size: int = Field(5 * 1024 * 1024 * 1024, description="Maximum total storage (5GB)")
    
    # Weave configuration
    wandb_api_key: Optional[str] = Field(None, description="Weights & Biases API key")
    wandb_project: Optional[str] = Field(None, description="Weights & Biases project name")
    
    # Server configuration
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    
    # Environment
    environment: str = Field("development", description="Environment (development/production)")
    
    # Health check configuration
    health_check_url: Optional[str] = Field(None, description="Health check service URL")
    health_ping_interval: int = Field(120, description="Health ping interval in seconds")
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables"""
        load_dotenv()
        
        return cls(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
            database_url=os.getenv("NARRATOR_DATABASE_URL"),
            file_storage_path=os.getenv("NARRATOR_FILE_STORAGE_PATH"),
            max_file_size=int(os.getenv("NARRATOR_MAX_FILE_SIZE", "52428800")),
            max_storage_size=int(os.getenv("NARRATOR_MAX_STORAGE_SIZE", "5368709120")),
            wandb_api_key=os.getenv("WANDB_API_KEY"),
            wandb_project=os.getenv("WANDB_PROJECT"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            environment=os.getenv("ENV", "development"),
            health_check_url=os.getenv("HEALTH_CHECK_URL"),
            health_ping_interval=int(os.getenv("HEALTH_PING_INTERVAL_SECONDS", "120")),
        )
    
    def validate_required_fields(self) -> None:
        """Validate that required fields are present"""
        if not self.slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required")
        if not self.slack_app_token:
            raise ValueError("SLACK_APP_TOKEN is required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.model_dump() 