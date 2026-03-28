// Package handlers provides node handlers for workflow execution.
// Each handler implements the NodeHandler interface and processes a specific node type.
package handlers

import (
	"context"
	"fmt"

	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
)

// TemplateRenderer renders template expressions with context variables.
// Used by operation, condition, and loop handlers for dynamic content.
type TemplateRenderer interface {
	// Render evaluates a template string with the given context.
	// Returns the rendered string result.
	Render(ctx context.Context, template string, data map[string]interface{}) (string, error)

	// RenderJSON evaluates a template and returns the result as a map.
	// Used for rendering operation payloads.
	RenderJSON(ctx context.Context, template map[string]interface{}, data map[string]interface{}) (map[string]interface{}, error)
}

// OperationExecutor executes operations against 1C databases.
// Abstraction over OData and RAS backends.
type OperationExecutor interface {
	// Execute runs an operation and returns the result.
	Execute(ctx context.Context, req *OperationRequest) (map[string]interface{}, error)
}

// PublicationAuth defines publication credentials lookup context propagated from workflow execution input.
type PublicationAuth struct {
	Strategy      string `json:"strategy,omitempty"`
	ActorUsername string `json:"actor_username,omitempty"`
	Source        string `json:"source,omitempty"`
}

// OperationRequest represents a request to execute an operation.
type OperationRequest struct {
	// OperationID identifies top-level worker operation execution.
	OperationID string `json:"operation_id,omitempty"`
	// OperationType specifies the operation kind (create, update, delete, query, etc.).
	OperationType string `json:"operation_type"`
	// TargetEntity is the OData entity or resource being operated on.
	TargetEntity string `json:"target_entity,omitempty"`
	// Payload contains the data to be sent with the operation.
	Payload map[string]interface{} `json:"payload,omitempty"`
	// TemplateID references the operation template.
	TemplateID string `json:"template_id,omitempty"`
	// OperationRef preserves template binding provenance for operation nodes.
	OperationRef *models.OperationRef `json:"operation_ref,omitempty"`
	// TargetDatabases is a list of database IDs to operate on.
	TargetDatabases []string `json:"target_databases,omitempty"`
	// TimeoutSeconds is the operation timeout.
	TimeoutSeconds int `json:"timeout_seconds,omitempty"`
	// ExecutionID identifies current workflow execution.
	ExecutionID string `json:"execution_id,omitempty"`
	// NodeID identifies current operation node.
	NodeID string `json:"node_id,omitempty"`
	// TenantID is tenant context propagated from workflow input.
	TenantID string `json:"tenant_id,omitempty"`
	// PoolRunID is pool runtime identifier propagated from workflow input.
	PoolRunID string `json:"pool_run_id,omitempty"`
	// StepAttempt is workflow-level attempt number for idempotency semantics.
	StepAttempt int `json:"step_attempt,omitempty"`
	// IdempotencyKey allows caller to force a stable key per step attempt.
	IdempotencyKey string `json:"idempotency_key,omitempty"`
	// PublicationAuth carries actor/service provenance for pool.publication_odata credentials lookup.
	PublicationAuth *PublicationAuth `json:"publication_auth,omitempty"`
}

const (
	// ErrorCodeWorkflowOperationExecutorNotConfigured indicates missing executor wiring for pool runtime.
	ErrorCodeWorkflowOperationExecutorNotConfigured = "WORKFLOW_OPERATION_EXECUTOR_NOT_CONFIGURED"
	// ErrorCodePoolRuntimeRouteDisabled indicates poolops route is disabled by runtime guard.
	ErrorCodePoolRuntimeRouteDisabled = "POOL_RUNTIME_ROUTE_DISABLED"
	// ErrorCodePoolRuntimePublicationPathDisabled indicates publication path is fail-closed and must not fallback to bridge.
	ErrorCodePoolRuntimePublicationPathDisabled = "POOL_RUNTIME_PUBLICATION_PATH_DISABLED"
	// ErrorCodePoolRuntimeFactualPathDisabled indicates factual sync path is fail-closed and must not fallback to bridge.
	ErrorCodePoolRuntimeFactualPathDisabled = "POOL_RUNTIME_FACTUAL_PATH_DISABLED"
	// ErrorCodePoolRuntimeBridgeRetryBudgetExhausted indicates bridge transport retries exhausted execution budget.
	ErrorCodePoolRuntimeBridgeRetryBudgetExhausted = "POOL_RUNTIME_BRIDGE_RETRY_BUDGET_EXHAUSTED"
)

// OperationExecutionError is a machine-readable operation runtime error.
type OperationExecutionError struct {
	Code    string
	Message string
}

func (e *OperationExecutionError) Error() string {
	if e == nil {
		return ""
	}
	if e.Code == "" {
		return e.Message
	}
	if e.Message == "" {
		return e.Code
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// NewOperationExecutionError creates a machine-readable operation error.
func NewOperationExecutionError(code, message string) *OperationExecutionError {
	return &OperationExecutionError{
		Code:    code,
		Message: message,
	}
}

// WorkflowStore provides access to workflow DAGs.
// Used by subworkflow handler to load nested workflows.
type WorkflowStore interface {
	// GetWorkflow retrieves a workflow DAG by ID.
	GetWorkflow(ctx context.Context, workflowID string) (*models.DAG, error)
}

// ExecutorFactory creates executor instances for workflows.
// Used by subworkflow and parallel handlers.
type ExecutorFactory interface {
	// Create creates a new executor for the given DAG.
	Create(dag *models.DAG, logger *zap.Logger) (*executor.Executor, error)
}

// HandlerDependencies contains all dependencies required by handlers.
type HandlerDependencies struct {
	// TemplateEngine renders template expressions.
	TemplateEngine TemplateRenderer
	// OperationExecutor executes 1C operations.
	OperationExecutor OperationExecutor
	// WorkflowStore provides access to workflow DAGs.
	WorkflowStore WorkflowStore
	// ExecutorFactory creates executor instances.
	ExecutorFactory ExecutorFactory
	// Logger for structured logging.
	Logger *zap.Logger
}

// NewHandlerDependencies creates a new dependencies instance with defaults.
func NewHandlerDependencies(logger *zap.Logger) *HandlerDependencies {
	if logger == nil {
		logger = zap.NewNop()
	}
	return &HandlerDependencies{
		Logger: logger,
	}
}

// WithTemplateEngine sets the template engine.
func (d *HandlerDependencies) WithTemplateEngine(engine TemplateRenderer) *HandlerDependencies {
	d.TemplateEngine = engine
	return d
}

// WithOperationExecutor sets the operation executor.
func (d *HandlerDependencies) WithOperationExecutor(exec OperationExecutor) *HandlerDependencies {
	d.OperationExecutor = exec
	return d
}

// WithWorkflowStore sets the workflow store.
func (d *HandlerDependencies) WithWorkflowStore(store WorkflowStore) *HandlerDependencies {
	d.WorkflowStore = store
	return d
}

// WithExecutorFactory sets the executor factory.
func (d *HandlerDependencies) WithExecutorFactory(factory ExecutorFactory) *HandlerDependencies {
	d.ExecutorFactory = factory
	return d
}

// HandlerRegistry manages node handlers for different node types.
// Thread-safe registry that maps node types to their handlers.
type HandlerRegistry struct {
	handlers map[models.NodeType]executor.NodeHandler
}

// NewHandlerRegistry creates a new empty handler registry.
func NewHandlerRegistry() *HandlerRegistry {
	return &HandlerRegistry{
		handlers: make(map[models.NodeType]executor.NodeHandler),
	}
}

// Register adds a handler for the specified node type.
// Overwrites any existing handler for the same type.
func (r *HandlerRegistry) Register(nodeType models.NodeType, handler executor.NodeHandler) {
	r.handlers[nodeType] = handler
}

// Get retrieves a handler for the specified node type.
// Returns the handler and true if found, nil and false otherwise.
func (r *HandlerRegistry) Get(nodeType models.NodeType) (executor.NodeHandler, bool) {
	h, ok := r.handlers[nodeType]
	return h, ok
}

// Has checks if a handler is registered for the specified node type.
func (r *HandlerRegistry) Has(nodeType models.NodeType) bool {
	_, ok := r.handlers[nodeType]
	return ok
}

// RegisteredTypes returns a list of all registered node types.
func (r *HandlerRegistry) RegisteredTypes() []models.NodeType {
	types := make([]models.NodeType, 0, len(r.handlers))
	for t := range r.handlers {
		types = append(types, t)
	}
	return types
}

// AllHandlers returns all registered handlers.
func (r *HandlerRegistry) AllHandlers() []executor.NodeHandler {
	handlers := make([]executor.NodeHandler, 0, len(r.handlers))
	for _, h := range r.handlers {
		handlers = append(handlers, h)
	}
	return handlers
}

// RegisterAllHandlers registers all standard handlers with the given dependencies.
// This is the main entry point for setting up the handler registry.
func (r *HandlerRegistry) RegisterAllHandlers(deps *HandlerDependencies) {
	r.Register(models.NodeTypeOperation, NewOperationHandler(deps))
	r.Register(models.NodeTypeCondition, NewConditionHandler(deps))
	r.Register(models.NodeTypeParallel, NewParallelHandler(deps, r))
	r.Register(models.NodeTypeLoop, NewLoopHandler(deps, r))
	r.Register(models.NodeTypeSubworkflow, NewSubworkflowHandler(deps))
}

// NewRegistryWithHandlers creates a registry with all standard handlers registered.
func NewRegistryWithHandlers(deps *HandlerDependencies) *HandlerRegistry {
	r := NewHandlerRegistry()
	r.RegisterAllHandlers(deps)
	return r
}
