"""Generic API wrapper utilities"""
import aiohttp
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class APIWrapper:
    """Generic API wrapper for consistent error handling"""
    
    @staticmethod
    async def make_request(
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Make an HTTP request with error handling"""
        
        try:
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                kwargs = {}
                
                if headers:
                    kwargs['headers'] = headers
                if params:
                    kwargs['params'] = params
                if json_data:
                    kwargs['json'] = json_data
                
                async with session.request(method, url, **kwargs) as response:
                    # Handle successful responses
                    if response.status in [200, 201, 204]:
                        if response.status == 204:
                            return {'success': True, 'data': None}
                        
                        try:
                            data = await response.json()
                            return {'success': True, 'data': data}
                        except Exception:
                            text = await response.text()
                            return {'success': True, 'data': text}
                    
                    # Handle errors
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text}")
                    
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}',
                        'error_details': error_text
                    }
                    
        except aiohttp.ClientTimeout:
            logger.error(f"Request timeout: {url}")
            return {'success': False, 'error': 'Request timed out'}
            
        except aiohttp.ClientError as e:
            logger.error(f"Client error: {e}")
            return {'success': False, 'error': f'Connection error: {str(e)}'}
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
    
    @staticmethod
    def handle_api_error(response: Dict) -> str:
        """Convert API error response to user-friendly message"""
        
        if response.get('success'):
            return ""
        
        error = response.get('error', 'Unknown error')
        
        # Map common errors to user-friendly messages
        error_messages = {
            'HTTP 401': 'Authentication failed. Please check your credentials.',
            'HTTP 403': 'Access denied. You may not have permission for this action.',
            'HTTP 404': 'The requested resource was not found.',
            'HTTP 429': 'Too many requests. Please try again later.',
            'HTTP 500': 'Server error. Please try again later.',
            'Request timed out': 'The request took too long. Please try again.',
            'Connection error': 'Could not connect to the service. Please check your connection.'
        }
        
        for key, message in error_messages.items():
            if key in error:
                return message
        
        return f"An error occurred: {error}"
