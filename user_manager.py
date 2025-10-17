"""
User management system for Shakshuka application
"""
import os
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging

# Try to import bcrypt for secure password hashing
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("Warning: bcrypt not available. Installing bcrypt for secure password hashing...")
    try:
        import subprocess
        subprocess.check_call(['pip', 'install', 'bcrypt'])
        import bcrypt
        BCRYPT_AVAILABLE = True
        print("bcrypt installed successfully!")
    except Exception as e:
        print(f"Failed to install bcrypt: {e}")
        print("Using fallback password hashing (less secure)")

class UserManager:
    """Secure user management with proper password hashing and session handling"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.users_file = os.path.join(data_dir, "users.json")
        self.sessions_file = os.path.join(data_dir, "sessions.json")
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Load existing data
        self.users = self._load_users()
        self.sessions = self._load_sessions()
        
        # Clean up expired sessions
        self._cleanup_expired_sessions()
    
    def _load_users(self) -> Dict[str, Dict]:
        """Load users from file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading users: {e}")
            return {}
    
    def _save_users(self) -> bool:
        """Save users to file"""
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving users: {e}")
            return False
    
    def _load_sessions(self) -> Dict[str, Dict]:
        """Load sessions from file"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading sessions: {e}")
            return {}
    
    def _save_sessions(self) -> bool:
        """Save sessions to file"""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(self.sessions, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving sessions: {e}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password securely"""
        if BCRYPT_AVAILABLE:
            # Use bcrypt for secure hashing
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        else:
            # Fallback to PBKDF2 (less secure but better than plain text)
            salt = secrets.token_hex(32)
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
            return f"{salt}:{key.hex()}"
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        if BCRYPT_AVAILABLE:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
            except Exception:
                return False
        else:
            try:
                salt, stored_key = hashed.split(':')
                key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
                return key.hex() == stored_key
            except Exception:
                return False
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session_data in self.sessions.items():
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if current_time > expires_at:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            self._save_sessions()
    
    def register_user(self, username: str, password: str) -> Dict[str, any]:
        """Register a new user with username and password only"""
        # Validate input
        if not username or len(username) < 3:
            return {'success': False, 'error': 'Username must be at least 3 characters long'}
        
        if not password or len(password) < 6:
            return {'success': False, 'error': 'Password must be at least 6 characters long'}
        
        # Check if user already exists
        if username.lower() in [user['username'].lower() for user in self.users.values()]:
            return {'success': False, 'error': 'Username already exists'}
        
        # Create new user
        user_id = str(uuid.uuid4())
        hashed_password = self._hash_password(password)
        
        user_data = {
            'id': user_id,
            'username': username,
            'password_hash': hashed_password,
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'is_active': True,
            'profile': {
                'display_name': username,
                'theme': 'orange',
                'dpi_scale': 100,
                'autosave_interval': 30
            }
        }
        
        self.users[user_id] = user_data
        
        if self._save_users():
            self.logger.info(f"New user registered: {username}")
            return {'success': True, 'user_id': user_id, 'message': 'Registration successful'}
        else:
            return {'success': False, 'error': 'Failed to save user data'}
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, any]:
        """Authenticate user login with username only"""
        # Find user by username
        user = None
        for user_data in self.users.values():
            if user_data['username'].lower() == username.lower():
                user = user_data
                break
        
        if not user:
            return {'success': False, 'error': 'Invalid username or password'}
        
        if not user['is_active']:
            return {'success': False, 'error': 'Account is disabled'}
        
        # Verify password
        if not self._verify_password(password, user['password_hash']):
            return {'success': False, 'error': 'Invalid username or password'}
        
        # Update last login
        user['last_login'] = datetime.now().isoformat()
        self._save_users()
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=24)
        
        session_data = {
            'user_id': user['id'],
            'username': user['username'],
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'ip_address': None,  # Will be set by the web app
            'user_agent': None   # Will be set by the web app
        }
        
        self.sessions[session_id] = session_data
        self._save_sessions()
        
        self.logger.info(f"User authenticated: {user['username']}")
        return {
            'success': True,
            'session_id': session_id,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'profile': user['profile']
            }
        }
    
    def validate_session(self, session_id: str) -> Optional[Dict]:
        """Validate session and return user data"""
        if not session_id or session_id not in self.sessions:
            return None
        
        session_data = self.sessions[session_id]
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        
        if datetime.now() > expires_at:
            # Session expired
            del self.sessions[session_id]
            self._save_sessions()
            return None
        
        # Get user data
        user_id = session_data['user_id']
        if user_id not in self.users:
            return None
        
        user = self.users[user_id]
        if not user['is_active']:
            return None
        
        return {
            'user_id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'profile': user['profile']
        }
    
    def logout_user(self, session_id: str) -> bool:
        """Logout user by removing session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()
            return True
        return False
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> Dict[str, any]:
        """Change user password"""
        if user_id not in self.users:
            return {'success': False, 'error': 'User not found'}
        
        user = self.users[user_id]
        
        # Verify old password
        if not self._verify_password(old_password, user['password_hash']):
            return {'success': False, 'error': 'Current password is incorrect'}
        
        # Validate new password
        if not new_password or len(new_password) < 6:
            return {'success': False, 'error': 'New password must be at least 6 characters long'}
        
        # Update password
        user['password_hash'] = self._hash_password(new_password)
        
        if self._save_users():
            self.logger.info(f"Password changed for user: {user['username']}")
            return {'success': True, 'message': 'Password changed successfully'}
        else:
            return {'success': False, 'error': 'Failed to save password'}
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return self._verify_password(password, hashed)
    
    def update_password(self, user_id: str, new_password: str) -> Dict[str, any]:
        """Update user password (simplified version without old password verification)"""
        if user_id not in self.users:
            return {'success': False, 'error': 'User not found'}
        
        user = self.users[user_id]
        
        # Update password
        user['password_hash'] = self._hash_password(new_password)
        
        if self._save_users():
            self.logger.info(f"Password updated for user: {user['username']}")
            return {'success': True, 'message': 'Password updated successfully'}
        else:
            return {'success': False, 'error': 'Failed to save password'}
    
    def update_profile(self, user_id: str, profile_data: Dict) -> Dict[str, any]:
        """Update user profile"""
        if user_id not in self.users:
            return {'success': False, 'error': 'User not found'}
        
        user = self.users[user_id]
        
        # Update profile fields
        for key, value in profile_data.items():
            if key in ['display_name', 'theme', 'dpi_scale', 'autosave_interval']:
                user['profile'][key] = value
        
        if self._save_users():
            return {'success': True, 'profile': user['profile']}
        else:
            return {'success': False, 'error': 'Failed to save profile'}
    
    def get_user_stats(self) -> Dict[str, int]:
        """Get user statistics"""
        total_users = len(self.users)
        active_users = len([u for u in self.users.values() if u['is_active']])
        active_sessions = len(self.sessions)
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'active_sessions': active_sessions
        }

# Global user manager instance
user_manager = UserManager()
