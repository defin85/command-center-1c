package django

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNewClient(t *testing.T) {
	tests := []struct {
		name     string
		baseURL  string
		wantURL  string
	}{
		{
			name:    "with custom URL",
			baseURL: "http://example.com:8000",
			wantURL: "http://example.com:8000",
		},
		{
			name:    "with default URL",
			baseURL: "",
			wantURL: "http://localhost:8200",
		},
		{
			name:    "with https URL",
			baseURL: "https://api.example.com",
			wantURL: "https://api.example.com",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			client := NewClient(tt.baseURL)
			assert.NotNil(t, client)
			assert.Equal(t, tt.wantURL, client.baseURL)
			assert.NotNil(t, client.httpClient)
			assert.Equal(t, 30*time.Second, client.httpClient.Timeout)
		})
	}
}

func TestNewClient_DefaultTimeout(t *testing.T) {
	client := NewClient("")
	assert.Equal(t, 30*time.Second, client.httpClient.Timeout)
}

func TestCallbackPayload_Marshaling(t *testing.T) {
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
		ErrorMessage:    "",
	}

	jsonData, err := json.Marshal(payload)
	assert.NoError(t, err)

	// Verify we can unmarshal it back
	var decoded CallbackPayload
	err = json.Unmarshal(jsonData, &decoded)
	assert.NoError(t, err)
	assert.Equal(t, payload.DatabaseID, decoded.DatabaseID)
	assert.Equal(t, payload.ExtensionName, decoded.ExtensionName)
	assert.Equal(t, payload.Status, decoded.Status)
	assert.Equal(t, payload.DurationSeconds, decoded.DurationSeconds)
}

func TestCallbackPayload_WithError(t *testing.T) {
	payload := CallbackPayload{
		DatabaseID:    "test-db-id",
		ExtensionName: "TestExt",
		Status:        "failed",
		ErrorMessage:  "Extension not found",
	}

	jsonData, err := json.Marshal(payload)
	assert.NoError(t, err)

	var decoded CallbackPayload
	err = json.Unmarshal(jsonData, &decoded)
	assert.NoError(t, err)
	assert.Equal(t, "failed", decoded.Status)
	assert.Equal(t, "Extension not found", decoded.ErrorMessage)
}

func TestClient_NotifyInstallationComplete_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request method and path
		assert.Equal(t, "POST", r.Method)
		assert.Equal(t, "/api/v1/extensions/installation/callback/", r.URL.Path)

		// Verify content type
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

		// Parse request body
		var payload CallbackPayload
		err := json.NewDecoder(r.Body).Decode(&payload)
		assert.NoError(t, err)

		// Verify payload
		assert.Equal(t, "test-db-id", payload.DatabaseID)
		assert.Equal(t, "TestExt", payload.ExtensionName)
		assert.Equal(t, "completed", payload.Status)
		assert.Equal(t, 45.5, payload.DurationSeconds)

		// Return success
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_Created(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]string{"status": "created"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal server error"))
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "status 500")
}

func TestClient_NotifyInstallationComplete_BadRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte("Bad request"))
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "status 400")
}

func TestClient_NotifyInstallationComplete_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte("Unauthorized"))
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "status 401")
}

func TestClient_NotifyInstallationComplete_FailedStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload CallbackPayload
		json.NewDecoder(r.Body).Decode(&payload)

		assert.Equal(t, "failed", payload.Status)
		assert.NotEmpty(t, payload.ErrorMessage)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "failed",
		ErrorMessage:    "Operation timeout",
		DurationSeconds: 120.0,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_ConnectionError(t *testing.T) {
	// Use an invalid address that will cause connection error
	client := NewClient("http://localhost:1")

	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed")
}

func TestClient_NotifyInstallationComplete_Timeout(t *testing.T) {
	// Create a server that doesn't respond quickly
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second) // Sleep longer than timeout
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// Create client with short timeout
	client := NewClient(server.URL)
	client.httpClient.Timeout = 100 * time.Millisecond

	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed")
}

func TestClient_NotifyInstallationComplete_InvalidJSON(t *testing.T) {
	// This test verifies that payload marshaling works correctly
	// CallbackPayload should always be serializable

	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	jsonData, err := json.Marshal(payload)
	assert.NoError(t, err)
	assert.NotEmpty(t, jsonData)
}

func TestClient_NotifyInstallationComplete_EmptyErrorMessage(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload CallbackPayload
		err := json.NewDecoder(r.Body).Decode(&payload)
		assert.NoError(t, err)

		// Verify empty error message is handled
		assert.Equal(t, "", payload.ErrorMessage)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_SpecialCharactersInPayload(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload CallbackPayload
		json.NewDecoder(r.Body).Decode(&payload)

		// Verify special characters are preserved
		assert.Equal(t, "БД_тест", payload.DatabaseID)
		assert.Equal(t, "Расширение#1", payload.ExtensionName)
		assert.Equal(t, "Ошибка: таймаут", payload.ErrorMessage)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "БД_тест",
		ExtensionName:   "Расширение#1",
		Status:          "failed",
		ErrorMessage:    "Ошибка: таймаут",
		DurationSeconds: 60.0,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_LongExtensionName(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)

	longName := "VeryLongExtensionNameWithManyCharacters_" + string(make([]byte, 500))
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   longName,
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_VerifyURL(t *testing.T) {
	expectedURL := "/api/v1/extensions/installation/callback/"

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, expectedURL, r.URL.Path)
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_VerifyContentType(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_ReadResponseBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify that the request body is fully read
		body, err := io.ReadAll(r.Body)
		assert.NoError(t, err)
		assert.NotEmpty(t, body)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_ZeroDuration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload CallbackPayload
		json.NewDecoder(r.Body).Decode(&payload)
		assert.Equal(t, 0.0, payload.DurationSeconds)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 0.0,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

func TestClient_NotifyInstallationComplete_VeryLargeDuration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload CallbackPayload
		json.NewDecoder(r.Body).Decode(&payload)
		assert.Equal(t, 999999.99, payload.DurationSeconds)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 999999.99,
	}

	err := client.NotifyInstallationComplete(payload)
	assert.NoError(t, err)
}

// BenchmarkNotifyInstallationComplete benchmarks the callback notification
func BenchmarkNotifyInstallationComplete(b *testing.B) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer server.Close()

	client := NewClient(server.URL)
	payload := CallbackPayload{
		DatabaseID:      "test-db-id",
		ExtensionName:   "TestExt",
		Status:          "completed",
		DurationSeconds: 45.5,
	}

	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_ = client.NotifyInstallationComplete(payload)
	}
}
