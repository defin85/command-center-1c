package workflowops

import (
	"context"

	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
)

// OrchestratorWorkflowClient adapts orchestrator.Client to WorkflowClient interface.
type OrchestratorWorkflowClient struct {
	client *orchestrator.Client
}

// NewOrchestratorWorkflowClient creates a new adapter for orchestrator.Client.
func NewOrchestratorWorkflowClient(client *orchestrator.Client) *OrchestratorWorkflowClient {
	return &OrchestratorWorkflowClient{client: client}
}

// GetWorkflowExecution fetches workflow execution from Orchestrator.
func (a *OrchestratorWorkflowClient) GetWorkflowExecution(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error) {
	return a.client.GetWorkflowExecution(ctx, executionID)
}

// UpdateWorkflowExecutionStatus updates workflow execution status in Orchestrator.
func (a *OrchestratorWorkflowClient) UpdateWorkflowExecutionStatus(ctx context.Context, executionID, status, errorMessage string) error {
	return a.client.UpdateWorkflowExecutionStatus(ctx, executionID, status, errorMessage)
}
