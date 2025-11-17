"""
Unit Tests for Shakshuka Task Manager
Comprehensive test suite for all application components
"""

import unittest
import tempfile
import os
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sqlite_data_manager import SQLiteDataManager
from src.security_manager import SecurityManager
from src.monitoring import PerformanceMonitor
from src.user_manager import UserManager

class TestSQLiteDataManager(unittest.TestCase):
    """Test cases for SQLiteDataManager"""
    
    def setUp(self):
        """Set up test database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.data_manager = SQLiteDataManager(self.temp_db.name)
        self.test_user_id = "test_user_123"
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.temp_db.name)
    
    def test_database_initialization(self):
        """Test database initialization"""
        self.assertTrue(os.path.exists(self.temp_db.name))
        self.assertIsNotNone(self.data_manager)
    
    def test_user_creation(self):
        """Test user creation"""
        success = self.data_manager.create_user(self.test_user_id, "test_user", "hashed_password")
        self.assertTrue(success)
    
    def test_task_operations(self):
        """Test task CRUD operations"""
        # Create user first
        self.data_manager.create_user(self.test_user_id, "test_user", "hashed_password")
        
        # Test create task
        task_data = {
            'id': 'task_123',
            'title': 'Test Task',
            'description': 'Test Description',
            'priority': 'high',
            'status': 'pending'
        }
        
        created_task = self.data_manager.create_task_for_user(self.test_user_id, task_data)
        self.assertIsNotNone(created_task)
        self.assertEqual(created_task['title'], 'Test Task')
        
        # Test load tasks
        tasks = self.data_manager.load_tasks_for_user(self.test_user_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['title'], 'Test Task')
        
        # Test update task
        updated_data = {'title': 'Updated Task'}
        success = self.data_manager.update_task_for_user(self.test_user_id, 'task_123', updated_data)
        self.assertTrue(success)
        
        # Verify update
        tasks = self.data_manager.load_tasks_for_user(self.test_user_id)
        self.assertEqual(tasks[0]['title'], 'Updated Task')
        
        # Test delete task
        success = self.data_manager.delete_task_for_user(self.test_user_id, 'task_123')
        self.assertTrue(success)
        
        # Verify deletion
        tasks = self.data_manager.load_tasks_for_user(self.test_user_id)
        self.assertEqual(len(tasks), 0)
    
    def test_settings_operations(self):
        """Test settings operations"""
        # Create user first
        self.data_manager.create_user(self.test_user_id, "test_user", "hashed_password")
        
        # Test load default settings
        settings = self.data_manager.load_settings_for_user(self.test_user_id)
        self.assertIsInstance(settings, dict)
        self.assertIn('theme', settings)
        
        # Test save settings
        new_settings = {
            'theme': 'blue',
            'dpi_scale': 120,
            'autosave_interval': 60
        }
        success = self.data_manager.save_settings_for_user(self.test_user_id, new_settings)
        self.assertTrue(success)
        
        # Test load updated settings
        loaded_settings = self.data_manager.load_settings_for_user(self.test_user_id)
        self.assertEqual(loaded_settings['theme'], 'blue')
        self.assertEqual(loaded_settings['dpi_scale'], 120)
    
    def test_concurrent_operations(self):
        """Test concurrent operations"""
        # Create user first
        self.data_manager.create_user(self.test_user_id, "test_user", "hashed_password")
        
        results = []
        errors = []
        
        def create_task(task_id):
            try:
                task_data = {
                    'id': f'task_{task_id}',
                    'title': f'Task {task_id}',
                    'priority': 'medium',
                    'status': 'pending'
                }
                result = self.data_manager.create_task_for_user(self.test_user_id, task_data)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple tasks concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_task, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all tasks were created successfully
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 10)
        
        # Verify tasks exist in database
        tasks = self.data_manager.load_tasks_for_user(self.test_user_id)
        self.assertEqual(len(tasks), 10)

class TestSecurityManager(unittest.TestCase):
    """Test cases for SecurityManager"""
    
    def setUp(self):
        """Set up security manager"""
        self.security_manager = SecurityManager()
    
    def test_input_sanitization(self):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = "<script>alert('xss')</script>Hello"
        sanitized = self.security_manager.sanitize_input(malicious_input)
        self.assertNotIn('<script>', sanitized)
        self.assertIn('Hello', sanitized)
        
        # Test length limiting
        long_input = "A" * 2000
        sanitized = self.security_manager.sanitize_input(long_input, max_length=100)
        self.assertEqual(len(sanitized), 100)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        test_ip = "192.168.1.1"
        
        # Test normal requests
        for i in range(10):
            result = self.security_manager.check_rate_limit(test_ip)
            self.assertTrue(result)
        
        # Test rate limit exceeded (if configured low)
        # Note: This test might not trigger if max_requests_per_window is high
        # In a real scenario, you'd configure lower limits for testing
    
    def test_session_secret_generation(self):
        """Test session secret generation"""
        user_id = "test_user"
        secret = self.security_manager.generate_session_secret(user_id)
        
        self.assertIsNotNone(secret)
        self.assertIsInstance(secret, str)
        self.assertEqual(len(secret), 43)  # Base64 encoded 32 bytes
        
        # Test validation
        is_valid = self.security_manager.validate_session_secret(user_id, secret)
        self.assertTrue(is_valid)
        
        # Test invalid secret
        is_valid = self.security_manager.validate_session_secret(user_id, "invalid_secret")
        self.assertFalse(is_valid)

class TestPerformanceMonitor(unittest.TestCase):
    """Test cases for PerformanceMonitor"""
    
    def setUp(self):
        """Set up performance monitor"""
        self.monitor = PerformanceMonitor()
    
    def test_request_recording(self):
        """Test request recording"""
        endpoint = "test_endpoint"
        method = "GET"
        response_time = 0.5
        status_code = 200
        
        self.monitor.record_request(endpoint, method, response_time, status_code)
        
        metrics = self.monitor.get_metrics_summary()
        self.assertEqual(metrics['performance']['total_requests'], 1)
    
    def test_error_recording(self):
        """Test error recording"""
        error_type = "test_error"
        error_message = "Test error message"
        context = {"test": "context"}
        
        self.monitor.record_error(error_type, error_message, context)
        
        metrics = self.monitor.get_metrics_summary()
        self.assertEqual(metrics['performance']['total_errors'], 1)
    
    def test_health_status(self):
        """Test health status calculation"""
        health_status = self.monitor.get_health_status()
        
        self.assertIn('status', health_status)
        self.assertIn('health_score', health_status)
        self.assertIn('issues', health_status)
        self.assertIn('timestamp', health_status)
        
        # Health score should be between 0 and 100
        self.assertGreaterEqual(health_status['health_score'], 0)
        self.assertLessEqual(health_status['health_score'], 100)
    
    def test_metrics_export(self):
        """Test metrics export"""
        # Record some test data
        self.monitor.record_request("test_endpoint", "GET", 0.5, 200)
        self.monitor.record_error("test_error", "Test error")
        
        # Export metrics
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_path = temp_file.name
        
        try:
            success = self.monitor.export_metrics(temp_path)
            self.assertTrue(success)
            
            # Verify file was created and contains data
            self.assertTrue(os.path.exists(temp_path))
            
            with open(temp_path, 'r') as f:
                exported_data = json.load(f)
            
            self.assertIn('metrics_summary', exported_data)
            self.assertIn('health_status', exported_data)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

class TestUserManager(unittest.TestCase):
    """Test cases for UserManager"""
    
    def setUp(self):
        """Set up user manager"""
        self.user_manager = UserManager()
    
    def test_user_creation(self):
        """Test user creation"""
        user_id = "test_user_123"
        username = "testuser"
        password = "testpassword123"
        
        success = self.user_manager.create_user(user_id, username, password)
        self.assertTrue(success)
        
        # Verify user exists
        user = self.user_manager.get_user(user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user['username'], username)
    
    def test_password_verification(self):
        """Test password verification"""
        user_id = "test_user_456"
        username = "testuser2"
        password = "testpassword456"
        
        # Create user
        self.user_manager.create_user(user_id, username, password)
        
        # Test correct password
        is_valid = self.user_manager.verify_password(user_id, password)
        self.assertTrue(is_valid)
        
        # Test incorrect password
        is_valid = self.user_manager.verify_password(user_id, "wrongpassword")
        self.assertFalse(is_valid)
    
    def test_user_authentication(self):
        """Test user authentication"""
        user_id = "test_user_789"
        username = "testuser3"
        password = "testpassword789"
        
        # Create user
        self.user_manager.create_user(user_id, username, password)
        
        # Test authentication
        auth_user = self.user_manager.authenticate_user(username, password)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user['id'], user_id)
        
        # Test failed authentication
        auth_user = self.user_manager.authenticate_user(username, "wrongpassword")
        self.assertIsNone(auth_user)

class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.data_manager = SQLiteDataManager(self.temp_db.name)
        self.user_manager = UserManager()
        self.security_manager = SecurityManager()
        self.monitor = PerformanceMonitor()
        self.test_user_id = "integration_test_user"
    
    def tearDown(self):
        """Clean up integration test environment"""
        os.unlink(self.temp_db.name)
    
    def test_complete_user_workflow(self):
        """Test complete user workflow"""
        # Create user
        success = self.user_manager.create_user(self.test_user_id, "integration_user", "password123")
        self.assertTrue(success)
        
        # Create user in data manager
        success = self.data_manager.create_user(self.test_user_id, "integration_user", "hashed_password")
        self.assertTrue(success)
        
        # Create tasks
        task_data = {
            'id': 'integration_task_1',
            'title': 'Integration Test Task',
            'description': 'Testing complete workflow',
            'priority': 'high',
            'status': 'pending'
        }
        
        created_task = self.data_manager.create_task_for_user(self.test_user_id, task_data)
        self.assertIsNotNone(created_task)
        
        # Update settings
        settings = {
            'theme': 'green',
            'dpi_scale': 110,
            'autosave_interval': 45
        }
        
        success = self.data_manager.save_settings_for_user(self.test_user_id, settings)
        self.assertTrue(success)
        
        # Verify complete workflow
        tasks = self.data_manager.load_tasks_for_user(self.test_user_id)
        self.assertEqual(len(tasks), 1)
        
        loaded_settings = self.data_manager.load_settings_for_user(self.test_user_id)
        self.assertEqual(loaded_settings['theme'], 'green')
        
        # Record monitoring data
        self.monitor.record_request("integration_test", "POST", 0.3, 200)
        self.monitor.record_database_operation("create_task", 0.1, True)
        
        # Verify monitoring
        metrics = self.monitor.get_metrics_summary()
        self.assertGreater(metrics['performance']['total_requests'], 0)

if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestSQLiteDataManager))
    test_suite.addTest(unittest.makeSuite(TestSecurityManager))
    test_suite.addTest(unittest.makeSuite(TestPerformanceMonitor))
    test_suite.addTest(unittest.makeSuite(TestUserManager))
    test_suite.addTest(unittest.makeSuite(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nTest Summary:")
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
