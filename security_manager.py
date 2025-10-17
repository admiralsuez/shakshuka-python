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
        self.rate_limit_requests = defaultdict(lambda: deque())
        self.rate_limit_window = 300  # 5 minutes
        self.max_requests_per_window = 100  # Increased from 10 to 100 requests per 5 minutes
        self.session_secrets = {}
        
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
        """Check if client has exceeded rate limit"""
        now = time.time()
        requests = self.rate_limit_requests[client_ip]
        
        # Remove old requests outside the window
        while requests and requests[0] < now - self.rate_limit_window:
            requests.popleft()
        
        # Check if limit exceeded
        if len(requests) >= self.max_requests_per_window:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return False
        
        # Add current request
        requests.append(now)
        return True
    
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
