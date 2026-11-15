#!/usr/bin/env python3
"""Print a new Fernet key for the encrypted local Gmail SQLite store.

Save the command in a password manager or secure local secret manager. Do not commit the key.
"""

from cryptography.fernet import Fernet


def main() -> None:
    key = Fernet.generate_key().decode("utf-8")
    print("Copy this command into the terminal that will run the Gmail tool:")
    print(f"export GMAIL_TOKEN_ENCRYPTION_KEY='{key}'")


if __name__ == "__main__":
    main()
