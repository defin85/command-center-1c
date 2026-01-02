package workflowops

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/models"
	"github.com/commandcenter1c/commandcenter/shared/tracing"
	"github.com/commandcenter1c/commandcenter/worker/internal/events"
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
	timeline        tracing.TimelineRecorder
}

// NewWorkflowHandler creates a new workflow handler.
func NewWorkflowHandler(
	workflowClient WorkflowClient,
	redisClient *redis.Client,
	orchestratorURL string,
	logger *zap.Logger,
	timeline tracing.TimelineRecorder,
) (*WorkflowHandler, error) {
	slogger := slog.Default()
	if logger == nil {
		logger = zap.NewNop()
	}
	if timeline == nil {
		timeline = tracing.NewNoopTimeline()
	}

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
		timeline:        timeline,
	}, nil
}

// ExecuteWorkflow executes a workflow by execution_id.
// The execution_id references an existing WorkflowExecution in Orchestrator.
func (h *WorkflowHandler) ExecuteWorkflow(ctx context.Context, msg *models.OperationMessage) models.DatabaseResultV2 {
	start := time.Now()
	workflowMetadata := events.WorkflowMetadataFromMessage(msg)
	if h.logger == nil {
		h.logger = zap.NewNop()
	}
	if h.timeline == nil {
		h.timeline = tracing.NewNoopTimeline()
	}

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

	h.timeline.Record(ctx, msg.OperationID, "workflow.execute.started", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
	}, workflowMetadata))

	h.logger.Info("executing workflow",
		zap.String("execution_id", executionID),
		zap.String("operation_id", msg.OperationID),
	)

	// Fetch workflow execution from Orchestrator
	h.timeline.Record(ctx, msg.OperationID, "external.orchestrator.get_workflow_execution.started", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
	}, workflowMetadata))
	fetchStart := time.Now()
	execution, err := h.workflowClient.GetWorkflowExecution(ctx, executionID)
	if err != nil {
		h.timeline.Record(ctx, msg.OperationID, "external.orchestrator.get_workflow_execution.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"duration_ms":  time.Since(fetchStart).Milliseconds(),
			"error":        err.Error(),
		}, workflowMetadata))
		h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "failed", err.Error(), workflowMetadata)
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
	h.timeline.Record(ctx, msg.OperationID, "external.orchestrator.get_workflow_execution.completed", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
		"duration_ms":  time.Since(fetchStart).Milliseconds(),
	}, workflowMetadata))

	// Validate workflow template
	if !execution.WorkflowTemplate.IsValid {
		h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "failed", "workflow template is not valid", workflowMetadata)
		h.timeline.Record(ctx, msg.OperationID, "workflow.execute.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"error":        "workflow template is not valid",
			"duration_ms":  time.Since(start).Milliseconds(),
		}, workflowMetadata))
		return models.DatabaseResultV2{
			Success:   false,
			Error:     "workflow template is not valid",
			ErrorCode: "INVALID_WORKFLOW",
			Duration:  time.Since(start).Seconds(),
		}
	}

	if !execution.WorkflowTemplate.IsActive {
		h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "failed", "workflow template is not active", workflowMetadata)
		h.timeline.Record(ctx, msg.OperationID, "workflow.execute.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"error":        "workflow template is not active",
			"duration_ms":  time.Since(start).Milliseconds(),
		}, workflowMetadata))
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
		h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "failed", err.Error(), workflowMetadata)
		h.timeline.Record(ctx, msg.OperationID, "workflow.execute.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"error":        err.Error(),
			"duration_ms":  time.Since(start).Milliseconds(),
		}, workflowMetadata))
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
	if len(msg.TargetDatabases) > 0 {
		// Pass TargetDatabases as objects ([]models.TargetDatabase)
		inputVars["target_databases"] = msg.TargetDatabases
		// Also pass IDs for backward compatibility
		inputVars["target_database_ids"] = msg.GetTargetDatabaseIDs()
	}

	// Execute workflow synchronously
	h.timeline.Record(ctx, msg.OperationID, "external.workflow_engine.execute.started", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
	}, workflowMetadata))
	execStart := time.Now()
	result, err := h.engine.ExecuteWorkflowSync(ctx, dagJSON, inputVars)
	if err != nil {
		h.timeline.Record(ctx, msg.OperationID, "external.workflow_engine.execute.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"duration_ms":  time.Since(execStart).Milliseconds(),
			"error":        err.Error(),
		}, workflowMetadata))
		h.logger.Error("workflow execution failed",
			zap.String("execution_id", executionID),
			zap.Error(err),
		)

		// Update status in Orchestrator
		h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "failed", err.Error(), workflowMetadata)

		h.timeline.Record(ctx, msg.OperationID, "workflow.execute.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"error":        err.Error(),
			"duration_ms":  time.Since(start).Milliseconds(),
		}, workflowMetadata))

		return models.DatabaseResultV2{
			Success:   false,
			Error:     fmt.Sprintf("workflow execution failed: %v", err),
			ErrorCode: "WORKFLOW_EXECUTION_ERROR",
			Duration:  time.Since(start).Seconds(),
		}
	}
	h.timeline.Record(ctx, msg.OperationID, "external.workflow_engine.execute.completed", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
		"duration_ms":  time.Since(execStart).Milliseconds(),
	}, workflowMetadata))

	h.logger.Info("workflow execution completed",
		zap.String("execution_id", executionID),
		zap.String("result_execution_id", result.ExecutionID),
		zap.String("status", result.Status),
		zap.Duration("duration", time.Since(start)),
	)

	// Update status in Orchestrator
	h.updateStatusWithRetry(ctx, msg.OperationID, executionID, "completed", "", workflowMetadata)

	h.timeline.Record(ctx, msg.OperationID, "workflow.execute.completed", events.MergeMetadata(map[string]interface{}{
		"execution_id": executionID,
		"duration_ms":  time.Since(start).Milliseconds(),
	}, workflowMetadata))

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
	if dag == nil {
		dag = map[string]interface{}{}
	}

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
	if _, ok := dag["config"]; !ok && len(execution.WorkflowTemplate.Config) > 0 {
		dag["config"] = execution.WorkflowTemplate.Config
	}

	if rawNodes, ok := dag["nodes"]; ok {
		if nodeList, ok := rawNodes.([]interface{}); ok {
			nodeMap := make(map[string]interface{}, len(nodeList))
			for _, node := range nodeList {
				nodeObj, ok := node.(map[string]interface{})
				if !ok {
					continue
				}
				nodeID, _ := nodeObj["id"].(string)
				if nodeID == "" {
					if legacyID, ok := nodeObj["node_id"].(string); ok && legacyID != "" {
						nodeID = legacyID
						nodeObj["id"] = legacyID
					}
				}
				if nodeID == "" {
					continue
				}
				nodeMap[nodeID] = nodeObj
			}
			if len(nodeMap) > 0 {
				dag["nodes"] = nodeMap
			}
		}
	}

	if rawEdges, ok := dag["edges"]; ok {
		if edgeList, ok := rawEdges.([]interface{}); ok {
			for _, edge := range edgeList {
				edgeObj, ok := edge.(map[string]interface{})
				if !ok {
					continue
				}
				if _, ok := edgeObj["from"]; !ok {
					if legacyFrom, ok := edgeObj["from_node"]; ok {
						edgeObj["from"] = legacyFrom
						delete(edgeObj, "from_node")
					}
				}
				if _, ok := edgeObj["to"]; !ok {
					if legacyTo, ok := edgeObj["to_node"]; ok {
						edgeObj["to"] = legacyTo
						delete(edgeObj, "to_node")
					}
				}
			}
		}
	}

	return dag
}

func (h *WorkflowHandler) updateStatusWithRetry(
	ctx context.Context,
	operationID, executionID, status, errorMessage string,
	workflowMetadata map[string]interface{},
) {
	if h.workflowClient == nil {
		return
	}
	if h.timeline == nil {
		h.timeline = tracing.NewNoopTimeline()
	}
	const maxAttempts = 3
	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		select {
		case <-ctx.Done():
			return
		default:
		}

		h.timeline.Record(ctx, operationID, "external.orchestrator.update_workflow_status.started", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"status":       status,
			"attempt":      attempt,
		}, workflowMetadata))
		start := time.Now()
		err := h.workflowClient.UpdateWorkflowExecutionStatus(ctx, executionID, status, errorMessage)
		if err == nil {
			h.timeline.Record(ctx, operationID, "external.orchestrator.update_workflow_status.completed", events.MergeMetadata(map[string]interface{}{
				"execution_id": executionID,
				"status":       status,
				"attempt":      attempt,
				"duration_ms":  time.Since(start).Milliseconds(),
			}, workflowMetadata))
			return
		}

		lastErr = err
		h.timeline.Record(ctx, operationID, "external.orchestrator.update_workflow_status.failed", events.MergeMetadata(map[string]interface{}{
			"execution_id": executionID,
			"status":       status,
			"attempt":      attempt,
			"duration_ms":  time.Since(start).Milliseconds(),
			"error":        err.Error(),
		}, workflowMetadata))
		h.logger.Warn("failed to update workflow status",
			zap.String("execution_id", executionID),
			zap.String("status", status),
			zap.Int("attempt", attempt),
			zap.Error(err),
		)
		if attempt < maxAttempts {
			backoff := time.Duration(attempt) * 200 * time.Millisecond
			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
		}
	}

	if lastErr != nil {
		h.logger.Warn("exhausted workflow status update retries",
			zap.String("execution_id", executionID),
			zap.String("status", status),
			zap.Error(lastErr),
		)
	}
}

// Close releases handler resources.
func (h *WorkflowHandler) Close() error {
	if h.engine != nil {
		return h.engine.Close()
	}
	return nil
}
