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
        self.max_requests_per_window = 10
        self.session_secrets = {}
        
    def store_encryption_key(self, key: bytes, service_name: str = "shakshuka") -> bool:
        """Store encryption key in OS keyring"""
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot store encryption key")
            return False
            
        try:
            # Convert bytes to base64 string for storage
            import base64
            key_str = base64.b64encode(key).decode('utf-8')
            keyring.set_password(service_name, "encryption_key", key_str)
            logger.info("Encryption key stored in OS keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to store encryption key: {e}")
            return False
    
    def retrieve_encryption_key(self, service_name: str = "shakshuka") -> Optional[bytes]:
        """Retrieve encryption key from OS keyring"""
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot retrieve encryption key")
            return None
            
        try:
            key_str = keyring.get_password(service_name, "encryption_key")
            if key_str:
                import base64
                return base64.b64decode(key_str.encode('utf-8'))
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve encryption key: {e}")
            return None
    
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
    
    def verify_update_signature(self, file_path: str, expected_signature: str) -> bool:
        """Verify downloaded update file signature"""
        try:
            import hashlib
            
            # Calculate SHA256 hash of the file
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Compare with expected signature
            return hmac.compare_digest(file_hash, expected_signature)
        except Exception as e:
            logger.error(f"Failed to verify update signature: {e}")
            return False
    
    def generate_csrf_token(self) -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    def validate_csrf_token(self, token: str, session_token: str) -> bool:
        """Validate CSRF token"""
        return hmac.compare_digest(token, session_token)

# Global security manager instance
security_manager = SecurityManager()
