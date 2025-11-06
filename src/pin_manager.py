"""
PIN Authentication Manager for Shakshuka
Handles 4-digit PIN authentication with encryption, retry logic, and cooldown
"""

import os
import json
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class PINManager:
    """Manages PIN authentication with encryption and security features"""
    
    MAX_ATTEMPTS = 10
    COOLDOWN_MINUTES = 10
    PIN_LENGTH = 4
    
    def __init__(self, data_dir: str):
        """
        Initialize PIN manager
        
        Args:
            data_dir: Directory to store PIN data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.pin_file = self.data_dir / "pin_data.json"
        self.key_file = self.data_dir / "pin_key.key"
        
        # Initialize encryption
        self._ensure_encryption_key()
        self._load_pin_data()
        
        logger.info("PIN manager initialized")
    
    def _ensure_encryption_key(self):
        """Create or load encryption key"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self.encryption_key = f.read()
        else:
            # Generate a new encryption key
            self.encryption_key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.encryption_key)
            logger.info("Generated new encryption key")
        
        self.cipher = Fernet(self.encryption_key)
    
    def _load_pin_data(self):
        """Load PIN data from file"""
        if self.pin_file.exists():
            try:
                with open(self.pin_file, 'r') as f:
                    self.pin_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load PIN data: {e}")
                self.pin_data = self._get_default_pin_data()
        else:
            self.pin_data = self._get_default_pin_data()
    
    def _get_default_pin_data(self) -> Dict[str, Any]:
        """Get default PIN data structure"""
        return {
            "pin_hash": None,
            "salt": None,
            "setup_complete": False,
            "failed_attempts": 0,
            "cooldown_until": None,
            "last_attempt": None,
            "recovery_questions": [],
            "created_at": None,
            "last_login": None,
            "remember_pin": False,
            "session_expires": None
        }
    
    def _save_pin_data(self):
        """Save PIN data to file"""
        try:
            with open(self.pin_file, 'w') as f:
                json.dump(self.pin_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save PIN data: {e}")
            raise
    
    def _hash_pin(self, pin: str, salt: bytes) -> str:
        """
        Hash PIN with salt using PBKDF2
        
        Args:
            pin: 4-digit PIN
            salt: Salt bytes
            
        Returns:
            Hex string of hashed PIN
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(pin.encode())
        return key.hex()
    
    def is_setup_complete(self) -> bool:
        """Check if PIN setup is complete"""
        return self.pin_data.get("setup_complete", False)
    
    def is_in_cooldown(self) -> Tuple[bool, Optional[int]]:
        """
        Check if account is in cooldown
        
        Returns:
            Tuple of (is_in_cooldown, seconds_remaining)
        """
        cooldown_until = self.pin_data.get("cooldown_until")
        if not cooldown_until:
            return False, None
        
        cooldown_time = datetime.fromisoformat(cooldown_until)
        now = datetime.now()
        
        if now < cooldown_time:
            seconds_remaining = int((cooldown_time - now).total_seconds())
            return True, seconds_remaining
        else:
            # Cooldown expired, reset
            self.pin_data["cooldown_until"] = None
            self.pin_data["failed_attempts"] = 0
            self._save_pin_data()
            return False, None
    
    def validate_pin_format(self, pin: str) -> Tuple[bool, str]:
        """
        Validate PIN format
        
        Args:
            pin: PIN to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not pin:
            return False, "PIN is required"
        
        if len(pin) != self.PIN_LENGTH:
            return False, f"PIN must be exactly {self.PIN_LENGTH} digits"
        
        if not pin.isdigit():
            return False, "PIN must contain only digits"
        
        return True, ""
    
    def setup_pin(self, pin: str, confirm_pin: str, recovery_questions: list = None) -> Tuple[bool, str]:
        """
        Setup a new PIN
        
        Args:
            pin: 4-digit PIN
            confirm_pin: Confirmation of PIN
            recovery_questions: Optional recovery questions
            
        Returns:
            Tuple of (success, message)
        """
        # Validate PIN format
        is_valid, error = self.validate_pin_format(pin)
        if not is_valid:
            return False, error
        
        # Check confirmation
        if pin != confirm_pin:
            return False, "PINs do not match"
        
        # Generate salt
        salt = secrets.token_bytes(32)
        
        # Hash PIN
        pin_hash = self._hash_pin(pin, salt)
        
        # Store encrypted data
        self.pin_data = {
            "pin_hash": pin_hash,
            "salt": salt.hex(),
            "setup_complete": True,
            "failed_attempts": 0,
            "cooldown_until": None,
            "last_attempt": None,
            "recovery_questions": recovery_questions or [],
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        self._save_pin_data()
        logger.info("PIN setup completed successfully")
        
        return True, "PIN setup successful"
    
    def is_session_valid(self) -> bool:
        """
        Check if current session is still valid (within 7 days)
        
        Returns:
            True if session is valid, False if expired
        """
        if not self.pin_data.get("remember_pin", False):
            return False
        
        session_expires = self.pin_data.get("session_expires")
        if not session_expires:
            return False
        
        expiry_time = datetime.fromisoformat(session_expires)
        return datetime.now() < expiry_time
    
    def verify_pin(self, pin: str, remember: bool = False) -> Tuple[bool, str, Optional[int]]:
        """
        Verify PIN
        
        Args:
            pin: 4-digit PIN to verify
            remember: If True, remember this session for 7 days
            
        Returns:
            Tuple of (success, message, attempts_remaining)
        """
        # Check setup
        if not self.is_setup_complete():
            return False, "PIN not setup", None
        
        # Check cooldown
        in_cooldown, seconds_remaining = self.is_in_cooldown()
        if in_cooldown:
            minutes = seconds_remaining // 60
            seconds = seconds_remaining % 60
            return False, f"Too many failed attempts. Try again in {minutes}m {seconds}s", None
        
        # Validate format
        is_valid, error = self.validate_pin_format(pin)
        if not is_valid:
            return False, error, None
        
        # Get stored data
        stored_hash = self.pin_data.get("pin_hash")
        salt_hex = self.pin_data.get("salt")
        
        if not stored_hash or not salt_hex:
            return False, "PIN data corrupted", None
        
        # Hash provided PIN
        salt = bytes.fromhex(salt_hex)
        pin_hash = self._hash_pin(pin, salt)
        
        # Update last attempt time
        self.pin_data["last_attempt"] = datetime.now().isoformat()
        
        # Verify
        if pin_hash == stored_hash:
            # Success - reset attempts
            self.pin_data["failed_attempts"] = 0
            self.pin_data["last_login"] = datetime.now().isoformat()
            
            # Handle remember PIN option
            if remember:
                self.pin_data["remember_pin"] = True
                # Set session to expire in 7 days
                expiry = datetime.now() + timedelta(days=7)
                self.pin_data["session_expires"] = expiry.isoformat()
                logger.info(f"Session will expire on {expiry}")
            else:
                self.pin_data["remember_pin"] = False
                self.pin_data["session_expires"] = None
            
            self._save_pin_data()
            
            logger.info("PIN verified successfully")
            return True, "Login successful", None
        else:
            # Failed attempt
            self.pin_data["failed_attempts"] += 1
            attempts_used = self.pin_data["failed_attempts"]
            attempts_remaining = self.MAX_ATTEMPTS - attempts_used
            
            logger.warning(f"Failed PIN attempt {attempts_used}/{self.MAX_ATTEMPTS}")
            
            # Check if max attempts reached
            if attempts_used >= self.MAX_ATTEMPTS:
                # Set cooldown
                cooldown_until = datetime.now() + timedelta(minutes=self.COOLDOWN_MINUTES)
                self.pin_data["cooldown_until"] = cooldown_until.isoformat()
                self._save_pin_data()
                
                logger.warning(f"Max attempts reached. Cooldown until {cooldown_until}")
                return False, f"Too many failed attempts. Locked for {self.COOLDOWN_MINUTES} minutes", 0
            else:
                self._save_pin_data()
                return False, f"Incorrect PIN. {attempts_remaining} attempts remaining", attempts_remaining
    
    def reset_pin(self, new_pin: str, confirm_pin: str) -> Tuple[bool, str]:
        """
        Reset PIN (for forgot PIN recovery)
        
        Args:
            new_pin: New 4-digit PIN
            confirm_pin: Confirmation of new PIN
            
        Returns:
            Tuple of (success, message)
        """
        # Use same logic as setup
        success, message = self.setup_pin(new_pin, confirm_pin)
        
        if success:
            # Reset cooldown and attempts
            self.pin_data["failed_attempts"] = 0
            self.pin_data["cooldown_until"] = None
            self._save_pin_data()
            logger.info("PIN reset successfully")
        
        return success, message
    
    def get_recovery_questions(self) -> list:
        """Get recovery questions if available"""
        return self.pin_data.get("recovery_questions", [])
    
    def get_failed_attempts(self) -> int:
        """Get current failed attempt count"""
        return self.pin_data.get("failed_attempts", 0)
    
    def get_last_login(self) -> Optional[str]:
        """Get last successful login time"""
        return self.pin_data.get("last_login")
    
    def is_remembered(self) -> bool:
        """Check if 'remember PIN' is enabled"""
        return self.pin_data.get("remember_pin", False)
    
    def get_session_expiry(self) -> Optional[str]:
        """Get session expiry time"""
        return self.pin_data.get("session_expires")
    
    def logout(self):
        """Logout - clear remember session"""
        self.pin_data["remember_pin"] = False
        self.pin_data["session_expires"] = None
        self._save_pin_data()
        logger.info("User logged out - session cleared")
    
    def clear_all_data(self):
        """Clear all PIN data (use with caution!)"""
        self.pin_data = self._get_default_pin_data()
        self._save_pin_data()
        logger.warning("All PIN data cleared")

