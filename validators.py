"""Input validation utilities"""
import re
from typing import Optional, Tuple

class Validators:
    """Input validation utilities"""
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """Validate email address"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not email:
            return False, "Email address is required"
        
        if not re.match(pattern, email):
            return False, "Invalid email address format"
        
        return True, None
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
        """Validate phone number"""
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)]+', '', phone)
        
        if not cleaned:
            return False, "Phone number is required"
        
        # Check if it's all digits (with optional + at start)
        if not re.match(r'^\+?\d+$', cleaned):
            return False, "Invalid phone number format"
        
        # Check length (between 7 and 15 digits)
        digit_count = len(re.sub(r'\D', '', cleaned))
        if digit_count < 7 or digit_count > 15:
            return False, "Phone number should be between 7 and 15 digits"
        
        return True, None
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """Validate URL"""
        pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        
        if not url:
            return False, "URL is required"
        
        if not re.match(pattern, url):
            return False, "Invalid URL format"
        
        return True, None
    
    @staticmethod
    def validate_date_format(date_str: str) -> Tuple[bool, Optional[str]]:
        """Validate date format"""
        formats = [
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
            r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
            r'^\d{2}-\d{2}-\d{4}$',  # MM-DD-YYYY
        ]
        
        if not date_str:
            return False, "Date is required"
        
        for pattern in formats:
            if re.match(pattern, date_str):
                return True, None
        
        return False, "Invalid date format. Use YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to remove invalid characters"""
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Replace spaces with underscores
        sanitized = sanitized.replace(' ', '_')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = name[:250] + (f'.{ext}' if ext else '')
        
        return sanitized or 'unnamed_file'
    
    @staticmethod
    def validate_permission_role(role: str) -> Tuple[bool, Optional[str]]:
        """Validate Google Drive permission role"""
        valid_roles = ['owner', 'organizer', 'fileOrganizer', 'writer', 'commenter', 'reader']
        
        if role not in valid_roles:
            return False, f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        
        return True, None
