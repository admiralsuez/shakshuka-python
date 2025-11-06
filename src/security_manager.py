"""
Security Manager for Shakshuka Task Manager
Handles encryption key storage, input sanitization, rate limiting, and session management
"""

import os
import time
import hashlib
import hmac
import secrets
import html
import re
import threading
from typing import Dict, Optional, Any
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

# Try to import keyring, fallback if not available
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring module not available. OS keyring features will be disabled.")

class SecurityManager:
    def __init__(self):
        # Enhanced rate limiting with memory management
        self.rate_limit_requests = defaultdict(lambda: deque())
        self.rate_limit_window = 300  # 5 minutes
        self.max_requests_per_window = 100  # Increased from 10 to 100 requests per 5 minutes
        self.session_secrets = {}
        
        # Memory management for rate limiting
        self.max_ip_entries = 1000  # Maximum number of IPs to track
        self.cleanup_interval = 600  # Cleanup every 10 minutes
        self.last_cleanup = time.time()
        
        # Performance monitoring
        self.request_count = 0
        self.blocked_count = 0
        self.cleanup_count = 0
        
        # Thread safety
        self._rate_limit_lock = threading.RLock()
        
    # Unused encryption key functions removed - were dead code
    # Unused update signature verification removed - was dead code  
    # Unused CSRF functions removed - duplicate implementations
    
    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """Sanitize user input to prevent XSS attacks"""
        if not text:
            return ""
        
        # Limit length
        text = text[:max_length]
        
        # HTML escape
        text = html.escape(text, quote=True)
        
        # Remove potentially dangerous characters
        text = re.sub(r'[<>"\']', '', text)
        
        # Remove script tags and javascript: protocols
        text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Enhanced rate limiting with memory management and performance monitoring"""
        with self._rate_limit_lock:
            now = time.time()
            self.request_count += 1
            
            # Periodic cleanup to prevent memory leaks
            if now - self.last_cleanup > self.cleanup_interval:
                self._cleanup_rate_limit_data(now)
                self.last_cleanup = now
            
            # Get or create request queue for this IP
            requests = self.rate_limit_requests[client_ip]
            
            # Remove old requests outside the window
            while requests and requests[0] < now - self.rate_limit_window:
                requests.popleft()
            
            # Check if limit exceeded
            if len(requests) >= self.max_requests_per_window:
                self.blocked_count += 1
                logger.warning(f"Rate limit exceeded for IP: {client_ip} ({len(requests)} requests in window)")
                return False
            
            # Add current request
            requests.append(now)
            return True
    
    def _cleanup_rate_limit_data(self, now: float):
        """Clean up old rate limiting data to prevent memory leaks"""
        try:
            cleanup_threshold = now - (self.rate_limit_window * 2)  # Remove data older than 2 windows
            ips_to_remove = []
            
            for ip, requests in self.rate_limit_requests.items():
                # Remove old requests
                while requests and requests[0] < cleanup_threshold:
                    requests.popleft()
                
                # Remove IPs with no recent requests
                if not requests:
                    ips_to_remove.append(ip)
            
            # Remove empty IP entries
            for ip in ips_to_remove:
                del self.rate_limit_requests[ip]
            
            # If we still have too many IPs, remove the oldest ones
            if len(self.rate_limit_requests) > self.max_ip_entries:
                # Sort by oldest request time and remove excess
                ip_ages = []
                for ip, requests in self.rate_limit_requests.items():
                    if requests:
                        ip_ages.append((ip, requests[0]))
                
                # Sort by oldest request time
                ip_ages.sort(key=lambda x: x[1])
                
                # Remove oldest IPs
                excess_count = len(self.rate_limit_requests) - self.max_ip_entries
                for i in range(excess_count):
                    ip_to_remove = ip_ages[i][0]
                    del self.rate_limit_requests[ip_to_remove]
            
            self.cleanup_count += 1
            logger.info(f"Rate limit cleanup completed: {len(ips_to_remove)} IPs removed, "
                       f"{len(self.rate_limit_requests)} IPs remaining")
            
        except Exception as e:
            logger.error(f"Error during rate limit cleanup: {e}")
    
    def get_rate_limit_stats(self) -> dict:
        """Get rate limiting statistics for monitoring"""
        with self._rate_limit_lock:
            active_ips = len(self.rate_limit_requests)
            total_requests = sum(len(requests) for requests in self.rate_limit_requests.values())
            
            return {
                'active_ips': active_ips,
                'total_requests': total_requests,
                'request_count': self.request_count,
                'blocked_count': self.blocked_count,
                'cleanup_count': self.cleanup_count,
                'block_rate': (self.blocked_count / max(self.request_count, 1)) * 100,
                'memory_usage_mb': self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage of rate limiting data"""
        try:
            import sys
            total_size = 0
            
            # Estimate size of defaultdict
            total_size += sys.getsizeof(self.rate_limit_requests)
            
            # Estimate size of each IP entry
            for ip, requests in self.rate_limit_requests.items():
                total_size += sys.getsizeof(ip)
                total_size += sys.getsizeof(requests)
                total_size += len(requests) * sys.getsizeof(0.0)  # Each timestamp
            
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0
    
    def generate_session_secret(self, user_id: str) -> str:
        """Generate a secure session secret"""
        secret = secrets.token_urlsafe(32)
        self.session_secrets[user_id] = {
            'secret': secret,
            'created': time.time(),
            'last_activity': time.time()
        }
        return secret
    
    def validate_session(self, user_id: str, session_secret: str) -> bool:
        """Validate session secret"""
        if user_id not in self.session_secrets:
            return False
        
        session_data = self.session_secrets[user_id]
        
        # Check if secret matches
        if session_data['secret'] != session_secret:
            return False
        
        # Check if session is expired (24 hours)
        if time.time() - session_data['created'] > 86400:
            del self.session_secrets[user_id]
            return False
        
        # Update last activity
        session_data['last_activity'] = time.time()
        return True
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = time.time()
        expired_users = []
        
        for user_id, session_data in self.session_secrets.items():
            if now - session_data['last_activity'] > 86400:  # 24 hours
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.session_secrets[user_id]
    
    # Unused update signature verification removed - was dead code

# Global security manager instance
security_manager = SecurityManager()
