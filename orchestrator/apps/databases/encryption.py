"""
AES-GCM encryption для transport credentials между сервисами.

Security Architecture:
- At Rest: PostgreSQL EncryptedCharField (django-encrypted-model-fields)
- In Transit: TLS 1.3 (to be implemented in Phase 2)
- In Payload: AES-GCM-256 (this module) - defense in depth
- In Memory: Encrypted cache в Worker

Encryption Flow:
1. Orchestrator: encrypt_credentials_for_transport() -> encrypted payload
2. Worker: DecryptCredentials() in Go -> plaintext credentials
3. Worker: Use credentials -> discard immediately

Version: v1.0.0
"""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
import os
import base64
import json
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Transport encryption key (32 bytes для AES-256)
# ВАЖНО: ДОЛЖЕН совпадать между Django и Go Worker!
TRANSPORT_KEY_BYTES = 32  # AES-256


def _get_transport_key() -> bytes:
    """
    Получить transport encryption key из settings.

    Raises:
        ValueError: если ключ не установлен или некорректный
    """
    key_str = getattr(settings, 'CREDENTIALS_TRANSPORT_KEY', None)

    if not key_str:
        raise ValueError(
            "CREDENTIALS_TRANSPORT_KEY not set in Django settings. "
            "Add to .env.local: CREDENTIALS_TRANSPORT_KEY=<64+ hex chars (32+ bytes)>"
        )

    try:
        key_bytes = bytes.fromhex(key_str)
    except ValueError as e:
        raise ValueError(
            "CREDENTIALS_TRANSPORT_KEY invalid: must be hex-encoded "
            "(64+ hex chars = 32+ bytes). Generate with: openssl rand -hex 32"
        ) from e

    if len(key_bytes) < TRANSPORT_KEY_BYTES:
        raise ValueError(
            f"CREDENTIALS_TRANSPORT_KEY too short ({len(key_bytes)} bytes), "
            f"need {TRANSPORT_KEY_BYTES} bytes (64+ hex chars)"
        )

    # Truncate to exactly 32 bytes for AES-256 (Go side does the same)
    return key_bytes[:TRANSPORT_KEY_BYTES]


def encrypt_credentials_for_transport(credentials_dict: dict) -> dict:
    """
    Encrypt credentials dictionary для безопасной передачи между сервисами.

    Uses AES-GCM-256 with random nonce для forward secrecy.

    Security Properties:
    - Authenticated Encryption (integrity + confidentiality)
    - Unique nonce per encryption (forward secrecy)
    - Short TTL (5 minutes) для defense against replay attacks

    Args:
        credentials_dict: Dictionary с чувствительными данными:
            {
                "database_id": "uuid",
                "odata_url": "http://...",
                "username": "user",
                "password": "secret",
                "server_address": "...",
                "server_port": 1541,
                "infobase_name": "..."
            }

    Returns:
        Dictionary с encrypted payload:
        {
            "encrypted_data": "base64(...)",
            "nonce": "base64(...)",
            "expires_at": "ISO8601 timestamp",
            "encryption_version": "aes-gcm-256-v1"
        }

    Raises:
        ValueError: если transport key не установлен
        Exception: если encryption failed
    """
    try:
        # Get transport key
        key = _get_transport_key()

        # Create AES-GCM cipher
        aesgcm = AESGCM(key)

        # Generate random nonce (12 bytes для GCM mode)
        nonce = os.urandom(12)

        # Serialize credentials to JSON
        plaintext = json.dumps(credentials_dict).encode('utf-8')

        # Encrypt using AES-GCM (authenticated encryption)
        # No additional authenticated data (AAD) needed
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # Calculate expiration (5 minutes from now)
        expires_at = timezone.now() + timedelta(minutes=5)

        # Return encrypted payload
        result = {
            "encrypted_data": base64.b64encode(ciphertext).decode('utf-8'),
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "expires_at": expires_at.isoformat(),
            "encryption_version": "aes-gcm-256-v1"
        }

        logger.info(
            "credentials encrypted for transport",
            extra={
                "database_id": credentials_dict.get("database_id"),
                "encryption_version": result["encryption_version"],
                "expires_at": result["expires_at"],
                "ciphertext_size": len(ciphertext),
            }
        )

        return result

    except Exception as e:
        logger.error(f"Failed to encrypt credentials: {e}", exc_info=True)
        raise


def decrypt_credentials_from_transport(encrypted_payload: dict) -> dict:
    """
    Decrypt credentials payload (для тестирования в Python).

    В production Worker будет декодировать на Go стороне.

    Args:
        encrypted_payload: Dictionary from encrypt_credentials_for_transport()

    Returns:
        Original credentials dictionary (plaintext)

    Raises:
        ValueError: если payload некорректный или истек TTL
        Exception: если decryption failed (wrong key, tampered data)
    """
    try:
        # Validate required fields
        required_fields = ["encrypted_data", "nonce", "expires_at", "encryption_version"]
        for field in required_fields:
            if field not in encrypted_payload:
                raise ValueError(f"Missing required field: {field}")

        # Check expiration
        expires_at = timezone.datetime.fromisoformat(encrypted_payload["expires_at"])
        if timezone.now() > expires_at:
            raise ValueError("Encrypted payload expired (TTL exceeded)")

        # Validate encryption version
        if encrypted_payload["encryption_version"] != "aes-gcm-256-v1":
            raise ValueError(
                f"Unsupported encryption version: {encrypted_payload['encryption_version']}"
            )

        # Decode base64
        ciphertext = base64.b64decode(encrypted_payload["encrypted_data"])
        nonce = base64.b64decode(encrypted_payload["nonce"])

        # Get transport key
        key = _get_transport_key()

        # Create AES-GCM cipher
        aesgcm = AESGCM(key)

        # Decrypt using AES-GCM
        # Will raise exception if authentication tag verification fails (tampered data)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        # Parse JSON
        credentials = json.loads(plaintext.decode('utf-8'))

        logger.info(
            "credentials decrypted from transport",
            extra={
                "database_id": credentials.get("database_id"),
                "encryption_version": encrypted_payload["encryption_version"],
            }
        )

        return credentials

    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {e}", exc_info=True)
        raise
