#!/usr/bin/env python3
"""Start the one-time local Gmail OAuth connection for the representative system."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from role_matching.tools.gmail_candidate_submissions import GmailCredentialStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secrets", type=Path, required=True, help="Downloaded Google OAuth desktop-client JSON")
    # Preserve the identifier of the connection already stored by the initial local setup.
    parser.add_argument("--connection-id", default="demo-applications-mailbox")
    args = parser.parse_args()
    if not args.client_secrets.is_file():
        parser.error(f"No OAuth client JSON found at {args.client_secrets}")
    GmailCredentialStore(connection_id=args.connection_id).connect(args.client_secrets)
    print("Encrypted Gmail credentials stored in local SQLite.")


if __name__ == "__main__":
    main()
