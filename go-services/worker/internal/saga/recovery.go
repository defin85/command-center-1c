package saga

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/commandcenter1c/commandcenter/worker/internal/resourcemanager"
)

// RecoveryStrategy defines how to handle stale sagas.
type RecoveryStrategy int

const (
	// StrategyResume attempts to continue execution from last checkpoint.
	StrategyResume RecoveryStrategy = iota

	// StrategyCompensate immediately rolls back the saga.
	StrategyCompensate

	// StrategyManual marks the saga for manual intervention.
	StrategyManual
)

// String returns string representation of RecoveryStrategy.
func (s RecoveryStrategy) String() string {
	switch s {
	case StrategyResume:
		return "resume"
	case StrategyCompensate:
		return "compensate"
	case StrategyManual:
		return "manual"
	default:
		return "unknown"
	}
}

// RecoveryConfig holds configuration for RecoveryManager.
type RecoveryConfig struct {
	// WorkerID is the identifier of current worker instance.
	WorkerID string

	// RecoverOnStart enables automatic recovery on worker startup.
	RecoverOnStart bool

	// MaxRecoveryTime is the maximum duration for recovery process at startup.
	MaxRecoveryTime time.Duration

	// StaleSagaThreshold defines when a saga is considered stale.
	StaleSagaThreshold time.Duration

	// RecoveryStrategy defines how to handle stale sagas.
	RecoveryStrategy RecoveryStrategy

	// EventChannel is the Redis Stream channel for recovery events.
	EventChannel string

	// WorkerHeartbeatTTL is the TTL for worker heartbeat keys.
	WorkerHeartbeatTTL time.Duration
}

// DefaultRecoveryConfig returns default configuration.
func DefaultRecoveryConfig() *RecoveryConfig {
	return &RecoveryConfig{
		RecoverOnStart:     true,
		MaxRecoveryTime:    2 * time.Minute,
		StaleSagaThreshold: 5 * time.Minute,
		RecoveryStrategy:   StrategyResume,
		EventChannel:       "events:saga:recovery",
		WorkerHeartbeatTTL: 30 * time.Second,
	}
}

// RecoveryStats holds statistics about recovery operations.
type RecoveryStats struct {
	TotalScanned         int       `json:"total_scanned"`
	ResumedSagas         int       `json:"resumed_sagas"`
	CompensatedSagas     int       `json:"compensated_sagas"`
	FailedRecoveries     int       `json:"failed_recoveries"`
	ManualReviewRequired int       `json:"manual_review_required"`
	OrphanedLocksCleaned int       `json:"orphaned_locks_cleaned"`
	LastRecoveryTime     time.Time `json:"last_recovery_time"`
}

// RecoveryEvent represents a recovery lifecycle event.
type RecoveryEvent struct {
	Type        string    `json:"type"`
	ExecutionID string    `json:"execution_id"`
	SagaID      string    `json:"saga_id"`
	WorkerID    string    `json:"worker_id"`
	Strategy    string    `json:"strategy"`
	Error       string    `json:"error,omitempty"`
	Timestamp   time.Time `json:"timestamp"`
}

// RecoveryManager defines the interface for saga recovery operations.
type RecoveryManager interface {
	// Start initiates recovery process on worker startup.
	Start(ctx context.Context) error

	// RecoverSaga attempts to recover a specific saga execution.
	RecoverSaga(ctx context.Context, executionID string) error

	// CleanupOrphanedLocks releases locks from crashed workers.
	CleanupOrphanedLocks(ctx context.Context) (int, error)

	// GetRecoveryStats returns recovery statistics.
	GetRecoveryStats() *RecoveryStats

	// RegisterWorkerHeartbeat updates the worker's heartbeat.
	RegisterWorkerHeartbeat(ctx context.Context) error

	// Close releases resources.
	Close() error
}

// recoveryManager implements RecoveryManager.
type recoveryManager struct {
	store           SagaStore
	orchestrator    SagaOrchestrator
	resourceManager resourcemanager.ResourceManager
	publisher       *events.Publisher
	redisClient     redis.Cmdable
	logger          *zap.Logger
	config          *RecoveryConfig
	metrics         *recoveryMetrics

	mu    sync.RWMutex
	stats *RecoveryStats
}

// NewRecoveryManager creates a new RecoveryManager.
func NewRecoveryManager(
	store SagaStore,
	orchestrator SagaOrchestrator,
	resourceManager resourcemanager.ResourceManager,
	publisher *events.Publisher,
	redisClient redis.Cmdable,
	logger *zap.Logger,
	config *RecoveryConfig,
) RecoveryManager {
	if config == nil {
		config = DefaultRecoveryConfig()
	}
	if logger == nil {
		logger = zap.NewNop()
	}

	return &recoveryManager{
		store:           store,
		orchestrator:    orchestrator,
		resourceManager: resourceManager,
		publisher:       publisher,
		redisClient:     redisClient,
		logger:          logger,
		config:          config,
		metrics:         newRecoveryMetrics(),
		stats:           &RecoveryStats{},
	}
}

// Start implements RecoveryManager.Start.
func (r *recoveryManager) Start(ctx context.Context) error {
	if !r.config.RecoverOnStart {
		r.logger.Info("recovery on start is disabled")
		return nil
	}

	r.logger.Info("starting saga recovery",
		zap.String("worker_id", r.config.WorkerID),
		zap.Duration("max_recovery_time", r.config.MaxRecoveryTime),
		zap.String("strategy", r.config.RecoveryStrategy.String()),
	)

	// Create context with timeout for recovery process
	recoveryCtx, cancel := context.WithTimeout(ctx, r.config.MaxRecoveryTime)
	defer cancel()

	// Register this worker's heartbeat
	if err := r.RegisterWorkerHeartbeat(recoveryCtx); err != nil {
		r.logger.Warn("failed to register worker heartbeat", zap.Error(err))
	}

	// 1. Find all sagas in running status
	runningSagas, err := r.store.ListByStatus(recoveryCtx, SagaStatusRunning, 1000)
	if err != nil {
		r.logger.Error("failed to list running sagas", zap.Error(err))
		return fmt.Errorf("failed to list running sagas: %w", err)
	}

	// 2. Find all sagas in compensating status
	compensatingSagas, err := r.store.ListByStatus(recoveryCtx, SagaStatusCompensating, 1000)
	if err != nil {
		r.logger.Error("failed to list compensating sagas", zap.Error(err))
		return fmt.Errorf("failed to list compensating sagas: %w", err)
	}

	r.mu.Lock()
	r.stats.TotalScanned = len(runningSagas) + len(compensatingSagas)
	r.mu.Unlock()

	r.logger.Info("found sagas to recover",
		zap.Int("running", len(runningSagas)),
		zap.Int("compensating", len(compensatingSagas)),
	)

	// 3. Process running sagas
	for _, state := range runningSagas {
		select {
		case <-recoveryCtx.Done():
			r.logger.Warn("recovery timeout reached")
			return recoveryCtx.Err()
		default:
		}

		if err := r.recoverRunningSaga(recoveryCtx, state); err != nil {
			r.logger.Error("failed to recover running saga",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
			r.incrementFailedRecoveries()
		}
	}

	// 4. Process compensating sagas
	for _, state := range compensatingSagas {
		select {
		case <-recoveryCtx.Done():
			r.logger.Warn("recovery timeout reached")
			return recoveryCtx.Err()
		default:
		}

		if err := r.recoverCompensatingSaga(recoveryCtx, state); err != nil {
			r.logger.Error("failed to recover compensating saga",
				zap.String("execution_id", state.ExecutionID),
				zap.Error(err),
			)
			r.incrementFailedRecoveries()
		}
	}

	// 5. Cleanup orphaned locks
	cleaned, err := r.CleanupOrphanedLocks(recoveryCtx)
	if err != nil {
		r.logger.Warn("failed to cleanup orphaned locks", zap.Error(err))
	} else if cleaned > 0 {
		r.logger.Info("cleaned up orphaned locks", zap.Int("count", cleaned))
	}

	r.mu.Lock()
	r.stats.LastRecoveryTime = time.Now()
	r.mu.Unlock()

	r.logger.Info("saga recovery completed",
		zap.Int("total_scanned", r.stats.TotalScanned),
		zap.Int("resumed", r.stats.ResumedSagas),
		zap.Int("compensated", r.stats.CompensatedSagas),
		zap.Int("failed", r.stats.FailedRecoveries),
		zap.Int("manual_review", r.stats.ManualReviewRequired),
		zap.Int("orphaned_locks_cleaned", r.stats.OrphanedLocksCleaned),
	)

	return nil
}

// recoverRunningSaga handles recovery of a saga in running state.
func (r *recoveryManager) recoverRunningSaga(ctx context.Context, state *SagaState) error {
	// Check if saga is stale
	if time.Since(state.UpdatedAt) < r.config.StaleSagaThreshold {
		r.logger.Debug("saga not stale yet, skipping",
			zap.String("execution_id", state.ExecutionID),
			zap.Duration("age", time.Since(state.UpdatedAt)),
		)
		return nil
	}

	r.logger.Info("recovering stale running saga",
		zap.String("execution_id", state.ExecutionID),
		zap.String("saga_id", state.SagaID),
		zap.Duration("age", time.Since(state.UpdatedAt)),
		zap.String("strategy", r.config.RecoveryStrategy.String()),
	)

	r.publishRecoveryEvent(ctx, "recovery.started", state.ExecutionID, state.SagaID, "")

	switch r.config.RecoveryStrategy {
	case StrategyResume:
		return r.attemptResume(ctx, state)

	case StrategyCompensate:
		return r.compensateSaga(ctx, state)

	case StrategyManual:
		return r.markForManualReview(ctx, state)

	default:
		return fmt.Errorf("unknown recovery strategy: %d", r.config.RecoveryStrategy)
	}
}

// attemptResume tries to resume saga execution.
func (r *recoveryManager) attemptResume(ctx context.Context, state *SagaState) error {
	result, err := r.orchestrator.Resume(ctx, state.ExecutionID)
	if err != nil {
		r.logger.Warn("resume failed, falling back to compensation",
			zap.String("execution_id", state.ExecutionID),
			zap.Error(err),
		)
		// Fallback to compensation
		return r.compensateSaga(ctx, state)
	}

	r.metrics.recoveryTotal.WithLabelValues("resume", "success").Inc()
	r.incrementResumedSagas()

	r.publishRecoveryEvent(ctx, "recovery.completed", state.ExecutionID, state.SagaID, "")

	r.logger.Info("saga resumed successfully",
		zap.String("execution_id", state.ExecutionID),
		zap.String("status", string(result.Status)),
	)

	return nil
}

// compensateSaga initiates compensation for a saga.
func (r *recoveryManager) compensateSaga(ctx context.Context, state *SagaState) error {
	// Cancel the saga to trigger compensation
	err := r.orchestrator.Cancel(ctx, state.ExecutionID)
	if err != nil {
		r.metrics.recoveryTotal.WithLabelValues("compensate", "failed").Inc()
		r.publishRecoveryEvent(ctx, "recovery.failed", state.ExecutionID, state.SagaID, err.Error())
		return fmt.Errorf("failed to cancel saga for compensation: %w", err)
	}

	r.metrics.recoveryTotal.WithLabelValues("compensate", "success").Inc()
	r.incrementCompensatedSagas()

	r.publishRecoveryEvent(ctx, "recovery.completed", state.ExecutionID, state.SagaID, "")

	r.logger.Info("saga compensation initiated",
		zap.String("execution_id", state.ExecutionID),
	)

	return nil
}

// markForManualReview marks a saga for manual intervention.
func (r *recoveryManager) markForManualReview(ctx context.Context, state *SagaState) error {
	r.logger.Warn("saga marked for manual review",
		zap.String("execution_id", state.ExecutionID),
		zap.String("saga_id", state.SagaID),
		zap.Int("current_step", state.CurrentStep),
		zap.String("current_step_id", state.CurrentStepID),
	)

	r.metrics.recoveryTotal.WithLabelValues("manual", "pending").Inc()
	r.incrementManualReviewRequired()

	r.publishRecoveryEvent(ctx, "recovery.manual_required", state.ExecutionID, state.SagaID, "")

	return nil
}

// recoverCompensatingSaga continues compensation for a saga.
func (r *recoveryManager) recoverCompensatingSaga(ctx context.Context, state *SagaState) error {
	r.logger.Info("continuing compensation for saga",
		zap.String("execution_id", state.ExecutionID),
		zap.String("saga_id", state.SagaID),
		zap.Int("remaining_compensations", len(state.CompensationStack)),
	)

	r.publishRecoveryEvent(ctx, "recovery.compensation_continued", state.ExecutionID, state.SagaID, "")

	// Resume the saga - orchestrator will continue compensation
	result, err := r.orchestrator.Resume(ctx, state.ExecutionID)
	if err != nil {
		r.metrics.recoveryTotal.WithLabelValues("compensation_continue", "failed").Inc()
		r.publishRecoveryEvent(ctx, "recovery.failed", state.ExecutionID, state.SagaID, err.Error())
		return fmt.Errorf("failed to continue compensation: %w", err)
	}

	r.metrics.recoveryTotal.WithLabelValues("compensation_continue", "success").Inc()
	r.incrementCompensatedSagas()

	r.logger.Info("saga compensation continued",
		zap.String("execution_id", state.ExecutionID),
		zap.String("final_status", string(result.Status)),
	)

	return nil
}

// RecoverSaga implements RecoveryManager.RecoverSaga.
func (r *recoveryManager) RecoverSaga(ctx context.Context, executionID string) error {
	state, err := r.store.LoadState(ctx, executionID)
	if err != nil {
		return fmt.Errorf("failed to load saga state: %w", err)
	}

	if state.Status.IsFinal() {
		return fmt.Errorf("saga is in final state: %s", state.Status)
	}

	switch state.Status {
	case SagaStatusRunning:
		return r.recoverRunningSaga(ctx, state)
	case SagaStatusCompensating:
		return r.recoverCompensatingSaga(ctx, state)
	default:
		return fmt.Errorf("unexpected saga status for recovery: %s", state.Status)
	}
}

// CleanupOrphanedLocks implements RecoveryManager.CleanupOrphanedLocks.
func (r *recoveryManager) CleanupOrphanedLocks(ctx context.Context) (int, error) {
	if r.resourceManager == nil {
		return 0, nil
	}

	// Get all currently held locks
	locks, err := r.resourceManager.GetAllLocks(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to get all locks: %w", err)
	}

	cleaned := 0
	for _, lock := range locks {
		// Check if the owner (worker) is still alive
		alive, err := r.isWorkerAlive(ctx, lock.OwnerID)
		if err != nil {
			r.logger.Warn("failed to check worker status",
				zap.String("owner_id", lock.OwnerID),
				zap.Error(err),
			)
			continue
		}

		if !alive {
			r.logger.Info("releasing orphaned lock",
				zap.String("database_id", lock.DatabaseID),
				zap.String("owner_id", lock.OwnerID),
			)

			if err := r.resourceManager.ReleaseLock(ctx, lock.DatabaseID, lock.OwnerID); err != nil {
				r.logger.Warn("failed to release orphaned lock",
					zap.String("database_id", lock.DatabaseID),
					zap.Error(err),
				)
				continue
			}

			cleaned++
			r.metrics.orphanedLocksCleaned.Inc()
		}
	}

	r.mu.Lock()
	r.stats.OrphanedLocksCleaned += cleaned
	r.mu.Unlock()

	return cleaned, nil
}

// isWorkerAlive checks if a worker is still running by checking its heartbeat.
func (r *recoveryManager) isWorkerAlive(ctx context.Context, workerID string) (bool, error) {
	if r.redisClient == nil {
		// Without Redis client, assume worker is alive (conservative approach)
		return true, nil
	}

	key := workerHeartbeatKey(workerID)
	exists, err := r.redisClient.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("failed to check heartbeat: %w", err)
	}

	return exists > 0, nil
}

// RegisterWorkerHeartbeat implements RecoveryManager.RegisterWorkerHeartbeat.
func (r *recoveryManager) RegisterWorkerHeartbeat(ctx context.Context) error {
	if r.redisClient == nil || r.config.WorkerID == "" {
		return nil
	}

	key := workerHeartbeatKey(r.config.WorkerID)
	timestamp := time.Now().Unix()

	err := r.redisClient.Set(ctx, key, timestamp, r.config.WorkerHeartbeatTTL).Err()
	if err != nil {
		return fmt.Errorf("failed to set worker heartbeat: %w", err)
	}

	return nil
}

// GetRecoveryStats implements RecoveryManager.GetRecoveryStats.
func (r *recoveryManager) GetRecoveryStats() *RecoveryStats {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// Return a copy
	return &RecoveryStats{
		TotalScanned:         r.stats.TotalScanned,
		ResumedSagas:         r.stats.ResumedSagas,
		CompensatedSagas:     r.stats.CompensatedSagas,
		FailedRecoveries:     r.stats.FailedRecoveries,
		ManualReviewRequired: r.stats.ManualReviewRequired,
		OrphanedLocksCleaned: r.stats.OrphanedLocksCleaned,
		LastRecoveryTime:     r.stats.LastRecoveryTime,
	}
}

// Close implements RecoveryManager.Close.
func (r *recoveryManager) Close() error {
	return nil
}

// publishRecoveryEvent publishes a recovery event to Redis Streams.
func (r *recoveryManager) publishRecoveryEvent(ctx context.Context, eventType, executionID, sagaID, errorMsg string) {
	if r.publisher == nil {
		return
	}

	event := RecoveryEvent{
		Type:        eventType,
		ExecutionID: executionID,
		SagaID:      sagaID,
		WorkerID:    r.config.WorkerID,
		Strategy:    r.config.RecoveryStrategy.String(),
		Error:       errorMsg,
		Timestamp:   time.Now(),
	}

	err := r.publisher.Publish(ctx, r.config.EventChannel, eventType, event, executionID)
	if err != nil {
		r.logger.Warn("failed to publish recovery event",
			zap.String("event_type", eventType),
			zap.String("execution_id", executionID),
			zap.Error(err),
		)
	}
}

// Helper methods for stats updates
func (r *recoveryManager) incrementResumedSagas() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.stats.ResumedSagas++
}

func (r *recoveryManager) incrementCompensatedSagas() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.stats.CompensatedSagas++
}

func (r *recoveryManager) incrementFailedRecoveries() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.stats.FailedRecoveries++
}

func (r *recoveryManager) incrementManualReviewRequired() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.stats.ManualReviewRequired++
}

// Redis key helpers
func workerHeartbeatKey(workerID string) string {
	return fmt.Sprintf("worker:heartbeat:%s", workerID)
}

func workerSagasKey(workerID string) string {
	return fmt.Sprintf("worker:sagas:%s", workerID)
}

// Prometheus metrics for recovery
type recoveryMetrics struct {
	recoveryTotal        *prometheus.CounterVec
	orphanedLocksCleaned prometheus.Counter
	recoveryDuration     prometheus.Histogram
}

var (
	globalRecoveryMetrics     *recoveryMetrics
	globalRecoveryMetricsOnce sync.Once
)

func newRecoveryMetrics() *recoveryMetrics {
	globalRecoveryMetricsOnce.Do(func() {
		globalRecoveryMetrics = &recoveryMetrics{
			recoveryTotal: promauto.NewCounterVec(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "recovery_total",
					Help:      "Total number of saga recoveries attempted",
				},
				[]string{"strategy", "result"},
			),

			orphanedLocksCleaned: promauto.NewCounter(
				prometheus.CounterOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "orphaned_locks_cleaned_total",
					Help:      "Total number of orphaned locks cleaned up",
				},
			),

			recoveryDuration: promauto.NewHistogram(
				prometheus.HistogramOpts{
					Namespace: "cc1c",
					Subsystem: "saga",
					Name:      "recovery_duration_seconds",
					Help:      "Duration of saga recovery operations",
					Buckets:   []float64{0.1, 0.5, 1, 5, 10, 30, 60, 120},
				},
			),
		}
	})
	return globalRecoveryMetrics
}
