package orchestrator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestClient_GetPendingFailedEvents_Success(t *testing.T) {
	now := time.Now()
	events := []FailedEvent{
		{
			ID:                1,
			Channel:           "cc1c:operations:status",
			EventType:         "operation.status.changed",
			CorrelationID:     "op-123",
			Payload:           map[string]interface{}{"operation_id": "123"},
			SourceService:     "orchestrator",
			OriginalTimestamp: now,
			Status:            "pending",
			RetryCount:        0,
			MaxRetries:        5,
			CreatedAt:         now,
		},
		{
			ID:                2,
			Channel:           "cc1c:operations:status",
			EventType:         "operation.completed",
			CorrelationID:     "op-456",
			Payload:           map[string]interface{}{"operation_id": "456"},
			SourceService:     "orchestrator",
			OriginalTimestamp: now,
			Status:            "pending",
			RetryCount:        2,
			MaxRetries:        5,
			LastError:         "Connection refused",
			CreatedAt:         now,
		},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}

		if !strings.HasPrefix(r.URL.Path, "/api/v2/internal/list-pending-failed-events") {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}

		batchSize := r.URL.Query().Get("batch_size")
		if batchSize != "50" {
			t.Errorf("expected batch_size=50, got %s", batchSize)
		}

		if r.Header.Get("X-Internal-Token") != "test-token" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}

		resp := FailedEventsPendingResponse{
			Events: events,
			Count:  len(events),
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})
	if err != nil {
		t.Fatalf("failed to create client: %v", err)
	}

	result, err := client.GetPendingFailedEvents(context.Background(), 50)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if len(result) != 2 {
		t.Errorf("expected 2 events, got %d", len(result))
	}

	if result[0].ID != 1 {
		t.Errorf("expected event ID 1, got %d", result[0].ID)
	}

	if result[1].RetryCount != 2 {
		t.Errorf("expected retry count 2, got %d", result[1].RetryCount)
	}
}

func TestClient_GetPendingFailedEvents_DefaultBatchSize(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		batchSize := r.URL.Query().Get("batch_size")
		if batchSize != "100" {
			t.Errorf("expected default batch_size=100, got %s", batchSize)
		}

		resp := FailedEventsPendingResponse{Events: []FailedEvent{}, Count: 0}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	// Test with 0 (should use default)
	_, _ = client.GetPendingFailedEvents(context.Background(), 0)
}

func TestClient_GetPendingFailedEvents_MaxBatchSize(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		batchSize := r.URL.Query().Get("batch_size")
		if batchSize != "1000" {
			t.Errorf("expected capped batch_size=1000, got %s", batchSize)
		}

		resp := FailedEventsPendingResponse{Events: []FailedEvent{}, Count: 0}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	// Test with value > 1000 (should be capped)
	_, _ = client.GetPendingFailedEvents(context.Background(), 5000)
}

func TestClient_MarkEventReplayed_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}

		if r.URL.Path != "/api/v2/internal/mark-event-replayed" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}

		eventID := r.URL.Query().Get("event_id")
		if eventID != "123" {
			t.Errorf("expected event_id=123, got %s", eventID)
		}

		resp := FailedEventReplayedResponse{Success: true, EventID: 123, Status: "replayed"}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	err := client.MarkEventReplayed(context.Background(), 123)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestClient_MarkEventReplayed_InvalidID(t *testing.T) {
	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: "http://localhost",
		Token:   "test-token",
	})

	err := client.MarkEventReplayed(context.Background(), 0)
	if err == nil {
		t.Fatal("expected error for invalid event ID")
	}

	if !strings.Contains(err.Error(), "must be positive") {
		t.Errorf("unexpected error message: %v", err)
	}

	err = client.MarkEventReplayed(context.Background(), -1)
	if err == nil {
		t.Fatal("expected error for negative event ID")
	}
}

func TestClient_MarkEventReplayed_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := APIError{
			Error: "Event not found",
			Code:  "NOT_FOUND",
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	err := client.MarkEventReplayed(context.Background(), 999)
	if err == nil {
		t.Fatal("expected error for not found event")
	}

	clientErr, ok := err.(*ClientError)
	if !ok {
		// Error is wrapped
		if !strings.Contains(err.Error(), "NOT_FOUND") && !strings.Contains(err.Error(), "not found") {
			t.Errorf("unexpected error type: %T, message: %v", err, err)
		}
	} else if !clientErr.IsNotFound() {
		t.Errorf("expected not found error, got status %d", clientErr.StatusCode)
	}
}

func TestClient_MarkEventFailed_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}

		if r.URL.Path != "/api/v2/internal/mark-event-failed" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}

		eventID := r.URL.Query().Get("event_id")
		if eventID != "456" {
			t.Errorf("expected event_id=456, got %s", eventID)
		}

		var req FailedEventFailedRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Decode request failed: %v", err)
		}

		if req.ErrorMessage != "Connection refused" {
			t.Errorf("expected error message 'Connection refused', got %s", req.ErrorMessage)
		}

		if req.IncrementRetry == nil || !*req.IncrementRetry {
			t.Error("expected increment_retry to be true")
		}

		resp := FailedEventFailedResponse{
			Success:    true,
			NewStatus:  "pending",
			RetryCount: 3,
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	resp, err := client.MarkEventFailed(context.Background(), 456, "Connection refused")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if resp.RetryCount != 3 {
		t.Errorf("expected retry count 3, got %d", resp.RetryCount)
	}

	if resp.NewStatus != "pending" {
		t.Errorf("expected status 'pending', got %s", resp.NewStatus)
	}
}

func TestClient_MarkEventFailed_MaxRetriesReached(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := FailedEventFailedResponse{
			Success:    true,
			NewStatus:  "failed", // Permanently failed
			RetryCount: 5,
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	resp, err := client.MarkEventFailed(context.Background(), 789, "Final failure")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if resp.NewStatus != "failed" {
		t.Errorf("expected status 'failed', got %s", resp.NewStatus)
	}
}

func TestClient_MarkEventFailed_InvalidInputs(t *testing.T) {
	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: "http://localhost",
		Token:   "test-token",
	})

	// Invalid event ID
	_, err := client.MarkEventFailed(context.Background(), 0, "error")
	if err == nil || !strings.Contains(err.Error(), "must be positive") {
		t.Errorf("expected error for invalid event ID, got %v", err)
	}

	// Empty error message
	_, err = client.MarkEventFailed(context.Background(), 1, "")
	if err == nil || !strings.Contains(err.Error(), "error message is required") {
		t.Errorf("expected error for empty error message, got %v", err)
	}
}

func TestClient_MarkEventFailedWithOptions_NoIncrement(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req FailedEventFailedRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Decode request failed: %v", err)
		}

		if req.IncrementRetry == nil || *req.IncrementRetry {
			t.Error("expected increment_retry to be false")
		}

		resp := FailedEventFailedResponse{
			Success:    true,
			NewStatus:  "pending",
			RetryCount: 2, // Not incremented
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	resp, err := client.MarkEventFailedWithOptions(context.Background(), 100, "Temporary error", false)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if resp.RetryCount != 2 {
		t.Errorf("expected retry count 2, got %d", resp.RetryCount)
	}
}

func TestClient_CleanupOldEvents_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}

		if r.URL.Path != "/api/v2/internal/cleanup-failed-events" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}

		var req FailedEventsCleanupRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Decode request failed: %v", err)
		}

		if req.RetentionDays != 14 {
			t.Errorf("expected retention_days 14, got %d", req.RetentionDays)
		}

		resp := FailedEventsCleanupResponse{Success: true, DeletedCount: 150}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	deleted, err := client.CleanupOldEvents(context.Background(), 14)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if deleted != 150 {
		t.Errorf("expected 150 deleted, got %d", deleted)
	}
}

func TestClient_CleanupOldEvents_DefaultRetention(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req FailedEventsCleanupRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Decode request failed: %v", err)
		}

		if req.RetentionDays != 7 {
			t.Errorf("expected default retention_days 7, got %d", req.RetentionDays)
		}

		resp := FailedEventsCleanupResponse{DeletedCount: 0}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	// Test with 0 (should use default 7)
	_, _ = client.CleanupOldEvents(context.Background(), 0)
}

func TestClient_CleanupOldEvents_MaxRetention(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req FailedEventsCleanupRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("Decode request failed: %v", err)
		}

		if req.RetentionDays != 365 {
			t.Errorf("expected capped retention_days 365, got %d", req.RetentionDays)
		}

		resp := FailedEventsCleanupResponse{DeletedCount: 0}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "test-token",
	})

	// Test with value > 365 (should be capped)
	_, _ = client.CleanupOldEvents(context.Background(), 1000)
}

func TestClient_FailedEvents_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := APIError{
			Error: "Invalid or missing authentication token",
			Code:  "UNAUTHORIZED",
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL: server.URL,
		Token:   "invalid-token",
	})

	_, err := client.GetPendingFailedEvents(context.Background(), 100)
	if err == nil {
		t.Fatal("expected error for unauthorized request")
	}
}

func TestClient_FailedEvents_ServerError(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		resp := APIError{
			Error: "Internal server error",
			Code:  "INTERNAL_ERROR",
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		if err := json.NewEncoder(w).Encode(resp); err != nil {
			t.Errorf("Encode response failed: %v", err)
		}
	}))
	defer server.Close()

	client, _ := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		MaxRetries:  2,
		BaseBackoff: 10 * time.Millisecond,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := client.GetPendingFailedEvents(ctx, 100)
	if err == nil {
		t.Fatal("expected error for server error")
	}

	// Should have retried (1 initial + 2 retries = 3 calls)
	if callCount != 3 {
		t.Errorf("expected 3 calls with retries, got %d", callCount)
	}
}

// Test that Client implements EventReplayClient interface
func TestClient_ImplementsEventReplayClient(t *testing.T) {
	var _ EventReplayClient = (*Client)(nil)
}
