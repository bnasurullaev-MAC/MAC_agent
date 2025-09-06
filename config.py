"""Configuration management for the Google Assistant Bot"""
import os
from typing import Dict, Any, List
import pytz
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

class Config:
    """Central configuration class"""
    
    # Bot configuration
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
    
    # Default timezone
    DEFAULT_TIMEZONE = pytz.timezone(os.getenv('DEFAULT_TIMEZONE', 'America/Chicago'))
    
    # Service configurations
    SERVICES = {
        'calendar': {
            'enabled': os.getenv('ENABLE_CALENDAR', 'true').lower() == 'true',
            'api_version': os.getenv('CALENDAR_API_VERSION', 'v3'),
            'base_url': 'https://www.googleapis.com/calendar/v3',
            'scopes': ['https://www.googleapis.com/auth/calendar']
        },
        'gmail': {
            'enabled': os.getenv('ENABLE_GMAIL', 'true').lower() == 'true',
            'api_version': os.getenv('GMAIL_API_VERSION', 'v1'),
            'base_url': 'https://gmail.googleapis.com/gmail/v1',
            'scopes': ['https://www.googleapis.com/auth/gmail.modify']
        },
        'contacts': {
            'enabled': os.getenv('ENABLE_CONTACTS', 'true').lower() == 'true',
            'api_version': os.getenv('CONTACTS_API_VERSION', 'v1'),
            'base_url': 'https://people.googleapis.com/v1',
            'scopes': ['https://www.googleapis.com/auth/contacts']
        },
        'drive': {
            'enabled': os.getenv('ENABLE_DRIVE', 'true').lower() == 'true',
            'api_version': os.getenv('DRIVE_API_VERSION', 'v3'),
            'base_url': 'https://www.googleapis.com/drive/v3',
            'scopes': ['https://www.googleapis.com/auth/drive']
        },
        'tasks': {
            'enabled': os.getenv('ENABLE_TASKS', 'true').lower() == 'true',
            'api_version': os.getenv('TASKS_API_VERSION', 'v1'),
            'base_url': 'https://tasks.googleapis.com/tasks/v1',
            'scopes': ['https://www.googleapis.com/auth/tasks']
        }
    }
    
    # Conversation settings
    MAX_CONVERSATION_LENGTH = 10
    MAX_CONTEXT_MESSAGES = 6
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 60
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Dict[str, Any]:
        """Get configuration for a specific service"""
        return cls.SERVICES.get(service_name, {})
    
    @classmethod
    def get_enabled_services(cls) -> List[str]:
        """Get list of enabled services"""
        return [name for name, config in cls.SERVICES.items() if config['enabled']]
    
    @classmethod
    def get_all_scopes(cls) -> List[str]:
        """Get all required OAuth scopes"""
        scopes = set()
        for service_config in cls.SERVICES.values():
            if service_config['enabled']:
                scopes.update(service_config['scopes'])
        return list(scopes)
