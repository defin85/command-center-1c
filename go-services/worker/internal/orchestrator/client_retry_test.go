package orchestrator

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestClientRetryAfterHeaderIsRespected(t *testing.T) {
	var calls int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		if calls == 1 {
			w.Header().Set("Retry-After", "1")
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte(`{"error":"rate limited","code":"RATE_LIMITED"}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		Timeout:     3 * time.Second,
		MaxRetries:  1,
		BaseBackoff: 10 * time.Millisecond,
	})
	require.NoError(t, err)

	start := time.Now()
	var out map[string]interface{}
	err = client.post(context.Background(), "/retry-after", map[string]interface{}{"a": "b"}, &out)
	elapsed := time.Since(start)

	require.NoError(t, err)
	assert.Equal(t, 2, calls)
	assert.GreaterOrEqual(t, elapsed, 900*time.Millisecond)
}

func TestClientRetryBudgetBoundByContextDeadline(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Retry-After", time.Now().Add(2*time.Second).UTC().Format(http.TimeFormat))
		w.WriteHeader(http.StatusTooManyRequests)
		_, _ = w.Write([]byte(`{"error":"rate limited","code":"RATE_LIMITED"}`))
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		Timeout:     5 * time.Second,
		MaxRetries:  2,
		BaseBackoff: 10 * time.Millisecond,
	})
	require.NoError(t, err)

	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Millisecond)
	defer cancel()

	start := time.Now()
	err = client.post(ctx, "/retry-budget", map[string]interface{}{"a": "b"}, nil)
	elapsed := time.Since(start)

	require.Error(t, err)
	assert.True(t, errors.Is(err, context.DeadlineExceeded))
	assert.Less(t, elapsed, time.Second)
}

func TestClientRetryIncrementsTransportAttemptForBridgeRequests(t *testing.T) {
	attempts := make([]int, 0, 2)
	var calls int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var payload PoolRuntimeStepExecutionRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&payload))
		attempts = append(attempts, payload.TransportAttempt)

		w.Header().Set("Content-Type", "application/json")
		if calls == 1 {
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte(`{"error":"rate limited","code":"RATE_LIMITED"}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"success":true,"status":"completed","result":{"ok":true}}`))
	}))
	defer server.Close()

	client, err := NewClientWithConfig(ClientConfig{
		BaseURL:     server.URL,
		Token:       "test-token",
		Timeout:     3 * time.Second,
		MaxRetries:  1,
		BaseBackoff: 10 * time.Millisecond,
	})
	require.NoError(t, err)

	_, err = client.ExecutePoolRuntimeStep(context.Background(), &PoolRuntimeStepExecutionRequest{
		TenantID:            "tenant-1",
		PoolRunID:           "pool-run-1",
		WorkflowExecutionID: "exec-1",
		NodeID:              "node-1",
		OperationType:       "pool.prepare_input",
		OperationRef: &PoolRuntimeOperationRef{
			Alias:                    "pool.prepare_input",
			BindingMode:              "pinned_exposure",
			TemplateExposureID:       "exp-1",
			TemplateExposureRevision: 1,
		},
		StepAttempt:      1,
		TransportAttempt: 1,
		IdempotencyKey:   "bridge-key-1",
		Payload:          map[string]interface{}{"pool_runtime": map[string]interface{}{"step_id": "prepare_input"}},
	})

	require.NoError(t, err)
	assert.Equal(t, []int{1, 2}, attempts)
}
