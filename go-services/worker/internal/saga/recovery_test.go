package saga

import (
	"context"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// mockOrchestrator implements SagaOrchestrator for testing.
type mockOrchestrator struct {
	resumeFunc func(ctx context.Context, executionID string) (*SagaResult, error)
	cancelFunc func(ctx context.Context, executionID string) error
	sagas      map[string]*SagaDefinition
}

func newMockOrchestrator() *mockOrchestrator {
	return &mockOrchestrator{
		sagas: make(map[string]*SagaDefinition),
	}
}

func (m *mockOrchestrator) RegisterSaga(def *SagaDefinition) error {
	m.sagas[def.ID] = def
	return nil
}

func (m *mockOrchestrator) GetSaga(sagaID string) (*SagaDefinition, error) {
	saga, ok := m.sagas[sagaID]
	if !ok {
		return nil, ErrSagaNotFound
	}
	return saga, nil
}

func (m *mockOrchestrator) Execute(ctx context.Context, sagaID string, input map[string]interface{}) (*SagaResult, error) {
	return nil, nil
}

func (m *mockOrchestrator) ExecuteWithCorrelation(ctx context.Context, sagaID string, input map[string]interface{}, correlationID string) (*SagaResult, error) {
	return nil, nil
}

func (m *mockOrchestrator) Resume(ctx context.Context, executionID string) (*SagaResult, error) {
	if m.resumeFunc != nil {
		return m.resumeFunc(ctx, executionID)
	}
	return &SagaResult{
		ExecutionID: executionID,
		Status:      SagaStatusCompleted,
	}, nil
}

func (m *mockOrchestrator) GetStatus(ctx context.Context, executionID string) (*SagaState, error) {
	return nil, nil
}

func (m *mockOrchestrator) Cancel(ctx context.Context, executionID string) error {
	if m.cancelFunc != nil {
		return m.cancelFunc(ctx, executionID)
	}
	return nil
}

func (m *mockOrchestrator) Close() error {
	return nil
}

func TestNewRecoveryManager(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	t.Run("with default config", func(t *testing.T) {
		rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, nil)
		require.NotNil(t, rm)

		stats := rm.GetRecoveryStats()
		assert.NotNil(t, stats)
		assert.Zero(t, stats.TotalScanned)
	})

	t.Run("with custom config", func(t *testing.T) {
		config := &RecoveryConfig{
			WorkerID:           "test-worker-1",
			RecoverOnStart:     true,
			MaxRecoveryTime:    1 * time.Minute,
			StaleSagaThreshold: 2 * time.Minute,
			RecoveryStrategy:   StrategyCompensate,
		}

		rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)
		require.NotNil(t, rm)
	})
}

func TestRecoveryStrategy_String(t *testing.T) {
	tests := []struct {
		strategy RecoveryStrategy
		expected string
	}{
		{StrategyResume, "resume"},
		{StrategyCompensate, "compensate"},
		{StrategyManual, "manual"},
		{RecoveryStrategy(99), "unknown"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			assert.Equal(t, tt.expected, tt.strategy.String())
		})
	}
}

func TestRecoveryManager_Start_NoSagas(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 1 * time.Millisecond,
		RecoveryStrategy:   StrategyResume,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	ctx := context.Background()
	err := rm.Start(ctx)
	require.NoError(t, err)

	stats := rm.GetRecoveryStats()
	assert.Zero(t, stats.TotalScanned)
	assert.Zero(t, stats.ResumedSagas)
	assert.Zero(t, stats.CompensatedSagas)
}

func TestRecoveryManager_Start_RecoverOnStartDisabled(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	config := &RecoveryConfig{
		WorkerID:       "test-worker",
		RecoverOnStart: false, // Disabled
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	ctx := context.Background()
	err := rm.Start(ctx)
	require.NoError(t, err)

	stats := rm.GetRecoveryStats()
	assert.Zero(t, stats.TotalScanned)
}

func TestRecoveryManager_Start_WithRunningSagas(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a stale running saga
	staleSaga := NewSagaState("exec-1", "test-saga", "corr-1")
	staleSaga.Status = SagaStatusRunning
	staleSaga.UpdatedAt = time.Now().Add(-10 * time.Minute) // 10 minutes old
	require.NoError(t, store.SaveState(ctx, staleSaga))

	// Create a fresh running saga (should be skipped)
	freshSaga := NewSagaState("exec-2", "test-saga", "corr-2")
	freshSaga.Status = SagaStatusRunning
	freshSaga.UpdatedAt = time.Now() // Just now
	require.NoError(t, store.SaveState(ctx, freshSaga))

	resumeCalled := false
	orchestrator.resumeFunc = func(ctx context.Context, executionID string) (*SagaResult, error) {
		if executionID == "exec-1" {
			resumeCalled = true
		}
		return &SagaResult{
			ExecutionID: executionID,
			Status:      SagaStatusCompleted,
		}, nil
	}

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 5 * time.Minute, // Sagas older than 5 minutes are stale
		RecoveryStrategy:   StrategyResume,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	require.NoError(t, err)

	assert.True(t, resumeCalled, "expected Resume to be called for stale saga")

	stats := rm.GetRecoveryStats()
	assert.Equal(t, 2, stats.TotalScanned)
	assert.Equal(t, 1, stats.ResumedSagas)
}

func TestRecoveryManager_Start_WithCompensatingSagas(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a compensating saga
	compSaga := NewSagaState("exec-comp-1", "test-saga", "corr-1")
	compSaga.Status = SagaStatusCompensating
	compSaga.CompensationStack = []string{"step-1", "step-2"}
	compSaga.UpdatedAt = time.Now().Add(-2 * time.Minute)
	require.NoError(t, store.SaveState(ctx, compSaga))

	resumeCalled := false
	orchestrator.resumeFunc = func(ctx context.Context, executionID string) (*SagaResult, error) {
		resumeCalled = true
		return &SagaResult{
			ExecutionID: executionID,
			Status:      SagaStatusCompensated,
		}, nil
	}

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 1 * time.Minute,
		RecoveryStrategy:   StrategyResume,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	require.NoError(t, err)

	assert.True(t, resumeCalled, "expected Resume to be called for compensating saga")

	stats := rm.GetRecoveryStats()
	assert.Equal(t, 1, stats.TotalScanned)
	assert.Equal(t, 1, stats.CompensatedSagas)
}

func TestRecoveryManager_Start_StrategyCompensate(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a stale running saga
	staleSaga := NewSagaState("exec-1", "test-saga", "corr-1")
	staleSaga.Status = SagaStatusRunning
	staleSaga.UpdatedAt = time.Now().Add(-10 * time.Minute)
	require.NoError(t, store.SaveState(ctx, staleSaga))

	cancelCalled := false
	orchestrator.cancelFunc = func(ctx context.Context, executionID string) error {
		cancelCalled = true
		return nil
	}

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 1 * time.Minute,
		RecoveryStrategy:   StrategyCompensate, // Compensate strategy
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	require.NoError(t, err)

	assert.True(t, cancelCalled, "expected Cancel to be called for compensate strategy")

	stats := rm.GetRecoveryStats()
	assert.Equal(t, 1, stats.CompensatedSagas)
}

func TestRecoveryManager_Start_StrategyManual(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a stale running saga
	staleSaga := NewSagaState("exec-1", "test-saga", "corr-1")
	staleSaga.Status = SagaStatusRunning
	staleSaga.UpdatedAt = time.Now().Add(-10 * time.Minute)
	require.NoError(t, store.SaveState(ctx, staleSaga))

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 1 * time.Minute,
		RecoveryStrategy:   StrategyManual, // Manual strategy
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	require.NoError(t, err)

	stats := rm.GetRecoveryStats()
	assert.Equal(t, 1, stats.ManualReviewRequired)
	assert.Zero(t, stats.ResumedSagas)
	assert.Zero(t, stats.CompensatedSagas)
}

func TestRecoveryManager_RecoverSaga(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a running saga
	saga := NewSagaState("exec-1", "test-saga", "corr-1")
	saga.Status = SagaStatusRunning
	saga.UpdatedAt = time.Now().Add(-10 * time.Minute)
	require.NoError(t, store.SaveState(ctx, saga))

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		StaleSagaThreshold: 1 * time.Millisecond, // Very short for testing
		RecoveryStrategy:   StrategyResume,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.RecoverSaga(ctx, "exec-1")
	require.NoError(t, err)
}

func TestRecoveryManager_RecoverSaga_NotFound(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, nil)

	err := rm.RecoverSaga(ctx, "non-existent")
	require.Error(t, err)
}

func TestRecoveryManager_RecoverSaga_FinalState(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a completed saga
	saga := NewSagaState("exec-1", "test-saga", "corr-1")
	saga.SetCompleted()
	require.NoError(t, store.SaveState(ctx, saga))

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, nil)

	err := rm.RecoverSaga(ctx, "exec-1")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "final state")
}

func TestRecoveryManager_RegisterWorkerHeartbeat(t *testing.T) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	redisClient := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	defer redisClient.Close()

	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	config := &RecoveryConfig{
		WorkerID:           "test-worker-123",
		WorkerHeartbeatTTL: 30 * time.Second,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, redisClient, logger, config)

	ctx := context.Background()
	err = rm.RegisterWorkerHeartbeat(ctx)
	require.NoError(t, err)

	// Verify heartbeat was set in Redis
	key := workerHeartbeatKey("test-worker-123")
	exists := mr.Exists(key)
	assert.True(t, exists)
}

func TestRecoveryManager_GetRecoveryStats(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, nil)

	stats := rm.GetRecoveryStats()
	require.NotNil(t, stats)

	// Verify it returns a copy
	stats.TotalScanned = 100
	newStats := rm.GetRecoveryStats()
	assert.Zero(t, newStats.TotalScanned)
}

func TestRecoveryManager_Close(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, nil)

	err := rm.Close()
	require.NoError(t, err)
}

func TestWorkerHeartbeatKey(t *testing.T) {
	key := workerHeartbeatKey("worker-1")
	assert.Equal(t, "worker:heartbeat:worker-1", key)
}

func TestWorkerSagasKey(t *testing.T) {
	key := workerSagasKey("worker-1")
	assert.Equal(t, "worker:sagas:worker-1", key)
}

func TestDefaultRecoveryConfig(t *testing.T) {
	config := DefaultRecoveryConfig()

	assert.True(t, config.RecoverOnStart)
	assert.Equal(t, 2*time.Minute, config.MaxRecoveryTime)
	assert.Equal(t, 5*time.Minute, config.StaleSagaThreshold)
	assert.Equal(t, StrategyResume, config.RecoveryStrategy)
	assert.Equal(t, "events:saga:recovery", config.EventChannel)
	assert.Equal(t, 30*time.Second, config.WorkerHeartbeatTTL)
}

func TestRecoveryManager_Start_Timeout(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create many stale sagas
	for i := 0; i < 100; i++ {
		saga := NewSagaState("exec-"+string(rune('0'+i)), "test-saga", "corr-1")
		saga.Status = SagaStatusRunning
		saga.UpdatedAt = time.Now().Add(-10 * time.Minute)
		require.NoError(t, store.SaveState(ctx, saga))
	}

	// Mock slow Resume
	orchestrator.resumeFunc = func(ctx context.Context, executionID string) (*SagaResult, error) {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(100 * time.Millisecond):
			return &SagaResult{
				ExecutionID: executionID,
				Status:      SagaStatusCompleted,
			}, nil
		}
	}

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    50 * time.Millisecond, // Very short timeout
		StaleSagaThreshold: 1 * time.Minute,
		RecoveryStrategy:   StrategyResume,
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	// Should timeout but not return error (context deadline exceeded)
	assert.Error(t, err)
}

func TestRecoveryManager_ResumeFallbackToCompensate(t *testing.T) {
	store := NewInMemorySagaStore()
	orchestrator := newMockOrchestrator()
	logger := zap.NewNop()
	ctx := context.Background()

	// Create a stale running saga
	saga := NewSagaState("exec-1", "test-saga", "corr-1")
	saga.Status = SagaStatusRunning
	saga.UpdatedAt = time.Now().Add(-10 * time.Minute)
	require.NoError(t, store.SaveState(ctx, saga))

	// Mock Resume to fail
	resumeCalled := false
	cancelCalled := false

	orchestrator.resumeFunc = func(ctx context.Context, executionID string) (*SagaResult, error) {
		resumeCalled = true
		return nil, ErrExecutionAlreadyRunning
	}

	orchestrator.cancelFunc = func(ctx context.Context, executionID string) error {
		cancelCalled = true
		return nil
	}

	config := &RecoveryConfig{
		WorkerID:           "test-worker",
		RecoverOnStart:     true,
		MaxRecoveryTime:    10 * time.Second,
		StaleSagaThreshold: 1 * time.Minute,
		RecoveryStrategy:   StrategyResume, // Should fallback to compensate
	}

	rm := NewRecoveryManager(store, orchestrator, nil, nil, nil, logger, config)

	err := rm.Start(ctx)
	require.NoError(t, err)

	assert.True(t, resumeCalled, "Resume should be called first")
	assert.True(t, cancelCalled, "Cancel should be called as fallback")

	stats := rm.GetRecoveryStats()
	assert.Equal(t, 1, stats.CompensatedSagas)
}
