"""
Main SpaceMonkey bot class
"""

import os
import asyncio
import logging
import signal
import sys
import time
import threading
import json
import weave
import requests
from typing import Dict, Any, Optional, Tuple, Type
from contextlib import asynccontextmanager

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from narrator import Thread, Message, ThreadStore, FileStore

from .config import Config
from .events import EventRouter
from .middleware import MiddlewareManager
from ..agents.registry import AgentRegistry
from ..agents.base import SlackAgent, ClassifierAgent
from ..utils.health import start_health_ping

logger = logging.getLogger(__name__)

class SpaceMonkey:
    """
    Main SpaceMonkey bot class
    
    This class orchestrates all components of the bot including agents,
    event handling, storage, and the web server.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.agent_registry = AgentRegistry(self)
        self.middleware = MiddlewareManager()
        self.event_router = EventRouter(self)
        
        # These will be initialized during startup
        self.thread_store: Optional[ThreadStore] = None
        self.file_store: Optional[FileStore] = None
        self.slack_app: Optional[AsyncApp] = None
        self.socket_handler: Optional[AsyncSocketModeHandler] = None
        self.bot_user_id: Optional[str] = None
        
        # FastAPI app will be created during initialization
        self.app: Optional[FastAPI] = None
        
        # Running state
        self._running = False
        self._startup_complete = False
    
    @classmethod
    def from_env(cls) -> "SpaceMonkey":
        """Create a SpaceMonkey instance from environment variables"""
        config = Config.from_env()
        config.validate_required_fields()
        return cls(config)
    
    def add_agent(self, name: str, agent_class: Type[SlackAgent], config: Dict[str, Any] = None) -> None:
        """
        Add an agent to the bot
        
        Args:
            name: Unique name for the agent
            agent_class: The agent class to add
            config: Configuration for the agent
        """
        if self._startup_complete:
            raise RuntimeError("Cannot add agents after bot startup is complete")
        
        self.agent_registry.register(name, agent_class, config or {})
    
    def add_middleware(self, middleware_func) -> None:
        """
        Add middleware to the processing pipeline
        
        Args:
            middleware_func: The middleware function to add
        """
        self.middleware.add(middleware_func)
    
    async def _initialize_weave(self) -> None:
        """Initialize Weave monitoring if configured"""
        try:
            if self.config.wandb_api_key and self.config.wandb_project:
                weave.init(self.config.wandb_project)
                logger.info("Weave tracing initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize weave tracing: {e}. Continuing without weave.")
    
    async def _initialize_stores(self) -> None:
        """Initialize thread and file stores"""
        # Initialize ThreadStore
        try:
            if self.config.database_url:
                self.thread_store = await ThreadStore.create(self.config.database_url)
                logger.info(f"Initialized database thread store")
            else:
                self.thread_store = await ThreadStore.create()
                logger.info("Initialized in-memory thread store")
        except Exception as e:
            logger.error(f"Failed to initialize thread store: {str(e)}")
            raise RuntimeError(f"Could not initialize thread store: {str(e)}") from e
        
        # Initialize FileStore
        try:
            if self.config.file_storage_path:
                self.file_store = await FileStore.create(
                    base_path=self.config.file_storage_path,
                    max_file_size=self.config.max_file_size,
                    max_storage_size=self.config.max_storage_size
                )
                logger.info(f"Initialized file store at: {self.config.file_storage_path}")
            else:
                self.file_store = await FileStore.create(
                    max_file_size=self.config.max_file_size,
                    max_storage_size=self.config.max_storage_size
                )
                logger.info(f"Initialized file store with default path")
        except Exception as e:
            logger.error(f"Failed to initialize file store: {str(e)}")
            raise RuntimeError(f"Could not initialize file store: {str(e)}") from e
    
    async def _initialize_slack_app(self) -> None:
        """Initialize the Slack app and get bot user ID"""
        self.slack_app = AsyncApp(token=self.config.slack_bot_token)
        
        # Get bot user ID for mention detection
        auth_response = await self.slack_app.client.auth_test()
        self.bot_user_id = auth_response["user_id"]
        logger.info(f"Bot initialized with user ID: {self.bot_user_id}")
        
        # Register event handlers
        self._register_slack_handlers()
    
    def _register_slack_handlers(self) -> None:
        """Register Slack event handlers"""
        if not self.slack_app:
            raise RuntimeError("Slack app not initialized")
        
        # Register global middleware
        @self.slack_app.use
        async def log_all_events(client, context, logger_instance, payload, next):
            await self.event_router.handle_middleware(payload, next)
        
        # Register event handlers
        self.slack_app.event({"type": "message", "subtype": None})(self.event_router.handle_user_message)
        self.slack_app.event("app_mention")(self.event_router.handle_app_mention)
        self.slack_app.event("reaction_added")(self.event_router.handle_reaction_added)
        self.slack_app.event("reaction_removed")(self.event_router.handle_reaction_removed)
    
    async def _start_slack_connection(self) -> None:
        """Start the Slack Socket Mode connection"""
        if not self.slack_app:
            raise RuntimeError("Slack app not initialized")
        
        self.socket_handler = AsyncSocketModeHandler(self.slack_app, self.config.slack_app_token)
        await self.socket_handler.start_async()
        logger.info("Slack bot connection started")
    
    async def _create_fastapi_app(self) -> FastAPI:
        """Create the FastAPI application"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            await self._startup()
            yield
            # Shutdown
            await self._shutdown()
        
        app = FastAPI(
            title="Space Monkey Bot",
            description="A powerful, extensible Slack bot framework",
            version="0.1.0",
            lifespan=lifespan
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add health check endpoint
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "bot_user_id": self.bot_user_id,
                "agents": self.agent_registry.list_agents(),
                "environment": self.config.environment
            }
        
        return app
    
    async def _startup(self) -> None:
        """Internal startup logic"""
        logger.info("Starting Space Monkey bot...")
        
        # Initialize Weave monitoring
        await self._initialize_weave()
        
        # Initialize stores
        await self._initialize_stores()
        
        # Initialize agents
        await self.agent_registry.initialize_all(self.thread_store, self.file_store)
        
        # Initialize Slack app
        await self._initialize_slack_app()
        
        # Start Slack connection
        await self._start_slack_connection()
        
        # Start health ping if configured
        if self.config.health_check_url:
            start_health_ping(self.config.health_check_url, self.config.health_ping_interval)
        
        self._startup_complete = True
        self._running = True
        logger.info("Space Monkey bot startup complete")
    
    async def _shutdown(self) -> None:
        """Internal shutdown logic"""
        logger.info("Shutting down Space Monkey bot...")
        self._running = False
        
        # Shutdown agents
        await self.agent_registry.shutdown_all()
        
        # Close Slack connection
        if self.socket_handler:
            await self.socket_handler.close_async()
        
        # Close database connections
        if self.thread_store and hasattr(self.thread_store, '_backend') and hasattr(self.thread_store._backend, 'engine'):
            try:
                await self.thread_store._backend.engine.dispose()
                logger.info("Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
        
        logger.info("Space Monkey bot shutdown complete")
    
    def run(self) -> None:
        """
        Run the bot using FastAPI/uvicorn
        
        This method starts the web server and runs the bot until interrupted.
        """
        async def create_app():
            self.app = await self._create_fastapi_app()
            return self.app
        
        # Create the app
        app = asyncio.run(create_app())
        
        # Configure uvicorn
        config = uvicorn.Config(
            app=app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
            workers=1,
            loop="asyncio",
            timeout_keep_alive=65,
        )
        
        # Start the server
        server = uvicorn.Server(config)
        
        # Handle signals
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}. Shutting down...")
            server.should_exit = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            logger.info(f"Starting Space Monkey bot on {self.config.host}:{self.config.port}")
            server.run()
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
        finally:
            logger.info("Space Monkey bot server stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if the bot is running"""
        return self._running
    
    @property
    def startup_complete(self) -> bool:
        """Check if startup is complete"""
        return self._startup_complete 