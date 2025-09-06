# test_token.py
import os
import pickle
from dotenv import load_dotenv

load_dotenv()

if os.path.exists('data/google_token.pickle'):
    with open('data/google_token.pickle', 'rb') as f:
        creds = pickle.load(f)
        print("Current token scopes:")
        for scope in creds.scopes:
            print(f"  • {scope}")
        
        if 'https://www.googleapis.com/auth/gmail.modify' in creds.scopes:
            print("\n✅ Gmail access is already enabled!")
        else:
            print("\n❌ Gmail access is MISSING - you need to regenerate token")
else:
    print("❌ No token file found - you need to generate one")