"""
Input Sanitizers - Clean and sanitize user input
"""
import html
import re
from typing import Any, Dict, List, Union


def sanitize_input(data: Any) -> Any:
    """
    Recursively sanitize input data to prevent XSS and injection attacks.
    
    Args:
        data: Data to sanitize (can be dict, list, string, or other types)
        
    Returns:
        Sanitized data
    """
    if isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    else:
        return data


def sanitize_string(text: str, max_length: int = 10000) -> str:
    """
    Sanitize a string by removing dangerous characters.

    NOTE: this deliberately does NOT HTML-escape. Stored text must stay raw;
    the display layer (Utils.sanitizeHTML in JS, Jinja auto-escaping, and the
    companion app) is responsible for escaping at render time. Escaping here
    corrupted apostrophes (&#x27;) and quotes (&quot;) in saved tasks.

    Args:
        text: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(text, str):
        return text

    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]

    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove other control characters except newlines, tabs, and carriage returns
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

    return text


# Task fields that hold user-typed text and may contain legacy HTML entities
# written by versions that escaped input before storing it (pre-35.9).
LEGACY_TEXT_TASK_FIELDS = ("title", "description", "strike_report", "project", "owner")


def unescape_legacy_html(text: str) -> str:
    """
    Reverse over-eager html.escape() applied at save time by older versions.

    Pre-35.9 releases HTML-escaped user input before storing it, so
    apostrophes were persisted as '&#x27;', quotes as '&quot;' and ampersands
    as '&amp;' — and every edit compounded the escaping. The display layer
    now escapes at render time, so stored text must be raw. Unescape
    repeatedly (bounded) to undo the compounding.
    """
    if not isinstance(text, str) or "&" not in text:
        return text
    for _ in range(5):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def normalize_task_text_fields(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heal task text fields that may contain legacy HTML entities.

    Applied at the data-layer read path so previously stored tasks display
    correctly without a one-time migration. Idempotent for clean data.
    """
    for field in LEGACY_TEXT_TASK_FIELDS:
        value = task.get(field)
        if isinstance(value, str) and "&" in value:
            task[field] = unescape_legacy_html(value)
    return task


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Safe filename
    """
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove parent directory references
    filename = filename.replace('..', '_')
    
    # Only allow alphanumeric, dash, underscore, and dot
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    return filename


def sanitize_html_content(content: str, allow_basic_formatting: bool = False) -> str:
    """
    Sanitize HTML content, optionally allowing basic formatting tags.
    
    Args:
        content: HTML content to sanitize
        allow_basic_formatting: If True, allows <b>, <i>, <u>, <br> tags
        
    Returns:
        Sanitized HTML content
    """
    if not allow_basic_formatting:
        return html.escape(content)
    
    # Whitelist of allowed tags
    allowed_tags = ['b', 'i', 'u', 'br', 'strong', 'em']
    
    # Remove all tags except allowed ones
    for match in re.finditer(r'<(/?)(\w+)([^>]*)>', content):
        tag = match.group(2).lower()
        if tag not in allowed_tags:
            content = content.replace(match.group(0), '')
    
    # Remove any attributes from allowed tags
    content = re.sub(r'<(\w+)[^>]*>', r'<\1>', content)
    
    return content


def sanitize_sql_input(value: str) -> str:
    """
    Basic sanitization for SQL inputs (note: use parameterized queries instead).
    This is a backup defense layer.
    
    Args:
        value: Value to sanitize
        
    Returns:
        Sanitized value
    """
    if not isinstance(value, str):
        return value
    
    # Remove common SQL injection patterns
    dangerous_patterns = [
        '--', ';--', ';', '/*', '*/', 'xp_', 'sp_',
        'exec', 'execute', 'drop ', 'create ', 'insert ',
        'delete ', 'update ', 'union ', 'select '
    ]
    
    value_lower = value.lower()
    for pattern in dangerous_patterns:
        if pattern in value_lower:
            value = value.replace(pattern, '')
    
    return value


def strip_tags(text: str) -> str:
    """
    Remove all HTML tags from text.
    
    Args:
        text: Text with potential HTML tags
        
    Returns:
        Text without HTML tags
    """
    return re.sub(r'<[^>]+>', '', text)

