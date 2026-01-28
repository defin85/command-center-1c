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

// MaxIterationsHardLimit is the safety limit for loop iterations.
const MaxIterationsHardLimit = 10000

// LoopHandler executes loop nodes with count, while, and foreach modes.
//
// Loop modes:
//   - count: Execute body N times (for i in range(N))
//   - while: Execute body while condition is true
//   - foreach: Execute body for each item in collection
//
// Context updates for each iteration:
//   - loop.index: Current iteration index (0-based)
//   - loop.first: True if first iteration
//   - loop.last: True if last iteration (count/foreach only)
//   - item: Current item (foreach mode only)
//
// Safety:
//   - Hard limit of 10000 iterations
//   - Respects max_iterations from config
//   - Checks context cancellation between iterations
type LoopHandler struct {
	registry       *HandlerRegistry
	templateEngine TemplateRenderer
	logger         *zap.Logger
}

// NewLoopHandler creates a new loop handler.
func NewLoopHandler(deps *HandlerDependencies, registry *HandlerRegistry) *LoopHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &LoopHandler{
		registry:       registry,
		templateEngine: deps.TemplateEngine,
		logger:         logger.Named("loop_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *LoopHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeLoop}
}

// IterationResult holds the result of a single loop iteration.
type IterationResult struct {
	Iteration int
	Item      interface{}
	Result    interface{}
	Error     error
}

// HandleNode executes a loop based on its configuration.
func (h *LoopHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing loop node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Get loop config
	config := node.LoopConfig
	if config == nil {
		h.logger.Error("Loop node missing config",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("loop node %s missing loop_config", node.ID),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	// Calculate max iterations
	maxIterations := config.MaxIterations
	if maxIterations <= 0 || maxIterations > MaxIterationsHardLimit {
		maxIterations = MaxIterationsHardLimit
	}

	h.logger.Debug("Loop config",
		zap.String("node_id", node.ID),
		zap.String("mode", string(config.Mode)),
		zap.String("body_node", config.BodyNode),
		zap.Int("max_iterations", maxIterations))

	// Execute loop based on mode
	var result *LoopResult
	var err error

	switch config.Mode {
	case models.LoopModeCount:
		result, err = h.executeCountLoop(ctx, node, config, execCtx, maxIterations)
	case models.LoopModeWhile:
		result, err = h.executeWhileLoop(ctx, node, config, execCtx, maxIterations)
	case models.LoopModeForeach:
		result, err = h.executeForeachLoop(ctx, node, config, execCtx, maxIterations)
	default:
		err = fmt.Errorf("unknown loop mode: %s", config.Mode)
	}

	if err != nil {
		h.logger.Error("Loop execution failed",
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

	h.logger.Debug("Loop execution completed",
		zap.String("node_id", node.ID),
		zap.Int("iterations", result.Iterations),
		zap.Duration("duration", time.Since(startTime)))

	return &executor.NodeResult{
		NodeID: node.ID,
		Status: executor.NodeStatusCompleted,
		Output: map[string]interface{}{
			"mode":                   string(result.Mode),
			"iterations":             result.Iterations,
			"results":                result.Results,
			"max_iterations_reached": result.MaxIterationsReached,
			"total_items":            result.TotalItems,
			"truncated":              result.Truncated,
		},
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}, nil
}

// LoopResult holds the aggregated results of loop execution.
type LoopResult struct {
	Mode                 models.LoopMode
	Iterations           int
	Results              []interface{}
	MaxIterationsReached bool
	TotalItems           int
	Truncated            bool
}

// executeCountLoop executes a fixed number of iterations.
func (h *LoopHandler) executeCountLoop(
	ctx context.Context,
	node *models.Node,
	config *models.LoopNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	maxIterations int,
) (*LoopResult, error) {
	if config.Count <= 0 {
		return nil, fmt.Errorf("count must be positive for count loop mode")
	}

	count := config.Count
	if count > maxIterations {
		count = maxIterations
	}

	result := &LoopResult{
		Mode:    models.LoopModeCount,
		Results: make([]interface{}, 0, count),
	}

	for i := 0; i < count; i++ {
		// Check for cancellation
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		// Execute iteration
		iterResult, err := h.executeIteration(ctx, node, config, execCtx, i, count, nil)
		if err != nil {
			return nil, fmt.Errorf("loop iteration %d failed: %w", i, err)
		}

		result.Results = append(result.Results, map[string]interface{}{
			"iteration": i,
			"result":    iterResult,
		})
		result.Iterations++
	}

	result.MaxIterationsReached = config.Count > maxIterations

	return result, nil
}

// executeWhileLoop executes while condition is true.
func (h *LoopHandler) executeWhileLoop(
	ctx context.Context,
	node *models.Node,
	config *models.LoopNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	maxIterations int,
) (*LoopResult, error) {
	if config.Condition == "" {
		return nil, fmt.Errorf("condition is required for while loop mode")
	}

	result := &LoopResult{
		Mode:    models.LoopModeWhile,
		Results: make([]interface{}, 0),
	}

	// Working context that accumulates results
	workingCtx := execCtx

	for iteration := 0; iteration < maxIterations; iteration++ {
		// Check for cancellation
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		// Evaluate condition
		shouldContinue, err := h.evaluateCondition(ctx, config.Condition, workingCtx, iteration)
		if err != nil {
			h.logger.Error("Failed to evaluate while condition",
				zap.String("node_id", node.ID),
				zap.Int("iteration", iteration),
				zap.Error(err))
			break
		}

		if !shouldContinue {
			break
		}

		// Execute iteration
		iterResult, err := h.executeIteration(ctx, node, config, workingCtx, iteration, -1, nil)
		if err != nil {
			return nil, fmt.Errorf("loop iteration %d failed: %w", iteration, err)
		}

		result.Results = append(result.Results, map[string]interface{}{
			"iteration": iteration,
			"result":    iterResult,
		})
		result.Iterations++

		// Update working context with iteration result
		if iterResultMap, ok := iterResult.(map[string]interface{}); ok {
			workingCtx = workingCtx.Merge(iterResultMap)
		}
	}

	result.MaxIterationsReached = result.Iterations >= maxIterations

	return result, nil
}

// executeForeachLoop executes for each item in collection.
func (h *LoopHandler) executeForeachLoop(
	ctx context.Context,
	node *models.Node,
	config *models.LoopNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	maxIterations int,
) (*LoopResult, error) {
	if config.Items == "" {
		return nil, fmt.Errorf("items is required for foreach loop mode")
	}

	// Resolve items collection from context
	items, err := h.resolveItems(ctx, config.Items, execCtx)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve items: %w", err)
	}

	result := &LoopResult{
		Mode:       models.LoopModeForeach,
		Results:    make([]interface{}, 0),
		TotalItems: len(items),
	}

	// Apply max iterations limit
	itemsToProcess := items
	if len(items) > maxIterations {
		itemsToProcess = items[:maxIterations]
		result.Truncated = true
	}

	for i, item := range itemsToProcess {
		// Check for cancellation
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		default:
		}

		// Execute iteration with current item
		iterResult, err := h.executeIteration(ctx, node, config, execCtx, i, len(itemsToProcess), item)
		if err != nil {
			return nil, fmt.Errorf("loop iteration %d failed: %w", i, err)
		}

		result.Results = append(result.Results, map[string]interface{}{
			"iteration": i,
			"item":      item,
			"result":    iterResult,
		})
		result.Iterations++
	}

	return result, nil
}

// executeIteration executes a single loop iteration.
func (h *LoopHandler) executeIteration(
	ctx context.Context,
	node *models.Node,
	config *models.LoopNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	index int,
	totalCount int,
	item interface{},
) (interface{}, error) {
	// Placeholder implementation: iteration context is only used in ExecuteIterationWithDAG.

	// In production, we would execute the body node here.
	// For now, return a placeholder result.
	h.logger.Debug("Executing loop iteration",
		zap.String("node_id", node.ID),
		zap.String("body_node", config.BodyNode),
		zap.Int("iteration", index))

	// Placeholder result - in production, this would call the handler for body_node
	return map[string]interface{}{
		"iteration_executed": true,
		"body_node":          config.BodyNode,
		"index":              index,
	}, nil
}

// ExecuteIterationWithDAG executes a single loop iteration with access to the full DAG.
// This is the production version that should be used when DAG is available.
func (h *LoopHandler) ExecuteIterationWithDAG(
	ctx context.Context,
	dag *models.DAG,
	config *models.LoopNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	index int,
	totalCount int,
	item interface{},
) (interface{}, error) {
	// Create iteration context with loop variables
	iterCtx := execCtx.PushScope()

	// Set loop variables
	loopVars := map[string]interface{}{
		"index": index,
		"first": index == 0,
	}
	if totalCount >= 0 {
		loopVars["last"] = index == totalCount-1
	}
	iterCtx = iterCtx.SetScoped("loop", loopVars)
	iterCtx = iterCtx.SetScoped("loop_index", index)
	iterCtx = iterCtx.SetScoped("loop_first", index == 0)
	if totalCount >= 0 {
		iterCtx = iterCtx.SetScoped("loop_last", index == totalCount-1)
	}

	// Set item for foreach mode
	if item != nil {
		loopVar := config.LoopVar
		if loopVar == "" {
			loopVar = "item"
		}
		iterCtx = iterCtx.SetScoped(loopVar, item)
		iterCtx = iterCtx.SetScoped("item", item)
	}

	// Get body node from DAG
	bodyNode := dag.GetNode(config.BodyNode)
	if bodyNode == nil {
		return nil, fmt.Errorf("body node %s not found in DAG", config.BodyNode)
	}

	// Get handler for body node
	handler, ok := h.registry.Get(bodyNode.Type)
	if !ok {
		return nil, fmt.Errorf("no handler for node type: %s", bodyNode.Type)
	}

	// Execute body node
	result, err := handler.HandleNode(ctx, bodyNode, iterCtx)
	if err != nil {
		return nil, err
	}

	return result.Output, nil
}

// evaluateCondition evaluates a while loop condition.
func (h *LoopHandler) evaluateCondition(
	ctx context.Context,
	condition string,
	execCtx *wfcontext.ExecutionContext,
	iteration int,
) (bool, error) {
	// Add iteration to context for condition evaluation
	evalCtx := execCtx.SetScoped("loop_index", iteration)

	if h.templateEngine != nil {
		renderCtx := evalCtx.ToMap()
		rendered, err := h.templateEngine.Render(ctx, condition, renderCtx)
		if err != nil {
			return false, err
		}
		return isTruthy(rendered), nil
	}

	// Simple evaluation without template engine
	return isTruthy(condition), nil
}

// resolveItems resolves the items expression to a slice.
func (h *LoopHandler) resolveItems(
	ctx context.Context,
	itemsExpr string,
	execCtx *wfcontext.ExecutionContext,
) ([]interface{}, error) {
	// Try to render with template engine
	if h.templateEngine != nil {
		renderCtx := execCtx.ToMap()
		rendered, err := h.templateEngine.Render(ctx, itemsExpr, renderCtx)
		if err != nil {
			return nil, fmt.Errorf("failed to render items expression: %w", err)
		}

		// Try to parse as JSON array
		var items []interface{}
		if err := json.Unmarshal([]byte(rendered), &items); err == nil {
			return items, nil
		}

		// If not JSON, try as simple string
		return []interface{}{rendered}, nil
	}

	// Try to resolve from context using dot notation
	return h.resolvePath(execCtx, itemsExpr)
}

// resolvePath resolves a dot notation path to a slice.
func (h *LoopHandler) resolvePath(
	execCtx *wfcontext.ExecutionContext,
	path string,
) ([]interface{}, error) {
	// Clean path (remove template markers if present)
	path = strings.TrimSpace(path)
	path = strings.TrimPrefix(path, "{{")
	path = strings.TrimSuffix(path, "}}")
	path = strings.TrimSpace(path)

	// Get value from context
	val, ok := execCtx.Get(path)
	if !ok {
		return nil, fmt.Errorf("path '%s' not found in context", path)
	}

	// Convert to slice
	switch v := val.(type) {
	case []interface{}:
		return v, nil
	case []string:
		result := make([]interface{}, len(v))
		for i, s := range v {
			result[i] = s
		}
		return result, nil
	case []int:
		result := make([]interface{}, len(v))
		for i, n := range v {
			result[i] = n
		}
		return result, nil
	case []map[string]interface{}:
		result := make([]interface{}, len(v))
		for i, m := range v {
			result[i] = m
		}
		return result, nil
	default:
		return nil, fmt.Errorf("path '%s' is not a list (got %T)", path, val)
	}
}
