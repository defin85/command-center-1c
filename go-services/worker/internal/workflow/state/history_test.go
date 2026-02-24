package state

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHistoryClient_RecordExecution_SetsInternalAuthHeaders(t *testing.T) {
	const token = "test-internal-token"

	var receivedHeaderInternalToken string
	var receivedHeaderInternalServiceToken string
	var receivedHeaderAuthorization string
	var receivedPayload map[string]interface{}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/api/v2/internal/workflow-executions/", r.URL.Path)

		receivedHeaderInternalToken = r.Header.Get(headerInternalToken)
		receivedHeaderInternalServiceToken = r.Header.Get(headerInternalServiceToken)
		receivedHeaderAuthorization = r.Header.Get("Authorization")

		require.NoError(t, json.NewDecoder(r.Body).Decode(&receivedPayload))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"success": true}`))
	}))
	t.Cleanup(server.Close)

	client := NewHistoryClient(&HistoryClientConfig{
		BaseURL:   server.URL,
		AuthToken: token,
		Timeout:   3 * time.Second,
	})

	now := time.Now().UTC()
	state := &WorkflowState{
		ExecutionID:     "exec-1",
		WorkflowID:      "workflow-1",
		DAGID:           "dag-1",
		DAGVersion:      1,
		Status:          WorkflowStatusPending,
		ContextSnapshot: map[string]interface{}{"foo": "bar"},
		StartedAt:       &now,
	}

	err := client.RecordExecution(context.Background(), state)
	require.NoError(t, err)

	assert.Equal(t, token, receivedHeaderInternalToken)
	assert.Equal(t, token, receivedHeaderInternalServiceToken)
	assert.Equal(t, "", receivedHeaderAuthorization)
	assert.Equal(t, "exec-1", receivedPayload["id"])
	assert.Equal(t, "pending", receivedPayload["status"])
}
