"""
SlackApp class for Slack App integration
"""
import os
import asyncio
import logging
import copy
import json
import time
import threading
import requests
import weave
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from narrator import Thread, Message
from tyler.tools.slack import generate_slack_blocks

# Set up logging
logger = logging.getLogger(__name__)

class SlackApp:
    """
    Main SlackApp class that encapsulates all Slack integration logic.
    
    This class provides a clean interface for running Tyler agents as Slack bots
    with intelligent message routing, thread management, and health monitoring.
    """
    
    def __init__(
        self,
        agent,
        thread_store,
        file_store,
        health_check_url: str = None,
        weave_project: str = None
    ):
        """
        Initialize SlackApp with agent and stores.
        
        Args:
            agent: The main Tyler agent to handle conversations
            thread_store: ThreadStore instance for conversation persistence
            file_store: FileStore instance for file handling
            health_check_url: Optional URL for health check pings
            weave_project: Optional Weave project name for tracing
        """
        # Load environment variables
        load_dotenv()
        
        # Store configuration
        self.agent = agent
        self.thread_store = thread_store
        self.file_store = file_store
        self.health_check_url = health_check_url or os.getenv("HEALTH_CHECK_URL")
        self.weave_project = weave_project or os.getenv("WANDB_PROJECT")
        
        # Internal state
        self.slack_app = None
        self.socket_handler = None
        self.bot_user_id = None
        self.message_classifier_agent = None
        self.health_thread = None
        
        # FastAPI app for server functionality
        self.fastapi_app = FastAPI(
            title="Space Monkey Slack Agent",
            lifespan=self._lifespan
        )
        
        # Add CORS middleware
        self.fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """FastAPI lifespan context manager for startup/shutdown logic."""
        # Startup
        await self._startup()
        yield
        # Shutdown
        await self._shutdown()
    
    async def _startup(self):
        """Initialize all components during startup."""
        logger.info("Starting Space Monkey Slack Agent...")
        
        # Initialize Weave if configured
        await self._init_weave()
        
        # Initialize Slack app and get bot user ID
        await self._init_slack_app()
        
        # Initialize message classifier
        await self._init_classifier()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Start Slack socket connection
        await self._start_slack()
        
        # Start health monitoring
        self._start_health_monitoring()
        
        logger.info("Space Monkey Slack Agent started successfully")
    
    async def _shutdown(self):
        """Clean shutdown logic."""
        logger.info("Shutting down Space Monkey Slack Agent...")
        
        if self.socket_handler:
            await self.socket_handler.close_async()
        
        # Close database connections if available
        if (self.thread_store and 
            hasattr(self.thread_store, '_backend') and 
            hasattr(self.thread_store._backend, 'engine')):
            try:
                await self.thread_store._backend.engine.dispose()
                logger.info("Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
    
    async def _init_weave(self):
        """Initialize Weave monitoring if configured."""
        try:
            if os.getenv("WANDB_API_KEY") and self.weave_project:
                weave.init(self.weave_project)
                logger.info("Weave tracing initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize weave tracing: {e}")
    
    async def _init_slack_app(self):
        """Initialize the Slack app and get bot user ID."""
        # Create Slack app
        self.slack_app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
        
        # Get bot user ID for mention detection
        auth_response = await self.slack_app.client.auth_test()
        self.bot_user_id = auth_response["user_id"]
        logger.info(f"Agent initialized with user ID: {self.bot_user_id}")
    
    async def _init_classifier(self):
        """Initialize the message classifier agent."""
        # Import here to avoid circular imports
        from .classifier import initialize_message_classifier_agent
        
        # Get classifier prompt version from environment
        classifier_prompt_version = os.getenv("MESSAGE_CLASSIFIER_PROMPT_VERSION")
        if not classifier_prompt_version:
            logger.error("MESSAGE_CLASSIFIER_PROMPT_VERSION not set")
            raise RuntimeError("MESSAGE_CLASSIFIER_PROMPT_VERSION not set")
        
        # Fetch prompt from Weave
        try:
            classifier_prompt_obj = weave.ref(f"MessageClassifierPurposePrompt:{classifier_prompt_version}").get()
            logger.info(f"Fetched classifier prompt: {classifier_prompt_version}")
        except Exception as e:
            logger.error(f"Failed to load classifier prompt: {e}")
            raise RuntimeError(f"Failed to load classifier prompt: {e}")
        
        # Initialize classifier agent
        self.message_classifier_agent = initialize_message_classifier_agent(
            model_name="gpt-4.1",
            purpose_prompt=classifier_prompt_obj,
            thread_store=self.thread_store,
            file_store=self.file_store,
            bot_user_id=self.bot_user_id
        )
        logger.info("Message classifier agent initialized")
    
    def _register_event_handlers(self):
        """Register Slack event handlers."""
        # Global middleware for logging
        @self.slack_app.use
        async def log_all_events(client, context, logger, payload, next):
            try:
                logger.info(f"MIDDLEWARE: Received payload: {list(payload.keys())}")
                if isinstance(payload, dict) and "type" in payload:
                    event_type = payload["type"]
                    logger.critical(f"MIDDLEWARE: Event type '{event_type}'")
                    
                    if event_type in ["reaction_added", "reaction_removed"]:
                        logger.critical(f"MIDDLEWARE: REACTION EVENT: {json.dumps(payload)}")
                    elif event_type == "message":
                        logger.critical(f"MIDDLEWARE: MESSAGE EVENT: channel={payload.get('channel')}, user={payload.get('user')}, ts={payload.get('ts')}")
                
                await next()
            except Exception as e:
                logger.error(f"Error in middleware: {str(e)}")
                await next()
        
        # Register event handlers
        self.slack_app.event({"type": "message", "subtype": None})(self._handle_user_message)
        self.slack_app.event("app_mention")(self._handle_app_mention)
        self.slack_app.event("reaction_added")(self._handle_reaction_added)
        self.slack_app.event("reaction_removed")(self._handle_reaction_removed)
    
    async def _start_slack(self):
        """Start the Slack socket connection."""
        self.socket_handler = AsyncSocketModeHandler(self.slack_app, os.environ["SLACK_APP_TOKEN"])
        await self.socket_handler.start_async()
        logger.info("Slack socket connection established")
    
    def _start_health_monitoring(self):
        """Start health monitoring thread if configured."""
        if not self.health_check_url:
            return
        
        def health_ping_loop():
            """Health ping loop in background thread."""
            ping_interval = int(os.getenv("HEALTH_PING_INTERVAL_SECONDS", "120"))
            logger.info(f"Starting health ping to {self.health_check_url} every {ping_interval}s")
            
            while True:
                try:
                    response = requests.get(self.health_check_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Health ping successful: {response.text}")
                    else:
                        logger.warning(f"Health ping returned status: {response.status_code}")
                except Exception as e:
                    logger.error(f"Health ping failed: {str(e)}")
                
                time.sleep(ping_interval)
        
        self.health_thread = threading.Thread(target=health_ping_loop, daemon=True)
        self.health_thread.start()
        logger.info("Health monitoring started")
    
    # Event handlers
    async def _handle_app_mention(self, event, say):
        """Handle app mention events."""
        logger.info(f"App mention event: ts={event.get('ts')}")
    
    async def _handle_user_message(self, event, say):
        """Handle user messages with intelligent routing."""
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        channel_type = event.get("channel_type")
        
        logger.info(f"Message: ts={ts}, thread_ts={thread_ts}, channel={channel}, type={channel_type}")
        
        # Check if message should be processed
        if not await self._should_process_message(event):
            logger.info("Skipping message processing")
            return
        
        text = event.get("text", "")
        
        # Process the message
        response_type, content = await self._process_message(text, event)
        
        # Handle different response types
        if response_type == "none":
            logger.info("No response needed")
            return
        elif response_type == "emoji":
            await self._send_emoji_reaction(content)
        elif response_type == "message":
            await self._send_text_response(content, event, say)
        else:
            logger.warning(f"Unknown response type: {response_type}")
    
    async def _handle_reaction_added(self, event, say):
        """Handle reaction added events."""
        try:
            user = event.get("user")
            emoji = event.get("reaction")
            item_ts = event.get("item", {}).get("ts")
            
            logger.info(f"Reaction added: {emoji} by {user} on {item_ts}")
            
            # Find message and thread
            message, thread = await self._find_message_and_thread(item_ts)
            if message and thread:
                if thread.add_reaction(message.id, emoji, user):
                    await self.thread_store.save(thread)
                    logger.info(f"Stored reaction {emoji}")
        except Exception as e:
            logger.error(f"Error handling reaction: {str(e)}")
    
    async def _handle_reaction_removed(self, event, say):
        """Handle reaction removed events."""
        try:
            user = event.get("user")
            emoji = event.get("reaction")
            item_ts = event.get("item", {}).get("ts")
            
            logger.info(f"Reaction removed: {emoji} by {user} on {item_ts}")
            
            # Find message and thread
            message, thread = await self._find_message_and_thread(item_ts)
            if message and thread:
                if thread.remove_reaction(message.id, emoji, user):
                    await self.thread_store.save(thread)
                    logger.info(f"Removed reaction {emoji}")
        except Exception as e:
            logger.error(f"Error handling reaction removal: {str(e)}")
    
    # Helper methods
    async def _should_process_message(self, event):
        """Determine if a message should be processed."""
        ts = str(event.get("ts"))
        channel_type = event.get("channel_type")
        thread_ts = event.get("thread_ts")
        
        # Check if already processed
        try:
            messages = await self.thread_store.find_messages_by_attribute("platforms.slack.ts", ts)
            if messages:
                logger.info(f"Message {ts} already processed")
                return False
        except Exception as e:
            logger.warning(f"Error checking message: {str(e)}")
        
        # Process DMs, threaded messages, and channel messages
        if channel_type == "im" or thread_ts:
            return True
        
        return True  # For now, process all channel messages
    
    async def _process_message(self, text: str, event: dict):
        """Process a message and return (type, content) tuple."""
        try:
            # Get or create thread
            thread = await self._get_or_create_thread(event)
            
            # Create user message
            user_id = event.get("user", "unknown_user")
            user_message = Message(
                role="user",
                content=text,
                source={"id": user_id, "type": "user"},
                platforms={
                    "slack": {
                        "channel": event.get("channel"),
                        "ts": event.get("ts"),
                        "thread_ts": event.get("thread_ts") or event.get("ts")
                    }
                }
            )
            
            # Add message to thread and save
            thread.add_message(user_message)
            await self.thread_store.save(thread)
            
            # Run message classifier
            classifier_thread = copy.deepcopy(thread)
            thread_ts = event.get("thread_ts") or event.get("ts")
            
            with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                _, classify_messages = await self.message_classifier_agent.go(classifier_thread)
            
            # Parse classification result
            classify_result = classify_messages[-1].content if classify_messages else None
            if classify_result:
                try:
                    classification = json.loads(classify_result)
                    response_type = classification.get("response_type", "full_response")
                    
                    if response_type == "ignore":
                        logger.info(f"Classification: IGNORE - {classification.get('reasoning', '')}")
                        return ("none", "")
                    elif response_type == "emoji_reaction":
                        emoji = classification.get("suggested_emoji", "thumbsup")
                        logger.info(f"Classification: EMOJI ({emoji}) - {classification.get('reasoning', '')}")
                        return ("emoji", {
                            "ts": event.get("ts"),
                            "channel": event.get("channel"),
                            "emoji": emoji
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse classification: {classify_result}")
            
            # Add thinking emoji while processing
            try:
                await self.slack_app.client.reactions_add(
                    channel=event.get("channel"),
                    timestamp=event.get("ts"),
                    name="thinking_face"
                )
            except Exception as e:
                logger.warning(f"Failed to add thinking emoji: {str(e)}")
            
            # Process with main agent
            with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                _, new_messages = await self.agent.go(thread.id)
            
            # Get assistant response
            assistant_messages = [m for m in new_messages if m.role == "assistant"]
            assistant_message = assistant_messages[-1] if assistant_messages else None
            
            if not assistant_message:
                return ("message", "I apologize, but I couldn't generate a response.")
            
            response_content = assistant_message.content
            
            # Add dev footer if metrics available
            if hasattr(assistant_message, 'metrics') and assistant_message.metrics:
                footer = self._get_dev_footer(assistant_message.metrics)
                if footer:
                    response_content += footer
            
            return ("message", response_content)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return ("message", f"I apologize, but I encountered an error: {str(e)}")
    
    async def _get_or_create_thread(self, event):
        """Get or create a thread based on Slack event data."""
        slack_platform_data = {
            "channel": event.get("channel"),
            "thread_ts": event.get("thread_ts") or event.get("ts"),
        }
        
        # Try to find existing thread
        if event.get("thread_ts"):
            try:
                threads = await self.thread_store.find_by_platform("slack", {"thread_ts": str(event.get("thread_ts"))})
                if threads:
                    return threads[0]
            except Exception as e:
                logger.warning(f"Error finding thread: {str(e)}")
        
        # Try by ts
        ts = event.get("ts")
        if ts:
            try:
                threads = await self.thread_store.find_by_platform("slack", {"thread_ts": str(ts)})
                if threads:
                    return threads[0]
            except Exception as e:
                logger.warning(f"Error finding thread by ts: {str(e)}")
        
        # Create new thread
        thread = Thread(platforms={"slack": slack_platform_data})
        await self.thread_store.save(thread)
        logger.info(f"Created new thread {thread.id}")
        return thread
    
    async def _find_message_and_thread(self, item_ts):
        """Find a message and its thread by timestamp."""
        try:
            messages = await self.thread_store.find_messages_by_attribute("platforms.slack.ts", item_ts)
            if not messages:
                return None, None
            
            message = messages[0]
            thread = await self.thread_store.get_thread_by_message_id(message.id)
            return message, thread
        except Exception as e:
            logger.error(f"Error finding message: {str(e)}")
            return None, None
    
    async def _send_emoji_reaction(self, reaction_info):
        """Send an emoji reaction."""
        try:
            await self.slack_app.client.reactions_add(
                channel=reaction_info["channel"],
                timestamp=reaction_info["ts"],
                name=reaction_info["emoji"]
            )
        except Exception as e:
            logger.error(f"Error sending emoji reaction: {str(e)}")
    
    async def _send_text_response(self, text, event, say):
        """Send a text response."""
        try:
            # Convert to Slack blocks
            thread_ts = event.get("thread_ts") or event.get("ts")
            response_blocks = await self._convert_to_slack_blocks(text, thread_ts)
            
            # Send response
            response = await say(
                thread_ts=thread_ts,
                text=response_blocks["text"],
                blocks=response_blocks["blocks"]
            )
            
            # Update assistant message with Slack timestamp
            if response and "ts" in response:
                thread = await self._get_or_create_thread(event)
                await self._update_assistant_message_with_slack_ts(
                    thread,
                    event.get("channel"),
                    response["ts"],
                    thread_ts
                )
        except Exception as e:
            logger.error(f"Error sending text response: {str(e)}")
    
    async def _convert_to_slack_blocks(self, text, thread_ts=None):
        """Convert markdown text to Slack blocks."""
        try:
            with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                result = await generate_slack_blocks(content=text)
            
            if result and isinstance(result, dict) and "blocks" in result:
                return {"blocks": result["blocks"], "text": result.get("text", text)}
            else:
                return {"text": text}
        except Exception as e:
            logger.error(f"Error converting to Slack blocks: {e}")
            return {"text": text}
    
    async def _update_assistant_message_with_slack_ts(self, thread, channel, response_ts, thread_ts):
        """Update assistant message with Slack timestamp."""
        try:
            for message in reversed(thread.messages):
                if message.role == "assistant" and (not message.platforms or "slack" not in message.platforms):
                    message.platforms = message.platforms or {}
                    message.platforms["slack"] = {
                        "channel": channel,
                        "ts": response_ts,
                        "thread_ts": thread_ts
                    }
                    await self.thread_store.save(thread)
                    logger.info(f"Updated assistant message with ts={response_ts}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error updating assistant message: {str(e)}")
            return False
    
    def _get_dev_footer(self, metrics):
        """Generate dev footer from metrics."""
        footer = f"\n\n{self.agent.name}: v{getattr(self.agent, 'version', '1.0.0')}"
        
        model = metrics.get('model', 'N/A')
        weave_url = None
        if 'weave_call' in metrics:
            weave_url = metrics['weave_call'].get('ui_url')
        
        if model:
            footer += f" {model}"
        if weave_url:
            footer += f" | [Weave trace]({weave_url})"
        
        return footer if (weave_url or model) else ""
    
    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the Slack bot server."""
        config = uvicorn.Config(
            app=self.fastapi_app,
            host=host,
            port=port,
            log_level="info",
            workers=1,
            loop="asyncio",
            timeout_keep_alive=65,
        )
        
        server = uvicorn.Server(config)
        
        try:
            logger.info(f"Starting server on {host}:{port}")
            await server.serve()
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info("Server shutting down") 