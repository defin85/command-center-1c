package workflowops

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/drivers/poolops"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
)

// mockWorkflowClient is a mock implementation of WorkflowClient for testing.
type mockWorkflowClient struct {
	getExecutionFunc func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error)
	updateStatusFunc func(
		ctx context.Context,
		executionID, status, errorMessage, errorCode string,
		errorDetails map[string]interface{},
	) error
	updateStatusCalled bool
	updateStatusCalls  int
}

func (m *mockWorkflowClient) GetWorkflowExecution(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
	if m.getExecutionFunc != nil {
		return m.getExecutionFunc(ctx, executionID)
	}
	return nil, errors.New("not implemented")
}

func (m *mockWorkflowClient) UpdateWorkflowExecutionStatus(
	ctx context.Context,
	executionID, status, errorMessage, errorCode string,
	errorDetails map[string]interface{},
) error {
	m.updateStatusCalled = true
	m.updateStatusCalls++
	if m.updateStatusFunc != nil {
		return m.updateStatusFunc(ctx, executionID, status, errorMessage, errorCode, errorDetails)
	}
	return nil
}

type timelineRecord struct {
	operationID string
	event       string
	metadata    map[string]interface{}
}

type timelineSpy struct {
	records []timelineRecord
}

func (s *timelineSpy) Record(ctx context.Context, operationID, event string, metadata map[string]interface{}) {
	s.records = append(s.records, timelineRecord{
		operationID: operationID,
		event:       event,
		metadata:    metadata,
	})
}

func (s *timelineSpy) GetTimeline(ctx context.Context, operationID string) ([]tracing.TimelineEntry, error) {
	return nil, nil
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

func TestWorkflowHandler_UpdateStatusWithRetry_DoesNotAmplifyRetriesOnTemporaryFailure(t *testing.T) {
	mockClient := &mockWorkflowClient{
		updateStatusFunc: func(
			ctx context.Context,
			executionID, status, errorMessage, errorCode string,
			errorDetails map[string]interface{},
		) error {
			return errors.New("temporary 503")
		},
	}
	timeline := &timelineSpy{}
	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       timeline,
	}

	handler.updateStatusWithRetry(
		context.Background(),
		"op-1",
		"exec-1",
		"failed",
		"bridge failed",
		"WORKFLOW_EXECUTION_ERROR",
		map[string]interface{}{"http_status": 503},
		nil,
	)

	assert.Equal(t, 1, mockClient.updateStatusCalls, "handler must delegate retries to transport client")
	require.Len(t, timeline.records, 2)
	assert.Equal(t, "external.orchestrator.update_workflow_status.started", timeline.records[0].event)
	assert.Equal(t, "external.orchestrator.update_workflow_status.failed", timeline.records[1].event)
	assert.Equal(t, 1, timeline.records[0].metadata["attempt"])
	assert.Equal(t, 1, timeline.records[1].metadata["attempt"])
	assert.Equal(t, "temporary 503", timeline.records[1].metadata["error"])
}

func TestWorkflowHandler_UpdateStatusWithRetry_RecordsSingleAttemptOnSuccess(t *testing.T) {
	mockClient := &mockWorkflowClient{}
	timeline := &timelineSpy{}
	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       timeline,
	}

	handler.updateStatusWithRetry(
		context.Background(),
		"op-1",
		"exec-1",
		"completed",
		"",
		"",
		nil,
		nil,
	)

	assert.Equal(t, 1, mockClient.updateStatusCalls)
	require.Len(t, timeline.records, 2)
	assert.Equal(t, "external.orchestrator.update_workflow_status.started", timeline.records[0].event)
	assert.Equal(t, "external.orchestrator.update_workflow_status.completed", timeline.records[1].event)
	assert.Equal(t, 1, timeline.records[0].metadata["attempt"])
	assert.Equal(t, 1, timeline.records[1].metadata["attempt"])
}

func TestDeriveStatusError_UsesClientErrorCodeOverFallback(t *testing.T) {
	err := &orchestrator.ClientError{
		StatusCode: 503,
		Message:    "service unavailable",
		Code:       "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED",
		RequestID:  "req-1",
	}

	code, details := deriveStatusError(err, "WORKFLOW_EXECUTION_ERROR")
	assert.Equal(t, "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED", code)
	require.NotNil(t, details)
	assert.Equal(t, 503, details["http_status"])
	assert.Equal(t, "req-1", details["request_id"])
}

func TestDeriveStatusError_PreservesOperationExecutionErrorCodePrecedence(t *testing.T) {
	err := fmt.Errorf(
		"wrapped: %w",
		handlers.NewOperationExecutionError(
			handlers.ErrorCodePoolRuntimeBridgeRetryBudgetExhausted,
			"retry budget exhausted",
		),
	)

	code, details := deriveStatusError(err, "WORKFLOW_EXECUTION_ERROR")
	assert.Equal(t, handlers.ErrorCodePoolRuntimeBridgeRetryBudgetExhausted, code)
	require.NotNil(t, details)
	assert.Equal(t, "retry budget exhausted", details["operation_error"])
}

func TestWorkflowHandler_ExecuteWorkflow_LatchesPoolRouteAtExecutionStart(t *testing.T) {
	var routeEnabled atomic.Bool
	routeEnabled.Store(true)

	bridge := &poolopsTestBridgeClient{
		res: &poolops.BridgeResponse{Result: map[string]interface{}{"status": "ok"}},
	}
	adapter := poolops.NewAdapterWithConfig(bridge, zap.NewNop(), poolops.AdapterConfig{
		PoolRouteEnabledProvider: routeEnabled.Load,
	})

	mockClient := &mockWorkflowClient{
		getExecutionFunc: func(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
			return nil, errors.New("fetch failed")
		},
	}
	handler := &WorkflowHandler{
		workflowClient: mockClient,
		logger:         zap.NewNop(),
		timeline:       tracing.NewNoopTimeline(),
		poolAdapter:    adapter,
	}

	msg := &models.OperationMessage{
		OperationID:   "op-1",
		OperationType: "execute_workflow",
		Payload: models.OperationPayload{
			Data: map[string]interface{}{"execution_id": "exec-1"},
		},
	}
	result := handler.ExecuteWorkflow(context.Background(), msg)
	assert.False(t, result.Success)

	routeEnabled.Store(false)
	_, err := adapter.Execute(context.Background(), &handlers.OperationRequest{
		OperationType: "pool.prepare_input",
		ExecutionID:   "exec-1",
		NodeID:        "node-1",
	})
	require.NoError(t, err)
	assert.Equal(t, 1, bridge.callCount)
}

type poolopsTestBridgeClient struct {
	callCount int
	res       *poolops.BridgeResponse
	err       error
}

func (m *poolopsTestBridgeClient) ExecutePoolRuntimeStep(
	ctx context.Context,
	req *poolops.BridgeRequest,
) (*poolops.BridgeResponse, error) {
	m.callCount++
	return m.res, m.err
}
