"""
Integration tests for container creation queue with real Docker containers

These tests actually create Docker containers and should be run separately
from unit tests. They require Docker daemon to be running and will use
real system resources.

Run with: pytest tests/test_container_queue_integration.py -v -s
Mark as integration: pytest -m integration
"""

import unittest
import time
import threading
import docker
from unittest.mock import Mock, patch, MagicMock
from docker.errors import DockerException
from app.services.container_queue import ContainerQueue, ContainerCreationRequest


class TestContainerQueueIntegration(unittest.TestCase):
    """Integration test cases for ContainerQueue with real Docker"""
    
    @classmethod
    def setUpClass(cls):
        """Check if Docker is available before running tests"""
        try:
            client = docker.from_env()
            client.ping()
            cls.docker_available = True
            cls.docker_client = client
        except (DockerException, Exception) as e:
            cls.docker_available = False
            cls.skip_reason = f"Docker not available: {e}"
            print(f"\n⚠️  Skipping integration tests: {cls.skip_reason}")
    
    def setUp(self):
        """Set up test fixtures"""
        if not self.docker_available:
            self.skipTest(self.skip_reason)
        
        # Track containers created during test for cleanup
        self.test_containers = []
        
        # Create a fresh queue instance
        self.queue = ContainerQueue()
        if self.queue.is_running():
            self.queue.stop()
        time.sleep(0.1)
        
        # Reset queue stats
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
        
        # Create mock Flask app with app context
        self.mock_app = Mock()
        self.mock_app.app_context = MagicMock()
        self.mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        self.mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        self.mock_app.logger = Mock()
    
    def tearDown(self):
        """Clean up after tests"""
        # Stop queue
        if self.queue.is_running():
            self.queue.stop()
        time.sleep(0.1)
        
        # Clean up any containers created during test
        if hasattr(self, 'test_containers'):
            for container_id in self.test_containers:
                try:
                    container = self.docker_client.containers.get(container_id)
                    container.stop(timeout=2)
                    container.remove(force=True)
                    print(f"✓ Cleaned up container: {container_id[:12]}")
                except Exception as e:
                    print(f"⚠️  Failed to cleanup container {container_id[:12]}: {e}")
    
    def _create_test_container(self, username, desktop_type):
        """
        Create a real Docker container for testing (using alpine for speed)
        Returns a mock container object that simulates database container model
        """
        container_name = f"test_{username}_{desktop_type}_{int(time.time() * 1000)}"
        
        # Create a lightweight container (alpine with sleep to keep it running)
        docker_container = self.docker_client.containers.run(
            'alpine:latest',
            command='sleep 300',
            name=container_name,
            detach=True,
            remove=False,
            labels={
                'test': 'container_queue_integration',
                'username': username,
                'desktop_type': desktop_type
            }
        )
        
        # Track for cleanup
        self.test_containers.append(docker_container.id)
        
        # Create mock container model that simulates database record
        mock_container = Mock()
        mock_container.id = len(self.test_containers)  # Sequential ID
        mock_container.container_id = docker_container.id
        mock_container.container_name = container_name
        mock_container.username = username
        mock_container.desktop_type = desktop_type
        mock_container.status = 'running'
        
        print(f"✓ Created real container: {container_name} ({docker_container.id[:12]})")
        
        return mock_container
    
    @patch('app.services.docker_manager.DockerManager')
    def test_integration_single_container_real_docker(self, mock_docker_manager):
        """Integration test: Create a single real Docker container through queue"""
        
        # Mock DockerManager to create real containers
        mock_manager_instance = Mock()
        mock_manager_instance.create_container = Mock(
            side_effect=lambda **kwargs: self._create_test_container(
                kwargs['username'], 
                kwargs.get('desktop_type', 'test-desktop')
            )
        )
        mock_docker_manager.return_value = mock_manager_instance
        
        # Track callback
        result = {'container': None, 'error': None}
        
        def success_callback(container):
            result['container'] = container
        
        def error_callback(error):
            result['error'] = error
        
        # Create request
        request = ContainerCreationRequest(
            user_id=1,
            session_id=1,
            username="testuser",
            desktop_type="alpine-test",
            callback=success_callback,
            error_callback=error_callback
        )
        
        # Start queue and enqueue
        self.queue.start(self.mock_app)
        self.queue.enqueue(request)
        
        # Wait for processing (Docker takes 3-4 seconds per container)
        time.sleep(6)
        
        # Verify
        self.assertIsNotNone(result['container'], "Container should be created")
        self.assertIsNone(result['error'], "No error should occur")
        
        # Verify container is actually running
        container_id = result['container'].container_id
        docker_container = self.docker_client.containers.get(container_id)
        self.assertEqual(docker_container.status, 'running')
        
        print(f"\n✓ Integration test passed: Container {docker_container.id[:12]} is running")
    
    @patch('app.services.docker_manager.DockerManager')
    def test_integration_multiple_containers_stress(self, mock_docker_manager):
        """Integration test: Create multiple real Docker containers simultaneously"""
        num_users = 3
        containers_per_user = 2
        total_containers = num_users * containers_per_user
        
        print(f"\n{'='*60}")
        print(f"Starting Docker stress test: {num_users} users × {containers_per_user} containers = {total_containers} total")
        print(f"{'='*60}\n")
        
        # Mock DockerManager to create real containers
        mock_manager_instance = Mock()
        mock_manager_instance.create_container = Mock(
            side_effect=lambda **kwargs: self._create_test_container(
                kwargs['username'], 
                kwargs.get('desktop_type', 'test-desktop')
            )
        )
        mock_docker_manager.return_value = mock_manager_instance
        
        # Track results
        results = {
            'success': [],
            'errors': [],
            'lock': threading.Lock()
        }
        
        def success_callback(container):
            with results['lock']:
                results['success'].append(container)
                print(f"  ✓ Container {len(results['success'])}/{total_containers}: {container.container_name}")
        
        def error_callback(error):
            with results['lock']:
                results['errors'].append(str(error))
                print(f"  ✗ Error: {error}")
        
        # Start queue
        self.queue.start(self.mock_app)
        
        # Create requests for multiple users
        desktop_types = ['alpine-desktop', 'test-desktop']
        
        def enqueue_user_containers(user_num):
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
                time.sleep(0.02)
        
        # Launch threads
        threads = []
        start_time = time.time()
        
        for user_num in range(num_users):
            thread = threading.Thread(
                target=enqueue_user_containers,
                args=(user_num,),
                name=f"UserThread-{user_num}"
            )
            threads.append(thread)
            thread.start()
        
        # Wait for enqueue
        for thread in threads:
            thread.join(timeout=10)
        
        enqueue_time = time.time() - start_time
        print(f"\nAll {total_containers} requests enqueued in {enqueue_time:.2f}s")
        print(f"Waiting for Docker containers to be created...\n")
        
        # Wait for processing (Docker container creation is slower than mocks)
        # On this system, each container takes ~3-4 seconds
        max_wait_time = total_containers * 6 + 20  # 6s per container + buffer
        processing_start = time.time()
        
        while time.time() - processing_start < max_wait_time:
            stats = self.queue.get_stats()
            completed = stats['successful'] + stats['failed']
            
            if completed >= total_containers:
                break
            
            time.sleep(0.5)
        
        processing_time = time.time() - processing_start
        
        # Get final stats
        final_stats = self.queue.get_stats()
        
        print(f"\n{'='*60}")
        print(f"DOCKER STRESS TEST RESULTS")
        print(f"{'='*60}")
        print(f"Processing time: {processing_time:.2f}s")
        print(f"Total requests: {final_stats['total_requests']}")
        print(f"Successful: {final_stats['successful']}")
        print(f"Failed: {final_stats['failed']}")
        print(f"In progress: {final_stats['in_progress']}")
        print(f"Queue size: {final_stats['queue_size']}")
        print(f"Callback successes: {len(results['success'])}")
        print(f"Callback errors: {len(results['errors'])}")
        print(f"Average time per container: {processing_time/total_containers:.2f}s")
        print(f"{'='*60}\n")
        
        # Assertions
        self.assertEqual(final_stats['total_requests'], total_containers,
                        "All requests should be counted")
        self.assertEqual(final_stats['successful'], total_containers,
                        "All requests should succeed")
        self.assertEqual(final_stats['failed'], 0,
                        "No requests should fail")
        self.assertEqual(len(results['success']), total_containers,
                        "All success callbacks should be called")
        self.assertEqual(len(results['errors']), 0,
                        "No error callbacks should be called")
        
        # Verify all containers are actually running
        print("Verifying all containers are running...")
        for i, container in enumerate(results['success'], 1):
            docker_container = self.docker_client.containers.get(container.container_id)
            self.assertEqual(docker_container.status, 'running',
                           f"Container {container.container_name} should be running")
            print(f"  ✓ {i}/{total_containers}: {docker_container.name[:30]} is running")
        
        # Verify no duplicate container IDs
        container_ids = [c.container_id for c in results['success']]
        unique_ids = set(container_ids)
        self.assertEqual(len(container_ids), len(unique_ids),
                        "All container IDs should be unique")
        
        print(f"\n{'='*60}")
        print(f"✓ DOCKER STRESS TEST PASSED")
        print(f"✓ {total_containers} real Docker containers created sequentially")
        print(f"✓ All containers verified running")
        print(f"✓ No race conditions detected")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
