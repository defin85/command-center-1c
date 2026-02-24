// Package engine provides a complete workflow engine for executing DAG-based workflows.
//
// The workflow engine supports:
// - DAG-based workflow definition and validation
// - Multiple node types: operation, condition, parallel, loop, subworkflow
// - Template rendering with pongo2 (Jinja2-compatible)
// - Checkpoint and resume for long-running workflows
// - State management with Redis and PostgreSQL
// - Distributed locks for concurrent execution safety
//
// Example usage:
//
//	eng := engine.NewEngine(config)
//	execID, err := eng.StartWorkflow(ctx, dagJSON, inputVars)
//	result, err := eng.WaitForCompletion(ctx, execID)
package engine

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"strings"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/worker/internal/workflow"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/checkpoint"
	wfcontext "github.com/commandcenter1c/commandcenter/worker/internal/workflow/context"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/executor"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/handlers"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/models"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/state"
	"github.com/commandcenter1c/commandcenter/worker/internal/workflow/validator"
)

// Engine is the main entry point for workflow execution.
type Engine struct {
	stateStore   state.StateStore
	historyStore state.HistoryStore
	stateManager *state.StateManager
	handlerReg   *handlers.HandlerRegistry
	handlerDeps  *handlers.HandlerDependencies
	logger       *slog.Logger
	zapLogger    *zap.Logger
	config       *EngineConfig
}

// EngineConfig holds configuration for the workflow engine.
type EngineConfig struct {
	// ExecutorConfig for underlying executor.
	ExecutorConfig *executor.ExecutorConfig
	// CheckpointConfig for checkpoint behavior.
	CheckpointConfig *checkpoint.CheckpointConfig
	// StateManagerConfig for state management.
	StateManagerConfig *state.StateManagerConfig
	// HistoryAuthToken is used by HistoryClient for internal API authentication.
	HistoryAuthToken string
}

// DefaultEngineConfig returns sensible default configuration.
func DefaultEngineConfig() *EngineConfig {
	return &EngineConfig{
		ExecutorConfig:     executor.DefaultExecutorConfig(),
		CheckpointConfig:   checkpoint.DefaultCheckpointConfig(),
		StateManagerConfig: state.DefaultStateManagerConfig(),
	}
}

// NewEngine creates a new workflow engine.
func NewEngine(
	redisClient *redis.Client,
	orchestratorURL string,
	logger *slog.Logger,
	zapLogger *zap.Logger,
	config *EngineConfig,
) (*Engine, error) {
	if config == nil {
		config = DefaultEngineConfig()
	}
	if logger == nil {
		logger = slog.Default()
	}
	if zapLogger == nil {
		zapLogger = zap.NewNop()
	}

	// Create state store
	stateStore := state.NewRedisStateStore(redisClient, nil)

	// Create history store (optional)
	var historyStore state.HistoryStore
	if orchestratorURL != "" {
		historyAuthToken := strings.TrimSpace(config.HistoryAuthToken)
		if historyAuthToken == "" {
			historyAuthToken = strings.TrimSpace(os.Getenv("INTERNAL_API_TOKEN"))
		}
		historyStore = state.NewHistoryClient(&state.HistoryClientConfig{
			BaseURL:   orchestratorURL,
			AuthToken: historyAuthToken,
		})
	} else {
		historyStore = &state.NoOpHistoryStore{}
	}

	// Create state manager
	stateManager := state.NewStateManager(stateStore, historyStore, logger, config.StateManagerConfig)

	// Create handler dependencies
	handlerDeps := handlers.NewHandlerDependencies(zapLogger)

	// Create handler registry with all handlers
	handlerReg := handlers.NewRegistryWithHandlers(handlerDeps)

	return &Engine{
		stateStore:   stateStore,
		historyStore: historyStore,
		stateManager: stateManager,
		handlerReg:   handlerReg,
		handlerDeps:  handlerDeps,
		logger:       logger,
		zapLogger:    zapLogger,
		config:       config,
	}, nil
}

// NewEngineWithStores creates an engine with custom stores (for testing).
func NewEngineWithStores(
	stateStore state.StateStore,
	historyStore state.HistoryStore,
	logger *slog.Logger,
	zapLogger *zap.Logger,
	config *EngineConfig,
) *Engine {
	if config == nil {
		config = DefaultEngineConfig()
	}
	if logger == nil {
		logger = slog.Default()
	}
	if zapLogger == nil {
		zapLogger = zap.NewNop()
	}

	stateManager := state.NewStateManager(stateStore, historyStore, logger, config.StateManagerConfig)
	handlerDeps := handlers.NewHandlerDependencies(zapLogger)
	handlerReg := handlers.NewRegistryWithHandlers(handlerDeps)

	return &Engine{
		stateStore:   stateStore,
		historyStore: historyStore,
		stateManager: stateManager,
		handlerReg:   handlerReg,
		handlerDeps:  handlerDeps,
		logger:       logger,
		zapLogger:    zapLogger,
		config:       config,
	}
}

// StartWorkflow starts a new workflow execution.
func (e *Engine) StartWorkflow(
	ctx context.Context,
	dagJSON []byte,
	inputVars map[string]interface{},
) (string, error) {
	// Parse DAG
	dag, err := models.FromJSON(dagJSON)
	if err != nil {
		return "", fmt.Errorf("failed to parse DAG: %w", err)
	}

	// Validate DAG
	v := validator.NewValidator(dag)
	result := v.Validate()
	if !result.IsValid {
		errMsg := "DAG validation failed"
		if len(result.Errors) > 0 {
			errMsg = result.Errors[0].Message
		}
		return "", workflow.NewValidationError(errMsg)
	}

	// Generate execution ID
	executionID := resolveExecutionID(inputVars)
	if executionID == "" {
		executionID = uuid.New().String()
	}

	// Create executor
	exec, err := executor.NewExecutorWithConfig(dag, e.zapLogger, e.config.ExecutorConfig)
	if err != nil {
		return "", fmt.Errorf("failed to create executor: %w", err)
	}

	// Register handlers
	e.configureExecutor(exec)

	// Initialize execution context
	execCtx := wfcontext.NewExecutionContextWithVars(executionID, dag.ID, inputVars)

	// Initialize state
	_, err = e.stateManager.InitializeExecution(ctx, executionID, dag.ID, dag.ID, dag.Version, inputVars)
	if err != nil {
		return "", fmt.Errorf("failed to initialize state: %w", err)
	}

	// Start execution in background
	go func() {
		bgCtx := context.Background()

		// Start
		if err := e.stateManager.StartExecution(bgCtx, executionID); err != nil {
			e.logger.Error("failed to start execution", "execution_id", executionID, "error", err)
			return
		}

		// Execute
		_, err := exec.Execute(bgCtx, execCtx)
		if err != nil {
			e.logger.Error("workflow execution failed", "execution_id", executionID, "error", err)
			if failErr := e.stateManager.FailExecution(bgCtx, executionID, err); failErr != nil {
				e.logger.Error("failed to mark as failed", "error", failErr)
			}
			return
		}

		// Complete
		if err := e.stateManager.CompleteExecution(bgCtx, executionID); err != nil {
			e.logger.Error("failed to complete execution", "error", err)
		}
	}()

	e.logger.Info("workflow started",
		"execution_id", executionID,
		"dag_id", dag.ID,
		"node_count", dag.NodeCount(),
	)

	return executionID, nil
}

// ExecuteWorkflowSync executes a workflow synchronously and returns the result.
func (e *Engine) ExecuteWorkflowSync(
	ctx context.Context,
	dagJSON []byte,
	inputVars map[string]interface{},
) (*ExecutionResult, error) {
	// Parse DAG
	dag, err := models.FromJSON(dagJSON)
	if err != nil {
		return nil, fmt.Errorf("failed to parse DAG: %w", err)
	}

	// Validate
	v := validator.NewValidator(dag)
	result := v.Validate()
	if !result.IsValid {
		errMsg := "DAG validation failed"
		if len(result.Errors) > 0 {
			errMsg = result.Errors[0].Message
		}
		return nil, workflow.NewValidationError(errMsg)
	}

	// Generate execution ID
	executionID := resolveExecutionID(inputVars)
	if executionID == "" {
		executionID = uuid.New().String()
	}

	// Create executor
	exec, err := executor.NewExecutorWithConfig(dag, e.zapLogger, e.config.ExecutorConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create executor: %w", err)
	}

	// Register handlers
	e.configureExecutor(exec)

	// Initialize context
	execCtx := wfcontext.NewExecutionContextWithVars(executionID, dag.ID, inputVars)

	// Initialize state
	_, err = e.stateManager.InitializeExecution(ctx, executionID, dag.ID, dag.ID, dag.Version, inputVars)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize state: %w", err)
	}

	// Start
	if err := e.stateManager.StartExecution(ctx, executionID); err != nil {
		return nil, fmt.Errorf("failed to start execution: %w", err)
	}

	// Execute
	finalCtx, err := exec.Execute(ctx, execCtx)
	if err != nil {
		if failErr := e.stateManager.FailExecution(ctx, executionID, err); failErr != nil {
			e.logger.Error("failed to mark as failed", "error", failErr)
		}
		return nil, err
	}

	// Complete
	if err := e.stateManager.CompleteExecution(ctx, executionID); err != nil {
		e.logger.Error("failed to complete execution", "error", err)
	}

	// Get final state
	workflowState, _ := e.stateManager.GetState(ctx, executionID)

	return &ExecutionResult{
		ExecutionID: executionID,
		Status:      string(state.WorkflowStatusCompleted),
		Output:      finalCtx.ToMap(),
		State:       workflowState,
	}, nil
}

// ResumeWorkflow resumes a paused or failed workflow.
func (e *Engine) ResumeWorkflow(ctx context.Context, executionID string, opts *checkpoint.ResumeOptions) error {
	// Get state
	workflowState, err := e.stateManager.GetState(ctx, executionID)
	if err != nil {
		return fmt.Errorf("failed to get state: %w", err)
	}

	// Validate resumability
	checkpointMgr := checkpoint.NewCheckpointManager(e.stateStore, e.logger, e.config.CheckpointConfig)
	if err := checkpointMgr.ValidateResume(ctx, executionID); err != nil {
		return err
	}

	// Load DAG (would need to be stored or passed)
	// For now, return error
	_ = workflowState
	return fmt.Errorf("resume requires DAG to be stored - not implemented yet")
}

func resolveExecutionID(inputVars map[string]interface{}) string {
	if inputVars == nil {
		return ""
	}
	rawExecutionID, ok := inputVars["execution_id"]
	if !ok {
		return ""
	}
	executionID, ok := rawExecutionID.(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(executionID)
}

// CancelWorkflow cancels a running workflow.
func (e *Engine) CancelWorkflow(ctx context.Context, executionID string) error {
	return e.stateManager.CancelExecution(ctx, executionID)
}

// PauseWorkflow pauses a running workflow.
func (e *Engine) PauseWorkflow(ctx context.Context, executionID string) error {
	return e.stateManager.PauseExecution(ctx, executionID)
}

// GetWorkflowState returns the current state of a workflow.
func (e *Engine) GetWorkflowState(ctx context.Context, executionID string) (*state.WorkflowState, error) {
	return e.stateManager.GetState(ctx, executionID)
}

// ValidateDAG validates a DAG without executing it.
func (e *Engine) ValidateDAG(dagJSON []byte) (*validator.ValidationResult, error) {
	dag, err := models.FromJSON(dagJSON)
	if err != nil {
		return nil, fmt.Errorf("failed to parse DAG: %w", err)
	}

	v := validator.NewValidator(dag)
	return v.Validate(), nil
}

// SetOperationExecutor injects an operation executor into handler dependencies.
// The operation handler is re-created to pick up updated dependencies.
func (e *Engine) SetOperationExecutor(operationExecutor handlers.OperationExecutor) {
	e.handlerDeps.WithOperationExecutor(operationExecutor)
	e.handlerReg.Register(models.NodeTypeOperation, handlers.NewOperationHandler(e.handlerDeps))
}

func (e *Engine) configureExecutor(exec *executor.Executor) {
	for _, handler := range e.handlerReg.AllHandlers() {
		exec.RegisterHandler(handler)
	}
	exec.SetConditionEvaluator(handlers.NewConditionEvaluator(e.handlerDeps.TemplateEngine))
}

// ExecutionResult holds the result of a workflow execution.
type ExecutionResult struct {
	ExecutionID string
	Status      string
	Output      map[string]interface{}
	State       *state.WorkflowState
	Error       error
}

// ToJSON serializes the result to JSON.
func (r *ExecutionResult) ToJSON() ([]byte, error) {
	return json.Marshal(r)
}

// Close releases engine resources.
func (e *Engine) Close() error {
	return e.stateManager.Close()
}
