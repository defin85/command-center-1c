package executor

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// MockNodeHandler implements NodeHandler for testing.
type MockNodeHandler struct {
	HandleFunc     func(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error)
	ExecutionOrder []string
}

func (h *MockNodeHandler) HandleNode(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error) {
	h.ExecutionOrder = append(h.ExecutionOrder, node.ID)
	if h.HandleFunc != nil {
		return h.HandleFunc(ctx, node, execCtx)
	}
	return &NodeResult{
		NodeID: node.ID,
		Status: NodeStatusCompleted,
		Output: map[string]interface{}{"status": "ok"},
	}, nil
}

func (h *MockNodeHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeOperation}
}

// MockConditionEvaluator implements ConditionEvaluator for testing.
type MockConditionEvaluator struct {
	EvaluateFunc func(condition string, ctx *wfcontext.ExecutionContext) (bool, error)
}

func (e *MockConditionEvaluator) Evaluate(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
	if e.EvaluateFunc != nil {
		return e.EvaluateFunc(condition, ctx)
	}
	return true, nil
}

func createLogger() *zap.Logger {
	return zap.NewNop()
}

func TestNewExecutor(t *testing.T) {
	dag := models.NewDAG("dag-1", "Test DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddEdge("A", "B")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)
	require.NotNil(t, executor)

	assert.Equal(t, dag, executor.DAG())
	assert.Equal(t, []string{"A", "B"}, executor.TopologicalOrder())
}

func TestNewExecutor_NilDAG(t *testing.T) {
	_, err := NewExecutor(nil, createLogger())
	require.Error(t, err)
}

func TestNewExecutor_EmptyDAG(t *testing.T) {
	dag := models.NewDAG("dag-1", "Empty DAG")

	_, err := NewExecutor(dag, createLogger())
	require.Error(t, err)
}

func TestNewExecutor_CyclicDAG(t *testing.T) {
	dag := models.NewDAG("dag-1", "Cyclic DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddEdge("A", "B")
	_ = dag.AddEdge("B", "A") // Creates cycle

	_, err := NewExecutor(dag, createLogger())
	require.Error(t, err)
}

func TestExecutor_LinearExecution(t *testing.T) {
	// Create linear DAG: A -> B -> C
	dag := models.NewDAG("dag-1", "Linear DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdge("A", "B")
	_ = dag.AddEdge("B", "C")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	resultCtx, err := executor.Execute(ctx, execCtx)
	require.NoError(t, err)
	require.NotNil(t, resultCtx)

	// Check execution order
	assert.Equal(t, []string{"A", "B", "C"}, handler.ExecutionOrder)

	// Check node results
	assert.True(t, resultCtx.HasNodeResult("A"))
	assert.True(t, resultCtx.HasNodeResult("B"))
	assert.True(t, resultCtx.HasNodeResult("C"))
}

func TestExecutor_TopologicalOrder(t *testing.T) {
	// Create DAG: A -> C, B -> C, C -> D
	dag := models.NewDAG("dag-1", "Diamond DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddNode(models.NewOperationNode("D", "Node D", "template-4"))
	_ = dag.AddEdge("A", "C")
	_ = dag.AddEdge("B", "C")
	_ = dag.AddEdge("C", "D")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	order := executor.TopologicalOrder()

	// A and B must come before C
	aIdx := indexOf(order, "A")
	bIdx := indexOf(order, "B")
	cIdx := indexOf(order, "C")
	dIdx := indexOf(order, "D")

	assert.Less(t, aIdx, cIdx)
	assert.Less(t, bIdx, cIdx)
	assert.Less(t, cIdx, dIdx)
}

func TestExecutor_NodeFailure(t *testing.T) {
	dag := models.NewDAG("dag-1", "Linear DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdge("A", "B")
	_ = dag.AddEdge("B", "C")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{
		HandleFunc: func(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error) {
			if node.ID == "B" {
				return nil, errors.New("node B failed")
			}
			return &NodeResult{
				NodeID: node.ID,
				Status: NodeStatusCompleted,
				Output: map[string]interface{}{"status": "ok"},
			}, nil
		},
	}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.Error(t, err)

	// Should have executed A and B, but not C
	assert.Equal(t, []string{"A", "B"}, handler.ExecutionOrder)
}

func TestExecutor_StopOnErrorFalse(t *testing.T) {
	// Create DAG: A -> B, A -> C (parallel branches from A)
	// When B fails, C should still execute since it doesn't depend on B
	dag := models.NewDAG("dag-1", "Parallel Branches DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B (will fail)", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdge("A", "B")
	_ = dag.AddEdge("A", "C")

	config := DefaultExecutorConfig()
	config.StopOnError = false

	executor, err := NewExecutorWithConfig(dag, createLogger(), config)
	require.NoError(t, err)

	handler := &MockNodeHandler{
		HandleFunc: func(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error) {
			if node.ID == "B" {
				return nil, errors.New("node B failed")
			}
			return &NodeResult{
				NodeID: node.ID,
				Status: NodeStatusCompleted,
				Output: map[string]interface{}{"status": "ok"},
			}, nil
		},
	}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	// Should complete without error (StopOnError=false)
	resultCtx, err := executor.Execute(ctx, execCtx)
	require.NoError(t, err)
	require.NotNil(t, resultCtx)

	// A, B and C should all be attempted (B fails but C still runs since it doesn't depend on B)
	assert.Len(t, handler.ExecutionOrder, 3)
	assert.Contains(t, handler.ExecutionOrder, "A")
	assert.Contains(t, handler.ExecutionOrder, "B")
	assert.Contains(t, handler.ExecutionOrder, "C")
}

func TestExecutor_ContextCancellation(t *testing.T) {
	dag := models.NewDAG("dag-1", "Linear DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddEdge("A", "B")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{
		HandleFunc: func(ctx context.Context, node *models.Node, execCtx *wfcontext.ExecutionContext) (*NodeResult, error) {
			// Simulate slow execution
			time.Sleep(100 * time.Millisecond)
			return &NodeResult{
				NodeID: node.ID,
				Status: NodeStatusCompleted,
			}, nil
		},
	}
	executor.RegisterHandler(handler)

	ctx, cancel := context.WithCancel(context.Background())
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	// Cancel immediately
	cancel()

	_, err = executor.Execute(ctx, execCtx)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "cancelled")
}

func TestExecutor_ConditionalEdge_True(t *testing.T) {
	// Create DAG: A -> B (condition: true), A -> C (condition: false)
	dag := models.NewDAG("dag-1", "Conditional DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B (if true)", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C (if false)", "template-3"))
	_ = dag.AddEdgeWithCondition("A", "B", "{{ condition == true }}")
	_ = dag.AddEdgeWithCondition("A", "C", "{{ condition == false }}")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	// Mock condition evaluator that evaluates based on condition string
	executor.SetConditionEvaluator(&MockConditionEvaluator{
		EvaluateFunc: func(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
			if condition == "{{ condition == true }}" {
				return true, nil
			}
			return false, nil
		},
	})

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	// Should execute A -> B, skip C
	assert.Contains(t, handler.ExecutionOrder, "A")
	assert.Contains(t, handler.ExecutionOrder, "B")
	assert.NotContains(t, handler.ExecutionOrder, "C")
}

func TestExecutor_ConditionalEdge_False(t *testing.T) {
	dag := models.NewDAG("dag-1", "Conditional DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B (if true)", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C (if false)", "template-3"))
	_ = dag.AddEdgeWithCondition("A", "B", "{{ condition == true }}")
	_ = dag.AddEdgeWithCondition("A", "C", "{{ condition == false }}")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	executor.SetConditionEvaluator(&MockConditionEvaluator{
		EvaluateFunc: func(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
			if condition == "{{ condition == false }}" {
				return true, nil
			}
			return false, nil
		},
	})

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	// Should execute A -> C, skip B
	assert.Contains(t, handler.ExecutionOrder, "A")
	assert.Contains(t, handler.ExecutionOrder, "C")
	assert.NotContains(t, handler.ExecutionOrder, "B")
}

func TestExecutor_NoCondition_AlwaysExecutes(t *testing.T) {
	dag := models.NewDAG("dag-1", "Simple DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddEdge("A", "B") // No condition

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	assert.Equal(t, []string{"A", "B"}, handler.ExecutionOrder)
}

func TestExecutor_SingleNode(t *testing.T) {
	dag := models.NewDAG("dag-1", "Single Node DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	resultCtx, err := executor.Execute(ctx, execCtx)
	require.NoError(t, err)
	require.NotNil(t, resultCtx)

	assert.Equal(t, []string{"A"}, handler.ExecutionOrder)
	assert.True(t, resultCtx.HasNodeResult("A"))
}

func TestExecutor_GetNextNodes(t *testing.T) {
	dag := models.NewDAG("dag-1", "Branching DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdgeWithCondition("A", "B", "{{ cond1 }}")
	_ = dag.AddEdgeWithCondition("A", "C", "{{ cond2 }}")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	executor.SetConditionEvaluator(&MockConditionEvaluator{
		EvaluateFunc: func(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
			if condition == "{{ cond1 }}" {
				return true, nil
			}
			return false, nil
		},
	})

	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	nextNodes := executor.GetNextNodes("A", execCtx)

	assert.Equal(t, []string{"B"}, nextNodes)
	assert.NotContains(t, nextNodes, "C")
}

func TestExecutor_Callback(t *testing.T) {
	dag := models.NewDAG("dag-1", "Linear DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddEdge("A", "B")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	var events []ExecutionEvent
	executor.SetCallback(func(event ExecutionEvent) {
		events = append(events, event)
	})

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	// Should have received start and complete events for each node
	assert.GreaterOrEqual(t, len(events), 4)

	// Check event types
	var startedCount, completedCount int
	for _, e := range events {
		switch e.Type {
		case EventNodeStarted:
			startedCount++
		case EventNodeCompleted:
			completedCount++
		}
	}
	assert.Equal(t, 2, startedCount)
	assert.Equal(t, 2, completedCount)
}

func TestExecutor_MissingHandler(t *testing.T) {
	dag := models.NewDAG("dag-1", "Simple DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	// Don't register any handler

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "no handler")
}

func TestExecutor_ConditionEvaluatorError(t *testing.T) {
	dag := models.NewDAG("dag-1", "Conditional DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdgeWithCondition("A", "B", "{{ invalid_condition }}")
	_ = dag.AddEdge("A", "C")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	executor.SetConditionEvaluator(&MockConditionEvaluator{
		EvaluateFunc: func(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
			if condition == "{{ invalid_condition }}" {
				return false, errors.New("evaluation error")
			}
			return true, nil
		},
	})

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	// Should execute A -> C, skip B (condition error = false)
	assert.Contains(t, handler.ExecutionOrder, "A")
	assert.Contains(t, handler.ExecutionOrder, "C")
	assert.NotContains(t, handler.ExecutionOrder, "B")
}

func TestExecutor_MultipleStartNodes(t *testing.T) {
	// Create DAG with multiple start nodes: A -> C, B -> C
	dag := models.NewDAG("dag-1", "Multi-start DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdge("A", "C")
	_ = dag.AddEdge("B", "C")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	resultCtx, err := executor.Execute(ctx, execCtx)
	require.NoError(t, err)
	require.NotNil(t, resultCtx)

	// All nodes should have executed
	assert.Len(t, handler.ExecutionOrder, 3)
	assert.Contains(t, handler.ExecutionOrder, "A")
	assert.Contains(t, handler.ExecutionOrder, "B")
	assert.Contains(t, handler.ExecutionOrder, "C")

	// C should be last
	assert.Equal(t, "C", handler.ExecutionOrder[2])
}

func TestExecutor_SkippedNodeDoesNotTriggerSuccessors(t *testing.T) {
	// DAG: A -> B -> C where B is skipped
	dag := models.NewDAG("dag-1", "Skip Chain DAG")
	_ = dag.AddNode(models.NewOperationNode("A", "Node A", "template-1"))
	_ = dag.AddNode(models.NewOperationNode("B", "Node B (skipped)", "template-2"))
	_ = dag.AddNode(models.NewOperationNode("C", "Node C", "template-3"))
	_ = dag.AddEdgeWithCondition("A", "B", "{{ should_skip }}")
	_ = dag.AddEdge("B", "C")

	executor, err := NewExecutor(dag, createLogger())
	require.NoError(t, err)

	handler := &MockNodeHandler{}
	executor.RegisterHandler(handler)

	// Condition evaluator that always returns false
	executor.SetConditionEvaluator(&MockConditionEvaluator{
		EvaluateFunc: func(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
			return false, nil
		},
	})

	ctx := context.Background()
	execCtx := wfcontext.NewExecutionContext("exec-1", "wf-1")

	_, err = executor.Execute(ctx, execCtx)
	require.NoError(t, err)

	// Only A should execute, B and C should be skipped
	assert.Equal(t, []string{"A"}, handler.ExecutionOrder)
}

// Helper function
func indexOf(slice []string, item string) int {
	for i, v := range slice {
		if v == item {
			return i
		}
	}
	return -1
}
