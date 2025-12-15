// go-services/shared/credentials/validation_test.go
package credentials

import (
	"encoding/hex"
	"testing"
)

func TestValidateTransportKey_Success(t *testing.T) {
	// 32 bytes = 64 hex chars
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}
	hexKey := hex.EncodeToString(testKey)

	result, err := ValidateTransportKey(hexKey)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if len(result) != 32 {
		t.Errorf("expected 32 bytes, got %d", len(result))
	}

	// Verify content matches
	for i := 0; i < 32; i++ {
		if result[i] != testKey[i] {
			t.Errorf("byte %d mismatch: expected %d, got %d", i, testKey[i], result[i])
		}
	}
}

func TestValidateTransportKey_TruncatesToExact32Bytes(t *testing.T) {
	// 64 bytes = 128 hex chars (longer than needed)
	testKey := make([]byte, 64)
	for i := range testKey {
		testKey[i] = byte(i)
	}
	hexKey := hex.EncodeToString(testKey)

	result, err := ValidateTransportKey(hexKey)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if len(result) != 32 {
		t.Errorf("expected 32 bytes (truncated), got %d", len(result))
	}

	// Verify first 32 bytes match
	for i := 0; i < 32; i++ {
		if result[i] != testKey[i] {
			t.Errorf("byte %d mismatch: expected %d, got %d", i, testKey[i], result[i])
		}
	}
}

func TestValidateTransportKey_EmptyKey(t *testing.T) {
	_, err := ValidateTransportKey("")
	if err == nil {
		t.Fatal("expected error for empty key")
	}

	expectedMsg := "transport key is required"
	if err.Error() != expectedMsg {
		t.Errorf("expected error %q, got %q", expectedMsg, err.Error())
	}
}

func TestValidateTransportKey_InvalidHex(t *testing.T) {
	_, err := ValidateTransportKey("not-valid-hex!")
	if err == nil {
		t.Fatal("expected error for invalid hex")
	}

	// Should contain "invalid hex encoding"
	if err.Error()[:20] != "invalid hex encoding" {
		t.Errorf("expected error starting with 'invalid hex encoding', got %q", err.Error())
	}
}

func TestValidateTransportKey_TooShort(t *testing.T) {
	// 16 bytes = 32 hex chars (too short for AES-256)
	shortKey := make([]byte, 16)
	hexKey := hex.EncodeToString(shortKey)

	_, err := ValidateTransportKey(hexKey)
	if err == nil {
		t.Fatal("expected error for short key")
	}

	expectedMsg := "key too short: 16 bytes (need 32)"
	if err.Error() != expectedMsg {
		t.Errorf("expected error %q, got %q", expectedMsg, err.Error())
	}
}

func TestMustValidateTransportKey_Success(t *testing.T) {
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}
	hexKey := hex.EncodeToString(testKey)

	// Should not panic
	result := MustValidateTransportKey(hexKey)
	if len(result) != 32 {
		t.Errorf("expected 32 bytes, got %d", len(result))
	}
}

func TestMustValidateTransportKey_Panics(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Error("expected panic for invalid key")
		}
	}()

	MustValidateTransportKey("invalid")
}
