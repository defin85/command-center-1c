package handlers

import (
	"context"
	"fmt"
	"strings"
	"time"

	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// MaxSubworkflowDepthHardLimit is the safety limit for subworkflow nesting.
const MaxSubworkflowDepthHardLimit = 20

// SubworkflowDepthKey is the context key for tracking recursion depth.
const SubworkflowDepthKey = "__subworkflow_depth"

// SubworkflowHandler executes nested workflow templates.
//
// Flow:
//  1. Check recursion depth to prevent infinite loops
//  2. Load subworkflow DAG from workflow store
//  3. Map input context using input_mapping
//  4. Create new executor and execute subworkflow
//  5. Map output context using output_mapping
//  6. Return result with mapped outputs
//
// Safety:
//   - Hard limit of 20 levels of nesting
//   - Respects max_depth from config
//   - Recursion depth tracking via context
type SubworkflowHandler struct {
	workflowStore   WorkflowStore
	executorFactory ExecutorFactory
	logger          *zap.Logger
}

// NewSubworkflowHandler creates a new subworkflow handler.
func NewSubworkflowHandler(deps *HandlerDependencies) *SubworkflowHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &SubworkflowHandler{
		workflowStore:   deps.WorkflowStore,
		executorFactory: deps.ExecutorFactory,
		logger:          logger.Named("subworkflow_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *SubworkflowHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeSubworkflow}
}

// HandleNode executes a nested subworkflow.
func (h *SubworkflowHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing subworkflow node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Get subworkflow config
	config := node.SubworkflowConfig
	if config == nil {
		h.logger.Error("Subworkflow node missing config",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("subworkflow node %s missing subworkflow_config", node.ID),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Calculate max depth
	maxDepth := config.MaxDepth
	if maxDepth <= 0 || maxDepth > MaxSubworkflowDepthHardLimit {
		maxDepth = MaxSubworkflowDepthHardLimit
	}

	// Check recursion depth
	currentDepth := h.getCurrentDepth(execCtx)
	if currentDepth >= maxDepth {
		h.logger.Error("Subworkflow recursion depth exceeded",
			zap.String("node_id", node.ID),
			zap.Int("current_depth", currentDepth),
			zap.Int("max_depth", maxDepth))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("subworkflow recursion depth exceeded: %d >= %d", currentDepth, maxDepth),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	h.logger.Debug("Subworkflow config",
		zap.String("node_id", node.ID),
		zap.String("workflow_id", config.WorkflowID),
		zap.Int("current_depth", currentDepth),
		zap.Int("max_depth", maxDepth))

	// Check for workflow store
	if h.workflowStore == nil {
		h.logger.Warn("No workflow store configured, returning placeholder result",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID: node.ID,
			Status: executor.NodeStatusCompleted,
			Output: map[string]interface{}{
				"subworkflow_id":    config.WorkflowID,
				"execution_skipped": true,
				"reason":            "No workflow store configured",
				"recursion_depth":   currentDepth,
			},
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Load subworkflow DAG
	subDAG, err := h.workflowStore.GetWorkflow(ctx, config.WorkflowID)
	if err != nil {
		h.logger.Error("Failed to load subworkflow",
			zap.String("node_id", node.ID),
			zap.String("workflow_id", config.WorkflowID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("failed to load subworkflow %s: %w", config.WorkflowID, err),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Create subworkflow context with mapped inputs
	subCtx := wfcontext.NewExecutionContext(
		fmt.Sprintf("%s-sub-%s", execCtx.ExecutionID(), node.ID),
		config.WorkflowID,
	)

	// Set recursion depth
	subCtx = subCtx.Set(SubworkflowDepthKey, currentDepth+1)

	// Map input variables
	if config.InputMapping != nil {
		for subVar, parentExpr := range config.InputMapping {
			val, err := h.resolveValue(execCtx, parentExpr)
			if err != nil {
				h.logger.Warn("Failed to map input variable",
					zap.String("sub_var", subVar),
					zap.String("parent_expr", parentExpr),
					zap.Error(err))
				continue
			}
			subCtx = subCtx.Set(subVar, val)
		}
	}

	// Check for executor factory
	if h.executorFactory == nil {
		h.logger.Warn("No executor factory configured, returning placeholder result",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID: node.ID,
			Status: executor.NodeStatusCompleted,
			Output: map[string]interface{}{
				"subworkflow_id":    config.WorkflowID,
				"execution_skipped": true,
				"reason":            "No executor factory configured",
				"recursion_depth":   currentDepth + 1,
			},
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Create subworkflow executor
	subExecutor, err := h.executorFactory.Create(subDAG, h.logger)
	if err != nil {
		h.logger.Error("Failed to create subworkflow executor",
			zap.String("node_id", node.ID),
			zap.String("workflow_id", config.WorkflowID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("failed to create subworkflow executor: %w", err),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Execute subworkflow
	resultCtx, err := subExecutor.Execute(ctx, subCtx)
	if err != nil {
		h.logger.Error("Subworkflow execution failed",
			zap.String("node_id", node.ID),
			zap.String("workflow_id", config.WorkflowID),
			zap.Error(err))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("subworkflow execution failed: %w", err),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Map output variables
	output := make(map[string]interface{})
	if config.OutputMapping != nil {
		for parentVar, subExpr := range config.OutputMapping {
			val, err := h.resolveValue(resultCtx, subExpr)
			if err != nil {
				h.logger.Warn("Failed to map output variable",
					zap.String("parent_var", parentVar),
					zap.String("sub_expr", subExpr),
					zap.Error(err))
				continue
			}
			output[parentVar] = val
		}
	} else {
		// If no output mapping, return entire subworkflow context
		output = resultCtx.ToMap()
	}

	h.logger.Debug("Subworkflow execution completed",
		zap.String("node_id", node.ID),
		zap.String("workflow_id", config.WorkflowID),
		zap.Int("recursion_depth", currentDepth+1),
		zap.Duration("duration", time.Since(startTime)))

	return &executor.NodeResult{
		NodeID: node.ID,
		Status: executor.NodeStatusCompleted,
		Output: map[string]interface{}{
			"subworkflow_id":  config.WorkflowID,
			"recursion_depth": currentDepth + 1,
			"result":          output,
		},
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}, nil
}

// getCurrentDepth gets the current recursion depth from context.
func (h *SubworkflowHandler) getCurrentDepth(ctx *wfcontext.ExecutionContext) int {
	if val, ok := ctx.GetInt(SubworkflowDepthKey); ok {
		return val
	}
	return 0
}

// resolveValue resolves a value from context using dot notation.
func (h *SubworkflowHandler) resolveValue(ctx *wfcontext.ExecutionContext, path string) (interface{}, error) {
	// Clean path
	path = strings.TrimSpace(path)

	// Try direct access first
	if val, ok := ctx.Get(path); ok {
		return val, nil
	}

	// Path not found
	return nil, fmt.Errorf("path '%s' not found in context", path)
}

// SubworkflowBuilder helps construct subworkflow configurations.
type SubworkflowBuilder struct {
	config *models.SubworkflowNodeConfig
}

// NewSubworkflowBuilder creates a new builder with default config.
func NewSubworkflowBuilder(workflowID string) *SubworkflowBuilder {
	return &SubworkflowBuilder{
		config: &models.SubworkflowNodeConfig{
			WorkflowID:    workflowID,
			InputMapping:  make(map[string]string),
			OutputMapping: make(map[string]string),
			MaxDepth:      10,
		},
	}
}

// WithInputMapping adds an input mapping.
func (b *SubworkflowBuilder) WithInputMapping(subVar, parentExpr string) *SubworkflowBuilder {
	b.config.InputMapping[subVar] = parentExpr
	return b
}

// WithOutputMapping adds an output mapping.
func (b *SubworkflowBuilder) WithOutputMapping(parentVar, subExpr string) *SubworkflowBuilder {
	b.config.OutputMapping[parentVar] = subExpr
	return b
}

// WithMaxDepth sets the maximum recursion depth.
func (b *SubworkflowBuilder) WithMaxDepth(depth int) *SubworkflowBuilder {
	b.config.MaxDepth = depth
	return b
}

// Build returns the configured SubworkflowNodeConfig.
func (b *SubworkflowBuilder) Build() *models.SubworkflowNodeConfig {
	return b.config
}

// CreateSubworkflowNode creates a new subworkflow node with the builder's config.
func (b *SubworkflowBuilder) CreateSubworkflowNode(id, name string) *models.Node {
	node := models.NewSubworkflowNode(id, name, b.config.WorkflowID)
	node.SubworkflowConfig = b.config
	return node
}
