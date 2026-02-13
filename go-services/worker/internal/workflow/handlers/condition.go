package handlers

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"go.uber.org/zap"

	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// ConditionHandler evaluates condition nodes for branching.
// Condition nodes evaluate boolean expressions and return the result
// to determine which branch of the workflow to follow.
//
// Flow:
//  1. Get expression from node config
//  2. Render expression with template engine (if available)
//  3. Convert result to boolean
//  4. Return result with next node hints (true_node or false_node)
//
// Security:
//   - Uses template engine's sandboxed environment
//   - No direct code execution
type ConditionHandler struct {
	templateEngine TemplateRenderer
	logger         *zap.Logger
}

// NewConditionHandler creates a new condition handler.
func NewConditionHandler(deps *HandlerDependencies) *ConditionHandler {
	logger := deps.Logger
	if logger == nil {
		logger = zap.NewNop()
	}
	return &ConditionHandler{
		templateEngine: deps.TemplateEngine,
		logger:         logger.Named("condition_handler"),
	}
}

// SupportedTypes returns the node types this handler can process.
func (h *ConditionHandler) SupportedTypes() []models.NodeType {
	return []models.NodeType{models.NodeTypeCondition}
}

// HandleNode evaluates a condition expression and returns the boolean result.
func (h *ConditionHandler) HandleNode(
	ctx context.Context,
	node *models.Node,
	execCtx *wfcontext.ExecutionContext,
) (*executor.NodeResult, error) {
	startTime := time.Now()

	h.logger.Debug("Executing condition node",
		zap.String("node_id", node.ID),
		zap.String("node_name", node.Name),
		zap.String("execution_id", execCtx.ExecutionID()))

	// Get expression from node
	expression := h.getExpression(node)
	if expression == "" {
		h.logger.Warn("No expression found, defaulting to false",
			zap.String("node_id", node.ID))
		return h.createResult(node.ID, false, "", startTime), nil
	}

	h.logger.Debug("Evaluating condition expression",
		zap.String("node_id", node.ID),
		zap.String("expression", expression))

	// Render expression with template engine
	var rendered string
	var err error

	if h.templateEngine != nil {
		renderCtx := execCtx.ToMap()
		rendered, err = h.templateEngine.Render(ctx, expression, renderCtx)
		if err != nil {
			h.logger.Error("Failed to evaluate condition expression",
				zap.String("node_id", node.ID),
				zap.String("expression", expression),
				zap.Error(err))
			return &executor.NodeResult{
				NodeID:      node.ID,
				Status:      executor.NodeStatusFailed,
				Error:       fmt.Errorf("condition evaluation failed: %w", err),
				StartedAt:   startTime,
				CompletedAt: time.Now(),
				Duration:    time.Since(startTime),
			}, nil
		}
	} else {
		// Without template engine, try to evaluate as simple expression
		rendered = h.evaluateSimpleExpression(expression, execCtx)
	}

	// Convert to boolean
	result := isTruthy(rendered)

	h.logger.Debug("Condition evaluated",
		zap.String("node_id", node.ID),
		zap.String("expression", expression),
		zap.String("rendered", rendered),
		zap.Bool("result", result),
		zap.Duration("duration", time.Since(startTime)))

	return h.createResult(node.ID, result, expression, startTime), nil
}

// getExpression extracts the condition expression from the node.
func (h *ConditionHandler) getExpression(node *models.Node) string {
	// First check condition config
	if node.ConditionConfig != nil && node.ConditionConfig.Expression != "" {
		return node.ConditionConfig.Expression
	}

	// Then check node config
	if node.Config != nil && node.Config.Expression != "" {
		return node.Config.Expression
	}

	return ""
}

// evaluateSimpleExpression handles basic expressions without template engine.
// Supports:
// - Direct boolean strings: "true", "false"
// - Simple variable references: "{{variable}}"
// - Comparison placeholders (for demonstration)
func (h *ConditionHandler) evaluateSimpleExpression(expr string, ctx *wfcontext.ExecutionContext) string {
	return evaluateExpressionWithoutTemplate(expr, ctx)
}

// createResult builds a NodeResult for the condition evaluation.
func (h *ConditionHandler) createResult(nodeID string, result bool, expression string, startTime time.Time) *executor.NodeResult {
	output := map[string]interface{}{
		"condition_result": result,
		"expression":       expression,
	}

	return &executor.NodeResult{
		NodeID:      nodeID,
		Status:      executor.NodeStatusCompleted,
		Output:      output,
		StartedAt:   startTime,
		CompletedAt: time.Now(),
		Duration:    time.Since(startTime),
	}
}

// isTruthy converts a string value to boolean.
// Handles various truthy/falsy representations.
func isTruthy(value string) bool {
	v := strings.TrimSpace(strings.ToLower(value))

	// Explicit true values
	switch v {
	case "true", "yes", "1", "on":
		return true
	case "false", "no", "0", "off", "", "none", "null", "nil":
		return false
	}

	// Try to parse as number
	if num, err := strconv.ParseFloat(v, 64); err == nil {
		return num != 0
	}

	// Non-empty string is truthy (Pythonic behavior)
	return len(v) > 0
}

// EvaluateCondition is a utility function to evaluate a condition expression.
// Can be used by the executor for edge conditions.
func EvaluateCondition(
	ctx context.Context,
	expression string,
	execCtx *wfcontext.ExecutionContext,
	templateEngine TemplateRenderer,
) (bool, error) {
	if expression == "" {
		return true, nil // Empty condition is always true
	}

	var rendered string
	var err error

	if templateEngine != nil {
		renderCtx := execCtx.ToMap()
		rendered, err = templateEngine.Render(ctx, expression, renderCtx)
		if err != nil {
			return false, fmt.Errorf("condition evaluation failed: %w", err)
		}
	} else {
		// Fail closed for unresolved template expressions when template engine is unavailable.
		rendered = evaluateExpressionWithoutTemplate(expression, execCtx)
	}

	return isTruthy(rendered), nil
}

func evaluateExpressionWithoutTemplate(expression string, execCtx *wfcontext.ExecutionContext) string {
	expr := strings.TrimSpace(expression)

	lower := strings.ToLower(expr)
	if lower == "true" || lower == "false" {
		return lower
	}

	if strings.HasPrefix(expr, "{{") && strings.HasSuffix(expr, "}}") {
		varName := strings.TrimSpace(expr[2 : len(expr)-2])
		if varName == "" {
			return "false"
		}
		val, ok := execCtx.Get(varName)
		if !ok {
			return "false"
		}
		return stringifyValueForTruthyCheck(val)
	}

	return expr
}

func stringifyValueForTruthyCheck(val interface{}) string {
	switch v := val.(type) {
	case nil:
		return "false"
	case bool:
		return strconv.FormatBool(v)
	case string:
		return v
	case int:
		return strconv.FormatBool(v != 0)
	case int8:
		return strconv.FormatBool(v != 0)
	case int16:
		return strconv.FormatBool(v != 0)
	case int32:
		return strconv.FormatBool(v != 0)
	case int64:
		return strconv.FormatBool(v != 0)
	case uint:
		return strconv.FormatBool(v != 0)
	case uint8:
		return strconv.FormatBool(v != 0)
	case uint16:
		return strconv.FormatBool(v != 0)
	case uint32:
		return strconv.FormatBool(v != 0)
	case uint64:
		return strconv.FormatBool(v != 0)
	case float32:
		return strconv.FormatBool(v != 0)
	case float64:
		return strconv.FormatBool(v != 0)
	default:
		return fmt.Sprintf("%v", val)
	}
}

// ConditionEvaluatorImpl implements the executor.ConditionEvaluator interface.
type ConditionEvaluatorImpl struct {
	templateEngine TemplateRenderer
}

// NewConditionEvaluator creates a new condition evaluator.
func NewConditionEvaluator(templateEngine TemplateRenderer) *ConditionEvaluatorImpl {
	return &ConditionEvaluatorImpl{
		templateEngine: templateEngine,
	}
}

// Evaluate evaluates a condition expression against the context.
func (e *ConditionEvaluatorImpl) Evaluate(condition string, ctx *wfcontext.ExecutionContext) (bool, error) {
	return EvaluateCondition(context.Background(), condition, ctx, e.templateEngine)
}
