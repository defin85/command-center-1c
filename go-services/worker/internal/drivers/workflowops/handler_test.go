package workflowops

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

// mockWorkflowClient is a mock implementation of WorkflowClient for testing.
type mockWorkflowClient struct {
	getExecutionFunc   func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error)
	updateStatusFunc   func(ctx context.Context, executionID, status, errorMessage string) error
	updateStatusCalled bool
}

func (m *mockWorkflowClient) GetWorkflowExecution(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
	if m.getExecutionFunc != nil {
		return m.getExecutionFunc(ctx, executionID)
	}
	return nil, errors.New("not implemented")
}

func (m *mockWorkflowClient) UpdateWorkflowExecutionStatus(ctx context.Context, executionID, status, errorMessage string) error {
	m.updateStatusCalled = true
	if m.updateStatusFunc != nil {
		return m.updateStatusFunc(ctx, executionID, status, errorMessage)
	}
	return nil
}

func TestWorkflowHandler_ExecuteWorkflow_MissingExecutionID(t *testing.T) {
	handler := &WorkflowHandler{logger: zap.NewNop(), timeline: tracing.NewNoopTimeline()}

	msg := &models.OperationMessage{
		OperationType: "execute_workflow",
		Payload:       models.OperationPayload{Data: map[string]interface{}{}},
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)
	assert.Equal(t, "VALIDATION_ERROR", result.ErrorCode)
}

func TestWorkflowHandler_ExecuteWorkflow_InvalidTemplate(t *testing.T) {
	msg := &models.OperationMessage{
		OperationType: "execute_workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	mockClient := &mockWorkflowClient{
		getExecutionFunc: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return &orchestrator.WorkflowExecutionData{
				WorkflowTemplate: orchestrator.WorkflowTemplateData{
					IsValid:  false,
					IsActive: true,
				},
			}, nil
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       tracing.NewNoopTimeline(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)
	assert.Equal(t, "INVALID_WORKFLOW", result.ErrorCode)
}

func TestWorkflowHandler_ExecuteWorkflow_InactiveTemplate(t *testing.T) {
	msg := &models.OperationMessage{
		OperationType: "execute_workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	mockClient := &mockWorkflowClient{
		getExecutionFunc: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return &orchestrator.WorkflowExecutionData{
				WorkflowTemplate: orchestrator.WorkflowTemplateData{
					IsValid:  true,
					IsActive: false,
				},
			}, nil
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       tracing.NewNoopTimeline(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)
	assert.Equal(t, "INACTIVE_WORKFLOW", result.ErrorCode)
}

func TestWorkflowHandler_ExecuteWorkflow_FetchError(t *testing.T) {
	msg := &models.OperationMessage{
		OperationType: "execute_workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	mockClient := &mockWorkflowClient{
		getExecutionFunc: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return nil, errors.New("fetch error")
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       tracing.NewNoopTimeline(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)
	assert.Equal(t, "WORKFLOW_FETCH_ERROR", result.ErrorCode)
}

func TestWorkflowHandler_ConvertDAGFormat(t *testing.T) {
	handler := &WorkflowHandler{logger: zap.NewNop(), timeline: tracing.NewNoopTimeline()}

	exec := &orchestrator.WorkflowExecutionData{
		WorkflowTemplate: orchestrator.WorkflowTemplateData{
			ID:            "wf-1",
			VersionNumber: 2,
			Name:          "Test Workflow",
			DAGStructure: map[string]interface{}{
				"nodes": []interface{}{
					map[string]interface{}{
						"id":          "node-1",
						"type":        "operation",
						"name":        "Node 1",
						"template_id": "tpl-1",
					},
					map[string]interface{}{
						"node_id": "node-2",
						"type":    "condition",
						"name":    "Node 2",
					},
				},
				"edges": []interface{}{
					map[string]interface{}{
						"from_node": "node-1",
						"to_node":   "node-2",
					},
				},
			},
			Config: map[string]interface{}{
				"timeout_seconds": 120,
			},
		},
	}

	dag := handler.convertDAGToEngineFormat(exec)
	assert.Equal(t, "wf-1", dag["id"])
	assert.Equal(t, 2, dag["version"])
	assert.Equal(t, "Test Workflow", dag["name"])
	assert.Equal(t, exec.WorkflowTemplate.Config, dag["config"])

	nodes, ok := dag["nodes"].(map[string]interface{})
	assert.True(t, ok)
	assert.Contains(t, nodes, "node-1")
	assert.Contains(t, nodes, "node-2")

	edges, ok := dag["edges"].([]interface{})
	assert.True(t, ok)
	assert.NotEmpty(t, edges)
	edge, ok := edges[0].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "node-1", edge["from"])
	assert.Equal(t, "node-2", edge["to"])
}

func TestWorkflowHandler_ResultDurationSet(t *testing.T) {
	msg := &models.OperationMessage{
		OperationType: "execute_workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{
				"execution_id": "exec-123",
			},
		},
	}

	mockClient := &mockWorkflowClient{
		getExecutionFunc: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return &orchestrator.WorkflowExecutionData{
				WorkflowTemplate: orchestrator.WorkflowTemplateData{
					IsValid:  false,
					IsActive: true,
				},
			}, nil
		},
	}

	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       tracing.NewNoopTimeline(),
	}

	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)
	assert.GreaterOrEqual(t, result.Duration, 0.0)
}
