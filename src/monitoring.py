"""
Comprehensive Monitoring System for Shakshuka Task Manager
Handles performance monitoring, health checks, and system metrics
"""

import time
import threading
import psutil
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Comprehensive performance monitoring system"""
    
    def __init__(self, auto_start: bool = False):
        self.start_time = time.time()
        self.metrics = defaultdict(lambda: deque(maxlen=1000))  # Keep last 1000 entries
        self.counters = defaultdict(int)
        self.timers = {}
        self.alerts = []
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # System metrics
        self.cpu_threshold = 80.0  # CPU usage threshold
        self.memory_threshold = 80.0  # Memory usage threshold
        self.disk_threshold = 90.0  # Disk usage threshold
        
        # Performance thresholds
        self.response_time_threshold = 2.0  # 2 seconds
        self.error_rate_threshold = 5.0  # 5% error rate
        
        if auto_start:
            self.start()
    
    def start(self) -> None:
        with self._lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = self._start_system_monitoring()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            t = self._monitor_thread
        if t and t.is_alive():
            t.join(timeout=2)

    def _start_system_monitoring(self) -> threading.Thread:
        """Start background system monitoring"""
        def monitor_system():
            while not self._stop_event.is_set():
                try:
                    self._collect_system_metrics()
                    time.sleep(30)  # Collect metrics every 30 seconds
                except Exception as e:
                    logger.error(f"Error in system monitoring: {e}")
                    time.sleep(60)  # Wait longer on error
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
        logger.info("System monitoring started")
        return monitor_thread
    
    def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            with self._lock:
                now = time.time()
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics['cpu_usage'].append((now, cpu_percent))
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.metrics['memory_usage'].append((now, memory.percent))
                self.metrics['memory_available'].append((now, memory.available / (1024**3)))  # GB
                
                # Disk usage
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                self.metrics['disk_usage'].append((now, disk_percent))
                
                # Process-specific metrics
                process = psutil.Process()
                self.metrics['process_cpu'].append((now, process.cpu_percent()))
                self.metrics['process_memory'].append((now, process.memory_info().rss / (1024**2)))  # MB
                
                # Check thresholds and create alerts
                self._check_thresholds(cpu_percent, memory.percent, disk_percent)
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _check_thresholds(self, cpu_percent: float, memory_percent: float, disk_percent: float):
        """Check system thresholds and create alerts"""
        now = datetime.now()
        
        if cpu_percent > self.cpu_threshold:
            self._create_alert('high_cpu', f"High CPU usage: {cpu_percent:.1f}%", 'warning')
        
        if memory_percent > self.memory_threshold:
            self._create_alert('high_memory', f"High memory usage: {memory_percent:.1f}%", 'warning')
        
        if disk_percent > self.disk_threshold:
            self._create_alert('high_disk', f"High disk usage: {disk_percent:.1f}%", 'critical')
    
    def _create_alert(self, alert_type: str, message: str, severity: str):
        """Create a new alert"""
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'resolved': False
        }
        
        with self._lock:
            self.alerts.append(alert)
            # Keep only last 100 alerts
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]
        
        logger.warning(f"Alert created: {message}")
    
    def record_request(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Record API request metrics"""
        with self._lock:
            now = time.time()
            
            # Record response time
            self.metrics['response_times'].append((now, response_time))
            
            # Record endpoint metrics
            endpoint_key = f"{method}_{endpoint}"
            self.metrics[f'endpoint_{endpoint_key}'].append((now, response_time))
            
            # Record status codes
            self.counters[f'status_{status_code}'] += 1
            self.counters['total_requests'] += 1
            
            # Check response time threshold
            if response_time > self.response_time_threshold:
                self._create_alert('slow_response', 
                                 f"Slow response time: {response_time:.2f}s for {endpoint}", 'warning')
    
    def record_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Record application errors"""
        with self._lock:
            now = time.time()
            
            # Record error metrics
            self.counters[f'error_{error_type}'] += 1
            self.counters['total_errors'] += 1
            
            # Store error details
            error_data = {
                'type': error_type,
                'message': error_message,
                'context': context or {},
                'timestamp': now
            }
            self.metrics['errors'].append((now, error_data))
            
            # Check error rate
            total_requests = self.counters['total_requests']
            total_errors = self.counters['total_errors']
            if total_requests > 0:
                error_rate = (total_errors / total_requests) * 100
                if error_rate > self.error_rate_threshold:
                    self._create_alert('high_error_rate', 
                                     f"High error rate: {error_rate:.1f}%", 'critical')
    
    def record_database_operation(self, operation: str, duration: float, success: bool):
        """Record database operation metrics"""
        with self._lock:
            now = time.time()
            
            # Record operation metrics
            self.metrics[f'db_{operation}'].append((now, duration))
            self.counters[f'db_{operation}_count'] += 1
            
            if success:
                self.counters[f'db_{operation}_success'] += 1
            else:
                self.counters[f'db_{operation}_error'] += 1
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        with self._lock:
            now = time.time()
            uptime = now - self.start_time
            
            # Calculate averages for recent metrics (last 5 minutes)
            recent_threshold = now - 300
            
            def get_recent_average(metric_name: str) -> float:
                if metric_name not in self.metrics:
                    return 0.0
                recent_values = [value for timestamp, value in self.metrics[metric_name] 
                               if timestamp > recent_threshold]
                return sum(recent_values) / len(recent_values) if recent_values else 0.0
            
            # System metrics
            cpu_avg = get_recent_average('cpu_usage')
            memory_avg = get_recent_average('memory_usage')
            disk_avg = get_recent_average('disk_usage')
            
            # Response time metrics
            response_times = [value for timestamp, value in self.metrics['response_times'] 
                            if timestamp > recent_threshold]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
            
            # Error metrics
            total_requests = self.counters['total_requests']
            total_errors = self.counters['total_errors']
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
            
            # Active alerts
            active_alerts = [alert for alert in self.alerts if not alert.get('resolved', False)]
            
            return {
                'uptime_seconds': uptime,
                'uptime_hours': uptime / 3600,
                'system': {
                    'cpu_usage_percent': cpu_avg,
                    'memory_usage_percent': memory_avg,
                    'disk_usage_percent': disk_avg,
                    'memory_available_gb': get_recent_average('memory_available')
                },
                'performance': {
                    'avg_response_time': avg_response_time,
                    'total_requests': total_requests,
                    'total_errors': total_errors,
                    'error_rate_percent': error_rate
                },
                'alerts': {
                    'total': len(self.alerts),
                    'active': len(active_alerts),
                    'critical': len([a for a in active_alerts if a['severity'] == 'critical']),
                    'warning': len([a for a in active_alerts if a['severity'] == 'warning'])
                },
                'database': {
                    'operations': {key.replace('db_', ''): value for key, value in self.counters.items() 
                                 if key.startswith('db_') and key.endswith('_count')}
                }
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        metrics = self.get_metrics_summary()
        
        # Determine overall health
        health_score = 100
        issues = []
        
        # Check system metrics
        if metrics['system']['cpu_usage_percent'] > self.cpu_threshold:
            health_score -= 20
            issues.append('High CPU usage')
        
        if metrics['system']['memory_usage_percent'] > self.memory_threshold:
            health_score -= 20
            issues.append('High memory usage')
        
        if metrics['system']['disk_usage_percent'] > self.disk_threshold:
            health_score -= 30
            issues.append('High disk usage')
        
        # Check performance metrics
        if metrics['performance']['avg_response_time'] > self.response_time_threshold:
            health_score -= 15
            issues.append('Slow response times')
        
        if metrics['performance']['error_rate_percent'] > self.error_rate_threshold:
            health_score -= 25
            issues.append('High error rate')
        
        # Check alerts
        critical_alerts = metrics['alerts']['critical']
        if critical_alerts > 0:
            health_score -= critical_alerts * 10
            issues.append(f'{critical_alerts} critical alerts')
        
        # Determine status
        if health_score >= 90:
            status = 'healthy'
        elif health_score >= 70:
            status = 'warning'
        elif health_score >= 50:
            status = 'degraded'
        else:
            status = 'critical'
        
        return {
            'status': status,
            'health_score': max(0, health_score),
            'issues': issues,
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }
    
    def export_metrics(self, filepath: str) -> bool:
        """Export metrics to JSON file"""
        try:
            with self._lock:
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'metrics_summary': self.get_metrics_summary(),
                    'health_status': self.get_health_status(),
                    'alerts': self.alerts[-50:],  # Last 50 alerts
                    'counters': dict(self.counters)
                }
                
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                logger.info(f"Metrics exported to {filepath}")
                return True
                
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return False
    
    def clear_old_data(self, max_age_hours: int = 24):
        """Clear old metrics data to prevent memory buildup"""
        try:
            with self._lock:
                cutoff_time = time.time() - (max_age_hours * 3600)
                
                for metric_name in list(self.metrics.keys()):
                    # Keep only recent data
                    self.metrics[metric_name] = deque(
                        [(timestamp, value) for timestamp, value in self.metrics[metric_name] 
                         if timestamp > cutoff_time],
                        maxlen=1000
                    )
                
                # Clear old alerts
                self.alerts = [alert for alert in self.alerts 
                              if datetime.fromisoformat(alert['timestamp']).timestamp() > cutoff_time]
                
                logger.info(f"Cleared metrics data older than {max_age_hours} hours")
                
        except Exception as e:
            logger.error(f"Error clearing old data: {e}")

# Global monitoring instance
monitor = PerformanceMonitor(auto_start=False)
