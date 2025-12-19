package processor

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/orchestrator"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/engine"
)

// WorkflowClient interface for fetching workflow data from Orchestrator.
type WorkflowClient interface {
	GetWorkflowExecution(ctx context.Context, executionID string) (*orchestrator.WorkflowExecutionData, error)
	UpdateWorkflowExecutionStatus(ctx context.Context, executionID, status, errorMessage string) error
}

// WorkflowHandler handles execute_workflow operations.
type WorkflowHandler struct {
	workflowClient  WorkflowClient
	redisClient     *redis.Client
	orchestratorURL string
	logger          *zap.Logger
	engine          *engine.Engine
}

// NewWorkflowHandler creates a new workflow handler.
func NewWorkflowHandler(
	workflowClient WorkflowClient,
	redisClient *redis.Client,
	orchestratorURL string,
	logger *zap.Logger,
) (*WorkflowHandler, error) {
	slogger := slog.Default()

	// Create workflow engine
	eng, err := engine.NewEngine(redisClient, orchestratorURL, slogger, logger, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create workflow engine: %w", err)
	}

	return &WorkflowHandler{
		workflowClient:  workflowClient,
		redisClient:     redisClient,
		orchestratorURL: orchestratorURL,
		logger:          logger,
		engine:          eng,
	}, nil
}

// ExecuteWorkflow executes a workflow by execution_id.
// The execution_id references an existing WorkflowExecution in Orchestrator.
func (h *WorkflowHandler) ExecuteWorkflow(ctx context.Context, msg *models.OperationMessage) models.DatabaseResultV2 {
	start := time.Now()

	// Extract execution_id from payload.data
	executionID, ok := msg.Payload.Data["execution_id"].(string)
	if !ok || executionID == "" {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "execution_id is required in payload.data for execute_workflow operation",
			ErrorCode: "VALIDATION_ERROR",
			Duration:  time.Since(start).Seconds(),
		}
	}

	h.logger.Info("executing workflow",
		zap.String("execution_id", executionID),
		zap.String("operation_id", msg.OperationID),
	)

	// Fetch workflow execution from Orchestrator
	execution, err := h.workflowClient.GetWorkflowExecution(ctx, executionID)
	if err != nil {
		h.logger.Error("failed to fetch workflow execution",
			zap.String("execution_id", executionID),
			zap.Error(err),
		)
		return models.DatabaseResultV2{
			Success:   false,
			Error:     fmt.Sprintf("failed to fetch workflow execution: %v", err),
			ErrorCode: "WORKFLOW_FETCH_ERROR",
			Duration:  time.Since(start).Seconds(),
		}
	}

	// Validate workflow template
	if !execution.WorkflowTemplate.IsValid {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "workflow template is not valid",
			ErrorCode: "INVALID_WORKFLOW",
			Duration:  time.Since(start).Seconds(),
		}
	}

	if !execution.WorkflowTemplate.IsActive {
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "workflow template is not active",
			ErrorCode: "INACTIVE_WORKFLOW",
			Duration:  time.Since(start).Seconds(),
		}
	}

	// Convert DAG structure to JSON for Go Workflow Engine
	dagJSON, err := json.Marshal(h.convertDAGToEngineFormat(execution))
	if err != nil {
		h.logger.Error("failed to marshal DAG structure",
			zap.String("execution_id", executionID),
			zap.Error(err),
		)
		return models.DatabaseResultV2{
			Success:   false,
			Error:     fmt.Sprintf("failed to prepare DAG: %v", err),
			ErrorCode: "DAG_MARSHAL_ERROR",
			Duration:  time.Since(start).Seconds(),
		}
	}

	// Build input variables from execution context
	inputVars := execution.InputContext
	if inputVars == nil {
		inputVars = make(map[string]interface{})
	}

	// Add operation metadata to input vars
	inputVars["operation_id"] = msg.OperationID
	// Pass TargetDatabases as objects ([]models.TargetDatabase)
	inputVars["target_databases"] = msg.TargetDatabases
	// Also pass IDs for backward compatibility
	inputVars["target_database_ids"] = msg.GetTargetDatabaseIDs()

	// Execute workflow synchronously
	result, err := h.engine.ExecuteWorkflowSync(ctx, dagJSON, inputVars)
	if err != nil {
		h.logger.Error("workflow execution failed",
			zap.String("execution_id", executionID),
			zap.Error(err),
		)

		// Update status in Orchestrator
		if updateErr := h.workflowClient.UpdateWorkflowExecutionStatus(ctx, executionID, "failed", err.Error()); updateErr != nil {
			h.logger.Warn("failed to update workflow status",
				zap.String("execution_id", executionID),
				zap.Error(updateErr),
			)
		}

		return models.DatabaseResultV2{
			Success:   false,
			Error:     fmt.Sprintf("workflow execution failed: %v", err),
			ErrorCode: "WORKFLOW_EXECUTION_ERROR",
			Duration:  time.Since(start).Seconds(),
		}
	}

	h.logger.Info("workflow execution completed",
		zap.String("execution_id", executionID),
		zap.String("result_execution_id", result.ExecutionID),
		zap.String("status", result.Status),
		zap.Duration("duration", time.Since(start)),
	)

	// Update status in Orchestrator
	if updateErr := h.workflowClient.UpdateWorkflowExecutionStatus(ctx, executionID, "completed", ""); updateErr != nil {
		h.logger.Warn("failed to update workflow status",
			zap.String("execution_id", executionID),
			zap.Error(updateErr),
		)
	}

	return models.DatabaseResultV2{
		Success: true,
		Data: map[string]interface{}{
			"execution_id":    result.ExecutionID,
			"workflow_status": result.Status,
			"output":          result.Output,
		},
		Duration: time.Since(start).Seconds(),
	}
}

// convertDAGToEngineFormat converts Orchestrator's DAG structure to Go Workflow Engine format.
func (h *WorkflowHandler) convertDAGToEngineFormat(execution *orchestrator.WorkflowExecutionData) map[string]interface{} {
	dag := execution.WorkflowTemplate.DAGStructure

	// The DAG structure from Orchestrator should match the engine format
	// Add ID and version if not present
	if _, ok := dag["id"]; !ok {
		dag["id"] = execution.WorkflowTemplate.ID
	}
	if _, ok := dag["version"]; !ok {
		dag["version"] = execution.WorkflowTemplate.VersionNumber
	}
	if _, ok := dag["name"]; !ok {
		dag["name"] = execution.WorkflowTemplate.Name
	}

	return dag
}

// Close releases handler resources.
func (h *WorkflowHandler) Close() error {
	if h.engine != nil {
		return h.engine.Close()
	}
	return nil
}
