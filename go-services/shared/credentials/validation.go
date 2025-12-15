// go-services/shared/credentials/validation.go
package credentials

import (
	"encoding/hex"
	"fmt"
)

const (
	// MinKeySize is the minimum key size for AES-256 encryption
	MinKeySize = 32
)

// ValidateTransportKey validates and decodes a hex-encoded transport key.
// Returns the decoded key (truncated to exactly 32 bytes for AES-256) or an error.
//
// Security Requirements:
//   - Key must be hex-encoded (64+ hex characters for 32+ bytes)
//   - Key must be at least 32 bytes after decoding
//   - Returns exactly 32 bytes (truncates longer keys)
//
// Usage:
//
//	transportKey, err := credentials.ValidateTransportKey(cfg.CredentialsTransportKey)
//	if err != nil {
//	    log.Fatal("CREDENTIALS_TRANSPORT_KEY invalid: ", err)
//	}
func ValidateTransportKey(hexKey string) ([]byte, error) {
	if hexKey == "" {
		return nil, fmt.Errorf("transport key is required")
	}

	key, err := hex.DecodeString(hexKey)
	if err != nil {
		return nil, fmt.Errorf("invalid hex encoding: %w", err)
	}

	if len(key) < MinKeySize {
		return nil, fmt.Errorf("key too short: %d bytes (need %d)", len(key), MinKeySize)
	}

	// Truncate to exactly 32 bytes for AES-256
	return key[:MinKeySize], nil
}

// MustValidateTransportKey is like ValidateTransportKey but panics on error.
// Use only in initialization code where failure is fatal.
func MustValidateTransportKey(hexKey string) []byte {
	key, err := ValidateTransportKey(hexKey)
	if err != nil {
		panic(fmt.Sprintf("invalid transport key: %v", err))
	}
	return key
}
