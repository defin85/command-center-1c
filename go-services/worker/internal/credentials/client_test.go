// worker/internal/credentials/client_test.go
package credentials

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClient_Fetch_Success(t *testing.T) {
	// Test key (32 bytes for AES-256)
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}

	// Create encrypted payload
	creds := &DatabaseCredentials{
		DatabaseID: "db-123",
		ODataURL:   "http://localhost/odata",
		Username:   "admin",
		Password:   "secret",
	}

	encResp, err := EncryptCredentials(creds, testKey)
	if err != nil {
		t.Fatalf("failed to encrypt credentials: %v", err)
	}

	// Mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer test-api-key" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(encResp)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key", testKey)

	fetchedCreds, err := client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if fetchedCreds.DatabaseID != "db-123" {
		t.Errorf("expected database_id db-123, got %s", fetchedCreds.DatabaseID)
	}
	if fetchedCreds.Password != "secret" {
		t.Errorf("expected password secret, got %s", fetchedCreds.Password)
	}
}

func TestClient_Fetch_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer server.Close()

	testKey := make([]byte, 32)
	client := NewClient(server.URL, "invalid-key", testKey)

	_, err := client.Fetch(context.Background(), "db-123")
	if err == nil {
		t.Fatal("expected error for unauthorized request")
	}

	if err.Error() != "authentication failed: invalid API key" {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestClient_Fetch_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	testKey := make([]byte, 32)
	client := NewClient(server.URL, "test-api-key", testKey)

	_, err := client.Fetch(context.Background(), "db-nonexistent")
	if err == nil {
		t.Fatal("expected error for not found database")
	}

	expectedErr := "database db-nonexistent not found"
	if err.Error() != expectedErr {
		t.Errorf("expected error %q, got %q", expectedErr, err.Error())
	}
}

func TestClient_Fetch_Cache(t *testing.T) {
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++

		creds := &DatabaseCredentials{
			DatabaseID: "db-123",
			ODataURL:   "http://localhost",
			Username:   "admin",
			Password:   "secret",
		}

		encResp, err := EncryptCredentials(creds, testKey)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(encResp)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key", testKey)

	// First call - should hit API
	_, err := client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("fetch failed: %v", err)
	}

	// Second call - should use cache
	_, err = client.Fetch(context.Background(), "db-123")
	if err != nil {
		t.Fatalf("fetch failed: %v", err)
	}

	if callCount != 1 {
		t.Errorf("expected 1 API call, got %d", callCount)
	}
}

func TestClient_Fetch_CacheExpiry(t *testing.T) {
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++

		creds := &DatabaseCredentials{
			DatabaseID: "db-123",
			ODataURL:   "http://localhost",
			Username:   "admin",
			Password:   "secret",
		}

		encResp, err := EncryptCredentials(creds, testKey)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(encResp)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key", testKey)
	client.cacheTTL = 100 * time.Millisecond // Short TTL for test

	// First call
	_, _ = client.Fetch(context.Background(), "db-123")

	// Wait for cache expiry
	time.Sleep(150 * time.Millisecond)

	// Second call - should hit API again
	_, _ = client.Fetch(context.Background(), "db-123")

	if callCount != 2 {
		t.Errorf("expected 2 API calls, got %d", callCount)
	}
}

func TestClient_ClearCache(t *testing.T) {
	testKey := make([]byte, 32)
	for i := range testKey {
		testKey[i] = byte(i)
	}

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++

		creds := &DatabaseCredentials{
			DatabaseID: "db-123",
			ODataURL:   "http://localhost",
			Username:   "admin",
			Password:   "secret",
		}

		encResp, err := EncryptCredentials(creds, testKey)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(encResp)
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-api-key", testKey)

	// First call
	_, _ = client.Fetch(context.Background(), "db-123")

	// Clear cache
	client.ClearCache()

	// Second call - should hit API again (cache was cleared)
	_, _ = client.Fetch(context.Background(), "db-123")

	if callCount != 2 {
		t.Errorf("expected 2 API calls after cache clear, got %d", callCount)
	}
}
