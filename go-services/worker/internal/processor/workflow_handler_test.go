package processor

import (
	"context"
	"testing"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

// mockWorkflowClient is a mock implementation of WorkflowClient for testing.
type mockWorkflowClient struct {
	getExecutionFn func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error)
	updateStatusFn func(ctx context.Context, executionID, status, errorMessage string) error
}

func (m *mockWorkflowClient) GetWorkflowExecution(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
	if m.getExecutionFn != nil {
		return m.getExecutionFn(ctx, executionID)
	}
	return nil, nil
}

func (m *mockWorkflowClient) UpdateWorkflowExecutionStatus(ctx context.Context, executionID, status, errorMessage string) error {
	if m.updateStatusFn != nil {
		return m.updateStatusFn(ctx, executionID, status, errorMessage)
	}
	return nil
}

func TestExecuteWorkflow_MissingExecutionID(t *testing.T) {
	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "test-op-123",
		OperationType: "execute_workflow",
		Entity:        "workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				// Missing execution_id
			},
		},
	}

	// Create mock client
	mockClient := &mockWorkflowClient{}

	// Create handler without full initialization (for unit test)
	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
	}

	// Execute
	result := handler.ExecuteWorkflow(context.Background(), msg)

	// Verify
	if result.Success {
		t.Error("expected failure when execution_id is missing")
	}
	if result.ErrorCode != "VALIDATION_ERROR" {
		t.Errorf("expected VALIDATION_ERROR, got %s", result.ErrorCode)
	}
}

func TestExecuteWorkflow_InvalidWorkflowTemplate(t *testing.T) {
	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "test-op-123",
		OperationType: "execute_workflow",
		Entity:        "workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	// Create mock client that returns invalid template
	mockClient := &mockWorkflowClient{
		getExecutionFn: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return &orchestrator.WorkflowExecutionData{
				ID: executionID,
				WorkflowTemplate: orchestrator.WorkflowTemplateData{
					ID:       "template-123",
					Name:     "Test Workflow",
					IsValid:  false, // Invalid template
					IsActive: true,
				},
			}, nil
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)

	if result.Success {
		t.Error("expected failure when workflow template is invalid")
	}
	if result.ErrorCode != "INVALID_WORKFLOW" {
		t.Errorf("expected INVALID_WORKFLOW, got %s", result.ErrorCode)
	}
}

func TestExecuteWorkflow_InactiveWorkflowTemplate(t *testing.T) {
	msg := &models.OperationMessage{
		Version:       "2.0",
		OperationID:   "test-op-123",
		OperationType: "execute_workflow",
		Entity:        "workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	mockClient := &mockWorkflowClient{
		getExecutionFn: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return &orchestrator.WorkflowExecutionData{
				ID: executionID,
				WorkflowTemplate: orchestrator.WorkflowTemplateData{
					ID:       "template-123",
					Name:     "Test Workflow",
					IsValid:  true,
					IsActive: false, // Inactive template
				},
			}, nil
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)

	if result.Success {
		t.Error("expected failure when workflow template is inactive")
	}
	if result.ErrorCode != "INACTIVE_WORKFLOW" {
		t.Errorf("expected INACTIVE_WORKFLOW, got %s", result.ErrorCode)
	}
}

func TestConvertDAGToEngineFormat(t *testing.T) {
	handler := &WorkflowHandler{}

	execution := &orchestrator.WorkflowExecutionData{
		ID: "exec-123",
		WorkflowTemplate: orchestrator.WorkflowTemplateData{
			ID:            "template-123",
			Name:          "Test Workflow",
			VersionNumber: 2,
			DAGStructure: map[string]interface{}{
				"nodes": []interface{}{
					map[string]interface{}{
						"id":   "start",
						"name": "Start Node",
						"type": "operation",
					},
				},
				"edges": []interface{}{},
			},
		},
	}

	dag := handler.convertDAGToEngineFormat(execution)

	// Check that ID is added
	if dag["id"] != "template-123" {
		t.Errorf("expected id=template-123, got %v", dag["id"])
	}

	// Check that version is added
	if dag["version"] != 2 {
		t.Errorf("expected version=2, got %v", dag["version"])
	}

	// Check that name is added
	if dag["name"] != "Test Workflow" {
		t.Errorf("expected name=Test Workflow, got %v", dag["name"])
	}

	// Check that nodes are preserved
	nodes, ok := dag["nodes"].([]interface{})
	if !ok || len(nodes) != 1 {
		t.Errorf("expected 1 node, got %v", dag["nodes"])
	}
}
