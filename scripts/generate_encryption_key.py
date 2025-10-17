#!/usr/bin/env python
"""
Generate encryption key for django-encrypted-model-fields.

Usage:
    python scripts/generate_encryption_key.py
"""

from cryptography.fernet import Fernet


def generate_key():
    """Generate a new Fernet encryption key."""
    key = Fernet.generate_key()
    print("=" * 70)
    print("🔐 ENCRYPTION KEY GENERATED")
    print("=" * 70)
    print(f"\nAdd this to your .env file:\n")
    print(f"DB_ENCRYPTION_KEY={key.decode()}")
    print(f"\n⚠️  IMPORTANT: Keep this key secure and never commit it to git!")
    print("=" * 70)


if __name__ == '__main__':
    generate_key()
