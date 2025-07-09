"""
Tests for the configuration module
"""

import os
import pytest
from unittest.mock import patch

from space_monkey.core.config import Config

class TestConfig:
    """Tests for the Config class"""
    
    def test_config_initialization(self):
        """Test basic config initialization"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test"
        )
        
        assert config.slack_bot_token == "xoxb-test"
        assert config.slack_app_token == "xapp-test"
        assert config.environment == "development"  # default
        assert config.host == "0.0.0.0"  # default
        assert config.port == 8000  # default
    
    def test_config_with_all_fields(self):
        """Test config with all fields set"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test",
            database_url="postgresql://user:pass@localhost/db",
            file_storage_path="/path/to/files",
            max_file_size=100_000_000,
            max_storage_size=10_000_000_000,
            wandb_api_key="wandb-key",
            wandb_project="test-project",
            host="127.0.0.1",
            port=9000,
            environment="production",
            health_check_url="http://health.example.com",
            health_ping_interval=60
        )
        
        assert config.database_url == "postgresql://user:pass@localhost/db"
        assert config.file_storage_path == "/path/to/files"
        assert config.max_file_size == 100_000_000
        assert config.max_storage_size == 10_000_000_000
        assert config.wandb_api_key == "wandb-key"
        assert config.wandb_project == "test-project"
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.environment == "production"
        assert config.health_check_url == "http://health.example.com"
        assert config.health_ping_interval == 60
    
    @patch.dict(os.environ, {
        "SLACK_BOT_TOKEN": "xoxb-env-token",
        "SLACK_APP_TOKEN": "xapp-env-token",
        "NARRATOR_DATABASE_URL": "postgresql://env/db",
        "NARRATOR_FILE_STORAGE_PATH": "/env/files",
        "NARRATOR_MAX_FILE_SIZE": "200000000",
        "NARRATOR_MAX_STORAGE_SIZE": "20000000000",
        "WANDB_API_KEY": "env-wandb-key",
        "WANDB_PROJECT": "env-project",
        "HOST": "0.0.0.0",
        "PORT": "8080",
        "ENV": "staging",
        "HEALTH_CHECK_URL": "http://env-health.com",
        "HEALTH_PING_INTERVAL_SECONDS": "30"
    })
    def test_config_from_env(self):
        """Test creating config from environment variables"""
        config = Config.from_env()
        
        assert config.slack_bot_token == "xoxb-env-token"
        assert config.slack_app_token == "xapp-env-token"
        assert config.database_url == "postgresql://env/db"
        assert config.file_storage_path == "/env/files"
        assert config.max_file_size == 200_000_000
        assert config.max_storage_size == 20_000_000_000
        assert config.wandb_api_key == "env-wandb-key"
        assert config.wandb_project == "env-project"
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.environment == "staging"
        assert config.health_check_url == "http://env-health.com"
        assert config.health_ping_interval == 30
    
    @patch.dict(os.environ, {})
    def test_config_from_env_with_defaults(self):
        """Test config from env with missing values uses defaults"""
        config = Config.from_env()
        
        assert config.slack_bot_token == ""  # Required but empty
        assert config.slack_app_token == ""  # Required but empty
        assert config.database_url is None
        assert config.file_storage_path is None
        assert config.max_file_size == 52_428_800  # 50MB default
        assert config.max_storage_size == 5_368_709_120  # 5GB default
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.environment == "development"
        assert config.health_ping_interval == 120
    
    def test_validate_required_fields_success(self):
        """Test validation passes with required fields"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test"
        )
        
        # Should not raise any exception
        config.validate_required_fields()
    
    def test_validate_required_fields_missing_bot_token(self):
        """Test validation fails with missing bot token"""
        config = Config(
            slack_bot_token="",
            slack_app_token="xapp-test"
        )
        
        with pytest.raises(ValueError, match="SLACK_BOT_TOKEN is required"):
            config.validate_required_fields()
    
    def test_validate_required_fields_missing_app_token(self):
        """Test validation fails with missing app token"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token=""
        )
        
        with pytest.raises(ValueError, match="SLACK_APP_TOKEN is required"):
            config.validate_required_fields()
    
    def test_to_dict(self):
        """Test converting config to dictionary"""
        config = Config(
            slack_bot_token="xoxb-test",
            slack_app_token="xapp-test",
            environment="test"
        )
        
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["slack_bot_token"] == "xoxb-test"
        assert config_dict["slack_app_token"] == "xapp-test"
        assert config_dict["environment"] == "test"
        assert config_dict["host"] == "0.0.0.0"
        assert config_dict["port"] == 8000 