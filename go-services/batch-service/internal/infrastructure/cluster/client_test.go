package cluster

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"go.uber.org/zap/zaptest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestCircuitBreakerOpensOnFailures verifies circuit breaker opens after 60% failures
func TestCircuitBreakerOpensOnFailures(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Create a mock server that returns errors
	failureCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		failureCount++
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
	}))
	defer server.Close()

	// Create cluster client with short timeout for testing
	client := NewClusterClient(server.URL, 100*time.Millisecond, logger)

	// Make 3+ failed requests to trigger circuit breaker (60% failure threshold with min 3 requests)
	for i := 0; i < 5; i++ {
		_, err := client.GetSessions("test-infobase")
		require.Error(t, err)
		t.Logf("Request %d failed: %v", i+1, err)
	}

	// Circuit should now be open, so next request should fail immediately
	startTime := time.Now()
	_, err := client.GetSessions("test-infobase")
	elapsed := time.Since(startTime)

	require.Error(t, err)
	// When circuit is open, request should fail immediately without waiting for timeout
	assert.Less(t, elapsed, 100*time.Millisecond,
		"Circuit breaker should fail immediately when open, not wait for timeout")
	t.Logf("Circuit breaker triggered: %v (elapsed: %v)", err, elapsed)
}

// TestCircuitBreakerClosedOnSuccess verifies circuit breaker stays closed with successful requests
func TestCircuitBreakerClosedOnSuccess(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Create a mock server that returns success
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"count": 2,
			"sessions": [
				{"id": "1", "user": "admin", "duration": 3600},
				{"id": "2", "user": "user1", "duration": 1800}
			]
		}`))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 5*time.Second, logger)

	// Make multiple successful requests
	for i := 0; i < 5; i++ {
		sessions, err := client.GetSessions("test-infobase")
		require.NoError(t, err)
		assert.NotNil(t, sessions)
		t.Logf("Request %d succeeded: got %d sessions", i+1, len(sessions))
	}

	// Circuit should still be closed, all requests should succeed
	assert.Equal(t, 5, requestCount)
	t.Log("Circuit breaker remained closed for all successful requests")
}

// TestCircuitBreakerRecovery verifies circuit breaker recovers from open state
func TestCircuitBreakerRecovery(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Start with a failing server
	serverErrors := true
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if serverErrors {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte("Internal Server Error"))
			return
		}
		// After serverErrors=false, return success
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"count": 1,
			"sessions": [{"id": "1", "user": "admin", "duration": 3600}]
		}`))
	}))
	defer server.Close()

	// Use short timeout and interval for faster testing
	client := NewClusterClient(server.URL, 100*time.Millisecond, logger)

	// Trigger circuit breaker by making failed requests
	for i := 0; i < 5; i++ {
		_, err := client.GetSessions("test-infobase")
		require.Error(t, err)
	}
	t.Log("Circuit breaker opened after failures")

	// Circuit should now be open - request should fail immediately
	startTime := time.Now()
	_, err := client.GetSessions("test-infobase")
	elapsed := time.Since(startTime)
	require.Error(t, err)
	assert.Less(t, elapsed, 100*time.Millisecond,
		"Circuit breaker should fail immediately when open")

	// Wait for circuit to transition to half-open state
	// Circuit timeout = request timeout * 2 = 200ms
	t.Log("Waiting for circuit to transition to half-open state...")
	time.Sleep(250 * time.Millisecond)

	// Now server returns success
	serverErrors = false

	// In half-open state, the first request is allowed (test request)
	sessions, err := client.GetSessions("test-infobase")
	require.NoError(t, err)
	assert.NotNil(t, sessions)
	t.Log("Circuit transitioned to half-open and request succeeded")

	// After successful test request, circuit should be closed
	// Make more requests to verify circuit is closed
	for i := 0; i < 3; i++ {
		sessions, err := client.GetSessions("test-infobase")
		require.NoError(t, err)
		assert.NotNil(t, sessions)
	}
	t.Log("Circuit breaker recovered and closed after successful requests")
}

// TestHealthCheckBypassesCircuitBreaker verifies health check doesn't use circuit breaker
func TestHealthCheckBypassesCircuitBreaker(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Create a mock server that fails for normal requests but succeeds for health checks
	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		if r.RequestURI == "/health" {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{"status":"healthy"}`))
			return
		}
		// All other requests fail
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 100*time.Millisecond, logger)

	// Trigger circuit breaker with failed requests
	for i := 0; i < 5; i++ {
		_, err := client.GetSessions("test-infobase")
		require.Error(t, err)
	}
	t.Log("Circuit breaker triggered")

	// Health check should succeed even though circuit is open
	// because it bypasses circuit breaker
	err := client.HealthCheck()
	require.NoError(t, err)
	t.Log("Health check succeeded despite open circuit breaker")

	// Verify the health check was actually called (endpoint = /health)
	initialCount := requestCount
	err = client.HealthCheck()
	require.NoError(t, err)
	assert.Greater(t, requestCount, initialCount,
		"Health check should make actual HTTP request")
}

// TestTerminateSessionsProtectedByCircuitBreaker verifies TerminateSessions uses circuit breaker
func TestTerminateSessionsProtectedByCircuitBreaker(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Create a mock server that fails for terminate requests
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.RequestURI == "/health" {
			w.WriteHeader(http.StatusOK)
			return
		}
		// Terminate requests fail
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 100*time.Millisecond, logger)

	// Make failed terminate requests to trigger circuit breaker
	sessionIDs := []string{"session-1", "session-2"}
	for i := 0; i < 5; i++ {
		_, err := client.TerminateSessions("test-infobase", sessionIDs)
		require.Error(t, err)
	}

	// Circuit should now be open
	startTime := time.Now()
	_, err := client.TerminateSessions("test-infobase", sessionIDs)
	elapsed := time.Since(startTime)

	require.Error(t, err)
	assert.Less(t, elapsed, 100*time.Millisecond,
		"TerminateSessions should fail immediately when circuit is open")
	t.Logf("TerminateSessions protected by circuit breaker: %v", err)
}

// TestCircuitBreakerDoesNotBlockConnectionRefusedErrors
// This test verifies that connection refused errors also trigger circuit breaker
func TestCircuitBreakerHandlesConnectionRefused(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Use an unreachable address to trigger connection refused
	client := NewClusterClient("http://127.0.0.1:1", 100*time.Millisecond, logger)

	// Make requests to unreachable service
	for i := 0; i < 5; i++ {
		_, err := client.GetSessions("test-infobase")
		require.Error(t, err)
		t.Logf("Request %d failed: %v", i+1, err)
	}

	// Circuit should be open
	startTime := time.Now()
	_, err := client.GetSessions("test-infobase")
	elapsed := time.Since(startTime)

	require.Error(t, err)
	assert.Less(t, elapsed, 100*time.Millisecond,
		"Circuit breaker should fail immediately when open")
	t.Logf("Circuit breaker handles connection refused: %v", err)
}

// TestCircuitBreakerWithTimeout verifies circuit breaker respects HTTP timeout
func TestCircuitBreakerWithTimeout(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	// Create a slow server that times out
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(500 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// Create client with very short timeout (50ms)
	client := NewClusterClient(server.URL, 50*time.Millisecond, logger)

	// Requests should timeout
	for i := 0; i < 5; i++ {
		startTime := time.Now()
		_, err := client.GetSessions("test-infobase")
		elapsed := time.Since(startTime)
		require.Error(t, err)
		assert.Less(t, elapsed, 200*time.Millisecond,
			"Request should timeout quickly")
		t.Logf("Request %d timed out after %v", i+1, elapsed)
	}

	// Circuit should be open
	startTime := time.Now()
	_, err := client.GetSessions("test-infobase")
	elapsed := time.Since(startTime)

	require.Error(t, err)
	assert.Less(t, elapsed, 50*time.Millisecond,
		"Circuit breaker should fail immediately when open")
	t.Log("Circuit breaker correctly handles timeouts")
}

// TestGetSessionsSuccessful tests successful GetSessions call
func TestGetSessionsSuccessful(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/v1/sessions?infobase_id=test-infobase", r.RequestURI)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"count": 2,
			"sessions": [
				{"session_id": "sess-1", "user_name": "admin", "application": "app", "started_at": "2025-01-01T00:00:00Z"},
				{"session_id": "sess-2", "user_name": "user1", "application": "app2", "started_at": "2025-01-01T00:00:00Z"}
			]
		}`))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 5*time.Second, logger)
	sessions, err := client.GetSessions("test-infobase")

	require.NoError(t, err)
	assert.NotNil(t, sessions)
	assert.Equal(t, 2, len(sessions))
	assert.Equal(t, "sess-1", sessions[0].SessionID)
	assert.Equal(t, "admin", sessions[0].UserName)
	t.Log("GetSessions returned correct data")
}

// TestTerminateSessionsSuccessful tests successful TerminateSessions call
func TestTerminateSessionsSuccessful(t *testing.T) {
	logger := zaptest.NewLogger(t)
	defer logger.Sync()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/v1/sessions/terminate", r.RequestURI)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"terminated_count": 2,
			"failed_sessions": []
		}`))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 5*time.Second, logger)
	resp, err := client.TerminateSessions("test-infobase", []string{"sess-1", "sess-2"})

	require.NoError(t, err)
	assert.Equal(t, 2, resp.TerminatedCount)
	assert.Equal(t, 0, len(resp.FailedSessions))
	t.Log("TerminateSessions returned correct data")
}

// BenchmarkCircuitBreakerOverhead measures the performance impact of circuit breaker
func BenchmarkCircuitBreakerOverhead(b *testing.B) {
	logger := zaptest.NewLogger(&testing.T{})
	defer logger.Sync()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"count": 1, "sessions": []}`))
	}))
	defer server.Close()

	client := NewClusterClient(server.URL, 5*time.Second, logger)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		client.GetSessions("test-infobase")
	}
	b.StopTimer()
	b.ReportAllocs()
}
