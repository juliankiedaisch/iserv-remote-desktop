"""
Unit tests for container creation queue system
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from app.services.container_queue import ContainerQueue, ContainerCreationRequest, get_container_queue


class TestContainerQueue(unittest.TestCase):
    """Test cases for ContainerQueue class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a fresh queue instance for each test
        self.queue = ContainerQueue()
        if self.queue.is_running():
            self.queue.stop()
        time.sleep(0.1)  # Give time for worker to stop
    
    def tearDown(self):
        """Clean up after tests"""
        if self.queue.is_running():
            self.queue.stop()
        time.sleep(0.1)
    
    def test_queue_initialization(self):
        """Test that queue initializes correctly"""
        self.assertIsNotNone(self.queue)
        self.assertFalse(self.queue.is_running())
        self.assertEqual(self.queue.get_queue_size(), 0)
    
    def test_queue_start_stop(self):
        """Test starting and stopping the queue"""
        self.queue.start()
        self.assertTrue(self.queue.is_running())
        
        self.queue.stop()
        time.sleep(0.2)  # Give time for worker to stop
        self.assertFalse(self.queue.is_running())
    
    def test_enqueue_request(self):
        """Test enqueueing a container creation request"""
        request = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="testuser",
            desktop_type="ubuntu-desktop"
        )
        
        request_id = self.queue.enqueue(request)
        self.assertIsNotNone(request_id)
        self.assertEqual(self.queue.get_queue_size(), 1)
    
    def test_queue_stats(self):
        """Test getting queue statistics"""
        self.queue.start()
        
        stats = self.queue.get_stats()
        self.assertIsNotNone(stats)
        self.assertIn('total_requests', stats)
        self.assertIn('successful', stats)
        self.assertIn('failed', stats)
        self.assertIn('queue_size', stats)
        self.assertEqual(stats['total_requests'], 0)
    
    @patch('app.services.container_queue.DockerManager')
    def test_process_request_success(self, mock_docker_manager):
        """Test successful processing of a request"""
        # Mock container creation
        mock_container = Mock()
        mock_container.id = 123
        mock_manager_instance = Mock()
        mock_manager_instance.create_container.return_value = mock_container
        mock_docker_manager.return_value = mock_manager_instance
        
        # Create request with callback
        success_callback = Mock()
        request = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="testuser",
            desktop_type="ubuntu-desktop",
            callback=success_callback
        )
        
        # Start queue and enqueue request
        self.queue.start()
        self.queue.enqueue(request)
        
        # Wait for processing
        time.sleep(1)
        
        # Verify callback was called
        success_callback.assert_called_once()
        
        # Verify stats
        stats = self.queue.get_stats()
        self.assertEqual(stats['total_requests'], 1)
        self.assertEqual(stats['successful'], 1)
        self.assertEqual(stats['failed'], 0)
    
    @patch('app.services.container_queue.DockerManager')
    def test_process_request_failure(self, mock_docker_manager):
        """Test handling of failed request"""
        # Mock container creation failure
        mock_manager_instance = Mock()
        mock_manager_instance.create_container.side_effect = Exception("Docker error")
        mock_docker_manager.return_value = mock_manager_instance
        
        # Create request with error callback
        error_callback = Mock()
        request = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="testuser",
            desktop_type="ubuntu-desktop",
            error_callback=error_callback
        )
        
        # Start queue and enqueue request
        self.queue.start()
        self.queue.enqueue(request)
        
        # Wait for processing
        time.sleep(1)
        
        # Verify error callback was called
        error_callback.assert_called_once()
        
        # Verify stats
        stats = self.queue.get_stats()
        self.assertEqual(stats['total_requests'], 1)
        self.assertEqual(stats['successful'], 0)
        self.assertEqual(stats['failed'], 1)
    
    def test_multiple_requests(self):
        """Test processing multiple requests in sequence"""
        # Create multiple requests
        requests = []
        for i in range(3):
            request = ContainerCreationRequest(
                user_id=i,
                session_id=i,
                username=f"user{i}",
                desktop_type="ubuntu-desktop"
            )
            requests.append(request)
        
        # Enqueue all requests
        for request in requests:
            self.queue.enqueue(request)
        
        # Verify queue size
        self.assertEqual(self.queue.get_queue_size(), 3)
    
    def test_singleton_pattern(self):
        """Test that get_container_queue returns singleton instance"""
        queue1 = get_container_queue()
        queue2 = get_container_queue()
        self.assertIs(queue1, queue2)
    
    def test_request_id_generation(self):
        """Test that request IDs are unique"""
        request1 = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="user1",
            desktop_type="ubuntu-desktop"
        )
        
        time.sleep(0.01)  # Ensure different timestamps
        
        request2 = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="user1",
            desktop_type="ubuntu-desktop"
        )
        
        self.assertNotEqual(request1.request_id, request2.request_id)


if __name__ == '__main__':
    unittest.main()