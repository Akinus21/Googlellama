# authorize.py
import os
from pathlib import Path
import dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from akinus_utils.utils.app_details import PROJECT_ROOT
from akinus_utils.utils.logger import log

CREDENTIALS_PATH = PROJECT_ROOT / "data" / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "data" / "token.json"

ALL_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("ALL_SCOPES", "").split(",")

def authorize():
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Missing credentials file at {CREDENTIALS_PATH}")
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        ALL_SCOPES,
    )
    
    creds = flow.run_local_server(port=4100, access_type="offline", prompt="consent")
    
    # Save the credentials for future use
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, "w") as token_file:
        token_file.write(creds.to_json())
    
    print(f"Credentials saved to {TOKEN_PATH}")

def get_credentials(scopes=None):
    scopes = scopes or ALL_SCOPES

    def load_creds():
        return Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)

    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"Missing token file at {TOKEN_PATH}")

    creds = load_creds()

    if not creds.valid:
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, "w") as f:
                    f.write(creds.to_json())
            else:
                raise Exception("No refresh token available.")
        except Exception as e:
            log("ERROR", "google_tools", f"Credential refresh failed: {e}")
            log("INFO", "google_tools", "Attempting to re-authorize via utils/authorize.py")

            # Attempt to re-authorize
            authorize_script = PROJECT_ROOT / "utils" / "authorize.py"
            try:
                import subprocess
                result = subprocess.run(
                    ["python3", str(authorize_script)],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    log("CRITICAL", "google_tools", f"Authorization script failed: {result.stderr.strip()}")
                    raise RuntimeError(f"Authorization failed:\n{result.stderr}")
                else:
                    log("INFO", "google_tools", "Authorization script succeeded. Reloading credentials.")
                    creds = load_creds()
            except Exception as ex:
                raise RuntimeError(f"Authorization process failed: {ex}")

    return creds

if __name__ == "__main__":
    authorize()
