package handlers

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
	"golang.org/x/sync/errgroup"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// ParallelHandler executes multiple branches in parallel using goroutines.
// Uses errgroup for controlled concurrency and error handling.
//
// Flow:
//  1. Parse parallel config (branch_nodes, wait_for, fail_fast, max_concurrent)
//  2. Create errgroup with optional concurrency limit
//  3. Execute each branch in a separate goroutine
//  4. Collect results based on wait_for mode
//  5. Return aggregated results
//
// Wait modes:
//   - "all": Wait for all branches to complete
//   - "any": Return after first successful branch
//   - "N" (number): Wait for N branches to complete
type ParallelHandler struct {
	registry *HandlerRegistry
	deps     *HandlerDependencies
	logger   *zap.Logger
}

// NewParallelHandler creates a new parallel handler.
func NewParallelHandler(deps *HandlerDependencies, registry *HandlerRegistry) *ParallelHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &ParallelHandler{
		registry: registry,
		deps:     deps,
		logger:   logger.Named("parallel_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *ParallelHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeParallel}
}

// BranchResult holds the result of a single branch execution.
type BranchResult struct {
	NodeID    string
	Result    *executor.NodeResult
	Error     error
	Completed bool
}

// HandleNode executes branches in parallel and aggregates results.
func (h *ParallelHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing parallel node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Get parallel config
	config := node.ParallelConfig
	if config == nil {
		h.logger.Error("Parallel node missing config",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID:      node.ID,
			Status:      executor.NodeStatusFailed,
			Error:       fmt.Errorf("parallel node %s missing parallel_config", node.ID),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	if len(config.BranchNodes) == 0 {
		h.logger.Warn("Parallel node has no branches",
			zap.String("node_id", node.ID))
		return &executor.NodeResult{
			NodeID: node.ID,
			Status: executor.NodeStatusCompleted,
			Output: map[string]interface{}{
				"mode":      "parallel",
				"completed": []interface{}{},
				"failed":    []interface{}{},
			},
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, nil
	}

	h.logger.Debug("Parallel config",
		zap.String("node_id", node.ID),
		zap.Strings("branch_nodes", config.BranchNodes),
		zap.Bool("wait_all", config.WaitAll),
		zap.String("wait_for", config.WaitFor),
		zap.Bool("fail_fast", config.FailFast),
		zap.Int("max_concurrent", config.MaxConcurrent))

	// Execute based on wait mode
	waitFor := config.WaitFor
	if waitFor == "" {
		if config.WaitAll {
			waitFor = "all"
		} else {
			waitFor = "any"
		}
	}

	var result *ParallelResult
	var err error

	switch waitFor {
	case "all":
		result, err = h.executeWaitAll(ctx, node, config, execCtx)
	case "any":
		result, err = h.executeWaitAny(ctx, node, config, execCtx)
	default:
		// Try to parse as number
		var count int
		if _, parseErr := fmt.Sscanf(waitFor, "%d", &count); parseErr == nil && count > 0 {
			result, err = h.executeWaitCount(ctx, node, config, execCtx, count)
		} else {
			result, err = h.executeWaitAll(ctx, node, config, execCtx)
		}
	}

	if err != nil {
		h.logger.Error("Parallel execution failed",
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

	// Determine overall status
	status := executor.NodeStatusCompleted
	if config.FailFast && len(result.Failed) > 0 {
		status = executor.NodeStatusFailed
	}

	h.logger.Debug("Parallel execution completed",
		zap.String("node_id", node.ID),
		zap.Int("completed", len(result.Completed)),
		zap.Int("failed", len(result.Failed)),
		zap.Bool("timed_out", result.TimedOut),
		zap.Duration("duration", time.Since(startTime)))

	return &executor.NodeResult{
		NodeID: node.ID,
		Status: status,
		Output: map[string]interface{}{
			"mode":       result.Mode,
			"completed":  result.Completed,
			"failed":     result.Failed,
			"cancelled":  result.Cancelled,
			"timed_out":  result.TimedOut,
		},
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}, nil
}

// ParallelResult holds the aggregated results of parallel execution.
type ParallelResult struct {
	Mode      string
	Completed []map[string]interface{}
	Failed    []map[string]interface{}
	Cancelled []string
	TimedOut  bool
}

// executeWaitAll waits for all branches to complete.
func (h *ParallelHandler) executeWaitAll(
	ctx context.Context,
	node *models.Node,
	config *models.ParallelNodeConfig,
	execCtx *wfcontext.ExecutionContext,
) (*ParallelResult, error) {
	// Apply timeout if configured
	if config.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(config.TimeoutSeconds)*time.Second)
		defer cancel()
	}

	// Create errgroup with optional concurrency limit
	g, gctx := errgroup.WithContext(ctx)
	if config.MaxConcurrent > 0 {
		g.SetLimit(config.MaxConcurrent)
	}

	// Results map (thread-safe)
	results := &sync.Map{}
	var collectErr error
	var collectErrMu sync.Mutex

	// Execute each branch
	for _, branchNodeID := range config.BranchNodes {
		branchNodeID := branchNodeID // capture for closure

		g.Go(func() error {
			branchResult := h.executeBranch(gctx, branchNodeID, execCtx)
			results.Store(branchNodeID, branchResult)

			if branchResult.Error != nil && config.FailFast {
				collectErrMu.Lock()
				if collectErr == nil {
					collectErr = branchResult.Error
				}
				collectErrMu.Unlock()
				return branchResult.Error
			}
			return nil
		})
	}

	// Wait for all branches
	waitErr := g.Wait()
	timedOut := ctx.Err() == context.DeadlineExceeded

	// Collect results
	result := &ParallelResult{
		Mode:      "all",
		Completed: make([]map[string]interface{}, 0),
		Failed:    make([]map[string]interface{}, 0),
		TimedOut:  timedOut,
	}

	results.Range(func(key, value interface{}) bool {
		nodeID := key.(string)
		branchResult := value.(*BranchResult)

		if branchResult.Error != nil || !branchResult.Completed {
			result.Failed = append(result.Failed, map[string]interface{}{
				"node_id": nodeID,
				"error":   fmt.Sprintf("%v", branchResult.Error),
			})
		} else {
			var output interface{}
			if branchResult.Result != nil {
				output = branchResult.Result.Output
			}
			result.Completed = append(result.Completed, map[string]interface{}{
				"node_id": nodeID,
				"result":  output,
			})
		}
		return true
	})

	// Return error only if fail_fast and there was an error
	if config.FailFast && waitErr != nil {
		return result, waitErr
	}

	return result, nil
}

// executeWaitAny waits for the first successful branch.
func (h *ParallelHandler) executeWaitAny(
	ctx context.Context,
	node *models.Node,
	config *models.ParallelNodeConfig,
	execCtx *wfcontext.ExecutionContext,
) (*ParallelResult, error) {
	// Apply timeout if configured
	if config.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(config.TimeoutSeconds)*time.Second)
		defer cancel()
	}

	// Create cancellable context for all branches
	branchCtx, cancelBranches := context.WithCancel(ctx)
	defer cancelBranches()

	// Results channel
	resultChan := make(chan *BranchResult, len(config.BranchNodes))

	// Start all branches
	for _, branchNodeID := range config.BranchNodes {
		branchNodeID := branchNodeID
		go func() {
			result := h.executeBranch(branchCtx, branchNodeID, execCtx)
			select {
			case resultChan <- result:
			case <-branchCtx.Done():
			}
		}()
	}

	// Wait for first success
	result := &ParallelResult{
		Mode:      "any",
		Completed: make([]map[string]interface{}, 0),
		Failed:    make([]map[string]interface{}, 0),
		Cancelled: make([]string, 0),
	}

	remaining := make(map[string]bool)
	for _, nodeID := range config.BranchNodes {
		remaining[nodeID] = true
	}

	for len(remaining) > 0 {
		select {
		case branchResult := <-resultChan:
			delete(remaining, branchResult.NodeID)

			if branchResult.Error == nil && branchResult.Completed {
				// First success - cancel others and return
				cancelBranches()

				var output interface{}
				if branchResult.Result != nil {
					output = branchResult.Result.Output
				}
				result.Completed = append(result.Completed, map[string]interface{}{
					"node_id": branchResult.NodeID,
					"result":  output,
				})

				for nodeID := range remaining {
					result.Cancelled = append(result.Cancelled, nodeID)
				}

				return result, nil
			}

			// Branch failed, continue waiting
			result.Failed = append(result.Failed, map[string]interface{}{
				"node_id": branchResult.NodeID,
				"error":   fmt.Sprintf("%v", branchResult.Error),
			})

		case <-ctx.Done():
			result.TimedOut = true
			for nodeID := range remaining {
				result.Cancelled = append(result.Cancelled, nodeID)
			}
			return result, nil
		}
	}

	// All branches failed
	return result, nil
}

// executeWaitCount waits for N branches to complete.
func (h *ParallelHandler) executeWaitCount(
	ctx context.Context,
	node *models.Node,
	config *models.ParallelNodeConfig,
	execCtx *wfcontext.ExecutionContext,
	count int,
) (*ParallelResult, error) {
	if count > len(config.BranchNodes) {
		return nil, fmt.Errorf("wait_for count (%d) exceeds branch count (%d)", count, len(config.BranchNodes))
	}

	// Apply timeout if configured
	if config.TimeoutSeconds > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, time.Duration(config.TimeoutSeconds)*time.Second)
		defer cancel()
	}

	// Create cancellable context for all branches
	branchCtx, cancelBranches := context.WithCancel(ctx)
	defer cancelBranches()

	// Results channel
	resultChan := make(chan *BranchResult, len(config.BranchNodes))

	// Start all branches
	for _, branchNodeID := range config.BranchNodes {
		branchNodeID := branchNodeID
		go func() {
			result := h.executeBranch(branchCtx, branchNodeID, execCtx)
			select {
			case resultChan <- result:
			case <-branchCtx.Done():
			}
		}()
	}

	// Wait for N successes
	result := &ParallelResult{
		Mode:      fmt.Sprintf("count_%d", count),
		Completed: make([]map[string]interface{}, 0),
		Failed:    make([]map[string]interface{}, 0),
		Cancelled: make([]string, 0),
	}

	remaining := make(map[string]bool)
	for _, nodeID := range config.BranchNodes {
		remaining[nodeID] = true
	}

	for len(remaining) > 0 {
		select {
		case branchResult := <-resultChan:
			delete(remaining, branchResult.NodeID)

			if branchResult.Error == nil && branchResult.Completed {
				var output interface{}
				if branchResult.Result != nil {
					output = branchResult.Result.Output
				}
				result.Completed = append(result.Completed, map[string]interface{}{
					"node_id": branchResult.NodeID,
					"result":  output,
				})

				if len(result.Completed) >= count {
					// Got enough successes - cancel others and return
					cancelBranches()
					for nodeID := range remaining {
						result.Cancelled = append(result.Cancelled, nodeID)
					}
					return result, nil
				}
			} else {
				result.Failed = append(result.Failed, map[string]interface{}{
					"node_id": branchResult.NodeID,
					"error":   fmt.Sprintf("%v", branchResult.Error),
				})
			}

		case <-ctx.Done():
			result.TimedOut = true
			for nodeID := range remaining {
				result.Cancelled = append(result.Cancelled, nodeID)
			}
			return result, nil
		}
	}

	return result, nil
}

// executeBranch executes a single branch node.
func (h *ParallelHandler) executeBranch(
	ctx context.Context,
	nodeID string,
	execCtx *wfcontext.ExecutionContext,
) *BranchResult {
	result := &BranchResult{
		NodeID: nodeID,
	}

	// Check for cancellation
	select {
	case <-ctx.Done():
		result.Error = ctx.Err()
		return result
	default:
	}

	// Clone context for this branch (will be used in production implementation)
	_ = execCtx.Clone()

	// Get handler for the branch node
	// Note: In production, we'd need access to the DAG to get the actual node.
	// For now, we'll create a placeholder that needs to be resolved by the executor.
	h.logger.Debug("Executing branch",
		zap.String("branch_node_id", nodeID),
		zap.String("execution_id", execCtx.ExecutionID()))

	// This is a simplified implementation.
	// In production, we would:
	// 1. Get the branch node from the DAG
	// 2. Find the appropriate handler
	// 3. Execute the handler

	// For now, return a placeholder result indicating the branch should be executed
	result.Completed = true
	result.Result = &executor.NodeResult{
		NodeID: nodeID,
		Status: executor.NodeStatusCompleted,
		Output: map[string]interface{}{
			"branch_executed": true,
			"node_id":         nodeID,
		},
	}

	return result
}

// ExecuteBranchWithDAG executes a branch node with access to the full DAG.
// This is the production version that should be used when DAG is available.
func (h *ParallelHandler) ExecuteBranchWithDAG(
	ctx context.Context,
	dag *models.DAG,
	nodeID string,
	execCtx *wfcontext.ExecutionContext,
) *BranchResult {
	result := &BranchResult{
		NodeID: nodeID,
	}

	// Check for cancellation
	select {
	case <-ctx.Done():
		result.Error = ctx.Err()
		return result
	default:
	}

	// Get the node from DAG
	node := dag.GetNode(nodeID)
	if node == nil {
		result.Error = fmt.Errorf("branch node %s not found in DAG", nodeID)
		return result
	}

	// Get handler for this node type
	handler, ok := h.registry.Get(node.Type)
	if !ok {
		result.Error = fmt.Errorf("no handler for node type: %s", node.Type)
		return result
	}

	// Clone context for this branch
	branchCtx := execCtx.Clone()

	// Execute the handler
	nodeResult, err := handler.HandleNode(ctx, node, branchCtx)
	if err != nil {
		result.Error = err
		return result
	}

	result.Completed = nodeResult.Status == executor.NodeStatusCompleted
	result.Result = nodeResult
	if nodeResult.Error != nil {
		result.Error = nodeResult.Error
	}

	return result
}
