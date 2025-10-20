"""
User management system for Shakshuka application - SQLite version
"""
import os
import json
import hashlib
import secrets
import uuid
import sqlite3
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
    """Secure user management with SQLite database"""
    
    def __init__(self, data_dir=None):
        # Use user data directory if not specified
        if data_dir is None:
            if os.name == 'nt':  # Windows
                appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
                data_dir = os.path.join(appdata, 'Shakshuka', 'data')
            else:  # Unix-like systems
                data_dir = os.path.expanduser('~/.shakshuka/data')
        
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "shakshuka.db")
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize database
        self._initialize_db()
        
        # Clean up expired sessions
        self._cleanup_expired_sessions()
    
    def _get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_db(self):
        """Initialize database tables"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
    
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
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now().isoformat(),))
            conn.commit()
    
    def create_user(self, username: str, password: str) -> Dict[str, any]:
        """Create a new user"""
        try:
            # Check if user already exists
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    return {'success': False, 'message': 'User already exists'}
                
                # Create new user
                user_id = str(uuid.uuid4())
                password_hash = self._hash_password(password)
                
                cursor.execute("""
                    INSERT INTO users (id, username, password_hash)
                    VALUES (?, ?, ?)
                """, (user_id, username, password_hash))
                
                conn.commit()
                
                return {
                    'success': True,
                    'message': 'User created successfully',
                    'user': {
                        'id': user_id,
                        'username': username
                    }
                }
        except Exception as e:
            self.logger.error(f"Error creating user: {e}")
            return {'success': False, 'message': f'Error creating user: {str(e)}'}
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, any]:
        """Authenticate user with username and password"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, username, password_hash FROM users 
                    WHERE username = ? AND is_active = 1
                """, (username,))
                
                user = cursor.fetchone()
                if not user:
                    return {'success': False, 'message': 'Invalid username or password'}
                
                if not self._verify_password(password, user['password_hash']):
                    return {'success': False, 'message': 'Invalid username or password'}
                
                return {
                    'success': True,
                    'message': 'Authentication successful',
                    'user': {
                        'id': user['id'],
                        'username': user['username']
                    }
                }
        except Exception as e:
            self.logger.error(f"Error authenticating user: {e}")
            return {'success': False, 'message': f'Authentication error: {str(e)}'}
    
    def create_session(self, user_id: str) -> str:
        """Create a new session for user"""
        session_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=7)  # 7 days session
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, user_id, expires_at)
                VALUES (?, ?, ?)
            """, (session_id, user_id, expires_at.isoformat()))
            conn.commit()
        
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[Dict[str, any]]:
        """Validate session and return user info"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.id, u.username, s.expires_at
                    FROM users u
                    JOIN sessions s ON u.id = s.user_id
                    WHERE s.session_id = ? AND u.is_active = 1
                """, (session_id,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                # Check if session is expired
                expires_at = datetime.fromisoformat(result['expires_at'])
                if datetime.now() > expires_at:
                    # Remove expired session
                    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    conn.commit()
                    return None
                
                return {
                    'id': result['id'],
                    'username': result['username']
                }
        except Exception as e:
            self.logger.error(f"Error validating session: {e}")
            return None
    
    def logout_user(self, session_id: str) -> bool:
        """Logout user by removing session"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error logging out user: {e}")
            return False
    
    def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password"""
        try:
            password_hash = self._hash_password(new_password)
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?, updated_at = ?
                    WHERE id = ?
                """, (password_hash, datetime.now().isoformat(), user_id))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error updating password: {e}")
            return False
    
    def verify_password(self, password: str, user_id: str) -> bool:
        """Verify current password for user"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return False
                return self._verify_password(password, user['password_hash'])
        except Exception as e:
            self.logger.error(f"Error verifying password: {e}")
            return False

# Create global instance
user_manager = UserManager()