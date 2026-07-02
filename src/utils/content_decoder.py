"""
Utility functions for decoding split-encoded content.

The __SHAKSHUKA_SPLIT_B64_V1__ format is used to encode large or complex
content while maintaining a specific structure. This module provides
utilities to decode and normalize such content.
"""

import base64
import json
from typing import Any, Optional


def decode_split_b64_v1(encoded_content: str) -> Optional[dict]:
    """
    Decode __SHAKSHUKA_SPLIT_B64_V1__ encoded content.
    
    Args:
        encoded_content: String starting with __SHAKSHUKA_SPLIT_B64_V1__
        
    Returns:
        Dict with keys: {'primary': str, 'secondary': str, 'was_split': bool}
        or None if decoding fails
    """
    if not isinstance(encoded_content, str):
        return None
        
    if not encoded_content.startswith('__SHAKSHUKA_SPLIT_B64_V1__'):
        return None
    
    try:
        b64_payload = encoded_content[len('__SHAKSHUKA_SPLIT_B64_V1__'):]
        decoded_json = base64.b64decode(b64_payload).decode('utf-8')
        parsed = json.loads(decoded_json)
        
        if isinstance(parsed, dict):
            primary = parsed.get('primary', '')
            secondary = parsed.get('secondary', '')
            return {
                'primary': primary,
                'secondary': secondary,
                'was_split': True
            }
        return None
    except Exception:
        # If decoding fails, return None to indicate failure
        return None


def normalize_content(raw_content: Any) -> str:
    """
    Normalize content by decoding any split-encoded strings.
    Combines primary and secondary parts if both exist.
    
    Args:
        raw_content: The raw content (may be encoded or plain string)
        
    Returns:
        Decoded and combined content if it was encoded, otherwise the original content
    """
    if not isinstance(raw_content, str):
        return str(raw_content) if raw_content else ""
    
    # Try to decode if it looks like split-encoded content
    if raw_content.startswith('__SHAKSHUKA_SPLIT_B64_V1__'):
        decoded = decode_split_b64_v1(raw_content)
        if decoded is not None:
            primary = decoded.get('primary', '')
            secondary = decoded.get('secondary', '')
            # Combine both parts with a separator if secondary exists
            if secondary.strip():
                return f"{primary}\n\n--- Split Editor ---\n\n{secondary}"
            return primary
        # If decoding fails, return the original
        return raw_content
    
    return raw_content


def is_split_encoded(raw_content: Any) -> bool:
    """Return True when content was saved using split-editor encoding."""
    return isinstance(raw_content, str) and raw_content.startswith('__SHAKSHUKA_SPLIT_B64_V1__')
