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
import signal
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from narrator import Thread, Message
from lye.slack import generate_slack_blocks
from tyler import Agent
from .message_classifier_prompt import format_classifier_prompt
from .utils import get_logger

# Get logger for this module
logger = get_logger(__name__)

class SlackApp:
    """
    Main SlackApp class that encapsulates all Slack integration logic.
    
    This class provides a clean interface for running Tyler agents as Slack agents
    with intelligent message routing, thread management, and health monitoring.
    """
    
    def __init__(
        self,
        agent,
        thread_store,
        file_store,
        response_topics: str = None
    ):
        """
        Initialize SlackApp with agent and stores.
        
        Args:
            agent: The main Tyler agent to handle conversations
            thread_store: ThreadStore instance for conversation persistence
            file_store: FileStore instance for file handling
            response_topics: Simple sentence describing what topics the bot should respond to
        """
        # Load environment variables
        load_dotenv()
        
        # Store configuration
        self.agent = agent
        self.thread_store = thread_store
        self.file_store = file_store
        self.health_check_url = os.getenv("HEALTH_CHECK_URL")
        self.weave_project = os.getenv("WANDB_PROJECT")
        
        # Classifier configuration
        self.response_topics = response_topics  # Will use default in format_classifier_prompt if None
        
        # Internal state
        self.slack_app = None
        self.socket_handler = None
        self.bot_user_id = None
        self.message_classifier_agent = None
        self.health_thread = None
        self.server = None  # Store uvicorn server instance
        self._original_sigint = None  # Store original SIGINT handler
        self._original_sigterm = None  # Store original SIGTERM handler
        self._shutdown_event = asyncio.Event()  # Event to signal shutdown
        self._background_tasks = set()  # Track background tasks
        
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
        
        # Close the socket handler
        if self.socket_handler:
            try:
                await self.socket_handler.close_async()
                logger.info("Slack socket handler closed")
            except Exception as e:
                logger.error(f"Error closing socket handler: {e}")
        
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
        # Use the configurable classifier prompt
        logger.info("Initializing message classifier with custom configuration")
        
        # Format the classifier prompt with configured parameters
        agent_name = getattr(self.agent, 'name', 'Assistant')
        if self.response_topics:
            formatted_prompt = format_classifier_prompt(
                agent_name=agent_name,
                bot_user_id=self.bot_user_id,
                response_topics=self.response_topics
            )
        else:
            # Use default response_topics
            formatted_prompt = format_classifier_prompt(
                agent_name=agent_name,
                bot_user_id=self.bot_user_id
            )
        
        # Initialize classifier agent
        self.message_classifier_agent = Agent(
            name="MessageClassifier",
            model_name="gpt-4.1",
            version="2.0.0",
            purpose=formatted_prompt
            # Note: Message classifier doesn't need stores - it only processes thread copies
        )
        topics_msg = self.response_topics or "default topics"
        logger.info(f"Message classifier initialized for agent '{agent_name}' with topics: {topics_msg}")
    
    def _register_event_handlers(self):
        """Register Slack event handlers."""
        # Global middleware for logging
        @self.slack_app.use
        async def log_all_events(client, context, logger, payload, next):
            try:
                logger.info(f"MIDDLEWARE: Received payload: {list(payload.keys())}")
                if isinstance(payload, dict) and "type" in payload:
                    event_type = payload["type"]
                    subtype = payload.get("subtype")
                    logger.critical(f"MIDDLEWARE: Event type '{event_type}', subtype: '{subtype}'")
                    
                    if event_type in ["reaction_added", "reaction_removed"]:
                        logger.critical(f"MIDDLEWARE: REACTION EVENT: {json.dumps(payload)}")
                    elif event_type == "message":
                        logger.critical(f"MIDDLEWARE: MESSAGE EVENT: channel={payload.get('channel')}, user={payload.get('user')}, ts={payload.get('ts')}, subtype={subtype}")
                    elif event_type == "app_mention":
                        logger.critical(f"MIDDLEWARE: APP_MENTION EVENT: channel={payload.get('channel')}, user={payload.get('user')}, ts={payload.get('ts')}")
                
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
        # Start the socket handler as a background task instead of blocking
        task = asyncio.create_task(self.socket_handler.start_async())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        # Give it a moment to connect
        await asyncio.sleep(0.5)
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
        logger.info(f"App mention event: ts={event.get('ts')}, channel={event.get('channel')}, user={event.get('user')}")
        
        # Check if this message has already been processed
        ts = event.get("ts")
        if await self._should_process_message(event):
            # Process the mention directly since sometimes Slack doesn't send a corresponding message event
            logger.info(f"Processing app_mention as message since it hasn't been processed yet")
            await self._handle_user_message(event, say)
        else:
            logger.info(f"App mention with ts={ts} already processed, skipping")
    
    async def _handle_user_message(self, event, say):
        """Handle user messages with intelligent routing."""
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        channel_type = event.get("channel_type")
        
        logger.info(f"Received user message: ts={ts}, thread_ts={thread_ts}, channel={channel}, channel_type={channel_type}")
        
        # Check if message should be processed
        if not await self._should_process_message(event):
            logger.info(f"Skipping message processing based on checks")
            return
        
        text = event.get("text", "")
        logger.info(f"Processing message text: {text[:100]}{'...' if len(text) > 100 else ''}")
        
        # Process the message
        response_type, content = await self._process_message(text, event)
        
        # Handle different response types
        if response_type == "none":
            logger.info("No response needed from agent")
            return
        elif response_type == "emoji":
            logger.info(f"Sending emoji reaction: {content.get('emoji')}")
            await self._send_emoji_reaction(content)
        elif response_type == "message":
            logger.info(f"Sending text response (length: {len(content['text'])} chars)")
            await self._send_response(content['text'], event, say)
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
        
        logger.info(f"Checking if message should be processed: ts={ts}, channel_type={channel_type}, thread_ts={thread_ts}")
        
        # Check if already processed in the database
        try:
            logger.info(f"Checking if message with ts={ts} has already been processed in database")
            messages = await self.thread_store.find_messages_by_attribute("platforms.slack.ts", ts)
            if messages:
                logger.info(f"Found existing message with ts={ts} - skipping processing")
                return False
            else:
                logger.info(f"No existing message found with ts={ts} - will process")
        except Exception as e:
            logger.warning(f"Error checking if message is already processed: {str(e)}")
            # Be conservative - if we can't check, assume it might have been processed
            # This prevents duplicate processing when there are database errors
            logger.info(f"Due to error, being conservative and skipping message with ts={ts}")
            return False
        
        # Process DMs, threaded messages, and channel messages
        if channel_type == "im":
            logger.info("Processing direct message")
            return True
        
        if thread_ts:
            logger.info(f"Processing thread reply in thread_ts={thread_ts}")
            return True
        
        logger.info("Processing channel message")
        return True  # For now, process all channel messages
    
    async def _process_message(self, text: str, event: dict):
        """Process a message and return (type, content) tuple."""
        try:
            logger.info("Starting message processing...")
            
            # Get or create thread
            thread = await self._get_or_create_thread(event)
            logger.info(f"Using thread {thread.id} with {len(thread.messages)} existing messages")
            
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
            logger.info(f"Added user message to thread and saved")
            
            # Run message classifier
            classifier_thread = copy.deepcopy(thread)
            thread_ts = event.get("thread_ts") or event.get("ts")
            
            logger.info(f"Passing copy of thread {classifier_thread.id} with {len(classifier_thread.messages)} messages to classifier")
            with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                classifier_result = await self.message_classifier_agent.go(classifier_thread)
            
            # Parse classification result
            classify_result = classifier_result.new_messages[-1].content if classifier_result.new_messages else None
            if classify_result:
                try:
                    classification = json.loads(classify_result)
                    response_type = classification.get("response_type", "full_response")
                    
                    if response_type == "ignore":
                        logger.info(f"Classification result: IGNORE - {classification.get('reasoning', 'No reason provided')}")
                        return ("none", "")
                    elif response_type == "emoji_reaction":
                        emoji = classification.get("suggested_emoji", "thumbsup")
                        logger.info(f"Classification result: EMOJI ({emoji}) - {classification.get('reasoning', 'No reason provided')}")
                        return ("emoji", {
                            "ts": event.get("ts"),
                            "channel": event.get("channel"),
                            "emoji": emoji
                        })
                    else:
                        logger.info(f"Classification result: FULL RESPONSE - {classification.get('reasoning', 'No reason provided')}")
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse classification response: {classify_result}")
            else:
                logger.warning("No classification result, proceeding with full response")
            
            # Add thinking emoji while processing
            try:
                logger.info(f"Adding thinking face emoji reaction to message {event.get('ts')} to indicate processing")
                await self.slack_app.client.reactions_add(
                    channel=event.get("channel"),
                    timestamp=event.get("ts"),
                    name="thinking_face"
                )
            except Exception as e:
                logger.warning(f"Failed to add thinking emoji: {str(e)}")
            
            # Process with main agent
            logger.info(f"Processing with main agent {self.agent.name}")
            logger.info(f"Thread ID: {thread.id}, Message count: {len(thread.messages)}")
            logger.info(f"Agent thread_store ID: {id(self.agent.thread_store)}, SlackApp thread_store ID: {id(self.thread_store)}")
            
            try:
                with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                    result = await self.agent.go(thread)
                    new_messages = result.new_messages
            except ValueError as e:
                if "Thread with ID" in str(e) and "not found" in str(e):
                    logger.error(f"Thread lookup failed: {e}")
                    logger.error(f"Failed thread ID: {thread.id}")
                    logger.error(f"Thread store contents: {await self.thread_store.list()}")
                raise
            
            logger.info(f"Agent returned {len(new_messages)} new messages")
            
            # Check for attachments in tool messages BEFORE sending response
            attachments_to_upload = []
            for msg in new_messages:
                if msg.role == "tool" and msg.attachments:
                    for attachment in msg.attachments:
                        attachments_to_upload.append({
                            "message": msg,
                            "attachment": attachment
                        })
            
            # Get assistant response
            assistant_messages = [m for m in new_messages if m.role == "assistant"]
            assistant_message = assistant_messages[-1] if assistant_messages else None
            
            if not assistant_message:
                logger.warning("No assistant message found in agent response")
                return ("message", {"text": "I apologize, but I couldn't generate a response."})
            
            response_content = assistant_message.content
            
            # Upload attachments BEFORE sending the message
            uploaded_files = []
            if attachments_to_upload:
                logger.info(f"Found {len(attachments_to_upload)} attachments to upload to Slack")
                for item in attachments_to_upload:
                    attachment = item["attachment"]
                    try:
                        # Get the file content
                        content_bytes = await attachment.get_content_bytes()
                        
                        # Get upload URL from Slack
                        logger.info(f"Getting upload URL for {attachment.filename}")
                        upload_url_response = await self.slack_app.client.files_getUploadURLExternal(
                            length=len(content_bytes),
                            filename=attachment.filename
                        )
                        
                        upload_url = upload_url_response['upload_url']
                        file_id = upload_url_response['file_id']
                        
                        # Upload the file
                        logger.info(f"Uploading {attachment.filename} to Slack")
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                upload_url,
                                data={'file': content_bytes}
                            ) as resp:
                                if resp.status != 200:
                                    logger.error(f"Failed to upload file: {await resp.text()}")
                                    continue
                        
                        # Don't complete the upload yet - save the file info
                        uploaded_files.append({
                            "file_id": file_id,
                            "filename": attachment.filename,
                            "mime_type": attachment.mime_type
                        })
                        logger.info(f"File {attachment.filename} uploaded, ready to share")
                        
                    except Exception as e:
                        logger.error(f"Error uploading attachment {attachment.filename}: {str(e)}")
            
            # Now send the message with files if any
            if uploaded_files:
                # Complete all uploads and share them with the message
                thread_ts_for_files = event.get("thread_ts") or event.get("ts")
                
                # Complete uploads with initial_comment containing our response
                files_to_complete = [{"id": f["file_id"], "title": f["filename"]} for f in uploaded_files]
                
                try:
                    complete_response = await self.slack_app.client.files_completeUploadExternal(
                        files=files_to_complete,
                        channel_id=event.get("channel"),
                        thread_ts=thread_ts_for_files,
                        initial_comment=response_content
                    )
                    
                    if complete_response['ok']:
                        logger.info(f"Successfully shared {len(files_to_complete)} files with message")
                        # Return empty response since files_completeUploadExternal already posted the message
                        return ("none", "")
                except Exception as e:
                    logger.error(f"Error completing file uploads: {str(e)}")
                    # Fall back to sending message without files
            
            # Log metrics if available
            if hasattr(assistant_message, 'metrics') and assistant_message.metrics:
                metrics = assistant_message.metrics
                logger.info(f"Message metrics - Model: {metrics.get('model', 'N/A')}, "
                           f"Tokens: {metrics.get('completion_tokens', 'N/A')}/{metrics.get('prompt_tokens', 'N/A')}")
            
            # Add dev footer if metrics available
            if hasattr(assistant_message, 'metrics') and assistant_message.metrics:
                footer = self._get_dev_footer(assistant_message.metrics)
                if footer:
                    response_content += footer
            
            logger.info(f"Returning message response with length: {len(response_content)} chars")
            return ("message", {"text": response_content})
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_msg = str(e)
            
            # Log thread IDs to help debug phantom thread errors
            if "Thread with ID" in error_msg and "not found" in error_msg:
                logger.error(f"Thread error detected!")
                logger.error(f"Current thread ID: {thread.id if 'thread' in locals() else 'No thread object'}")
                logger.error(f"Error mentions thread ID in message: {error_msg}")
                
                # Try to extract the error thread ID
                import re
                match = re.search(r'Thread with ID (\S+) not found', error_msg)
                if match:
                    error_thread_id = match.group(1)
                    logger.error(f"Error thread ID: {error_thread_id}")
                    logger.error(f"Current thread ID: {thread.id if 'thread' in locals() else 'No thread'}")
                    logger.error(f"Do they match? {error_thread_id == thread.id if 'thread' in locals() else 'No thread to compare'}")
                
                # Don't expose internal thread errors to users
                return ("message", {"text": "I apologize, but I'm having trouble processing your message. Please try again."})
            
            # For other errors, provide a generic error message
            return ("message", {"text": "I apologize, but I encountered an error. Please try again."})
    
    async def _get_or_create_thread(self, event):
        """Get or create a thread based on Slack event data."""
        slack_platform_data = {
            "channel": event.get("channel"),
            "thread_ts": event.get("thread_ts") or event.get("ts"),
        }
        
        # Try to find existing thread
        if event.get("thread_ts"):
            try:
                logger.info(f"Searching for thread with thread_ts: {event.get('thread_ts')}")
                threads = await self.thread_store.find_by_platform("slack", {"thread_ts": str(event.get("thread_ts"))})
                if threads:
                    logger.info(f"Found existing thread {threads[0].id} for Slack thread {event.get('thread_ts')}")
                    return threads[0]
                logger.info(f"No thread found with thread_ts: {event.get('thread_ts')}")
            except Exception as e:
                logger.warning(f"Error finding thread by thread_ts: {str(e)}", exc_info=True)
        
        # Try by ts
        ts = event.get("ts")
        if ts:
            try:
                logger.info(f"Searching for thread with ts as thread_ts: {ts}")
                threads = await self.thread_store.find_by_platform("slack", {"thread_ts": str(ts)})
                if threads:
                    logger.info(f"Found existing thread {threads[0].id} for Slack ts {ts}")
                    return threads[0]
                logger.info(f"No thread found with ts: {ts}")
            except Exception as e:
                logger.warning(f"Error finding thread by ts: {str(e)}", exc_info=True)
        
        # Create new thread
        thread = Thread(platforms={"slack": slack_platform_data})
        await self.thread_store.save(thread)
        logger.info(f"Created new thread {thread.id} with thread_ts: {slack_platform_data['thread_ts']}")
        return thread
    
    async def _find_message_and_thread(self, item_ts):
        """Find a message and its thread by timestamp."""
        try:
            logger.info(f"Searching for message with slack ts={item_ts}")
            messages = await self.thread_store.find_messages_by_attribute("platforms.slack.ts", item_ts)
            if not messages:
                logger.info(f"No message found with ts={item_ts}")
                return None, None
            
            message = messages[0]
            thread = await self.thread_store.get_thread_by_message_id(message.id)
            if not thread:
                logger.warning(f"Thread not found for message {message.id}")
                return message, None
            
            logger.info(f"Found message {message.id} in thread {thread.id}")
            return message, thread
        except Exception as e:
            logger.error(f"Error finding message and thread: {str(e)}", exc_info=True)
            return None, None
    
    async def _send_emoji_reaction(self, reaction_info):
        """Send an emoji reaction."""
        try:
            emoji = reaction_info["emoji"]
            ts = reaction_info["ts"]
            channel = reaction_info["channel"]
            logger.info(f"Adding emoji reaction '{emoji}' to message {ts} in channel {channel}")
            await self.slack_app.client.reactions_add(
                channel=channel,
                timestamp=ts,
                name=emoji
            )
            logger.info(f"Successfully added emoji reaction '{emoji}'")
        except Exception as e:
            logger.error(f"Error sending emoji reaction: {str(e)}", exc_info=True)
    
    async def _send_response(self, text, event, say):
        """Send a text response."""
        try:
            thread_ts = event.get("thread_ts") or event.get("ts")
            
            # Convert text to Slack blocks
            logger.info(f"Converting response to Slack blocks for thread_ts={thread_ts}")
            response_blocks = await self._convert_to_slack_blocks(text, thread_ts)
            
            # Send the text message
            logger.info(f"Sending response with thread_ts={thread_ts}")
            response = await say(
                thread_ts=thread_ts,
                text=response_blocks["text"],
                blocks=response_blocks["blocks"]
            )
            
            # Update assistant message with Slack timestamp
            if response and "ts" in response:
                logger.info(f"Response sent successfully with ts={response['ts']}")
                thread = await self._get_or_create_thread(event)
                updated = await self._update_assistant_message_with_slack_ts(
                    thread,
                    event.get("channel"),
                    response["ts"],
                    thread_ts
                )
                if updated:
                    logger.info(f"Updated assistant message with Slack timestamp")
                else:
                    logger.warning("Failed to update assistant message with Slack timestamp")
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}", exc_info=True)
    
    async def _convert_to_slack_blocks(self, text, thread_ts=None):
        """Convert markdown text to Slack blocks."""
        try:
            logger.debug(f"Converting text to Slack blocks (length: {len(text)} chars)")
            with weave.attributes({'env': os.getenv("ENV", "development"), 'event_id': thread_ts}):
                result = await generate_slack_blocks(content=text)
            
            if result and isinstance(result, dict) and "blocks" in result:
                logger.debug(f"Successfully converted to {len(result['blocks'])} blocks")
                return {"blocks": result["blocks"], "text": result.get("text", text)}
            else:
                logger.warning("Unexpected response format from generate_slack_blocks")
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
                    logger.info(f"Updated assistant message {message.id} with slack ts={response_ts}")
                    return True
            logger.info("No assistant messages found to update with Slack timestamp")
            return False
        except Exception as e:
            logger.error(f"Error updating assistant message with slack ts: {str(e)}", exc_info=True)
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
        """Start the Slack agent server."""
        config = uvicorn.Config(
            app=self.fastapi_app,
            host=host,
            port=port,
            log_level="info",
            workers=1,
            loop="asyncio",
            timeout_keep_alive=65,
            # Disable uvicorn's signal handlers so we can use our own
            use_colors=True,
            server_header=False,
        )
        
        self.server = uvicorn.Server(config)
        
        # Override uvicorn's signal handling
        self.server.install_signal_handlers = lambda: None
        
        # Set up our own signal handlers
        self._setup_signal_handlers()
        
        try:
            logger.info(f"Starting server on {host}:{port}")
            # Run server with shutdown event monitoring
            server_task = asyncio.create_task(self.server.serve())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            
            # Wait for either server completion or shutdown signal
            done, pending = await asyncio.wait(
                {server_task, shutdown_task},
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except asyncio.CancelledError:
            logger.info("Server task cancelled")
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise
        finally:
            # Ensure proper cleanup
            await self._cleanup()
            # Restore original signal handlers
            self._restore_signal_handlers()
            logger.info("Server shutting down")
    
    async def _cleanup(self):
        """Clean up all resources."""
        logger.info("Starting cleanup...")
        
        # Cancel all background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Shutdown server if still running
        if self.server and not self.server.should_exit:
            self.server.should_exit = True
            
        logger.info("Cleanup complete")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, triggering shutdown event...")
            # Simply set the shutdown event - let async code handle the rest
            self._shutdown_event.set()
        
        # Store original handlers and set new ones
        self._original_sigint = signal.signal(signal.SIGINT, signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers installed for graceful shutdown")
    
    def _restore_signal_handlers(self):
        """Restore original signal handlers."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        logger.info("Original signal handlers restored") 