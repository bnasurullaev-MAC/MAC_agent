# =====================================
# FILE: services/base_service.py (FIXED VERSION)
# =====================================
"""Base class for all Google services"""
import logging
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from aiogram import types
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

class BaseGoogleService(ABC):
    """Base class for Google service implementations"""
    
    def __init__(self, auth_manager, config: Dict):
        self.auth_manager = auth_manager
        self.config = config
        self.service_name = self.__class__.__name__
        self.api_version = config.get('api_version', 'v1')
        self.base_url = config.get('base_url', '')
        self.scopes = config.get('scopes', [])
        
        logger.info(f"Initialized {self.service_name}")
    
    @abstractmethod
    async def handle_action(self, action: str, params: Dict, message: types.Message, state: FSMContext) -> Dict:
        """Handle service-specific actions"""
        pass
    
    def get_access_token(self) -> Optional[str]:
        """Get valid access token from auth manager"""
        return self.auth_manager.get_valid_token(self.scopes)
    
    async def make_api_call(self, 
                            method: str, 
                            endpoint: str, 
                            params: Optional[Dict] = None,
                            json_data: Optional[Dict] = None,
                            headers: Optional[Dict] = None) -> Dict:
        """Generic API call wrapper with fix for empty responses"""
        token = self.get_access_token()
        if not token:
            return {'success': False, 'error': 'Authentication failed. Please re-authenticate.'}
        
        url = f"{self.base_url}/{endpoint}"
        
        default_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        if headers:
            default_headers.update(headers)
        
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {'headers': default_headers}
                
                if params:
                    kwargs['params'] = params
                if json_data:
                    kwargs['json'] = json_data
                
                async with session.request(method, url, **kwargs) as response:
                    # --- FIX STARTS HERE ---

                    # Check for any successful status code (200-299)
                    if 200 <= response.status < 300:
                        # Status 204 means No Content, which is a success with no body
                        if response.status == 204:
                            return {'success': True, 'data': {}}

                        # For other success codes, try to parse JSON, but handle empty responses
                        try:
                            data = await response.json()
                            return {'success': True, 'data': data}
                        except aiohttp.ContentTypeError:
                            # This handles cases like Gmail trash, which is a 200 OK with an empty body.
                            logger.info(f"API call to {url} was successful (status {response.status}) but had no JSON body.")
                            return {'success': True, 'data': {}}
                    
                    # Handle API error responses
                    else:
                        error_text = await response.text()
                        logger.error(f"API call failed: {response.status} - {error_text}")

                        # Try to parse a structured error message from Google's JSON response
                        try:
                            error_json = await response.json()
                            error_message = error_json.get('error', {}).get('message', error_text)
                        except Exception:
                            error_message = error_text

                        return {'success': False, 'error': f'API Error {response.status}: {error_message}'}

                    # --- FIX ENDS HERE ---
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during API call: {e}")
            return {'success': False, 'error': f'A network error occurred: {e}'}
        except Exception as e:
            logger.error(f"An unexpected exception occurred in make_api_call: {e}")
            return {'success': False, 'error': str(e)}