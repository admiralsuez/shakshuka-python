"""
Integration Tests for Shakshuka Task Manager API
Comprehensive API endpoint testing
"""

import unittest
import tempfile
import os
import json
import time
import threading
import requests
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import app
from src.sqlite_data_manager import SQLiteDataManager
from src.security_manager import security_manager
from src.monitoring import monitor

class TestAPIIntegration(unittest.TestCase):
    """Integration tests for API endpoints"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['DATABASE_PATH'] = self.temp_db.name
        
        # Create test client
        self.client = app.test_client()
        
        # Initialize data manager
        self.data_manager = SQLiteDataManager(self.temp_db.name)
        
        # Test user data
        self.test_user_id = "test_user_integration"
        self.test_username = "integration_test_user"
        self.test_password = "testpassword123"
        
        # Create test user
        self.data_manager.create_user(self.test_user_id, self.test_username, "hashed_password")
        
        # Mock authentication
        self.auth_token = "test_auth_token"
        self.session_secret = security_manager.generate_session_secret(self.test_user_id)
    
    def tearDown(self):
        """Clean up test environment"""
        os.unlink(self.temp_db.name)
    
    def test_health_endpoint(self):
        """Test health monitoring endpoint"""
        response = self.client.get('/api/monitoring/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertIn('health_score', data)
        self.assertIn('metrics', data)
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = self.client.get('/api/monitoring/metrics')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('uptime_seconds', data)
        self.assertIn('system', data)
        self.assertIn('performance', data)
    
    def test_rate_limit_stats_endpoint(self):
        """Test rate limit stats endpoint"""
        # Mock authentication for this test
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            response = self.client.get('/api/monitoring/rate-limit-stats')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertIn('active_ips', data)
            self.assertIn('total_requests', data)
            self.assertIn('memory_usage_mb', data)
    
    def test_task_crud_operations(self):
        """Test complete task CRUD operations via API"""
        # Mock authentication
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Test create task
            task_data = {
                'title': 'API Test Task',
                'description': 'Testing API task creation',
                'priority': 'high',
                'status': 'pending',
                'estimated_duration': 60
            }
            
            response = self.client.post('/api/tasks', 
                                     data=json.dumps(task_data),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
            created_task = json.loads(response.data)
            self.assertIn('id', created_task)
            self.assertEqual(created_task['title'], 'API Test Task')
            task_id = created_task['id']
            
            # Test get tasks
            response = self.client.get('/api/tasks')
            self.assertEqual(response.status_code, 200)
            
            tasks = json.loads(response.data)
            self.assertGreater(len(tasks), 0)
            
            # Test update task
            update_data = {
                'title': 'Updated API Test Task',
                'priority': 'medium'
            }
            
            response = self.client.put(f'/api/tasks/{task_id}',
                                     data=json.dumps(update_data),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
            # Test complete task
            response = self.client.post(f'/api/tasks/{task_id}/complete')
            self.assertEqual(response.status_code, 200)
            
            completed_task = json.loads(response.data)
            self.assertTrue(completed_task['completed'])
            
            # Test delete task
            response = self.client.delete(f'/api/tasks/{task_id}')
            self.assertEqual(response.status_code, 200)
            
            # Verify deletion
            response = self.client.get('/api/tasks')
            tasks = json.loads(response.data)
            task_ids = [task['id'] for task in tasks]
            self.assertNotIn(task_id, task_ids)
    
    def test_settings_operations(self):
        """Test settings operations via API"""
        # Mock authentication
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Test get settings
            response = self.client.get('/api/settings')
            self.assertEqual(response.status_code, 200)
            
            settings = json.loads(response.data)
            self.assertIn('theme', settings)
            self.assertIn('dpi_scale', settings)
            
            # Test update settings
            new_settings = {
                'theme': 'blue',
                'dpi_scale': 120,
                'autosave_interval': 45,
                'notifications': True
            }
            
            response = self.client.put('/api/settings',
                                     data=json.dumps(new_settings),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
            updated_settings = json.loads(response.data)
            self.assertEqual(updated_settings['theme'], 'blue')
            self.assertEqual(updated_settings['dpi_scale'], 120)
    
    def test_backup_operations(self):
        """Test backup operations via API"""
        # Mock authentication
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Create some test data first
            task_data = {
                'title': 'Backup Test Task',
                'description': 'Testing backup functionality',
                'priority': 'medium',
                'status': 'pending'
            }
            
            self.client.post('/api/tasks', 
                           data=json.dumps(task_data),
                           content_type='application/json')
            
            # Test create backup
            response = self.client.post('/api/backup/create')
            self.assertEqual(response.status_code, 200)
            
            backup_data = json.loads(response.data)
            self.assertIn('backup_path', backup_data)
            
            # Test list backups
            response = self.client.get('/api/backup/list')
            self.assertEqual(response.status_code, 200)
            
            backups = json.loads(response.data)
            self.assertGreater(len(backups), 0)
    
    def test_error_handling(self):
        """Test API error handling"""
        # Mock authentication
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Test invalid task data
            invalid_task_data = {
                'title': '',  # Empty title should fail validation
                'priority': 'invalid_priority'
            }
            
            response = self.client.post('/api/tasks',
                                     data=json.dumps(invalid_task_data),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 400)
            
            # Test non-existent task update
            response = self.client.put('/api/tasks/non_existent_id',
                                     data=json.dumps({'title': 'Updated'}),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 404)
            
            # Test non-existent task deletion
            response = self.client.delete('/api/tasks/non_existent_id')
            self.assertEqual(response.status_code, 404)
    
    def test_concurrent_requests(self):
        """Test concurrent API requests"""
        results = []
        errors = []
        
        def make_request(request_id):
            try:
                with patch('src.app.get_user_id', return_value=self.test_user_id):
                    task_data = {
                        'title': f'Concurrent Task {request_id}',
                        'description': f'Testing concurrent request {request_id}',
                        'priority': 'medium',
                        'status': 'pending'
                    }
                    
                    response = self.client.post('/api/tasks',
                                             data=json.dumps(task_data),
                                             content_type='application/json')
                    results.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Create multiple concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests succeeded
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 10)
        
        # All requests should return 200
        for status_code in results:
            self.assertEqual(status_code, 200)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Make many requests quickly to test rate limiting
        responses = []
        
        for i in range(150):  # Exceed the rate limit
            response = self.client.get('/api/monitoring/health')
            responses.append(response.status_code)
            
            if response.status_code == 429:  # Rate limited
                break
        
        # Should eventually get rate limited
        self.assertIn(429, responses)
    
    def test_monitoring_integration(self):
        """Test monitoring integration with API calls"""
        # Make some API calls
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Create a task
            task_data = {
                'title': 'Monitoring Test Task',
                'description': 'Testing monitoring integration',
                'priority': 'high',
                'status': 'pending'
            }
            
            response = self.client.post('/api/tasks',
                                     data=json.dumps(task_data),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            
            # Get tasks
            response = self.client.get('/api/tasks')
            self.assertEqual(response.status_code, 200)
            
            # Update settings
            settings_data = {'theme': 'green'}
            response = self.client.put('/api/settings',
                                     data=json.dumps(settings_data),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
        
        # Check monitoring data
        metrics = monitor.get_metrics_summary()
        self.assertGreater(metrics['performance']['total_requests'], 0)
        
        # Check health status
        health = monitor.get_health_status()
        self.assertIn('status', health)
        self.assertIn('health_score', health)

class TestPerformanceIntegration(unittest.TestCase):
    """Performance integration tests"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        app.config['TESTING'] = True
        app.config['DATABASE_PATH'] = self.temp_db.name
        
        self.client = app.test_client()
        self.data_manager = SQLiteDataManager(self.temp_db.name)
        self.test_user_id = "perf_test_user"
        
        # Create test user
        self.data_manager.create_user(self.test_user_id, "perf_user", "hashed_password")
    
    def tearDown(self):
        """Clean up performance test environment"""
        os.unlink(self.temp_db.name)
    
    def test_large_dataset_performance(self):
        """Test performance with large dataset"""
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Create many tasks
            start_time = time.time()
            
            for i in range(100):
                task_data = {
                    'title': f'Performance Test Task {i}',
                    'description': f'Testing performance with large dataset - Task {i}',
                    'priority': 'medium',
                    'status': 'pending'
                }
                
                response = self.client.post('/api/tasks',
                                         data=json.dumps(task_data),
                                         content_type='application/json')
                self.assertEqual(response.status_code, 200)
            
            creation_time = time.time() - start_time
            
            # Test loading all tasks
            start_time = time.time()
            response = self.client.get('/api/tasks')
            self.assertEqual(response.status_code, 200)
            load_time = time.time() - start_time
            
            tasks = json.loads(response.data)
            self.assertEqual(len(tasks), 100)
            
            # Performance assertions (adjust thresholds as needed)
            self.assertLess(creation_time, 10.0, "Task creation took too long")
            self.assertLess(load_time, 2.0, "Task loading took too long")
            
            print(f"Performance Test Results:")
            print(f"- Created 100 tasks in {creation_time:.2f} seconds")
            print(f"- Loaded 100 tasks in {load_time:.2f} seconds")
    
    def test_memory_usage(self):
        """Test memory usage under load"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        with patch('src.app.get_user_id', return_value=self.test_user_id):
            # Create many tasks to test memory usage
            for i in range(500):
                task_data = {
                    'title': f'Memory Test Task {i}',
                    'description': f'Testing memory usage - Task {i}',
                    'priority': 'low',
                    'status': 'pending'
                }
                
                response = self.client.post('/api/tasks',
                                         data=json.dumps(task_data),
                                         content_type='application/json')
                self.assertEqual(response.status_code, 200)
        
        final_memory = process.memory_info().rss / (1024 * 1024)  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory Usage Test:")
        print(f"- Initial memory: {initial_memory:.2f} MB")
        print(f"- Final memory: {final_memory:.2f} MB")
        print(f"- Memory increase: {memory_increase:.2f} MB")
        
        # Memory increase should be reasonable (less than 100MB for 500 tasks)
        self.assertLess(memory_increase, 100.0, "Memory usage increased too much")

if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestAPIIntegration))
    test_suite.addTest(unittest.makeSuite(TestPerformanceIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nIntegration Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
