package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

const (
	poolPublicationOperationType     = "pool.publication_odata"
	poolPublicationPayloadContextKey = "pool_runtime_publication_payload"
)

// OperationHandler executes operation nodes.
// Operation nodes render templates and execute operations against 1C databases
// via OData or RAS backends.
//
// Flow:
//  1. Parse operation config from node
//  2. Render payload with template engine
//  3. Execute operation via executor
//  4. Return result with output data
type OperationHandler struct {
	templateEngine TemplateRenderer
	executor       OperationExecutor
	logger         *zap.Logger
}

// NewOperationHandler creates a new operation handler.
func NewOperationHandler(deps *HandlerDependencies) *OperationHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &OperationHandler{
		templateEngine: deps.TemplateEngine,
		executor:       deps.OperationExecutor,
		logger:         logger.Named("operation_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *OperationHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeOperation}
}

// HandleNode executes an operation node.
func (h *OperationHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing operation node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("template_id", node.TemplateID),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Parse operation config
	config, err := parseOperationConfig(node)
	if err != nil {
		h.logger.Error("Failed to parse operation config",
			zap.String("node_id", node.ID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("invalid operation config: %w", err),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Render payload with template engine
	var renderedPayload map[string]interface{}
	if h.templateEngine != nil && config.Payload != nil {
		renderCtx := execCtx.ToMap()
		renderedPayload, err = h.templateEngine.RenderJSON(ctx, config.Payload, renderCtx)
		if err != nil {
			h.logger.Error("Template rendering failed",
				zap.String("node_id", node.ID),
				zap.Error(err))
			return &executor.NodeResult{
				NodeID:      node.ID,
				Status:      executor.NodeStatusFailed,
				Error:       fmt.Errorf("template rendering failed: %w", err),
				StartedAt:   startTime,
				CompletedAt: time.Now(),
				Duration:    time.Since(startTime),
			}, nil
		}
	} else {
		renderedPayload = config.Payload
	}

	// Check for operation executor
	if h.executor == nil {
		if isPoolOperationType(config.OperationType) {
			err := NewOperationExecutionError(
				ErrorCodeWorkflowOperationExecutorNotConfigured,
				"pool operation executor is not configured",
			)
			h.logger.Error("Pool operation executor is not configured",
				zap.String("node_id", node.ID),
				zap.String("operation_type", config.OperationType),
				zap.Error(err),
			)
			return &executor.NodeResult{
				NodeID:      node.ID,
				Status:      executor.NodeStatusFailed,
				Error:       err,
				StartedAt:   startTime,
				CompletedAt: time.Now(),
				Duration:    time.Since(startTime),
			}, nil
		}

		h.logger.Warn("No operation executor configured, returning rendered data only",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID: node.ID,
			Status: executor.NodeStatusCompleted,
			Output: map[string]interface{}{
				"rendered_payload":  renderedPayload,
				"execution_skipped": true,
				"reason":            "No operation executor configured",
				"operation_type":    config.OperationType,
				"target_entity":     config.TargetEntity,
			},
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Extract target databases from context
	targetDatabases := extractTargetDatabases(execCtx, node)
	tenantID, _ := execCtx.GetString("tenant_id")
	poolRunID, _ := execCtx.GetString("pool_run_id")
	operationID, _ := execCtx.GetString("operation_id")
	stepAttempt := getStepAttempt(execCtx, node.ID)
	operationPayload := renderedPayload
	if operationPayload == nil {
		operationPayload = resolveOperationPayloadFromContext(config.OperationType, execCtx)
	}

	// Build operation request
	req := &OperationRequest{
		OperationID:     operationID,
		OperationType:   config.OperationType,
		TargetEntity:    config.TargetEntity,
		Payload:         operationPayload,
		TemplateID:      config.TemplateID,
		OperationRef:    node.OperationRef,
		TargetDatabases: targetDatabases,
		TimeoutSeconds:  getNodeTimeout(node),
		ExecutionID:     execCtx.ExecutionID(),
		NodeID:          node.ID,
		TenantID:        tenantID,
		PoolRunID:       poolRunID,
		StepAttempt:     stepAttempt,
	}

	h.logger.Debug("Executing operation",
		zap.String("node_id", node.ID),
		zap.String("operation_type", config.OperationType),
		zap.String("target_entity", config.TargetEntity),
		zap.Int("target_db_count", len(targetDatabases)))

	// Execute operation
	result, err := h.executor.Execute(ctx, req)
	if err != nil {
		h.logger.Error("Operation execution failed",
			zap.String("node_id", node.ID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       err,
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	h.logger.Debug("Operation completed successfully",
		zap.String("node_id", node.ID),
		zap.Duration("duration", time.Since(startTime)))

	return &executor.NodeResult{
		NodeID:      node.ID,
		Status:      executor.NodeStatusCompleted,
		Output:      result,
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}, nil
}

// parseOperationConfig extracts operation configuration from node.
func parseOperationConfig(node *models.Node) (*models.OperationNodeConfig, error) {
	config := &models.OperationNodeConfig{
		TemplateID:    node.TemplateID,
		OperationType: node.TemplateID,
	}

	if node.OperationRef != nil && node.OperationRef.Alias != "" {
		config.OperationType = node.OperationRef.Alias
	}

	// For operation nodes, TemplateID is typically required
	if config.TemplateID == "" && config.OperationType == "" {
		return nil, fmt.Errorf("operation node requires template_id or operation_type")
	}

	return config, nil
}

// extractTargetDatabases gets target database IDs from context and node config.
// Handles both new format ([]models.TargetDatabase) and JSON-deserialized format ([]interface{}).
func extractTargetDatabases(execCtx *wfcontext.ExecutionContext, node *models.Node) []string {
	// Check context for target_databases
	if val, ok := execCtx.Get("target_databases"); ok {
		// Handle []interface{} from JSON deserialization
		if dbs, ok := val.([]interface{}); ok {
			result := make([]string, 0, len(dbs))
			for _, db := range dbs {
				// Try to extract ID from map (JSON object format)
				if m, ok := db.(map[string]interface{}); ok {
					if id, ok := m["id"].(string); ok && id != "" {
						result = append(result, id)
						continue
					}
				}
				// Fallback: try direct string (old format)
				if s, ok := db.(string); ok {
					result = append(result, s)
				}
			}
			if len(result) > 0 {
				return result
			}
		}
		// Handle []string (backward compatibility)
		if dbs, ok := val.([]string); ok {
			return dbs
		}
	}

	// Check for target_database_ids (helper field from workflow_handler)
	if val, ok := execCtx.Get("target_database_ids"); ok {
		if ids, ok := val.([]string); ok {
			return ids
		}
		if ids, ok := val.([]interface{}); ok {
			result := make([]string, 0, len(ids))
			for _, id := range ids {
				if s, ok := id.(string); ok {
					result = append(result, s)
				}
			}
			if len(result) > 0 {
				return result
			}
		}
	}

	// Check for single database_id
	if val, ok := execCtx.GetString("database_id"); ok {
		return []string{val}
	}

	return nil
}

// getNodeTimeout gets timeout from node config or returns default.
func getNodeTimeout(node *models.Node) int {
	if node.Config != nil && node.Config.TimeoutSeconds > 0 {
		return node.Config.TimeoutSeconds
	}
	return 300 // 5 minutes default
}

func isPoolOperationType(operationType string) bool {
	return strings.HasPrefix(operationType, "pool.")
}

func resolveOperationPayloadFromContext(
	operationType string,
	execCtx *wfcontext.ExecutionContext,
) map[string]interface{} {
	if execCtx == nil || operationType != poolPublicationOperationType {
		return nil
	}
	rawPayload, ok := execCtx.Get(poolPublicationPayloadContextKey)
	if !ok {
		return nil
	}
	payload, ok := rawPayload.(map[string]interface{})
	if !ok || len(payload) == 0 {
		return nil
	}
	return payload
}

func getStepAttempt(execCtx *wfcontext.ExecutionContext, nodeID string) int {
	if execCtx == nil {
		return 1
	}
	if nodeID != "" {
		if v, ok := execCtx.GetInt(fmt.Sprintf("step_attempts.%s", nodeID)); ok && v > 0 {
			return v
		}
	}
	if v, ok := execCtx.GetInt("step_attempt"); ok && v > 0 {
		return v
	}
	return 1
}

// OperationNodeConfigFromJSON parses operation config from JSON.
func OperationNodeConfigFromJSON(data []byte) (*models.OperationNodeConfig, error) {
	var config models.OperationNodeConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse operation config: %w", err)
	}
	return &config, nil
}
