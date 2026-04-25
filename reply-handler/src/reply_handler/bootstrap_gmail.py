"""One-time setup: opens a browser to authorize reply-handler to read Gmail
threads and create in-thread drafts. Writes the resulting refresh token to
disk. This is a SEPARATE token from outreach-agent's because the scope is
broader (gmail.modify vs gmail.compose)."""

from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Config
from .gmail_client import GMAIL_SCOPES


def main() -> int:
    cfg = Config.from_env()

    if not cfg.gmail_credentials_path.exists():
        print(
            f"ERROR: OAuth client credentials not found at "
            f"{cfg.gmail_credentials_path}.\n"
            f"Create an OAuth client (type: Desktop App) in Google Cloud Console "
            f"named 'reply-handler', download the JSON, and save it to that path.",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(
        str(cfg.gmail_credentials_path), GMAIL_SCOPES
    )
    creds = flow.run_local_server(port=0, open_browser=True)
    cfg.gmail_token_path.write_text(creds.to_json())
    print(f"✓ Gmail token saved to {cfg.gmail_token_path}")
    print("You can now run: uv run python -m reply_handler all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
