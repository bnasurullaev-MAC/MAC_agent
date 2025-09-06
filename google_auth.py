"""Unified Google authentication for all services"""
import os
import pickle
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import Config

logger = logging.getLogger(__name__)

class GoogleAuthManager:
    """Manages authentication for all Google services"""
    
    def __init__(self, token_file: str = 'data/google_token.pickle'):
        self.token_file = token_file
        self.credentials = None
        self.client_id = Config.GOOGLE_CLIENT_ID
        self.client_secret = Config.GOOGLE_CLIENT_SECRET
        self.refresh_token = Config.GOOGLE_REFRESH_TOKEN
        self.required_scopes = Config.get_all_scopes()
        self.load_credentials()
    
    def load_credentials(self):
        """Load saved credentials from pickle file or create from env"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'rb') as token:
                    self.credentials = pickle.load(token)
                logger.info("Loaded saved Google credentials")
                
                # Check if all required scopes are present
                if self.credentials and self.credentials.scopes:
                    missing_scopes = set(self.required_scopes) - set(self.credentials.scopes)
                    if missing_scopes:
                        logger.warning(f"Missing required scopes: {missing_scopes}")
                        # You might want to trigger re-authentication here
                        
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
                self.create_credentials_from_env()
        else:
            self.create_credentials_from_env()
    
    def create_credentials_from_env(self):
        """Create credentials from environment variables"""
        if self.refresh_token and self.client_id and self.client_secret:
            self.credentials = Credentials(
                token=None,  # Will be refreshed
                refresh_token=self.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.required_scopes
            )
            self.save_credentials()
            logger.info("Created credentials from environment variables")
    
    def get_valid_token(self, required_scopes: Optional[List[str]] = None) -> Optional[str]:
        """Get valid access token, refreshing if necessary"""
        if not self.credentials:
            logger.error("No credentials available")
            return None
        
        # Check if we have required scopes
        if required_scopes:
            if not self.credentials.scopes:
                logger.error("No scopes in credentials")
                return None
                
            missing_scopes = set(required_scopes) - set(self.credentials.scopes)
            if missing_scopes:
                logger.error(f"Missing required scopes: {missing_scopes}")
                return None
        
        # Refresh token if expired
        if not self.credentials.token or self.credentials.expired:
            try:
                self.credentials.refresh(Request())
                self.save_credentials()
                logger.info("Token refreshed successfully")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                return None
        
        return self.credentials.token
    
    def save_credentials(self):
        """Save credentials to pickle file"""
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.credentials, token)
            logger.info("Credentials saved")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    def revoke_credentials(self):
        """Revoke the current credentials"""
        if self.credentials:
            try:
                # Implement revocation if needed
                self.credentials = None
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
                logger.info("Credentials revoked")
            except Exception as e:
                logger.error(f"Error revoking credentials: {e}")
