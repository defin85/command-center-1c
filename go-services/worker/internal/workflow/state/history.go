package state

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// HistoryStore defines the interface for persisting workflow execution history.
// This is for long-term storage in PostgreSQL via the Orchestrator's Internal API.
type HistoryStore interface {
	// RecordExecution creates a new execution record.
	RecordExecution(ctx context.Context, state *WorkflowState) error

	// UpdateExecution updates an existing execution record.
	UpdateExecution(ctx context.Context, state *WorkflowState) error

	// RecordNodeExecution records a node's execution.
	RecordNodeExecution(ctx context.Context, executionID string, nodeState *NodeState) error

	// RecordTransition records a state transition event.
	RecordTransition(ctx context.Context, event *StateTransitionEvent) error

	// GetExecution retrieves an execution record by ID.
	GetExecution(ctx context.Context, executionID string) (*WorkflowExecutionRecord, error)

	// ListExecutions lists executions with pagination.
	ListExecutions(ctx context.Context, params *ListExecutionsParams) (*ListExecutionsResult, error)
}

// WorkflowExecutionRecord represents a workflow execution in PostgreSQL.
type WorkflowExecutionRecord struct {
	ID           string                 `json:"id"`
	WorkflowID   string                 `json:"workflow_id"`
	DAGID        string                 `json:"dag_id"`
	DAGVersion   int                    `json:"dag_version"`
	Status       string                 `json:"status"`
	StartedAt    *time.Time             `json:"started_at,omitempty"`
	CompletedAt  *time.Time             `json:"completed_at,omitempty"`
	ErrorMessage string                 `json:"error_message,omitempty"`
	InputData    map[string]interface{} `json:"input_data,omitempty"`
	OutputData   map[string]interface{} `json:"output_data,omitempty"`
	CreatedAt    time.Time              `json:"created_at"`
	UpdatedAt    time.Time              `json:"updated_at"`
}

// NodeExecutionRecord represents a node execution in PostgreSQL.
type NodeExecutionRecord struct {
	ID          string      `json:"id"`
	ExecutionID string      `json:"execution_id"`
	NodeID      string      `json:"node_id"`
	NodeType    string      `json:"node_type"`
	NodeName    string      `json:"node_name,omitempty"`
	Status      string      `json:"status"`
	StartedAt   *time.Time  `json:"started_at,omitempty"`
	CompletedAt *time.Time  `json:"completed_at,omitempty"`
	DurationMs  int64       `json:"duration_ms,omitempty"`
	Output      interface{} `json:"output,omitempty"`
	Error       string      `json:"error,omitempty"`
	RetryCount  int         `json:"retry_count"`
	CreatedAt   time.Time   `json:"created_at"`
}

// ListExecutionsParams holds parameters for listing executions.
type ListExecutionsParams struct {
	WorkflowID    string     `json:"workflow_id,omitempty"`
	Status        string     `json:"status,omitempty"`
	StartedAfter  *time.Time `json:"started_after,omitempty"`
	StartedBefore *time.Time `json:"started_before,omitempty"`
	Limit         int        `json:"limit,omitempty"`
	Offset        int        `json:"offset,omitempty"`
}

// ListExecutionsResult holds the result of listing executions.
type ListExecutionsResult struct {
	Executions []WorkflowExecutionRecord `json:"executions"`
	Total      int                       `json:"total"`
	Limit      int                       `json:"limit"`
	Offset     int                       `json:"offset"`
}

// HistoryClient implements HistoryStore using Orchestrator's Internal API.
type HistoryClient struct {
	baseURL    string
	httpClient *http.Client
	authToken  string
}

// HistoryClientConfig holds configuration for HistoryClient.
type HistoryClientConfig struct {
	BaseURL   string
	AuthToken string
	Timeout   time.Duration
}

// NewHistoryClient creates a new history client.
func NewHistoryClient(config *HistoryClientConfig) *HistoryClient {
	timeout := 30 * time.Second
	if config.Timeout > 0 {
		timeout = config.Timeout
	}

	return &HistoryClient{
		baseURL:   config.BaseURL,
		authToken: config.AuthToken,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

// RecordExecution creates a new execution record via Internal API.
func (c *HistoryClient) RecordExecution(ctx context.Context, state *WorkflowState) error {
	payload := map[string]interface{}{
		"id":          state.ExecutionID,
		"workflow_id": state.WorkflowID,
		"dag_id":      state.DAGID,
		"dag_version": state.DAGVersion,
		"status":      string(state.Status),
		"input_data":  state.ContextSnapshot,
	}
	if state.StartedAt != nil {
		payload["started_at"] = state.StartedAt.Format(time.RFC3339)
	}

	_, err := c.post(ctx, "/api/v2/internal/workflow-executions/", payload)
	return err
}

// UpdateExecution updates an existing execution record.
func (c *HistoryClient) UpdateExecution(ctx context.Context, state *WorkflowState) error {
	payload := map[string]interface{}{
		"status": string(state.Status),
	}
	if state.CompletedAt != nil {
		payload["completed_at"] = state.CompletedAt.Format(time.RFC3339)
	}
	if state.ErrorMessage != "" {
		payload["error_message"] = state.ErrorMessage
	}
	if len(state.ContextSnapshot) > 0 {
		payload["output_data"] = state.ContextSnapshot
	}

	url := fmt.Sprintf("/api/v2/internal/workflow-executions/%s/", state.ExecutionID)
	_, err := c.patch(ctx, url, payload)
	return err
}

// RecordNodeExecution records a node's execution.
func (c *HistoryClient) RecordNodeExecution(ctx context.Context, executionID string, nodeState *NodeState) error {
	payload := map[string]interface{}{
		"execution_id": executionID,
		"node_id":      nodeState.NodeID,
		"node_type":    nodeState.NodeType,
		"node_name":    nodeState.NodeName,
		"status":       string(nodeState.Status),
		"retry_count":  nodeState.RetryCount,
	}
	if nodeState.StartedAt != nil {
		payload["started_at"] = nodeState.StartedAt.Format(time.RFC3339)
	}
	if nodeState.CompletedAt != nil {
		payload["completed_at"] = nodeState.CompletedAt.Format(time.RFC3339)
	}
	if nodeState.Duration > 0 {
		payload["duration_ms"] = nodeState.Duration
	}
	if nodeState.Output != nil {
		payload["output"] = nodeState.Output
	}
	if nodeState.ErrorMessage != "" {
		payload["error"] = nodeState.ErrorMessage
	}

	_, err := c.post(ctx, "/api/v2/internal/node-executions/", payload)
	return err
}

// RecordTransition records a state transition event.
func (c *HistoryClient) RecordTransition(ctx context.Context, event *StateTransitionEvent) error {
	payload := map[string]interface{}{
		"execution_id": event.ExecutionID,
		"timestamp":    event.Timestamp.Format(time.RFC3339),
		"to_status":    string(event.ToStatus),
	}
	if event.FromStatus != "" {
		payload["from_status"] = string(event.FromStatus)
	}
	if event.NodeID != "" {
		payload["node_id"] = event.NodeID
	}
	if event.NodeStatus != "" {
		payload["node_status"] = string(event.NodeStatus)
	}
	if event.Message != "" {
		payload["message"] = event.Message
	}
	if len(event.Metadata) > 0 {
		payload["metadata"] = event.Metadata
	}

	_, err := c.post(ctx, "/api/v2/internal/workflow-transitions/", payload)
	return err
}

// GetExecution retrieves an execution record by ID.
func (c *HistoryClient) GetExecution(ctx context.Context, executionID string) (*WorkflowExecutionRecord, error) {
	url := fmt.Sprintf("/api/v2/internal/workflow-executions/%s/", executionID)
	data, err := c.get(ctx, url)
	if err != nil {
		return nil, err
	}

	var record WorkflowExecutionRecord
	if err := json.Unmarshal(data, &record); err != nil {
		return nil, fmt.Errorf("failed to parse execution record: %w", err)
	}

	return &record, nil
}

// ListExecutions lists executions with pagination.
func (c *HistoryClient) ListExecutions(ctx context.Context, params *ListExecutionsParams) (*ListExecutionsResult, error) {
	basePath := "/api/v2/internal/workflow-executions/"

	// Build query parameters with proper URL encoding
	query := url.Values{}
	if params != nil {
		if params.WorkflowID != "" {
			query.Set("workflow_id", params.WorkflowID)
		}
		if params.Status != "" {
			query.Set("status", params.Status)
		}
		if params.Limit > 0 {
			query.Set("limit", strconv.Itoa(params.Limit))
		}
		if params.Offset > 0 {
			query.Set("offset", strconv.Itoa(params.Offset))
		}
	}

	fullPath := basePath
	if len(query) > 0 {
		fullPath += "?" + query.Encode()
	}

	data, err := c.get(ctx, fullPath)
	if err != nil {
		return nil, err
	}

	var result ListExecutionsResult
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse executions list: %w", err)
	}

	return &result, nil
}

// post sends a POST request to the Internal API.
func (c *HistoryClient) post(ctx context.Context, path string, payload interface{}) ([]byte, error) {
	return c.request(ctx, http.MethodPost, path, payload)
}

// patch sends a PATCH request to the Internal API.
func (c *HistoryClient) patch(ctx context.Context, path string, payload interface{}) ([]byte, error) {
	return c.request(ctx, http.MethodPatch, path, payload)
}

// get sends a GET request to the Internal API.
func (c *HistoryClient) get(ctx context.Context, path string) ([]byte, error) {
	return c.request(ctx, http.MethodGet, path, nil)
}

// request sends an HTTP request to the Internal API.
func (c *HistoryClient) request(ctx context.Context, method, path string, payload interface{}) ([]byte, error) {
	url := c.baseURL + path

	var body io.Reader
	if payload != nil {
		data, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal payload: %w", err)
		}
		body = bytes.NewReader(data)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.authToken != "" {
		req.Header.Set("Authorization", "Bearer "+c.authToken)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, &HistoryAPIError{
			StatusCode: resp.StatusCode,
			Body:       string(respBody),
		}
	}

	return respBody, nil
}

// HistoryAPIError represents an error from the History API.
type HistoryAPIError struct {
	StatusCode int
	Body       string
}

func (e *HistoryAPIError) Error() string {
	return fmt.Sprintf("history API error (status=%d): %s", e.StatusCode, e.Body)
}

// NoOpHistoryStore is a no-op implementation for testing or when history is disabled.
type NoOpHistoryStore struct{}

func (s *NoOpHistoryStore) RecordExecution(_ context.Context, _ *WorkflowState) error {
	return nil
}

func (s *NoOpHistoryStore) UpdateExecution(_ context.Context, _ *WorkflowState) error {
	return nil
}

func (s *NoOpHistoryStore) RecordNodeExecution(_ context.Context, _ string, _ *NodeState) error {
	return nil
}

func (s *NoOpHistoryStore) RecordTransition(_ context.Context, _ *StateTransitionEvent) error {
	return nil
}

func (s *NoOpHistoryStore) GetExecution(_ context.Context, executionID string) (*WorkflowExecutionRecord, error) {
	return nil, fmt.Errorf("execution %s not found", executionID)
}

func (s *NoOpHistoryStore) ListExecutions(_ context.Context, _ *ListExecutionsParams) (*ListExecutionsResult, error) {
	return &ListExecutionsResult{
		Executions: []WorkflowExecutionRecord{},
		Total:      0,
	}, nil
}
