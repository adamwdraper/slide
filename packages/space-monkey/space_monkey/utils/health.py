"""
Health check utilities for Space Monkey bot framework
"""

import logging
import time
import threading
import requests
from typing import Optional

logger = logging.getLogger(__name__)

def start_health_ping(health_check_url: str, ping_interval: int = 120) -> None:
    """
    Start a background thread that sends periodic health pings
    
    Args:
        health_check_url: URL to send health pings to
        ping_interval: Interval between pings in seconds
    """
    logger.info("Starting health ping system")
    
    # Check if health ping thread is already running
    health_thread_running = any(t.name == "health_ping_thread" for t in threading.enumerate())
    if health_thread_running:
        logger.info("Health ping thread is already running, skipping initialization")
        return
    
    try:
        thread = threading.Thread(
            target=_health_ping_loop,
            args=(health_check_url, ping_interval),
            daemon=True
        )
        thread.name = "health_ping_thread"
        thread.start()
        logger.info(f"Health ping thread started with ID: {thread.ident}")
        
        # Verify thread is alive
        if thread.is_alive():
            logger.info("Confirmed health ping thread is running")
        else:
            logger.critical("Health ping thread failed to start properly!")
            
    except Exception as e:
        logger.critical(f"Failed to start health ping thread: {str(e)}")

def _health_ping_loop(health_check_url: str, ping_interval: int) -> None:
    """
    Main health ping loop that runs in a background thread
    
    Args:
        health_check_url: URL to send health pings to
        ping_interval: Interval between pings in seconds
    """
    logger.info(f"Starting health ping loop to {health_check_url} every {ping_interval} seconds")
    
    # Send initial ping
    _send_health_ping(health_check_url, is_initial=True)
    
    # Counter for consecutive failures
    consecutive_failures = 0
    
    while True:
        try:
            # Sleep first, then ping
            time.sleep(ping_interval)
            
            # Send health ping
            success = _send_health_ping(health_check_url)
            
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
            # Log critical message if too many failures
            if consecutive_failures >= 5:
                logger.critical(f"Health ping has failed {consecutive_failures} consecutive times. Check network connectivity.")
                
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"Error in health ping loop: {str(e)} (failures: {consecutive_failures})")

def _send_health_ping(health_check_url: str, is_initial: bool = False) -> bool:
    """
    Send a single health ping
    
    Args:
        health_check_url: URL to send the ping to
        is_initial: Whether this is the initial ping
        
    Returns:
        bool: True if ping was successful, False otherwise
    """
    try:
        ping_type = "initial" if is_initial else "regular"
        logger.info(f"Sending {ping_type} health ping to {health_check_url}")
        
        response = requests.get(health_check_url, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"Successfully sent {ping_type} health ping: {response.text}")
            return True
        else:
            logger.warning(f"Health ping returned non-200 status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error when sending health ping: {str(e)}")
        return False
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout when sending health ping: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send health ping: {str(e)}")
        return False

def get_health_status() -> dict:
    """
    Get the current health status
    
    Returns:
        dict: Health status information
    """
    active_threads = threading.enumerate()
    health_thread = next((t for t in active_threads if t.name == "health_ping_thread"), None)
    
    return {
        "health_ping_active": health_thread is not None and health_thread.is_alive(),
        "health_thread_id": health_thread.ident if health_thread else None,
        "active_threads": len(active_threads),
        "thread_names": [t.name for t in active_threads]
    } 