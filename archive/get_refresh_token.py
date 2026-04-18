# get_refresh_token.py
# Helper script to generate Google OAuth refresh token for Drive API

"""
This script helps you obtain a refresh token for Google Drive API.

To use:
1. Set up a Google Cloud project with Drive API enabled
2. Create OAuth 2.0 credentials (Desktop app type)
3. Run this script and follow the authentication flow
4. Copy the refresh_token and add it to your Replit secrets

The refresh token can be used to access Google Drive without
repeated manual authentication.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_refresh_token():
    """
    Run OAuth flow to get refresh token.
    You'll need client_id and client_secret from Google Cloud Console.
    """
    print("Google Drive OAuth Token Generator")
    print("=" * 50)
    print("\nYou'll need:")
    print("1. Client ID from Google Cloud Console")
    print("2. Client Secret from Google Cloud Console")
    print("\nMake sure the OAuth consent screen is configured.")
    print("=" * 50)
    
    client_id = input("\nEnter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    creds = flow.run_local_server(port=0)
    
    print("\n" + "=" * 50)
    print("SUCCESS! Copy this refresh token:")
    print("=" * 50)
    print(f"\n{creds.refresh_token}\n")
    print("=" * 50)
    print("\nAdd this to your Replit Secrets as:")
    print("GOOGLE_REFRESH_TOKEN")
    print("=" * 50)

if __name__ == "__main__":
    get_refresh_token()
