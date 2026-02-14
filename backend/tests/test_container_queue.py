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
        
        # Reset queue stats for isolation between tests
        self.queue._stats = {
            'total_requests': 0,
            'successful': 0,
            'failed': 0,
            'in_progress': 0
        }
        
        # Clear the queue
        while not self.queue._queue.empty():
            try:
                self.queue._queue.get_nowait()
            except:
                break
        
        # Create mock Flask app
        self.mock_app = Mock()
        self.mock_app.app_context = MagicMock()
        self.mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        self.mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
    
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
        self.queue.start(self.mock_app)
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
        self.queue.start(self.mock_app)
        
        stats = self.queue.get_stats()
        self.assertIsNotNone(stats)
        self.assertIn('total_requests', stats)
        self.assertIn('successful', stats)
        self.assertIn('failed', stats)
        self.assertIn('queue_size', stats)
        self.assertIn('worker_alive', stats)
        self.assertIn('running', stats)
        self.assertEqual(stats['total_requests'], 0)
    
    @patch('app.services.docker_manager.DockerManager')
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
        self.queue.start(self.mock_app)
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
    
    @patch('app.services.docker_manager.DockerManager')
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
        self.queue.start(self.mock_app)
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
    
    def test_desktop_image_id_support(self):
        """Test that desktop_image_id is supported in requests"""
        request = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="testuser",
            desktop_image_id=42
        )
        
        self.assertEqual(request.desktop_image_id, 42)
        self.assertIsNone(request.desktop_type)
        self.queue.enqueue(request)
        self.assertEqual(self.queue.get_queue_size(), 1)
    
    @patch('app.services.docker_manager.DockerManager')
    def test_stress_multiple_users_simultaneous(self, mock_docker_manager):
        """Stress test: Multiple users creating multiple containers simultaneously"""
        num_users = 30
        containers_per_user = 3
        total_containers = num_users * containers_per_user
        
        # Mock container creation with slight delay to simulate real Docker API
        def create_container_mock(*args, **kwargs):
            time.sleep(0.05)  # Simulate Docker API delay
            mock_container = Mock()
            mock_container.id = f"container_{kwargs.get('username', 'unknown')}_{time.time()}"
            return mock_container
        
        mock_manager_instance = Mock()
        mock_manager_instance.create_container = Mock(side_effect=create_container_mock)
        mock_docker_manager.return_value = mock_manager_instance
        
        # Track results across threads
        results = {
            'success': [],
            'errors': [],
            'lock': threading.Lock()
        }
        
        def success_callback(container):
            with results['lock']:
                results['success'].append(container.id)
        
        def error_callback(error):
            with results['lock']:
                results['errors'].append(str(error))
        
        # Start the queue
        self.queue.start(self.mock_app)
        
        # Create requests for multiple users simultaneously
        threads = []
        desktop_types = ['ubuntu-desktop', 'debian-desktop', 'fedora-desktop']
        
        def enqueue_user_containers(user_num):
            """Simulate a user creating multiple containers"""
            for container_num in range(containers_per_user):
                request = ContainerCreationRequest(
                    user_id=user_num,
                    session_id=user_num * 100 + container_num,
                    username=f"user{user_num}",
                    desktop_type=desktop_types[container_num % len(desktop_types)],
                    callback=success_callback,
                    error_callback=error_callback
                )
                self.queue.enqueue(request)
                # Small random delay to simulate realistic timing
                time.sleep(0.01)
        
        # Launch threads for all users simultaneously
        start_time = time.time()
        for user_num in range(num_users):
            thread = threading.Thread(
                target=enqueue_user_containers,
                args=(user_num,),
                name=f"UserThread-{user_num}"
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all enqueue threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        enqueue_time = time.time() - start_time
        print(f"\nAll {total_containers} requests enqueued in {enqueue_time:.2f}s")
        
        # Verify queue size
        initial_queue_size = self.queue.get_queue_size()
        self.assertGreater(initial_queue_size, 0)
        print(f"Queue size after enqueue: {initial_queue_size}")
        
        # Wait for all requests to be processed
        # Each container takes ~0.05s, so total time should be ~0.05 * total_containers
        max_wait_time = total_containers * 0.1 + 5  # Add buffer
        processing_start = time.time()
        
        while time.time() - processing_start < max_wait_time:
            stats = self.queue.get_stats()
            completed = stats['successful'] + stats['failed']
            
            if completed >= total_containers:
                break
            
            time.sleep(0.2)
        
        processing_time = time.time() - processing_start
        
        # Get final stats
        final_stats = self.queue.get_stats()
        print(f"\nProcessing completed in {processing_time:.2f}s")
        print(f"Total requests: {final_stats['total_requests']}")
        print(f"Successful: {final_stats['successful']}")
        print(f"Failed: {final_stats['failed']}")
        print(f"In progress: {final_stats['in_progress']}")
        print(f"Queue size: {final_stats['queue_size']}")
        print(f"Callback successes: {len(results['success'])}")
        print(f"Callback errors: {len(results['errors'])}")
        
        # Assertions
        self.assertEqual(final_stats['total_requests'], total_containers,
                        "All requests should be counted")
        self.assertEqual(final_stats['successful'], total_containers,
                        "All requests should succeed")
        self.assertEqual(final_stats['failed'], 0,
                        "No requests should fail")
        self.assertEqual(final_stats['in_progress'], 0,
                        "No requests should be in progress after completion")
        self.assertEqual(final_stats['queue_size'], 0,
                        "Queue should be empty after processing")
        self.assertEqual(len(results['success']), total_containers,
                        "All success callbacks should be called")
        self.assertEqual(len(results['errors']), 0,
                        "No error callbacks should be called")
        
        # Verify serialization: processing time should be roughly sequential
        # With 30 containers * 0.05s = 1.5s minimum, not parallel
        min_sequential_time = total_containers * 0.05 * 0.8  # 80% threshold
        self.assertGreater(processing_time, min_sequential_time,
                          f"Processing should be sequential, not parallel. "
                          f"Expected > {min_sequential_time:.2f}s, got {processing_time:.2f}s")
        
        # Verify DockerManager was called correct number of times
        self.assertEqual(mock_manager_instance.create_container.call_count,
                        total_containers,
                        "DockerManager.create_container should be called once per request")
        
        # Verify no duplicate container IDs (race condition check)
        container_ids = results['success']
        unique_ids = set(container_ids)
        self.assertEqual(len(container_ids), len(unique_ids),
                        "All container IDs should be unique (no race conditions)")
        
        print(f"\n✓ Stress test passed: {total_containers} containers created sequentially")
        print(f"✓ Average time per container: {processing_time/total_containers:.3f}s")
        print(f"✓ No race conditions detected")


if __name__ == '__main__':
    unittest.main()