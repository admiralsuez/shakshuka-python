"""
Performance Monitoring Service
Tracks optimization metrics and logs performance data for analysis
"""

import time
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.metrics = {}
        self.operation_times = {}
    
    def log_operation(self, operation_name: str, duration_ms: float, metadata: Optional[Dict[str, Any]] = None):
        """Log an operation with its duration"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation_name,
            'duration_ms': round(duration_ms, 2),
            'metadata': metadata or {}
        }
        
        # Track in memory
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = []
        self.operation_times[operation_name].append(duration_ms)
        
        # Log to file
        logger.info(f"PERF: {operation_name} took {duration_ms:.2f}ms | {json.dumps(log_entry)}")
    
    def log_database_operation(self, operation: str, query_count: int, duration_ms: float, user_id: str = None, task_count: int = None):
        """Log database operation with query count"""
        metadata = {
            'query_count': query_count,
            'user_id': user_id,
            'task_count': task_count
        }
        self.log_operation(f"db_{operation}", duration_ms, metadata)
    
    def log_api_request(self, endpoint: str, method: str, duration_ms: float, status_code: int, user_id: str = None):
        """Log API request"""
        metadata = {
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'user_id': user_id
        }
        self.log_operation(f"api_{endpoint}", duration_ms, metadata)
    
    def log_polling_event(self, poller_name: str, interval_ms: int, found_pending: bool, duration_ms: float):
        """Log polling event"""
        metadata = {
            'poller': poller_name,
            'interval_ms': interval_ms,
            'found_pending': found_pending
        }
        self.log_operation(f"poll_{poller_name}", duration_ms, metadata)
    
    def get_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get statistics for an operation"""
        if operation_name not in self.operation_times:
            return {}
        
        times = self.operation_times[operation_name]
        return {
            'operation': operation_name,
            'count': len(times),
            'min_ms': round(min(times), 2),
            'max_ms': round(max(times), 2),
            'avg_ms': round(sum(times) / len(times), 2),
            'total_ms': round(sum(times), 2)
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all operations"""
        return {op: self.get_stats(op) for op in self.operation_times.keys()}


# Global monitor instance
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor"""
    return _monitor


def monitor_operation(operation_name: str):
    """Decorator to monitor operation duration"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                _monitor.log_operation(operation_name, duration_ms)
        return wrapper
    return decorator


@contextmanager
def monitor_block(operation_name: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager to monitor a block of code"""
    start_time = time.time()
    try:
        yield _monitor
    finally:
        duration_ms = (time.time() - start_time) * 1000
        _monitor.log_operation(operation_name, duration_ms, metadata)


class DatabaseQueryMonitor:
    """Monitor database queries"""
    
    def __init__(self):
        self.query_count = 0
        self.start_time = None
    
    def __enter__(self):
        self.query_count = 0
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        return False
    
    def record_query(self):
        """Record a database query"""
        self.query_count += 1
    
    def log_operation(self, operation_name: str, user_id: str = None, task_count: int = None):
        """Log the database operation"""
        duration_ms = (time.time() - self.start_time) * 1000
        _monitor.log_database_operation(
            operation_name,
            self.query_count,
            duration_ms,
            user_id,
            task_count
        )


# Optimization-specific monitoring

def log_task_operation(operation: str, user_id: str, task_id: str, duration_ms: float, query_count: int = 1):
    """Log task operation (complete, strike, undo-strike)"""
    metadata = {
        'operation': operation,
        'user_id': user_id,
        'task_id': task_id,
        'query_count': query_count,
        'optimization': 'direct_update'
    }
    _monitor.log_operation(f"task_{operation}", duration_ms, metadata)
    logger.info(f"TASK_OP: {operation} completed in {duration_ms:.2f}ms with {query_count} queries")


def log_save_operation(user_id: str, task_count: int, duration_ms: float, method: str = 'upsert'):
    """Log task save operation"""
    metadata = {
        'user_id': user_id,
        'task_count': task_count,
        'method': method,
        'optimization': 'upsert_pattern'
    }
    _monitor.log_operation(f"save_tasks_{method}", duration_ms, metadata)
    logger.info(f"SAVE: {task_count} tasks saved in {duration_ms:.2f}ms using {method}")


def log_polling_interval_change(poller_name: str, old_interval: int, new_interval: int, reason: str):
    """Log polling interval changes"""
    metadata = {
        'poller': poller_name,
        'old_interval_ms': old_interval,
        'new_interval_ms': new_interval,
        'reason': reason,
        'optimization': 'exponential_backoff'
    }
    _monitor.log_operation(f"poll_interval_change_{poller_name}", 0, metadata)
    logger.info(f"POLL: {poller_name} interval changed {old_interval}ms → {new_interval}ms ({reason})")


def log_scheduler_job(job_name: str, duration_ms: float, success: bool, error: str = None):
    """Log scheduler job execution"""
    metadata = {
        'job_name': job_name,
        'success': success,
        'error': error,
        'optimization': 'scheduler_service'
    }
    _monitor.log_operation(f"scheduler_{job_name}", duration_ms, metadata)
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"SCHEDULER: {job_name} {status} in {duration_ms:.2f}ms" + (f" - {error}" if error else ""))
