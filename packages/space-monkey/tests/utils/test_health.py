"""
Tests for the health check utility module
"""

import threading
import time
import pytest
from unittest.mock import patch, Mock, call

from space_monkey.utils.health import (
    start_health_ping,
    get_health_status,
    _health_ping_loop,
    _send_health_ping
)

class TestStartHealthPing:
    """Tests for the start_health_ping function"""
    
    @patch('space_monkey.utils.health.threading.Thread')
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_start_health_ping_creates_thread(self, mock_enumerate, mock_thread):
        """Test that start_health_ping creates a new thread"""
        # Mock no existing health thread
        mock_enumerate.return_value = []
        
        mock_thread_instance = Mock()
        mock_thread_instance.ident = 12345
        mock_thread_instance.is_alive.return_value = True
        mock_thread.return_value = mock_thread_instance
        
        start_health_ping("http://test.com", 60)
        
        # Should create a thread
        mock_thread.assert_called_once()
        call_args = mock_thread.call_args
        assert call_args[1]['target'] == _health_ping_loop
        assert call_args[1]['args'] == ("http://test.com", 60)
        assert call_args[1]['daemon'] == True
        
        # Should start the thread
        mock_thread_instance.start.assert_called_once()
    
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_start_health_ping_skips_if_already_running(self, mock_enumerate):
        """Test that start_health_ping skips if thread already running"""
        # Mock existing health thread
        existing_thread = Mock()
        existing_thread.name = "health_ping_thread"
        mock_enumerate.return_value = [existing_thread]
        
        with patch('space_monkey.utils.health.threading.Thread') as mock_thread:
            start_health_ping("http://test.com", 60)
            
            # Should not create a new thread
            mock_thread.assert_not_called()
    
    @patch('space_monkey.utils.health.threading.Thread')
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_start_health_ping_handles_thread_creation_error(self, mock_enumerate, mock_thread):
        """Test error handling during thread creation"""
        mock_enumerate.return_value = []
        mock_thread.side_effect = RuntimeError("Thread creation failed")
        
        # Should not raise exception
        start_health_ping("http://test.com", 60)
    
    @patch('space_monkey.utils.health.threading.Thread')
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_start_health_ping_sets_thread_name(self, mock_enumerate, mock_thread):
        """Test that thread name is set correctly"""
        mock_enumerate.return_value = []
        mock_thread_instance = Mock()
        mock_thread_instance.is_alive.return_value = True
        mock_thread.return_value = mock_thread_instance
        
        start_health_ping("http://test.com", 60)
        
        # Should set thread name
        assert mock_thread_instance.name == "health_ping_thread"

class TestSendHealthPing:
    """Tests for the _send_health_ping function"""
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_success(self, mock_get):
        """Test successful health ping"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response
        
        result = _send_health_ping("http://test.com")
        
        assert result == True
        mock_get.assert_called_once_with("http://test.com", timeout=5)
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_non_200_status(self, mock_get):
        """Test health ping with non-200 status"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = _send_health_ping("http://test.com")
        
        assert result == False
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_connection_error(self, mock_get):
        """Test health ping with connection error"""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = _send_health_ping("http://test.com")
        
        assert result == False
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_timeout_error(self, mock_get):
        """Test health ping with timeout error"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        result = _send_health_ping("http://test.com")
        
        assert result == False
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_general_exception(self, mock_get):
        """Test health ping with general exception"""
        mock_get.side_effect = Exception("General error")
        
        result = _send_health_ping("http://test.com")
        
        assert result == False
    
    @patch('space_monkey.utils.health.requests.get')
    def test_send_health_ping_initial_flag(self, mock_get):
        """Test health ping with initial flag"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response
        
        result = _send_health_ping("http://test.com", is_initial=True)
        
        assert result == True
        # URL and timeout should be the same
        mock_get.assert_called_once_with("http://test.com", timeout=5)

class TestHealthPingLoop:
    """Tests for the _health_ping_loop function"""
    
    @patch('space_monkey.utils.health.time.sleep')
    @patch('space_monkey.utils.health._send_health_ping')
    def test_health_ping_loop_calls_send_ping(self, mock_send_ping, mock_sleep):
        """Test that health ping loop calls send ping"""
        # Mock successful pings
        mock_send_ping.return_value = True
        
        # Mock sleep to raise exception after first iteration to stop loop
        mock_sleep.side_effect = [None, KeyboardInterrupt()]
        
        try:
            _health_ping_loop("http://test.com", 30)
        except KeyboardInterrupt:
            pass
        
        # Should call send ping multiple times (initial + loop iterations)
        assert mock_send_ping.call_count >= 2
        
        # Should call sleep with correct interval
        mock_sleep.assert_called_with(30)
    
    @patch('space_monkey.utils.health.time.sleep')
    @patch('space_monkey.utils.health._send_health_ping')
    def test_health_ping_loop_handles_ping_failures(self, mock_send_ping, mock_sleep):
        """Test that loop handles ping failures gracefully"""
        # Mock failing pings
        mock_send_ping.return_value = False
        
        # Stop after a few iterations
        mock_sleep.side_effect = [None, None, KeyboardInterrupt()]
        
        try:
            _health_ping_loop("http://test.com", 30)
        except KeyboardInterrupt:
            pass
        
        # Should continue despite failures
        assert mock_send_ping.call_count >= 2
    
    @patch('space_monkey.utils.health.time.sleep')
    @patch('space_monkey.utils.health._send_health_ping')
    def test_health_ping_loop_handles_sleep_exception(self, mock_send_ping, mock_sleep):
        """Test that loop handles sleep exceptions"""
        mock_send_ping.return_value = True
        
        # First sleep works, second raises exception, third stops loop
        mock_sleep.side_effect = [None, RuntimeError("Sleep error"), KeyboardInterrupt()]
        
        try:
            _health_ping_loop("http://test.com", 30)
        except KeyboardInterrupt:
            pass
        
        # Should continue despite sleep exception
        assert mock_send_ping.call_count >= 2

class TestGetHealthStatus:
    """Tests for the get_health_status function"""
    
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_get_health_status_with_active_thread(self, mock_enumerate):
        """Test health status with active health ping thread"""
        # Mock health ping thread
        health_thread = Mock()
        health_thread.name = "health_ping_thread"
        health_thread.ident = 12345
        health_thread.is_alive.return_value = True
        
        other_thread = Mock()
        other_thread.name = "other_thread"
        
        mock_enumerate.return_value = [health_thread, other_thread]
        
        status = get_health_status()
        
        assert status["health_ping_active"] == True
        assert status["health_thread_id"] == 12345
        assert status["active_threads"] == 2
        assert "health_ping_thread" in status["thread_names"]
        assert "other_thread" in status["thread_names"]
    
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_get_health_status_with_inactive_thread(self, mock_enumerate):
        """Test health status with inactive health ping thread"""
        # Mock health ping thread that's not alive
        health_thread = Mock()
        health_thread.name = "health_ping_thread"
        health_thread.ident = 12345
        health_thread.is_alive.return_value = False
        
        mock_enumerate.return_value = [health_thread]
        
        status = get_health_status()
        
        assert status["health_ping_active"] == False
        assert status["health_thread_id"] == 12345
    
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_get_health_status_without_health_thread(self, mock_enumerate):
        """Test health status without health ping thread"""
        # Mock only other threads
        other_thread = Mock()
        other_thread.name = "other_thread"
        
        mock_enumerate.return_value = [other_thread]
        
        status = get_health_status()
        
        assert status["health_ping_active"] == False
        assert status["health_thread_id"] is None
        assert status["active_threads"] == 1
        assert status["thread_names"] == ["other_thread"]
    
    @patch('space_monkey.utils.health.threading.enumerate')
    def test_get_health_status_empty_threads(self, mock_enumerate):
        """Test health status with no threads"""
        mock_enumerate.return_value = []
        
        status = get_health_status()
        
        assert status["health_ping_active"] == False
        assert status["health_thread_id"] is None
        assert status["active_threads"] == 0
        assert status["thread_names"] == []

class TestHealthIntegration:
    """Integration tests for health module"""
    
    def test_health_status_structure(self):
        """Test that health status returns expected structure"""
        status = get_health_status()
        
        # Should have all expected keys
        assert "health_ping_active" in status
        assert "health_thread_id" in status
        assert "active_threads" in status
        assert "thread_names" in status
        
        # Should have correct types
        assert isinstance(status["health_ping_active"], bool)
        assert isinstance(status["active_threads"], int)
        assert isinstance(status["thread_names"], list)
        
        # health_thread_id can be None or int
        assert status["health_thread_id"] is None or isinstance(status["health_thread_id"], int) 