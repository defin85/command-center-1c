// go-services/shared/credentials/encryption.go
package credentials

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"time"
)

const (
	// AES-256 requires 32 bytes key
	aesKeySize = 32

	// Expected encryption version
	encryptionVersionV1 = "aes-gcm-256-v1"
)

// DecryptCredentials decrypts AES-GCM encrypted credentials payload from Django Orchestrator.
//
// Security Properties:
// - Authenticated Encryption (integrity + confidentiality)
// - Forward secrecy (unique nonce per encryption)
// - TTL validation (5 minutes expiration)
//
// Args:
//   - resp: Encrypted payload from Django Orchestrator
//   - transportKey: 32-byte AES-256 key (MUST match Django CREDENTIALS_TRANSPORT_KEY)
//
// Returns:
//   - Decrypted credentials or error
//
// Errors:
//   - Invalid encryption version
//   - Expired payload (TTL exceeded)
//   - Invalid base64 encoding
//   - Decryption failed (wrong key or tampered data)
func DecryptCredentials(resp EncryptedCredentialsResponse, transportKey []byte) (*DatabaseCredentials, error) {
	// Validate encryption version
	if resp.EncryptionVersion != encryptionVersionV1 {
		return nil, fmt.Errorf(
			"unsupported encryption version: %s (expected: %s)",
			resp.EncryptionVersion,
			encryptionVersionV1,
		)
	}

	// Parse expiration timestamp
	expiresAt, err := time.Parse(time.RFC3339, resp.ExpiresAt)
	if err != nil {
		return nil, fmt.Errorf("failed to parse expires_at: %w", err)
	}

	// Check TTL (should be < 5 minutes from current time)
	if time.Now().After(expiresAt) {
		return nil, fmt.Errorf("credentials payload expired (TTL exceeded)")
	}

	// Decode base64 ciphertext
	ciphertext, err := base64.StdEncoding.DecodeString(resp.EncryptedData)
	if err != nil {
		return nil, fmt.Errorf("failed to decode ciphertext: %w", err)
	}

	// Decode base64 nonce
	nonce, err := base64.StdEncoding.DecodeString(resp.Nonce)
	if err != nil {
		return nil, fmt.Errorf("failed to decode nonce: %w", err)
	}

	// Validate nonce size (12 bytes for GCM mode)
	if len(nonce) != 12 {
		return nil, fmt.Errorf("invalid nonce size: %d bytes (expected 12)", len(nonce))
	}

	// Validate transport key size (32 bytes for AES-256)
	if len(transportKey) < aesKeySize {
		return nil, fmt.Errorf(
			"transport key too short: %d bytes (expected %d)",
			len(transportKey),
			aesKeySize,
		)
	}

	// Use first 32 bytes of transport key (for AES-256)
	key := transportKey[:aesKeySize]

	// Create AES cipher block
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("failed to create AES cipher: %w", err)
	}

	// Create GCM mode
	aesGcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to create GCM mode: %w", err)
	}

	// Decrypt and verify authentication tag
	// Will return error if:
	// - Wrong key
	// - Tampered ciphertext
	// - Tampered nonce
	plaintext, err := aesGcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		// Security: Don't expose underlying crypto error details
		return nil, fmt.Errorf("decryption failed: authentication check failed")
	}

	// Parse JSON credentials
	var creds DatabaseCredentials
	if err := json.Unmarshal(plaintext, &creds); err != nil {
		return nil, fmt.Errorf("failed to parse credentials JSON: %w", err)
	}

	// Success: return decrypted credentials
	return &creds, nil
}

// EncryptCredentials encrypts credentials for testing purposes.
// Used by tests to create properly encrypted payloads.
func EncryptCredentials(creds *DatabaseCredentials, transportKey []byte) (*EncryptedCredentialsResponse, error) {
	// Validate transport key size (32 bytes for AES-256)
	if len(transportKey) < aesKeySize {
		return nil, fmt.Errorf(
			"transport key too short: %d bytes (expected %d)",
			len(transportKey),
			aesKeySize,
		)
	}

	// Use first 32 bytes of transport key (for AES-256)
	key := transportKey[:aesKeySize]

	// Create AES cipher block
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("failed to create AES cipher: %w", err)
	}

	// Create GCM mode
	aesGcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("failed to create GCM mode: %w", err)
	}

	// Generate random 12-byte nonce
	nonce := make([]byte, aesGcm.NonceSize())
	_, err = io.ReadFull(rand.Reader, nonce)
	if err != nil {
		return nil, fmt.Errorf("failed to generate nonce: %w", err)
	}

	// Marshal credentials to JSON
	plaintext, err := json.Marshal(creds)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal credentials: %w", err)
	}

	// Encrypt and authenticate
	ciphertext := aesGcm.Seal(nil, nonce, plaintext, nil)

	// Create response with encrypted data
	resp := &EncryptedCredentialsResponse{
		EncryptedData:     base64.StdEncoding.EncodeToString(ciphertext),
		Nonce:             base64.StdEncoding.EncodeToString(nonce),
		EncryptionVersion: encryptionVersionV1,
		ExpiresAt:         time.Now().Add(5 * time.Minute).Format(time.RFC3339),
	}

	return resp, nil
}
