package saga

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

// OrchestratorConfig holds configuration for the saga orchestrator.
type OrchestratorConfig struct {
	// DefaultStepTimeout is the default timeout for steps without explicit timeout.
	DefaultStepTimeout time.Duration

	// LockTTL is the TTL for execution locks.
	LockTTL time.Duration

	// LockHeartbeatInterval is the interval for lock heartbeat.
	LockHeartbeatInterval time.Duration

	// EnableEvents enables publishing saga events to Redis Streams.
	EnableEvents bool

	// EventChannel is the Redis Stream channel for saga events.
	EventChannel string
}

// DefaultOrchestratorConfig returns default configuration.
func DefaultOrchestratorConfig() *OrchestratorConfig {
	return &OrchestratorConfig{
		DefaultStepTimeout:    5 * time.Minute,
		LockTTL:               5 * time.Minute,
		LockHeartbeatInterval: 1 * time.Minute,
		EnableEvents:          true,
		EventChannel:          "events:saga",
	}
}

// orchestrator implements the SagaOrchestrator interface.
type orchestrator struct {
	store                SagaStore
	compensationExecutor *CompensationExecutor
	compensationRunner   *CompensationRunner
	publisher            *events.Publisher
	logger               *zap.Logger
	config               *OrchestratorConfig
	metrics              *Metrics

	mu    sync.RWMutex
	sagas map[string]*SagaDefinition
}

// NewOrchestrator creates a new saga orchestrator.
func NewOrchestrator(
	store SagaStore,
	publisher *events.Publisher,
	logger *zap.Logger,
	config *OrchestratorConfig,
) SagaOrchestrator {
	if config == nil {
		config = DefaultOrchestratorConfig()
	}
	if logger == nil {
		logger = zap.NewNop()
	}

	compensationExecutor := NewCompensationExecutor(logger)
	compensationRunner := NewCompensationRunner(compensationExecutor, store, logger)

	return &orchestrator{
		store:                store,
		compensationExecutor: compensationExecutor,
		compensationRunner:   compensationRunner,
		publisher:            publisher,
		logger:               logger,
		config:               config,
		metrics:              NewMetrics(),
		sagas:                make(map[string]*SagaDefinition),
	}
}

// RegisterSaga registers a saga definition.
func (o *orchestrator) RegisterSaga(def *SagaDefinition) error {
	if def == nil {
		return ErrInvalidSagaDefinition
	}

	if err := def.Validate(); err != nil {
		return fmt.Errorf("%w: %v", ErrInvalidSagaDefinition, err)
	}

	o.mu.Lock()
	defer o.mu.Unlock()

	if _, exists := o.sagas[def.ID]; exists {
		return ErrSagaAlreadyRegistered
	}

	// Apply default timeout if not set
	if def.DefaultTimeout == 0 {
		def.DefaultTimeout = o.config.DefaultStepTimeout
	}

	o.sagas[def.ID] = def
	o.logger.Info("saga registered",
		zap.String("saga_id", def.ID),
		zap.String("name", def.Name),
		zap.Int("steps", len(def.Steps)),
	)

	return nil
}

// GetSaga returns a registered saga definition.
func (o *orchestrator) GetSaga(sagaID string) (*SagaDefinition, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()

	saga, exists := o.sagas[sagaID]
	if !exists {
		return nil, ErrSagaNotFound
	}

	return saga, nil
}

// Execute starts a new saga execution.
func (o *orchestrator) Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*SagaResult, error) {
	correlationID := uuid.New().String()
	return o.ExecuteWithCorrelation(ctx, sagaID, input, correlationID)
}

// ExecuteWithCorrelation starts a saga with a specific correlation ID.
func (o *orchestrator) ExecuteWithCorrelation(
	ctx context.Context,
	sagaID string,
	input map[string]interface{},
	correlationID string,
) (*SagaResult, error) {
	start := time.Now()

	// Get saga definition
	saga, err := o.GetSaga(sagaID)
	if err != nil {
		return nil, err
	}

	// Generate execution ID
	executionID := uuid.New().String()

	// Create initial state
	state := NewSagaState(executionID, sagaID, correlationID)
	if input != nil {
		state.Variables = input
	}

	// Extract database IDs from input if present
	if dbIDs, ok := input["database_ids"].([]string); ok {
		state.Locks = dbIDs
	} else if dbIDs, ok := input["database_ids"].([]interface{}); ok {
		state.Locks = make([]string, 0, len(dbIDs))
		for _, id := range dbIDs {
			if str, ok := id.(string); ok {
				state.Locks = append(state.Locks, str)
			}
		}
	}

	// Save initial state
	if err := o.store.SaveState(ctx, state); err != nil {
		return nil, fmt.Errorf("failed to save initial state: %w", err)
	}

	// Acquire execution lock
	locked, err := o.store.AcquireLock(ctx, executionID, o.config.LockTTL)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire lock: %w", err)
	}
	if !locked {
		return nil, ErrExecutionAlreadyRunning
	}

	// Ensure lock is released
	defer func() {
		releaseCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := o.store.ReleaseLock(releaseCtx, executionID); err != nil {
			o.logger.Warn("failed to release saga lock",
				zap.String("execution_id", executionID),
				zap.Error(err),
			)
		}
	}()

	// Create saga context
	sagaCtx := state.ToContext()

	// Start metrics and events
	o.metrics.SagasStarted.WithLabelValues(sagaID).Inc()
	o.publishEvent(ctx, SagaEventStarted, executionID, sagaID, correlationID, "", nil, 0)

	// Execute saga
	result := o.executeSaga(ctx, saga, state, sagaCtx)

	// Record metrics
	duration := time.Since(start)
	result.Duration = duration

	o.metrics.SagaDuration.WithLabelValues(sagaID, string(result.Status)).Observe(duration.Seconds())

	switch result.Status {
	case SagaStatusCompleted:
		o.metrics.SagasCompleted.WithLabelValues(sagaID).Inc()
	case SagaStatusFailed:
		o.metrics.SagasFailed.WithLabelValues(sagaID).Inc()
	case SagaStatusCompensated, SagaStatusPartiallyCompensated:
		o.metrics.SagasCompensated.WithLabelValues(sagaID).Inc()
	}

	return result, nil
}
