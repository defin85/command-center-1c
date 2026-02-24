// Package executor provides DAG execution engine for workflow orchestration.
package executor

import (
	"context"
	"fmt"
	"sort"
	"time"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow"
	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/validator"
)

// NodeStatus represents the execution status of a node.
type NodeStatus string

const (
	// NodeStatusPending indicates the node has not started.
	NodeStatusPending NodeStatus = "pending"
	// NodeStatusRunning indicates the node is currently executing.
	NodeStatusRunning NodeStatus = "running"
	// NodeStatusCompleted indicates the node completed successfully.
	NodeStatusCompleted NodeStatus = "completed"
	// NodeStatusFailed indicates the node execution failed.
	NodeStatusFailed NodeStatus = "failed"
	// NodeStatusSkipped indicates the node was skipped due to conditions.
	NodeStatusSkipped NodeStatus = "skipped"
)

// NodeResult represents the result of executing a single node.
type NodeResult struct {
	// NodeID is the identifier of the executed node.
	NodeID string
	// Status is the execution status.
	Status NodeStatus
	// Output is the node's output data.
	Output interface{}
	// Error is the error if execution failed.
	Error error
	// Duration is how long execution took.
	Duration time.Duration
	// StartedAt is when execution started.
	StartedAt time.Time
	// CompletedAt is when execution completed.
	CompletedAt time.Time
}

// NodeHandler interface for executing nodes.
// Implementations handle specific node types (operation, condition, parallel, etc.).
type NodeHandler interface {
	// HandleNode executes a node and returns the result.
	HandleNode(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error)
	// SupportedTypes returns the node types this handler can process.
	SupportedTypes() []models.NodeType
}

// ConditionEvaluator interface for evaluating edge conditions.
type ConditionEvaluator interface {
	// Evaluate evaluates a condition expression against the context.
	// Returns true if condition is satisfied, false otherwise.
	Evaluate(condition string, ctx *wfcontext.ExecutionContext) (bool, error)
}

// ExecutionCallback is called during execution for status updates.
type ExecutionCallback func(event ExecutionEvent)

// ExecutionEvent represents an event during execution.
type ExecutionEvent struct {
	Type      EventType
	NodeID    string
	Status    NodeStatus
	Result    *NodeResult
	Progress  float64
	Error     error
	Timestamp time.Time
}

// EventType classifies execution events.
type EventType string

const (
	EventNodeStarted   EventType = "node_started"
	EventNodeCompleted EventType = "node_completed"
	EventNodeFailed    EventType = "node_failed"
	EventNodeSkipped   EventType = "node_skipped"
	EventProgress      EventType = "progress"
)

// ExecutorConfig holds configuration for the executor.
type ExecutorConfig struct {
	// MaxConcurrent is the maximum number of concurrent node executions (for parallel nodes).
	MaxConcurrent int
	// DefaultTimeout is the default node execution timeout.
	DefaultTimeout time.Duration
	// StopOnError stops execution on first node failure if true.
	StopOnError bool
}

// DefaultExecutorConfig returns sensible defaults.
func DefaultExecutorConfig() *ExecutorConfig {
	return &ExecutorConfig{
		MaxConcurrent:  10,
		DefaultTimeout: 5 * time.Minute,
		StopOnError:    true,
	}
}

// Executor executes a workflow DAG in topological order.
type Executor struct {
	dag              *models.DAG
	handlers         map[models.NodeType]NodeHandler
	conditionEval    ConditionEvaluator
	config           *ExecutorConfig
	logger           *zap.Logger
	callback         ExecutionCallback
	topologicalOrder []string
	incomingEdges    map[string][]*models.Edge
	outgoingEdges    map[string][]*models.Edge
}

// NewExecutor creates a new DAG executor.
func NewExecutor(dag *models.DAG, logger *zap.Logger) (*Executor, error) {
	return NewExecutorWithConfig(dag, logger, DefaultExecutorConfig())
}

// NewExecutorWithConfig creates a new DAG executor with custom configuration.
func NewExecutorWithConfig(dag *models.DAG, logger *zap.Logger, config *ExecutorConfig) (*Executor, error) {
	if dag == nil {
		return nil, workflow.ErrEmptyDAG
	}
	if logger == nil {
		logger = zap.NewNop()
	}
	if config == nil {
		config = DefaultExecutorConfig()
	}

	// Validate DAG and get topological order
	v := validator.NewValidator(dag)
	result := v.Validate()
	if !result.IsValid {
		errMsg := "DAG validation failed"
		if len(result.Errors) > 0 {
			errMsg = result.Errors[0].Message
		}
		return nil, workflow.NewValidationError(errMsg)
	}

	// Build edge maps
	incomingEdges := make(map[string][]*models.Edge)
	outgoingEdges := make(map[string][]*models.Edge)

	for _, edge := range dag.Edges {
		incomingEdges[edge.To] = append(incomingEdges[edge.To], edge)
		outgoingEdges[edge.From] = append(outgoingEdges[edge.From], edge)
	}

	e := &Executor{
		dag:              dag,
		handlers:         make(map[models.NodeType]NodeHandler),
		config:           config,
		logger:           logger,
		topologicalOrder: result.TopologicalOrder,
		incomingEdges:    incomingEdges,
		outgoingEdges:    outgoingEdges,
	}

	logger.Debug("Executor initialized",
		zap.String("dag_id", dag.ID),
		zap.Int("node_count", len(dag.Nodes)),
		zap.Int("edge_count", len(dag.Edges)),
		zap.Strings("topological_order", result.TopologicalOrder))

	return e, nil
}

// RegisterHandler registers a node handler for the specified types.
func (e *Executor) RegisterHandler(handler NodeHandler) {
	for _, nodeType := range handler.SupportedTypes() {
		e.handlers[nodeType] = handler
	}
}

// SetConditionEvaluator sets the condition evaluator.
func (e *Executor) SetConditionEvaluator(eval ConditionEvaluator) {
	e.conditionEval = eval
}

// SetCallback sets the execution callback for status updates.
func (e *Executor) SetCallback(callback ExecutionCallback) {
	e.callback = callback
}

// TopologicalOrder returns the topologically sorted node IDs.
func (e *Executor) TopologicalOrder() []string {
	return e.topologicalOrder
}

// Execute runs the workflow and returns the final context or error.
func (e *Executor) Execute(ctx context.Context, execCtx *wfcontext.ExecutionContext) (*wfcontext.ExecutionContext, error) {
	if len(e.topologicalOrder) == 0 {
		return nil, workflow.NewValidationError("no topological order available")
	}

	currentCtx := execCtx.Clone()
	executedNodes := make(map[string]bool)
	skippedNodes := make(map[string]bool)
	nodeStatuses := make(map[string]NodeStatus)

	// Initialize all nodes as pending
	for _, nodeID := range e.topologicalOrder {
		nodeStatuses[nodeID] = NodeStatusPending
	}

	e.logger.Info("Starting DAG execution",
		zap.String("execution_id", execCtx.ExecutionID()),
		zap.Int("total_nodes", len(e.topologicalOrder)))

	totalNodes := len(e.topologicalOrder)
	completedCount := 0

	for _, nodeID := range e.topologicalOrder {
		// Check for cancellation
		select {
		case <-ctx.Done():
			return nil, workflow.NewCancelledError("execution cancelled")
		default:
		}

		node := e.dag.GetNode(nodeID)
		if node == nil {
			return nil, workflow.NewInvalidNodeError(nodeID, "node not found in DAG")
		}

		// Check if node should be executed based on incoming edges
		shouldExecute := e.shouldExecuteNode(nodeID, currentCtx, executedNodes, skippedNodes)

		if !shouldExecute {
			skippedNodes[nodeID] = true
			nodeStatuses[nodeID] = NodeStatusSkipped
			completedCount++

			e.logger.Debug("Skipping node (conditions not met)",
				zap.String("node_id", nodeID),
				zap.String("execution_id", execCtx.ExecutionID()))

			e.emitEvent(ExecutionEvent{
				Type:      EventNodeSkipped,
				NodeID:    nodeID,
				Status:    NodeStatusSkipped,
				Progress:  float64(completedCount) / float64(totalNodes),
				Timestamp: time.Now(),
			})
			continue
		}

		// Execute the node
		currentCtx.SetCurrentNode(nodeID)
		nodeStatuses[nodeID] = NodeStatusRunning

		e.emitEvent(ExecutionEvent{
			Type:      EventNodeStarted,
			NodeID:    nodeID,
			Status:    NodeStatusRunning,
			Timestamp: time.Now(),
		})

		e.logger.Debug("Executing node",
			zap.String("node_id", nodeID),
			zap.String("node_type", string(node.Type)),
			zap.String("execution_id", execCtx.ExecutionID()))

		result, err := e.executeNode(ctx, node, currentCtx)
		if err != nil {
			nodeStatuses[nodeID] = NodeStatusFailed

			e.emitEvent(ExecutionEvent{
				Type:      EventNodeFailed,
				NodeID:    nodeID,
				Status:    NodeStatusFailed,
				Error:     err,
				Timestamp: time.Now(),
			})

			e.logger.Error("Node execution failed",
				zap.String("node_id", nodeID),
				zap.String("execution_id", execCtx.ExecutionID()),
				zap.Error(err))

			if e.config.StopOnError {
				return nil, workflow.NewExecutionError(nodeID, "node execution failed", err)
			}
			continue
		}
		if result == nil {
			nodeStatuses[nodeID] = NodeStatusFailed
			nilResultErr := fmt.Errorf("node handler returned nil result")

			e.emitEvent(ExecutionEvent{
				Type:      EventNodeFailed,
				NodeID:    nodeID,
				Status:    NodeStatusFailed,
				Error:     nilResultErr,
				Timestamp: time.Now(),
			})

			e.logger.Error("Node execution returned nil result",
				zap.String("node_id", nodeID),
				zap.String("execution_id", execCtx.ExecutionID()))

			if e.config.StopOnError {
				return nil, workflow.NewExecutionError(nodeID, "node execution failed", nilResultErr)
			}
			continue
		}
		if result.Status == NodeStatusFailed {
			nodeStatuses[nodeID] = NodeStatusFailed
			nodeErr := result.Error
			if nodeErr == nil {
				nodeErr = fmt.Errorf("node returned failed status without error")
			}

			e.emitEvent(ExecutionEvent{
				Type:      EventNodeFailed,
				NodeID:    nodeID,
				Status:    NodeStatusFailed,
				Error:     nodeErr,
				Timestamp: time.Now(),
			})

			e.logger.Error("Node execution reported failed status",
				zap.String("node_id", nodeID),
				zap.String("execution_id", execCtx.ExecutionID()),
				zap.Error(nodeErr))

			if e.config.StopOnError {
				return nil, workflow.NewExecutionError(nodeID, "node execution failed", nodeErr)
			}
			continue
		}
		if result.Status == NodeStatusSkipped {
			skippedNodes[nodeID] = true
			nodeStatuses[nodeID] = NodeStatusSkipped
			completedCount++

			e.emitEvent(ExecutionEvent{
				Type:      EventNodeSkipped,
				NodeID:    nodeID,
				Status:    NodeStatusSkipped,
				Progress:  float64(completedCount) / float64(totalNodes),
				Timestamp: time.Now(),
			})

			e.logger.Debug("Node reported skipped status",
				zap.String("node_id", nodeID),
				zap.String("execution_id", execCtx.ExecutionID()))

			continue
		}

		// Store result in context
		currentCtx = currentCtx.SetNodeResult(nodeID, result.Output)
		executedNodes[nodeID] = true
		nodeStatuses[nodeID] = NodeStatusCompleted
		completedCount++

		e.emitEvent(ExecutionEvent{
			Type:      EventNodeCompleted,
			NodeID:    nodeID,
			Status:    NodeStatusCompleted,
			Result:    result,
			Progress:  float64(completedCount) / float64(totalNodes),
			Timestamp: time.Now(),
		})

		e.logger.Debug("Node completed",
			zap.String("node_id", nodeID),
			zap.Duration("duration", result.Duration),
			zap.String("execution_id", execCtx.ExecutionID()))
	}

	e.logger.Info("DAG execution completed",
		zap.String("execution_id", execCtx.ExecutionID()),
		zap.Int("executed", len(executedNodes)),
		zap.Int("skipped", len(skippedNodes)))

	return currentCtx, nil
}

// shouldExecuteNode determines if a node should be executed based on edge conditions.
func (e *Executor) shouldExecuteNode(
	nodeID string,
	ctx *wfcontext.ExecutionContext,
	executedNodes map[string]bool,
	skippedNodes map[string]bool,
) bool {
	incoming := e.incomingEdges[nodeID]

	// Start nodes (no incoming edges) always execute
	if len(incoming) == 0 {
		return true
	}

	// Check each incoming edge
	for _, edge := range incoming {
		sourceNode := edge.From

		// Source must have been executed (not skipped)
		if skippedNodes[sourceNode] {
			continue
		}

		if !executedNodes[sourceNode] {
			// Source not yet processed - shouldn't happen in topological order
			e.logger.Warn("Source node not yet executed",
				zap.String("source", sourceNode),
				zap.String("target", nodeID))
			continue
		}

		// Check edge condition
		if e.evaluateEdgeCondition(edge, ctx) {
			return true
		}
	}

	return false
}

// evaluateEdgeCondition evaluates an edge's condition expression.
func (e *Executor) evaluateEdgeCondition(edge *models.Edge, ctx *wfcontext.ExecutionContext) bool {
	// No condition = always true
	if edge.Condition == "" {
		return true
	}

	// Use condition evaluator if available
	if e.conditionEval != nil {
		result, err := e.conditionEval.Evaluate(edge.Condition, ctx)
		if err != nil {
			e.logger.Warn("Edge condition evaluation failed, treating as false",
				zap.String("from", edge.From),
				zap.String("to", edge.To),
				zap.String("condition", edge.Condition),
				zap.Error(err))
			return false
		}
		return result
	}

	// Default: simple boolean check from context
	// TODO: Implement Jinja2-style evaluation
	e.logger.Debug("No condition evaluator, condition treated as true",
		zap.String("condition", edge.Condition))
	return true
}

// executeNode executes a single node using the appropriate handler.
func (e *Executor) executeNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*NodeResult, error) {
	startTime := time.Now()

	handler, ok := e.handlers[node.Type]
	if !ok {
		return nil, fmt.Errorf("no handler registered for node type: %s", node.Type)
	}

	// Apply node timeout
	timeout := e.config.DefaultTimeout
	if node.Config != nil && node.Config.TimeoutSeconds > 0 {
		timeout = time.Duration(node.Config.TimeoutSeconds) * time.Second
	}

	nodeCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Execute via handler
	result, err := handler.HandleNode(nodeCtx, node, execCtx)
	if err != nil {
		return &NodeResult{
			NodeID:      node.ID,
			Status:      NodeStatusFailed,
			Error:       err,
			StartedAt:   startTime,
			CompletedAt: time.Now(),
			Duration:    time.Since(startTime),
		}, err
	}

	if result == nil {
		result = &NodeResult{
			NodeID: node.ID,
			Status: NodeStatusCompleted,
		}
	}

	result.NodeID = node.ID
	result.StartedAt = startTime
	result.CompletedAt = time.Now()
	result.Duration = time.Since(startTime)

	if result.Status == "" {
		result.Status = NodeStatusCompleted
	}

	return result, nil
}

// GetNextNodes returns the next nodes to execute based on edge conditions.
// Useful for async execution to determine next steps.
func (e *Executor) GetNextNodes(nodeID string, ctx *wfcontext.ExecutionContext) []string {
	outgoing := e.outgoingEdges[nodeID]
	nextNodes := make([]string, 0, len(outgoing))

	for _, edge := range outgoing {
		if e.evaluateEdgeCondition(edge, ctx) {
			nextNodes = append(nextNodes, edge.To)
		}
	}

	// Sort for deterministic order
	sort.Strings(nextNodes)

	e.logger.Debug("Determined next nodes",
		zap.String("current_node", nodeID),
		zap.Strings("next_nodes", nextNodes))

	return nextNodes
}

// emitEvent sends an execution event to the callback if registered.
func (e *Executor) emitEvent(event ExecutionEvent) {
	if e.callback != nil {
		e.callback(event)
	}
}

// DAG returns the executor's DAG.
func (e *Executor) DAG() *models.DAG {
	return e.dag
}
