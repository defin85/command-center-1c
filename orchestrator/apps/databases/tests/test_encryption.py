"""
Unit tests для credentials encryption/decryption module.

Tests:
- Encryption/decryption roundtrip
- Payload format validation
- TTL expiration
- Invalid key handling
- Tampered data detection
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import override_settings
import base64

from apps.databases.encryption import (
    encrypt_credentials_for_transport,
    decrypt_credentials_from_transport,
    _get_transport_key,
)

VALID_TRANSPORT_KEY_HEX = "0123456789abcdef" * 4  # 64 hex chars (32 bytes)


@pytest.fixture
def sample_credentials():
    """Sample credentials для тестирования"""
    return {
        "database_id": "test-db-123",
        "odata_url": "http://localhost/odata",
        "username": "TestUser",
        "password": "SuperSecret123",
        "server_address": "localhost",
        "server_port": 1541,
        "infobase_name": "TestBase",
    }


@pytest.mark.django_db
@override_settings(CREDENTIALS_TRANSPORT_KEY=VALID_TRANSPORT_KEY_HEX)
class TestCredentialsEncryption:
    """Tests для credentials encryption module"""

    def test_encrypt_decrypt_roundtrip(self, sample_credentials):
        """Test что encryption → decryption возвращает original data"""
        # Encrypt
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Verify encrypted payload structure
        assert "encrypted_data" in encrypted
        assert "nonce" in encrypted
        assert "expires_at" in encrypted
        assert "encryption_version" in encrypted
        assert encrypted["encryption_version"] == "aes-gcm-256-v1"

        # Decrypt
        decrypted = decrypt_credentials_from_transport(encrypted)

        # Verify roundtrip
        assert decrypted == sample_credentials

    def test_encrypted_payload_format(self, sample_credentials):
        """Test формат encrypted payload"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Verify all fields present
        assert "encrypted_data" in encrypted
        assert "nonce" in encrypted
        assert "expires_at" in encrypted
        assert "encryption_version" in encrypted

        # Verify base64 encoding (должен decode без ошибок)
        base64.b64decode(encrypted["encrypted_data"])
        base64.b64decode(encrypted["nonce"])

        # Verify nonce size (12 bytes для GCM)
        nonce = base64.b64decode(encrypted["nonce"])
        assert len(nonce) == 12

        # Verify encryption version
        assert encrypted["encryption_version"] == "aes-gcm-256-v1"

        # Verify expires_at is ISO8601 timestamp
        expires_at = timezone.datetime.fromisoformat(encrypted["expires_at"])
        assert expires_at > timezone.now()

    def test_ttl_expiration(self, sample_credentials):
        """Test что expired payload не может быть decrypted"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Вручную изменить expires_at на прошлое
        past_time = timezone.now() - timedelta(minutes=10)
        encrypted["expires_at"] = past_time.isoformat()

        # Должен выбросить ошибку при decryption
        with pytest.raises(ValueError, match="expired"):
            decrypt_credentials_from_transport(encrypted)

    def test_tampered_ciphertext(self, sample_credentials):
        """Test что tampered ciphertext детектируется"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Изменить ciphertext (flip one bit)
        ciphertext_bytes = base64.b64decode(encrypted["encrypted_data"])
        tampered_bytes = bytearray(ciphertext_bytes)
        tampered_bytes[0] ^= 0x01  # Flip first bit
        encrypted["encrypted_data"] = base64.b64encode(bytes(tampered_bytes)).decode()

        # Должен выбросить ошибку при decryption (authentication tag verification failed)
        with pytest.raises(Exception):
            decrypt_credentials_from_transport(encrypted)

    def test_tampered_nonce(self, sample_credentials):
        """Test что tampered nonce детектируется"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Изменить nonce
        nonce_bytes = base64.b64decode(encrypted["nonce"])
        tampered_nonce = bytearray(nonce_bytes)
        tampered_nonce[0] ^= 0x01  # Flip first bit
        encrypted["nonce"] = base64.b64encode(bytes(tampered_nonce)).decode()

        # Должен выбросить ошибку при decryption
        with pytest.raises(Exception):
            decrypt_credentials_from_transport(encrypted)

    def test_invalid_encryption_version(self, sample_credentials):
        """Test что unsupported encryption version детектируется"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Изменить encryption version
        encrypted["encryption_version"] = "aes-gcm-128-v2"

        # Должен выбросить ошибку
        with pytest.raises(ValueError, match="Unsupported encryption version"):
            decrypt_credentials_from_transport(encrypted)

    def test_missing_required_fields(self, sample_credentials):
        """Test что missing required fields детектируются"""
        encrypted = encrypt_credentials_for_transport(sample_credentials)

        # Remove each field and test
        required_fields = ["encrypted_data", "nonce", "expires_at", "encryption_version"]
        for field in required_fields:
            incomplete = encrypted.copy()
            del incomplete[field]

            with pytest.raises(ValueError, match=f"Missing required field: {field}"):
                decrypt_credentials_from_transport(incomplete)

    @override_settings(CREDENTIALS_TRANSPORT_KEY="00" * 31)
    def test_short_key_rejected(self, sample_credentials):
        """Test что слишком короткий ключ отвергается"""
        with pytest.raises(ValueError, match="too short"):
            encrypt_credentials_for_transport(sample_credentials)

    @override_settings(CREDENTIALS_TRANSPORT_KEY="not-hex!!!")
    def test_invalid_hex_key_rejected(self, sample_credentials):
        """Test что не-hex ключ отвергается"""
        with pytest.raises(ValueError, match="hex-encoded"):
            encrypt_credentials_for_transport(sample_credentials)

    def test_unique_nonce_per_encryption(self, sample_credentials):
        """Test что каждый encryption использует unique nonce (forward secrecy)"""
        encrypted1 = encrypt_credentials_for_transport(sample_credentials)
        encrypted2 = encrypt_credentials_for_transport(sample_credentials)

        # Nonce должен быть разным
        assert encrypted1["nonce"] != encrypted2["nonce"]

        # Ciphertext тоже должен быть разным (даже для одинаковых credentials)
        assert encrypted1["encrypted_data"] != encrypted2["encrypted_data"]

        # Но оба должны decrypt в одинаковые credentials
        decrypted1 = decrypt_credentials_from_transport(encrypted1)
        decrypted2 = decrypt_credentials_from_transport(encrypted2)
        assert decrypted1 == decrypted2 == sample_credentials

    def test_transport_key_validation(self):
        """Test что transport key правильно загружается из settings"""
        key = _get_transport_key()

        # Должен быть 32 bytes для AES-256
        assert len(key) == 32

        # Должен быть bytes
        assert isinstance(key, bytes)

    def test_large_credentials_payload(self):
        """Test что large credentials payload корректно обрабатывается"""
        large_credentials = {
            "database_id": "test-db-123",
            "odata_url": "http://localhost/odata",
            "username": "VeryLongUsername" * 10,
            "password": "VeryLongPassword" * 10,
            "server_address": "very.long.hostname.example.com",
            "server_port": 1541,
            "infobase_name": "VeryLongInfobaseName" * 10,
            # Add extra metadata
            "metadata": {
                "description": "Lorem ipsum dolor sit amet" * 50,
                "tags": ["tag1", "tag2", "tag3"] * 100,
            }
        }

        # Should still work
        encrypted = encrypt_credentials_for_transport(large_credentials)
        decrypted = decrypt_credentials_from_transport(encrypted)
        assert decrypted == large_credentials
