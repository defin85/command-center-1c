// go-services/worker/internal/odata/client_test.go
package odata

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

type transportTraceRecord struct {
	event    string
	metadata map[string]interface{}
}

func TestClient_Create(t *testing.T) {
	// Mock 1C OData server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify method
		if r.Method != "POST" {
			t.Errorf("Expected POST, got %s", r.Method)
		}

		// Verify path
		if r.URL.Path != "/Catalog_Test" {
			t.Errorf("Expected /Catalog_Test, got %s", r.URL.Path)
		}

		// Verify auth
		username, password, ok := r.BasicAuth()
		if !ok || username != "testuser" || password != "testpass" {
			t.Error("Invalid auth")
		}

		// Verify content-type
		contentType := r.Header.Get("Content-Type")
		if contentType != "application/json;odata=nometadata" {
			t.Errorf("Expected application/json;odata=nometadata, got %s", contentType)
		}

		// Read request body
		var reqData map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&reqData); err != nil {
			t.Fatalf("Failed to decode request: %v", err)
		}

		// Verify request data
		if reqData["Name"] != "Test Entity" {
			t.Errorf("Expected Name='Test Entity', got %v", reqData["Name"])
		}

		// Return mock response
		response := map[string]interface{}{
			"Ref_Key": "guid'12345678-1234-1234-1234-123456789012'",
			"Name":    "Test Entity",
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	// Create client
	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth: Auth{
			Username: "testuser",
			Password: "testpass",
		},
	})

	// Test Create
	ctx := context.Background()
	result, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{
		"Name": "Test Entity",
	})

	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	if result["Ref_Key"] != "guid'12345678-1234-1234-1234-123456789012'" {
		t.Errorf("Unexpected Ref_Key: %v", result["Ref_Key"])
	}
}

func TestClient_Create_UnicodeBasicAuthHeader(t *testing.T) {
	username := "ГлавБух"
	password := "пароль"
	expectedAuthorization := "Basic " + base64.StdEncoding.EncodeToString([]byte(username+":"+password))

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("Expected POST, got %s", r.Method)
		}
		if got := r.Header.Get("Authorization"); got != expectedAuthorization {
			t.Errorf("Unexpected Authorization header. got=%q want=%q", got, expectedAuthorization)
		}

		response := map[string]interface{}{
			"Ref_Key": "guid'12345678-1234-1234-1234-123456789012'",
			"Name":    "Unicode Auth Test",
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth: Auth{
			Username: username,
			Password: password,
		},
	})

	ctx := context.Background()
	result, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{
		"Name": "Unicode Auth Test",
	})
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}
	if result["Ref_Key"] != "guid'12345678-1234-1234-1234-123456789012'" {
		t.Errorf("Unexpected Ref_Key: %v", result["Ref_Key"])
	}
}

func TestClient_Create_AuthError(t *testing.T) {
	// Mock server returning 401
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(ODataErrorResponse{
			Error: ODataErrorDetail{
				Code: "AUTH_FAILED",
				Message: ODataErrorMessage{
					Lang:  "ru",
					Value: "Неправильное имя пользователя или пароль",
				},
			},
		}); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth: Auth{
			Username: "wrong",
			Password: "wrong",
		},
	})

	ctx := context.Background()
	_, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{})

	if err == nil {
		t.Fatal("Expected error, got nil")
	}

	odataErr, ok := err.(*ODataError)
	if !ok {
		t.Fatalf("Expected ODataError, got %T", err)
	}

	if odataErr.StatusCode != 401 {
		t.Errorf("Expected status 401, got %d", odataErr.StatusCode)
	}

	if odataErr.IsTransient {
		t.Error("Auth error should not be transient")
	}
}

func TestClient_Create_Retry(t *testing.T) {
	attempts := 0

	// Mock server failing twice, then succeeding
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts <= 2 {
			w.WriteHeader(http.StatusServiceUnavailable) // 503 - transient
			return
		}

		// Success on 3rd attempt
		response := map[string]interface{}{"Ref_Key": "guid'...'"}
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL:       server.URL,
		Auth:          Auth{Username: "test", Password: "test"},
		MaxRetries:    3,
		RetryWaitTime: 10 * time.Millisecond, // Fast retry for testing
	})

	ctx := context.Background()
	result, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{})

	if err != nil {
		t.Fatalf("Expected success after retries, got error: %v", err)
	}

	if attempts != 3 {
		t.Errorf("Expected 3 attempts, got %d", attempts)
	}

	if result["Ref_Key"] != "guid'...'" {
		t.Error("Invalid result")
	}
}

func TestClient_Create_TransportTraceIncludesRetryAndResendAttempt(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts == 1 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		response := map[string]interface{}{"Ref_Key": "guid'abc'"}
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Fatalf("encode response: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL:       server.URL,
		Auth:          Auth{Username: "test", Password: "test"},
		MaxRetries:    2,
		RetryWaitTime: 10 * time.Millisecond,
	})

	records := make([]transportTraceRecord, 0, 4)
	ctx := WithTransportTelemetry(context.Background(), TransportTelemetry{
		Operation:   "pool.publication_odata",
		ExecutionID: "exec-1",
		NodeID:      "publication_odata",
		DatabaseID:  "db-1",
		Entity:      "Document_IntercompanyPoolDistribution",
		Trace: func(_ context.Context, event string, metadata map[string]interface{}) {
			copied := make(map[string]interface{}, len(metadata))
			for key, value := range metadata {
				copied[key] = value
			}
			records = append(records, transportTraceRecord{event: event, metadata: copied})
		},
	})

	_, err := client.Create(ctx, "Catalog_Test", map[string]interface{}{"Name": "Test"})
	if err != nil {
		t.Fatalf("expected successful retry path, got error: %v", err)
	}

	var sawRetryScheduled bool
	var sawResendCompleted bool
	for _, record := range records {
		if record.event == "external.odata.transport.retry.scheduled" {
			sawRetryScheduled = true
			if record.metadata["attempt"] != 1 {
				t.Fatalf("expected retry attempt=1, got %v", record.metadata["attempt"])
			}
			if record.metadata["next_attempt"] != 2 {
				t.Fatalf("expected next_attempt=2, got %v", record.metadata["next_attempt"])
			}
			if record.metadata["transport_operation"] != "pool.publication_odata" {
				t.Fatalf("expected transport_operation=pool.publication_odata, got %v", record.metadata["transport_operation"])
			}
		}
		if record.event == "external.odata.transport.request.completed" && record.metadata["attempt"] == 2 {
			sawResendCompleted = true
			if record.metadata["resend_attempt"] != true {
				t.Fatalf("expected resend_attempt=true, got %v", record.metadata["resend_attempt"])
			}
			if record.metadata["status_class"] != "2xx" {
				t.Fatalf("expected status_class=2xx, got %v", record.metadata["status_class"])
			}
		}
	}

	if !sawRetryScheduled {
		t.Fatal("expected retry scheduled trace event")
	}
	if !sawResendCompleted {
		t.Fatal("expected completed resend attempt trace event")
	}
}

func TestClient_Update(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "PATCH" {
			t.Errorf("Expected PATCH, got %s", r.Method)
		}

		expectedPath := "/Catalog_Test(guid'12345')"
		if r.URL.Path != expectedPath {
			t.Errorf("Expected %s, got %s", expectedPath, r.URL.Path)
		}

		w.WriteHeader(http.StatusNoContent) // PATCH часто возвращает 204
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.Update(ctx, "Catalog_Test", "guid'12345'", map[string]interface{}{
		"Name": "Updated Name",
	})

	if err != nil {
		t.Fatalf("Update failed: %v", err)
	}
}

func TestClient_Delete(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "DELETE" {
			t.Errorf("Expected DELETE, got %s", r.Method)
		}

		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.Delete(ctx, "Catalog_Test", "guid'12345'")

	if err != nil {
		t.Fatalf("Delete failed: %v", err)
	}
}

func TestClient_Query(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("Expected GET, got %s", r.Method)
		}

		// Check query params
		filter := r.URL.Query().Get("$filter")
		if filter != "Name eq 'Test'" {
			t.Errorf("Expected filter 'Name eq 'Test'', got %s", filter)
		}

		top := r.URL.Query().Get("$top")
		if top != "10" {
			t.Errorf("Expected top=10, got %s", top)
		}

		// Return mock data
		response := QueryResponse{
			Value: []map[string]interface{}{
				{"Ref_Key": "guid'1'", "Name": "Entity 1"},
				{"Ref_Key": "guid'2'", "Name": "Entity 2"},
			},
		}
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	results, err := client.Query(ctx, QueryRequest{
		Entity: "Catalog_Test",
		Filter: "Name eq 'Test'",
		Top:    10,
	})

	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}

	if len(results) != 2 {
		t.Errorf("Expected 2 results, got %d", len(results))
	}

	if results[0]["Name"] != "Entity 1" {
		t.Error("Invalid result")
	}
}

func TestClient_Query_WithSelect(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check $select parameter
		selectParam := r.URL.Query().Get("$select")
		if selectParam != "Ref_Key,Name,Code" {
			t.Errorf("Expected select='Ref_Key,Name,Code', got %s", selectParam)
		}

		response := QueryResponse{
			Value: []map[string]interface{}{
				{"Ref_Key": "guid'1'", "Name": "Test", "Code": "001"},
			},
		}
		if err := json.NewEncoder(w).Encode(response); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	results, err := client.Query(ctx, QueryRequest{
		Entity: "Catalog_Test",
		Select: []string{"Ref_Key", "Name", "Code"},
	})

	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}

	if len(results) != 1 {
		t.Errorf("Expected 1 result, got %d", len(results))
	}
}

func TestClient_HealthCheck(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write([]byte(`{"@odata.context": "..."}`)); err != nil {
			t.Errorf("Write response failed: %v", err)
		}
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.HealthCheck(ctx)

	if err != nil {
		t.Errorf("HealthCheck failed: %v", err)
	}
}

func TestClient_HealthCheck_Failure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewClient(ClientConfig{
		BaseURL: server.URL,
		Auth:    Auth{Username: "test", Password: "test"},
	})

	ctx := context.Background()
	err := client.HealthCheck(ctx)

	if err == nil {
		t.Error("Expected HealthCheck to fail")
	}
}
