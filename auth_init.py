from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET_FILE = BASE_DIR / "oauth_client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"


def main():
    print("🚀 AUTH SCRIPT STARTED")

    creds = None

    # 1. Load existing token
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(TOKEN_FILE), SCOPES
            )
            print("✅ Loaded existing token")
        except Exception as e:
            print("❌ Token load failed:", e)
            creds = None

    # 2. Refresh token safely
    if creds and creds.refresh_token:
        try:
            if creds.expired or not creds.valid:
                creds.refresh(Request())
                print("🔄 Token refreshed")
        except Exception as e:
            print("❌ Refresh failed:", e)
            creds = None

    # 3. If invalid → re-auth
    if not creds or not creds.valid:
        print("🔐 Starting OAuth login flow...")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE),
            SCOPES
        )

        creds = flow.run_local_server(
            host="localhost",
            port=8080,
            open_browser=True
        )

        print("✅ OAuth completed")

    # 4. Save token
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print("💾 Saved token to:", TOKEN_FILE)


if __name__ == "__main__":
    main()