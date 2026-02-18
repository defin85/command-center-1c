package handlers

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// mockTemplateRenderer is a mock implementation of TemplateRenderer.
type mockTemplateRenderer struct {
	renderFunc     func(ctx context.Context, template string, data map[string]interface{}) (string, error)
	renderJSONFunc func(ctx context.Context, template map[string]interface{}, data map[string]interface{}) (map[string]interface{}, error)
}

func (m *mockTemplateRenderer) Render(ctx context.Context, template string, data map[string]interface{}) (string, error) {
	if m.renderFunc != nil {
		return m.renderFunc(ctx, template, data)
	}
	return template, nil
}

func (m *mockTemplateRenderer) RenderJSON(ctx context.Context, template map[string]interface{}, data map[string]interface{}) (map[string]interface{}, error) {
	if m.renderJSONFunc != nil {
		return m.renderJSONFunc(ctx, template, data)
	}
	return template, nil
}

// mockOperationExecutor is a mock implementation of OperationExecutor.
type mockOperationExecutor struct {
	executeFunc func(ctx context.Context, req *OperationRequest) (map[string]interface{}, error)
}

func (m *mockOperationExecutor) Execute(ctx context.Context, req *OperationRequest) (map[string]interface{}, error) {
	if m.executeFunc != nil {
		return m.executeFunc(ctx, req)
	}
	return map[string]interface{}{"status": "success"}, nil
}

// TestHandlerRegistry tests the handler registry.
func TestHandlerRegistry(t *testing.T) {
	t.Run("empty registry", func(t *testing.T) {
		registry := NewHandlerRegistry()

		handler, ok := registry.Get(models.NodeTypeOperation)
		assert.False(t, ok)
		assert.Nil(t, handler)
	})

	t.Run("register and get handler", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())

		operationHandler := NewOperationHandler(deps)
		registry.Register(models.NodeTypeOperation, operationHandler)

		handler, ok := registry.Get(models.NodeTypeOperation)
		assert.True(t, ok)
		assert.NotNil(t, handler)
	})

	t.Run("has handler", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())

		assert.False(t, registry.Has(models.NodeTypeOperation))

		registry.Register(models.NodeTypeOperation, NewOperationHandler(deps))

		assert.True(t, registry.Has(models.NodeTypeOperation))
	})

	t.Run("registered types", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())

		registry.RegisterAllHandlers(deps)

		types := registry.RegisteredTypes()
		assert.Len(t, types, 5) // operation, condition, parallel, loop, subworkflow
	})
}

// TestOperationHandler tests the operation handler.
func TestOperationHandler(t *testing.T) {
	t.Run("handle node without executor returns rendered data", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Test Operation", "template-123")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)
		assert.NotNil(t, result.Output)

		output := result.Output.(map[string]interface{})
		assert.True(t, output["execution_skipped"].(bool))
	})

	t.Run("handle node with executor", func(t *testing.T) {
		mockExec := &mockOperationExecutor{
			executeFunc: func(ctx context.Context, req *OperationRequest) (map[string]interface{}, error) {
				return map[string]interface{}{
					"status":  "success",
					"records": 10,
				}, nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithOperationExecutor(mockExec)
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Test Operation", "template-123")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.Equal(t, "success", output["status"])
		assert.Equal(t, 10, output["records"])
	})

	t.Run("pool operation without executor fails closed", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Pool Operation", "pool.publication_odata")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusFailed, result.Status)
		assert.Nil(t, result.Output)
		require.NotNil(t, result.Error)
		opErr, ok := result.Error.(*OperationExecutionError)
		require.True(t, ok)
		assert.Equal(t, ErrorCodeWorkflowOperationExecutorNotConfigured, opErr.Code)
	})

	t.Run("operation type is derived from operation_ref alias", func(t *testing.T) {
		var captured *OperationRequest
		mockExec := &mockOperationExecutor{
			executeFunc: func(ctx context.Context, req *OperationRequest) (map[string]interface{}, error) {
				captured = req
				return map[string]interface{}{"status": "success"}, nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithOperationExecutor(mockExec)
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Pool Operation", "tpl-legacy")
		node.OperationRef = &models.OperationRef{
			Alias:       "pool.prepare_input",
			BindingMode: "pinned_exposure",
		}
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)
		require.NotNil(t, captured)
		assert.Equal(t, "pool.prepare_input", captured.OperationType)
	})

	t.Run("operation type falls back to template_id when operation_ref is absent", func(t *testing.T) {
		var captured *OperationRequest
		mockExec := &mockOperationExecutor{
			executeFunc: func(ctx context.Context, req *OperationRequest) (map[string]interface{}, error) {
				captured = req
				return map[string]interface{}{"status": "success"}, nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithOperationExecutor(mockExec)
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Pool Operation", "pool.publication_odata")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)
		require.NotNil(t, captured)
		assert.Equal(t, "pool.publication_odata", captured.OperationType)
	})

	t.Run("publication node payload falls back to execution context", func(t *testing.T) {
		var captured *OperationRequest
		mockExec := &mockOperationExecutor{
			executeFunc: func(ctx context.Context, req *OperationRequest) (map[string]interface{}, error) {
				captured = req
				return map[string]interface{}{"status": "success"}, nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithOperationExecutor(mockExec)
		handler := NewOperationHandler(deps)

		node := models.NewOperationNode("op1", "Pool Publication", "pool.publication_odata")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		fallbackPayload := map[string]interface{}{
			"pool_runtime": map[string]interface{}{
				"entity_name": "Document_IntercompanyPoolDistribution",
				"documents_by_database": map[string]interface{}{
					"db-1": []interface{}{
						map[string]interface{}{"Amount": "100.00"},
					},
				},
			},
		}
		execCtx = execCtx.Set("pool_runtime_publication_payload", fallbackPayload)

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)
		require.NotNil(t, captured)
		assert.Equal(t, fallbackPayload, captured.Payload)
	})

	t.Run("supported types", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewOperationHandler(deps)

		types := handler.SupportedTypes()
		assert.Len(t, types, 1)
		assert.Equal(t, models.NodeTypeOperation, types[0])
	})
}

// TestConditionHandler tests the condition handler.
func TestConditionHandler(t *testing.T) {
	t.Run("evaluate true expression", func(t *testing.T) {
		mockRenderer := &mockTemplateRenderer{
			renderFunc: func(ctx context.Context, template string, data map[string]interface{}) (string, error) {
				return "true", nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithTemplateEngine(mockRenderer)
		handler := NewConditionHandler(deps)

		node := models.NewConditionNode("cond1", "Check Condition", "{{ status == 'active' }}")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		execCtx = execCtx.Set("status", "active")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.True(t, output["condition_result"].(bool))
	})

	t.Run("evaluate false expression", func(t *testing.T) {
		mockRenderer := &mockTemplateRenderer{
			renderFunc: func(ctx context.Context, template string, data map[string]interface{}) (string, error) {
				return "false", nil
			},
		}

		deps := NewHandlerDependencies(zap.NewNop()).
			WithTemplateEngine(mockRenderer)
		handler := NewConditionHandler(deps)

		node := models.NewConditionNode("cond1", "Check Condition", "{{ count > 10 }}")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		execCtx = execCtx.Set("count", 5)

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.False(t, output["condition_result"].(bool))
	})

	t.Run("empty expression defaults to false", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewConditionHandler(deps)

		node := &models.Node{
			ID:     "cond1",
			Type:   models.NodeTypeCondition,
			Name:   "Empty Condition",
			Config: &models.NodeConfig{},
		}
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.False(t, output["condition_result"].(bool))
	})

	t.Run("supported types", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewConditionHandler(deps)

		types := handler.SupportedTypes()
		assert.Len(t, types, 1)
		assert.Equal(t, models.NodeTypeCondition, types[0])
	})
}

// TestIsTruthy tests the isTruthy function.
func TestIsTruthy(t *testing.T) {
	testCases := []struct {
		input    string
		expected bool
	}{
		{"true", true},
		{"True", true},
		{"TRUE", true},
		{"yes", true},
		{"Yes", true},
		{"1", true},
		{"on", true},
		{"false", false},
		{"False", false},
		{"FALSE", false},
		{"no", false},
		{"No", false},
		{"0", false},
		{"off", false},
		{"", false},
		{"none", false},
		{"null", false},
		{"nil", false},
		{"some_value", true}, // Non-empty string is truthy
		{"  true  ", true},   // Trimmed
		{"  false  ", false}, // Trimmed
		{"3.14", true},       // Non-zero number
		{"0.0", false},       // Zero number
		{"-1", true},         // Negative number is truthy
	}

	for _, tc := range testCases {
		t.Run(tc.input, func(t *testing.T) {
			result := isTruthy(tc.input)
			assert.Equal(t, tc.expected, result, "isTruthy(%q) = %v, want %v", tc.input, result, tc.expected)
		})
	}
}

// TestParallelHandler tests the parallel handler.
func TestParallelHandler(t *testing.T) {
	t.Run("parallel node without config fails", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewParallelHandler(deps, registry)

		node := &models.Node{
			ID:   "par1",
			Type: models.NodeTypeParallel,
			Name: "Parallel Test",
		}
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err) // Handler returns error in result, not as function error
		assert.Equal(t, executor.NodeStatusFailed, result.Status)
		assert.NotNil(t, result.Error)
	})

	t.Run("parallel node with empty branches", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewParallelHandler(deps, registry)

		node := models.NewParallelNode("par1", "Parallel Test", []string{})
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)
	})

	t.Run("parallel node with branches (placeholder execution)", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewParallelHandler(deps, registry)

		node := models.NewParallelNode("par1", "Parallel Test", []string{"branch1", "branch2"})
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		completed := output["completed"].([]map[string]interface{})
		assert.Len(t, completed, 2)
	})

	t.Run("supported types", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewParallelHandler(deps, registry)

		types := handler.SupportedTypes()
		assert.Len(t, types, 1)
		assert.Equal(t, models.NodeTypeParallel, types[0])
	})
}

// TestLoopHandler tests the loop handler.
func TestLoopHandler(t *testing.T) {
	t.Run("count loop", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		node := models.NewLoopNode("loop1", "Count Loop", models.LoopModeCount, "body_node")
		node.LoopConfig.Count = 3
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.Equal(t, 3, output["iterations"])
		assert.Equal(t, "count", output["mode"])
	})

	t.Run("count loop with max iterations limit", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		node := models.NewLoopNode("loop1", "Count Loop", models.LoopModeCount, "body_node")
		node.LoopConfig.Count = 100
		node.LoopConfig.MaxIterations = 10
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.Equal(t, 10, output["iterations"])
		assert.True(t, output["max_iterations_reached"].(bool))
	})

	t.Run("foreach loop", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		node := models.NewLoopNode("loop1", "Foreach Loop", models.LoopModeForeach, "body_node")
		node.LoopConfig.Items = "items"
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		execCtx = execCtx.Set("items", []interface{}{"a", "b", "c"})

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.Equal(t, 3, output["iterations"])
		assert.Equal(t, 3, output["total_items"])
		assert.Equal(t, "foreach", output["mode"])
	})

	t.Run("loop node without config fails", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		node := &models.Node{
			ID:   "loop1",
			Type: models.NodeTypeLoop,
			Name: "Loop Test",
		}
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusFailed, result.Status)
		assert.NotNil(t, result.Error)
	})

	t.Run("context cancellation stops loop", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		node := models.NewLoopNode("loop1", "Count Loop", models.LoopModeCount, "body_node")
		node.LoopConfig.Count = 1000
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
		defer cancel()

		result, err := handler.HandleNode(ctx, node, execCtx)

		// Either returns error or cancelled result
		if err != nil {
			assert.ErrorIs(t, err, context.DeadlineExceeded)
		} else {
			// May complete before timeout in fast execution
			assert.NotNil(t, result)
		}
	})

	t.Run("supported types", func(t *testing.T) {
		registry := NewHandlerRegistry()
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewLoopHandler(deps, registry)

		types := handler.SupportedTypes()
		assert.Len(t, types, 1)
		assert.Equal(t, models.NodeTypeLoop, types[0])
	})
}

// TestSubworkflowHandler tests the subworkflow handler.
func TestSubworkflowHandler(t *testing.T) {
	t.Run("subworkflow node without config fails", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewSubworkflowHandler(deps)

		node := &models.Node{
			ID:   "sub1",
			Type: models.NodeTypeSubworkflow,
			Name: "Subworkflow Test",
		}
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusFailed, result.Status)
		assert.NotNil(t, result.Error)
	})

	t.Run("subworkflow without store returns placeholder", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewSubworkflowHandler(deps)

		node := models.NewSubworkflowNode("sub1", "Subworkflow Test", "workflow-nested")
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusCompleted, result.Status)

		output := result.Output.(map[string]interface{})
		assert.True(t, output["execution_skipped"].(bool))
	})

	t.Run("recursion depth limit", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewSubworkflowHandler(deps)

		node := models.NewSubworkflowNode("sub1", "Subworkflow Test", "workflow-nested")
		node.SubworkflowConfig.MaxDepth = 5

		// Simulate being at max depth
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		execCtx = execCtx.Set(SubworkflowDepthKey, 5)

		result, err := handler.HandleNode(context.Background(), node, execCtx)
		require.NoError(t, err)
		assert.Equal(t, executor.NodeStatusFailed, result.Status)
		assert.Contains(t, result.Error.Error(), "recursion depth exceeded")
	})

	t.Run("supported types", func(t *testing.T) {
		deps := NewHandlerDependencies(zap.NewNop())
		handler := NewSubworkflowHandler(deps)

		types := handler.SupportedTypes()
		assert.Len(t, types, 1)
		assert.Equal(t, models.NodeTypeSubworkflow, types[0])
	})
}

// TestConditionEvaluatorImpl tests the condition evaluator implementation.
func TestConditionEvaluatorImpl(t *testing.T) {
	t.Run("evaluate with template engine", func(t *testing.T) {
		mockRenderer := &mockTemplateRenderer{
			renderFunc: func(ctx context.Context, template string, data map[string]interface{}) (string, error) {
				return "true", nil
			},
		}

		evaluator := NewConditionEvaluator(mockRenderer)
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := evaluator.Evaluate("{{ status == 'active' }}", execCtx)
		require.NoError(t, err)
		assert.True(t, result)
	})

	t.Run("evaluate empty condition returns true", func(t *testing.T) {
		evaluator := NewConditionEvaluator(nil)
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := evaluator.Evaluate("", execCtx)
		require.NoError(t, err)
		assert.True(t, result) // Empty condition is always true
	})

	t.Run("evaluate without template engine", func(t *testing.T) {
		evaluator := NewConditionEvaluator(nil)
		execCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")

		result, err := evaluator.Evaluate("true", execCtx)
		require.NoError(t, err)
		assert.True(t, result)
	})

	t.Run("evaluate template variable without template engine", func(t *testing.T) {
		evaluator := NewConditionEvaluator(nil)

		pendingCtx := wfcontext.NewExecutionContext("exec-1", "workflow-1")
		pendingCtx = pendingCtx.Set("approved_at", nil)
		pendingResult, err := evaluator.Evaluate("{{approved_at}}", pendingCtx)
		require.NoError(t, err)
		assert.False(t, pendingResult)

		approvedCtx := wfcontext.NewExecutionContext("exec-2", "workflow-1")
		approvedCtx = approvedCtx.Set("approved_at", "2026-01-01T00:00:00Z")
		approvedResult, err := evaluator.Evaluate("{{approved_at}}", approvedCtx)
		require.NoError(t, err)
		assert.True(t, approvedResult)
	})
}

// TestNewRegistryWithHandlers tests the convenience function.
func TestNewRegistryWithHandlers(t *testing.T) {
	deps := NewHandlerDependencies(zap.NewNop())
	registry := NewRegistryWithHandlers(deps)

	// All handlers should be registered
	assert.True(t, registry.Has(models.NodeTypeOperation))
	assert.True(t, registry.Has(models.NodeTypeCondition))
	assert.True(t, registry.Has(models.NodeTypeParallel))
	assert.True(t, registry.Has(models.NodeTypeLoop))
	assert.True(t, registry.Has(models.NodeTypeSubworkflow))
}

// TestSubworkflowBuilder tests the subworkflow builder.
func TestSubworkflowBuilder(t *testing.T) {
	builder := NewSubworkflowBuilder("nested-workflow-1")
	builder.
		WithInputMapping("target_db", "database_id").
		WithInputMapping("user", "current_user").
		WithOutputMapping("result", "subworkflow_result").
		WithMaxDepth(5)

	config := builder.Build()

	assert.Equal(t, "nested-workflow-1", config.WorkflowID)
	assert.Equal(t, 5, config.MaxDepth)
	assert.Len(t, config.InputMapping, 2)
	assert.Len(t, config.OutputMapping, 1)
	assert.Equal(t, "database_id", config.InputMapping["target_db"])
	assert.Equal(t, "subworkflow_result", config.OutputMapping["result"])
}
