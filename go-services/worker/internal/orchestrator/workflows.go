package orchestrator

import (
	"context"
	"fmt"
	"net/url"
)

// WorkflowExecutionData represents workflow execution data from Orchestrator.
type WorkflowExecutionData struct {
	ID               string                 `json:"id"`
	WorkflowTemplate WorkflowTemplateData   `json:"workflow_template"`
	InputContext     map[string]interface{} `json:"input_context"`
	Status           string                 `json:"status"`
	CurrentNodeID    string                 `json:"current_node_id"`
	CompletedNodes   []string               `json:"completed_nodes"`
	FailedNodes      []string               `json:"failed_nodes"`
}

// WorkflowTemplateData represents workflow template data from Orchestrator.
type WorkflowTemplateData struct {
	ID            string                 `json:"id"`
	Name          string                 `json:"name"`
	Description   string                 `json:"description"`
	WorkflowType  string                 `json:"workflow_type"`
	DAGStructure  map[string]interface{} `json:"dag_structure"`
	Config        map[string]interface{} `json:"config"`
	IsValid       bool                   `json:"is_valid"`
	IsActive      bool                   `json:"is_active"`
	VersionNumber int                    `json:"version_number"`
}

// GetWorkflowExecution fetches workflow execution by ID from Orchestrator.
// Returns the execution data including DAG structure for workflow execution.
func (c *Client) GetWorkflowExecution(ctx context.Context, executionID string) (*WorkflowExecutionData, error) {
	path := fmt.Sprintf(
		"/api/v2/internal/workflows/get-execution?execution_id=%s",
		url.QueryEscape(executionID),
	)

	var execution WorkflowExecutionData
	if err := c.get(ctx, path, &execution); err != nil {
		return nil, fmt.Errorf("failed to get workflow execution %s: %w", executionID, err)
	}

	return &execution, nil
}

// GetWorkflowTemplate fetches workflow template by ID from Orchestrator.
func (c *Client) GetWorkflowTemplate(ctx context.Context, templateID string) (*WorkflowTemplateData, error) {
	path := fmt.Sprintf("/api/v2/internal/workflow-templates/%s/", templateID)

	var template WorkflowTemplateData
	if err := c.get(ctx, path, &template); err != nil {
		return nil, fmt.Errorf("failed to get workflow template %s: %w", templateID, err)
	}

	return &template, nil
}

// UpdateWorkflowExecutionStatus updates execution status in Orchestrator.
func (c *Client) UpdateWorkflowExecutionStatus(
	ctx context.Context,
	executionID string,
	status string,
	errorMessage string,
	errorCode string,
	errorDetails map[string]interface{},
) error {
	path := "/api/v2/internal/workflows/update-execution-status"

	payload := map[string]interface{}{
		"execution_id": executionID,
		"status":       status,
	}
	if errorMessage != "" {
		payload["error_message"] = errorMessage
	}
	if errorCode != "" {
		payload["error_code"] = errorCode
	}
	if len(errorDetails) > 0 {
		payload["error_details"] = errorDetails
	}

	return c.post(ctx, path, payload, nil)
}

// ExecutePoolRuntimeStep executes pool runtime step via canonical internal bridge endpoint.
func (c *Client) ExecutePoolRuntimeStep(
	ctx context.Context,
	req *PoolRuntimeStepExecutionRequest,
) (*PoolRuntimeStepExecutionResponse, error) {
	if req == nil {
		return nil, fmt.Errorf("pool runtime step request is required")
	}

	path := "/api/v2/internal/workflows/execute-pool-runtime-step"
	var response PoolRuntimeStepExecutionResponse
	if err := c.post(ctx, path, req, &response); err != nil {
		return nil, err
	}
	return &response, nil
}
