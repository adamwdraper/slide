"""
Middleware management for Space Monkey bot framework
"""

import logging
from typing import List, Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)

class MiddlewareManager:
    """
    Manages middleware functions that process events before they reach agents
    
    Middleware functions can modify events, add logging, implement rate limiting,
    or perform other cross-cutting concerns.
    """
    
    def __init__(self):
        self._middleware: List[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = []
    
    def add(self, middleware_func: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        Add a middleware function to the pipeline
        
        Args:
            middleware_func: An async function that takes an event dict and returns a modified event dict
        """
        self._middleware.append(middleware_func)
        logger.info(f"Added middleware function: {middleware_func.__name__}")
    
    def remove(self, middleware_func: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> bool:
        """
        Remove a middleware function from the pipeline
        
        Args:
            middleware_func: The middleware function to remove
            
        Returns:
            bool: True if removed, False if not found
        """
        try:
            self._middleware.remove(middleware_func)
            logger.info(f"Removed middleware function: {middleware_func.__name__}")
            return True
        except ValueError:
            logger.warning(f"Middleware function {middleware_func.__name__} not found")
            return False
    
    async def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an event through all middleware functions
        
        Args:
            event: The event to process
            
        Returns:
            Dict[str, Any]: The processed event
        """
        processed_event = event.copy()
        
        for middleware in self._middleware:
            try:
                processed_event = await middleware(processed_event)
                if processed_event is None:
                    logger.warning(f"Middleware {middleware.__name__} returned None, using original event")
                    processed_event = event
            except Exception as e:
                logger.error(f"Error in middleware {middleware.__name__}: {e}")
                # Continue with the original event if middleware fails
                processed_event = event
        
        return processed_event
    
    def clear(self) -> None:
        """Clear all middleware functions"""
        count = len(self._middleware)
        self._middleware.clear()
        logger.info(f"Cleared {count} middleware functions")
    
    @property
    def middleware_count(self) -> int:
        """Get the number of registered middleware functions"""
        return len(self._middleware)
    
    def list_middleware(self) -> List[str]:
        """
        Get a list of middleware function names
        
        Returns:
            List[str]: List of middleware function names
        """
        return [func.__name__ for func in self._middleware] 