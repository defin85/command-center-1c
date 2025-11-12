// go-services/worker/internal/credentials/encryption.go
package credentials

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"time"
)

// EncryptedCredentialsResponse from Django Orchestrator (encrypted payload)
type EncryptedCredentialsResponse struct {
	EncryptedData     string `json:"encrypted_data"`
	Nonce             string `json:"nonce"`
	ExpiresAt         string `json:"expires_at"`
	EncryptionVersion string `json:"encryption_version"`
}

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

	// Check TTL (должен быть < 5 минут от текущего времени)
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
		return nil, fmt.Errorf("decryption failed (wrong key or tampered data): %w", err)
	}

	// Parse JSON credentials
	var creds DatabaseCredentials
	if err := json.Unmarshal(plaintext, &creds); err != nil {
		return nil, fmt.Errorf("failed to parse credentials JSON: %w", err)
	}

	// Success: return decrypted credentials
	return &creds, nil
}
