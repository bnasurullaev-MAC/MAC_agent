"""Generate Google OAuth token with all required scopes"""
import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',  # Gmail full access
    'https://www.googleapis.com/auth/calendar',      # Calendar
    'https://www.googleapis.com/auth/contacts',      # Contacts
    'https://www.googleapis.com/auth/drive',         # Drive
    'https://www.googleapis.com/auth/tasks'          # Tasks
]

def main():
    # Create credentials.json from environment variables
    client_config = {
        "installed": {
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }
    
    # Save config temporarily
    with open('credentials.json', 'w') as f:
        json.dump(client_config, f)
    
    print("Opening browser for Google authorization...")
    print("Please grant access to: Gmail, Calendar, Contacts, Drive, Tasks")
    
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Save the credentials
    with open('data/google_token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    
    print("\n✅ Token saved successfully!")
    print(f"\nYour refresh token: {creds.refresh_token}")
    print("\nUpdate your .env file with:")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    
    # Clean up
    os.remove('credentials.json')

if __name__ == '__main__':
    main()