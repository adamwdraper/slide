"""
Event routing and handling for Space Monkey bot framework
"""

import json
import logging
import weave
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

from narrator import Thread, Message

from ..utils.blocks import convert_to_slack_blocks

if TYPE_CHECKING:
    from .bot import SpaceMonkey

logger = logging.getLogger(__name__)

class EventRouter:
    """
    Routes Slack events to appropriate handlers and manages the agent processing pipeline
    """
    
    def __init__(self, bot: "SpaceMonkey"):
        self.bot = bot
    
    async def handle_middleware(self, payload: Dict[str, Any], next_func) -> None:
        """
        Global middleware handler for all Slack events
        
        Args:
            payload: The Slack event payload
            next_func: The next middleware function to call
        """
        try:
            # Log the event for debugging
            if isinstance(payload, dict) and "type" in payload:
                event_type = payload["type"]
                logger.debug(f"Received event of type '{event_type}'")
                
                # Special logging for specific event types
                if event_type in ["reaction_added", "reaction_removed"]:
                    logger.debug(f"REACTION EVENT: {json.dumps(payload)}")
                elif event_type == "message":
                    logger.debug(f"MESSAGE EVENT: channel={payload.get('channel')}, user={payload.get('user')}, ts={payload.get('ts')}")
            
            # Run through registered middleware
            processed_payload = await self.bot.middleware.process(payload)
            
            # Continue to the next middleware/listener
            await next_func()
            
        except Exception as e:
            logger.error(f"Error in global middleware: {str(e)}")
            # Make sure to call next() even if there's an error
            await next_func()
    
    async def handle_app_mention(self, event: Dict[str, Any], say) -> None:
        """
        Handle app_mention events
        
        Since mentions are already processed by the message event handler,
        this handler just acknowledges the event to prevent warnings.
        """
        logger.debug(f"Received app_mention event with ts={event.get('ts')} - will be processed by message handler")
        return
    
    @weave.op()
    async def handle_user_message(self, event: Dict[str, Any], say) -> None:
        """
        Handle regular user messages (no subtypes)
        
        Args:
            event: The Slack message event
            say: The Slack say function for sending responses
        """
        # Log message context
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        channel_type = event.get("channel_type")
        
        logger.info(f"Processing user message: ts={ts}, thread_ts={thread_ts}, channel={channel}, channel_type={channel_type}")
        
        # Check if we should process this message
        if not await self._should_process_message(event):
            logger.info("Skipping message processing based on checks")
            return
        
        text = event.get("text", "")
        
        # Process the message and get structured response
        response_type, content = await self._process_message(text, event)
        
        # Handle different response types
        if response_type == "none":
            logger.info("No response needed")
            return
        
        elif response_type == "emoji":
            # Add emoji reaction
            await self._add_emoji_reaction(content, event)
        
        elif response_type == "message":
            # Send text message response
            await self._send_message_response(content, event, say)
        
        else:
            logger.warning(f"Unknown response type: {response_type}")
    
    async def handle_reaction_added(self, event: Dict[str, Any], say) -> None:
        """
        Handle reaction_added events
        
        Args:
            event: The reaction event
            say: The Slack say function
        """
        try:
            user = event.get("user")
            emoji = event.get("reaction")
            item_ts = event.get("item", {}).get("ts")
            item_channel = event.get("item", {}).get("channel")
            
            logger.info(f"Reaction added: emoji={emoji}, user={user}, ts={item_ts}, channel={item_channel}")
            
            # Find the message and thread
            message, thread = await self._find_message_and_thread(item_ts)
            
            if not message or not thread:
                logger.warning(f"Could not find message or thread for reaction to ts: {item_ts}")
                return
            
            # Add reaction to thread
            if thread.add_reaction(message.id, emoji, user):
                await self.bot.thread_store.save(thread)
                logger.info(f"Stored reaction {emoji} from user {user} on message {message.id}")
            
            # Notify agents of reaction
            for agent in self.bot.agent_registry.get_agents_for_event(event, thread):
                try:
                    await agent.on_reaction_added(event, thread)
                except Exception as e:
                    logger.error(f"Error in agent {agent.name} reaction handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling reaction added event: {str(e)}")
    
    async def handle_reaction_removed(self, event: Dict[str, Any], say) -> None:
        """
        Handle reaction_removed events
        
        Args:
            event: The reaction event
            say: The Slack say function
        """
        try:
            user = event.get("user")
            emoji = event.get("reaction")
            item_ts = event.get("item", {}).get("ts")
            item_channel = event.get("item", {}).get("channel")
            
            logger.info(f"Reaction removed: emoji={emoji}, user={user}, ts={item_ts}, channel={item_channel}")
            
            # Find the message and thread
            message, thread = await self._find_message_and_thread(item_ts)
            
            if not message or not thread:
                logger.warning(f"Could not find message or thread for reaction removal from ts: {item_ts}")
                return
            
            # Remove reaction from thread
            if thread.remove_reaction(message.id, emoji, user):
                await self.bot.thread_store.save(thread)
                logger.info(f"Removed reaction {emoji} from user {user} on message {message.id}")
            
            # Notify agents of reaction removal
            for agent in self.bot.agent_registry.get_agents_for_event(event, thread):
                try:
                    await agent.on_reaction_removed(event, thread)
                except Exception as e:
                    logger.error(f"Error in agent {agent.name} reaction removal handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling reaction removed event: {str(e)}")
    
    async def _should_process_message(self, event: Dict[str, Any]) -> bool:
        """
        Determine if a message should be processed based on various criteria
        
        Args:
            event: The full Slack event data
            
        Returns:
            bool: True if the message should be processed, False otherwise
        """
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")
        channel_type = event.get("channel_type")
        
        # Check if this message has already been processed
        try:
            if self.bot.thread_store:
                ts_str = str(ts)
                messages = await self.bot.thread_store.find_messages_by_attribute("platforms.slack.ts", ts_str)
                
                if messages:
                    logger.info(f"Message with ts={ts_str} already processed - skipping")
                    return False
        except Exception as e:
            logger.warning(f"Error checking if message is already processed: {str(e)}")
        
        # Process all direct messages (DMs)
        if channel_type == "im":
            logger.info("Processing direct message")
            return True
        
        # Process all threaded messages
        if thread_ts:
            logger.info(f"Processing thread reply in thread_ts={thread_ts}")
            return True
        
        # For non-threaded messages in channels, process all
        logger.info("Processing channel message")
        return True
    
    @weave.op()
    async def _process_message(self, text: str, event: Dict[str, Any]) -> Tuple[str, Any]:
        """
        Process a message with agents and return structured response
        
        Args:
            text: The message text
            event: The Slack event data
            
        Returns:
            Tuple[str, Any]: (response_type, content) where response_type is 
                           "none", "message", or "emoji"
        """
        try:
            # Get or create a thread
            thread = await self._get_or_create_thread(event)
            
            # Create user message
            user_message = self._create_user_message(text, event)
            
            # Add message to thread and save
            thread.add_message(user_message)
            await self.bot.thread_store.save(thread)
            
            # Run through classifiers first
            classifiers = self.bot.agent_registry.get_classifiers()
            for classifier in classifiers:
                try:
                    thread_ts = event.get("thread_ts") or event.get("ts")
                    with weave.attributes({'env': self.bot.config.environment, 'event_id': thread_ts}):
                        classification = await classifier.classify_message(thread, event)
                    
                    # Handle classification result
                    response_type = classification.get("response_type", "full_response")
                    
                    if response_type == "ignore":
                        logger.info(f"Classification result: IGNORE - {classification.get('reasoning', 'No reason provided')}")
                        return ("none", "")
                    
                    elif response_type == "emoji_reaction":
                        suggested_emoji = classification.get("suggested_emoji", "thumbsup")
                        logger.info(f"Classification result: EMOJI ({suggested_emoji}) - {classification.get('reasoning', 'No reason provided')}")
                        reaction_info = {
                            "ts": event.get("ts"),
                            "channel": event.get("channel"),
                            "emoji": suggested_emoji
                        }
                        return ("emoji", reaction_info)
                    
                    # Otherwise, proceed with full response
                    logger.info(f"Classification result: FULL RESPONSE - {classification.get('reasoning', 'No reason provided')}")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in classifier {classifier.name}: {e}")
            
            # Add thinking face emoji to show processing
            try:
                await self.bot.slack_app.client.reactions_add(
                    channel=event.get("channel"),
                    timestamp=event.get("ts"),
                    name="thinking_face"
                )
            except Exception as e:
                logger.warning(f"Failed to add thinking face emoji: {str(e)}")
            
            # Process with regular agents
            agents = self.bot.agent_registry.get_agents_for_event(event, thread)
            
            for agent in agents:
                try:
                    thread_ts = event.get("thread_ts") or event.get("ts")
                    with weave.attributes({'env': self.bot.config.environment, 'event_id': thread_ts}):
                        response = await agent.process_message(thread, event)
                    
                    if response:
                        # Add dev footer if agent has metrics
                        if hasattr(agent, 'version'):
                            footer = f"\n\n{agent.name}: v{agent.version}"
                            response += footer
                        
                        return ("message", response)
                        
                except Exception as e:
                    logger.error(f"Error in agent {agent.name}: {e}")
            
            return ("message", "I apologize, but I couldn't generate a response.")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return ("message", f"I apologize, but I encountered an error: {str(e)}")
    
    @weave.op()
    async def _get_or_create_thread(self, event: Dict[str, Any]) -> Thread:
        """Get an existing thread or create a new one based on Slack event data"""
        # Create the thread platform information
        slack_platform_data = {
            "channel": event.get("channel"),
            "thread_ts": event.get("thread_ts") or event.get("ts"),
        }
        
        # First attempt: Find thread by thread_ts
        if event.get("thread_ts"):
            try:
                thread_query = {"thread_ts": str(event.get("thread_ts"))}
                existing_threads = await self.bot.thread_store.find_by_platform("slack", thread_query)
                
                if existing_threads:
                    logger.info(f"Found existing thread {existing_threads[0].id} for Slack thread {event.get('thread_ts')}")
                    return existing_threads[0]
                    
            except Exception as e:
                logger.warning(f"Error finding thread by thread_ts: {str(e)}")
        
        # Second attempt: Find thread by ts
        ts = event.get("ts")
        if ts:
            try:
                ts_query = {"thread_ts": str(ts)}
                existing_threads = await self.bot.thread_store.find_by_platform("slack", ts_query)
                
                if existing_threads:
                    logger.info(f"Found existing thread {existing_threads[0].id} for Slack ts {ts}")
                    return existing_threads[0]
                    
            except Exception as e:
                logger.warning(f"Error finding thread by ts: {str(e)}")
        
        # Create new thread
        thread = Thread(platforms={"slack": slack_platform_data})
        await self.bot.thread_store.save(thread)
        logger.info(f"Created new thread {thread.id} with thread_ts: {slack_platform_data['thread_ts']}")
        
        return thread
    
    def _create_user_message(self, text: str, event: Dict[str, Any]) -> Message:
        """Create a user message from Slack event data"""
        user_id = event.get("user", "unknown_user")
        
        return Message(
            role="user",
            content=text,
            source={
                "id": user_id,
                "type": "user"
            },
            platforms={
                "slack": {
                    "channel": event.get("channel"),
                    "ts": event.get("ts"),
                    "thread_ts": event.get("thread_ts") or event.get("ts")
                }
            }
        )
    
    async def _find_message_and_thread(self, item_ts: str) -> Tuple[Optional[Message], Optional[Thread]]:
        """Find a message by its timestamp and return the message and its thread"""
        try:
            if not self.bot.thread_store:
                return None, None
            
            # Find the message by its timestamp
            messages = await self.bot.thread_store.find_messages_by_attribute("platforms.slack.ts", item_ts)
            
            if not messages:
                return None, None
            
            # Get the first matching message
            message = messages[0]
            
            # Get the thread containing this message
            thread = await self.bot.thread_store.get_thread_by_message_id(message.id)
            
            return message, thread
            
        except Exception as e:
            logger.error(f"Error finding message and thread: {str(e)}")
            return None, None
    
    async def _add_emoji_reaction(self, reaction_info: Dict[str, Any], event: Dict[str, Any]) -> None:
        """Add an emoji reaction to a message"""
        try:
            reaction_ts = reaction_info.get("ts", event.get("ts"))
            reaction_channel = reaction_info.get("channel", event.get("channel"))
            reaction_emoji = reaction_info.get("emoji", "thumbsup")
            
            logger.info(f"Adding emoji reaction '{reaction_emoji}' to message {reaction_ts} in channel {reaction_channel}")
            
            await self.bot.slack_app.client.reactions_add(
                channel=reaction_channel,
                timestamp=reaction_ts,
                name=reaction_emoji
            )
        except Exception as e:
            logger.error(f"Error adding emoji reaction: {str(e)}")
    
    async def _send_message_response(self, response_text: str, event: Dict[str, Any], say) -> None:
        """Send a text message response"""
        try:
            thread_ts = event.get("thread_ts") or event.get("ts")
            
            # Convert the markdown response to Slack blocks
            response_blocks = await convert_to_slack_blocks(response_text, thread_ts)
            
            # Send the response as a threaded reply
            logger.info(f"Sending response with thread_ts={thread_ts}")
            response = await say(
                thread_ts=thread_ts,
                text=response_blocks["text"],
                blocks=response_blocks["blocks"]
            )
            
            # Update the assistant message with the Slack timestamp
            if response and "ts" in response:
                await self._update_assistant_message_with_slack_ts(
                    event, response["ts"], thread_ts
                )
                
        except Exception as e:
            logger.error(f"Error sending message response: {str(e)}")
    
    async def _update_assistant_message_with_slack_ts(self, event: Dict[str, Any], response_ts: str, thread_ts: str) -> None:
        """Update the most recent assistant message with Slack platform data"""
        try:
            thread = await self._get_or_create_thread(event)
            
            # Find the last assistant message without slack ts
            for message in reversed(thread.messages):
                if message.role == "assistant" and (not message.platforms or "slack" not in message.platforms):
                    # Add slack platform data
                    message.platforms = message.platforms or {}
                    message.platforms["slack"] = {
                        "channel": event.get("channel"),
                        "ts": response_ts,
                        "thread_ts": thread_ts
                    }
                    await self.bot.thread_store.save(thread)
                    logger.info(f"Updated assistant message {message.id} with slack ts={response_ts}")
                    return
                    
        except Exception as e:
            logger.error(f"Error updating assistant message with slack ts: {str(e)}") 