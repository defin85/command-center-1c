package statemachine

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Простой mock для Redis (для тестов которым нужен Redis client, но без реального соединения)
type mockRedisClient struct {
	data map[string]string
}

func newMockRedisClient() *redis.Client {
	// Для unit тестов можем использовать nil - методы работают без реального Redis
	return nil
}

func TestStateMachine_Creation(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(
		ctx,
		"op-123",
		"db-456",
		"corr-789",
		publisher,
		subscriber,
		newMockRedisClient(),
		nil, // Use default config
	)

	require.NoError(t, err)
	assert.NotNil(t, sm)
	assert.Equal(t, StateInit, sm.State)
	assert.Equal(t, "op-123", sm.OperationID)
	assert.Equal(t, "db-456", sm.DatabaseID)
	assert.Equal(t, "corr-789", sm.CorrelationID)
}

func TestStateMachine_StateTransitions_Valid(t *testing.T) {
	tests := []struct {
		name string
		from InstallState
		to   InstallState
		want bool
	}{
		{"init to jobs_locked", StateInit, StateJobsLocked, true},
		{"init to failed", StateInit, StateFailed, true},
		{"jobs_locked to sessions_closed", StateJobsLocked, StateSessionsClosed, true},
		{"jobs_locked to compensating", StateJobsLocked, StateCompensating, true},
		{"sessions_closed to extension_installed", StateSessionsClosed, StateExtensionInstalled, true},
		{"extension_installed to completed", StateExtensionInstalled, StateCompleted, true},
		{"compensating to failed", StateCompensating, StateFailed, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := CanTransition(tt.from, tt.to)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestStateMachine_StateTransitions_Invalid(t *testing.T) {
	tests := []struct {
		name string
		from InstallState
		to   InstallState
	}{
		{"completed to init", StateCompleted, StateInit},
		{"failed to completed", StateFailed, StateCompleted},
		{"init to completed", StateInit, StateCompleted},
		{"completed to jobs_locked", StateCompleted, StateJobsLocked},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := CanTransition(tt.from, tt.to)
			assert.False(t, got, "transition from %s to %s should be invalid", tt.from, tt.to)
		})
	}
}

func TestStateMachine_StateIsFinal(t *testing.T) {
	tests := []struct {
		state    InstallState
		isFinal  bool
	}{
		{StateInit, false},
		{StateJobsLocked, false},
		{StateSessionsClosed, false},
		{StateExtensionInstalled, false},
		{StateCompensating, false},
		{StateCompleted, true},
		{StateFailed, true},
	}

	for _, tt := range tests {
		t.Run(string(tt.state), func(t *testing.T) {
			got := tt.state.IsFinal()
			assert.Equal(t, tt.isFinal, got)
		})
	}
}

func TestStateMachine_TransitionTo(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	// Valid transition
	err = sm.transitionTo(StateJobsLocked)
	assert.NoError(t, err)
	assert.Equal(t, StateJobsLocked, sm.State)

	// Valid transition
	err = sm.transitionTo(StateSessionsClosed)
	assert.NoError(t, err)
	assert.Equal(t, StateSessionsClosed, sm.State)

	// Invalid transition
	err = sm.transitionTo(StateInit)
	assert.Error(t, err)
	assert.Equal(t, StateSessionsClosed, sm.State) // State unchanged
}

func TestStateMachine_CompensationStack(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	executed := []string{}

	// Push 3 compensations
	sm.pushCompensation("action1", func(ctx context.Context) error {
		executed = append(executed, "action1")
		return nil
	})
	sm.pushCompensation("action2", func(ctx context.Context) error {
		executed = append(executed, "action2")
		return nil
	})
	sm.pushCompensation("action3", func(ctx context.Context) error {
		executed = append(executed, "action3")
		return nil
	})

	assert.Equal(t, 3, len(sm.compensationStack))

	// Execute compensations (should be LIFO: action3, action2, action1)
	sm.State = StateCompensating
	err = sm.executeCompensations(ctx)

	assert.NoError(t, err)
	assert.Equal(t, StateFailed, sm.State)
	assert.Equal(t, []string{"action3", "action2", "action1"}, executed) // LIFO order!
}

func TestStateMachine_CompensationStack_WithError(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	executed := []string{}

	// Push 3 compensations, middle one fails
	sm.pushCompensation("action1", func(ctx context.Context) error {
		executed = append(executed, "action1")
		return nil
	})
	sm.pushCompensation("action2", func(ctx context.Context) error {
		executed = append(executed, "action2")
		return assert.AnError // This fails
	})
	sm.pushCompensation("action3", func(ctx context.Context) error {
		executed = append(executed, "action3")
		return nil
	})

	sm.State = StateCompensating
	err = sm.executeCompensations(ctx)

	assert.NoError(t, err) // executeCompensations не возвращает ошибку
	assert.Equal(t, StateFailed, sm.State)
	// Все compensations должны быть выполнены, даже если один failed
	assert.Equal(t, []string{"action3", "action2", "action1"}, executed)
}

func TestStateMachine_Config_Default(t *testing.T) {
	config := DefaultConfig()

	assert.NotNil(t, config)
	assert.Equal(t, 30*time.Second, config.TimeoutLockJobs)
	assert.Equal(t, 90*time.Second, config.TimeoutTerminate)
	assert.Equal(t, 5*time.Minute, config.TimeoutInstall)
	assert.Equal(t, 30*time.Second, config.TimeoutUnlock)
	assert.Equal(t, 2*time.Minute, config.TimeoutCompensation)
	assert.Equal(t, 3, config.MaxRetries)
	assert.Equal(t, 24*time.Hour, config.StateTTL)
	assert.Equal(t, 10*time.Minute, config.DeduplicationTTL)
}

func TestStateMachine_Config_Validate(t *testing.T) {
	tests := []struct {
		name      string
		config    *Config
		wantError bool
	}{
		{
			name:      "valid config",
			config:    DefaultConfig(),
			wantError: false,
		},
		{
			name: "invalid timeout lock",
			config: &Config{
				TimeoutLockJobs:  0,
				TimeoutTerminate: 90 * time.Second,
				TimeoutInstall:   5 * time.Minute,
			},
			wantError: true,
		},
		{
			name: "invalid timeout terminate",
			config: &Config{
				TimeoutLockJobs:  30 * time.Second,
				TimeoutTerminate: 0,
				TimeoutInstall:   5 * time.Minute,
			},
			wantError: true,
		},
		{
			name: "negative max retries",
			config: &Config{
				TimeoutLockJobs:  30 * time.Second,
				TimeoutTerminate: 90 * time.Second,
				TimeoutInstall:   5 * time.Minute,
				MaxRetries:       -1,
			},
			wantError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestStateMachine_PublishCommand(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	payload := map[string]string{"key": "value"}
	err = sm.publishCommand(ctx, "test-channel", "test.event", payload)

	assert.NoError(t, err)
	assert.Equal(t, 1, publisher.GetPublishedCount())

	lastCall := publisher.GetLastPublished()
	assert.Equal(t, "test-channel", lastCall.Channel)
	assert.Equal(t, "test.event", lastCall.EventType)
	assert.Equal(t, "corr1", lastCall.CorrelationID)
}

func TestStateMachine_PublishCommand_Error(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	publisher.PublishError = assert.AnError // Simulate publish error
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	err = sm.publishCommand(ctx, "test-channel", "test.event", map[string]string{})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish command")
}

func TestStateMachine_EventDeduplication(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	messageID := "msg-123"

	// First check - should not be processed
	assert.False(t, sm.isEventProcessed(messageID))

	// Mark as processed
	sm.markEventProcessed(messageID)

	// Second check - should be processed
	assert.True(t, sm.isEventProcessed(messageID))
}

func TestStateMachine_Close_Idempotent(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)

	// First close
	err = sm.Close()
	assert.NoError(t, err)
	assert.True(t, sm.closed)

	// Second close (idempotent)
	err = sm.Close()
	assert.NoError(t, err)
}

func TestStateMachine_CalculateBackoff(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	config := DefaultConfig()
	config.RetryInitialDelay = 1 * time.Second
	config.RetryMaxDelay = 30 * time.Second

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, config)
	require.NoError(t, err)

	// Test exponential backoff
	backoff1 := sm.calculateBackoff(1)
	backoff2 := sm.calculateBackoff(2)
	backoff3 := sm.calculateBackoff(3)

	// Should increase exponentially
	assert.Greater(t, backoff2, backoff1)
	assert.Greater(t, backoff3, backoff2)

	// Should not exceed max delay
	backoff10 := sm.calculateBackoff(10)
	assert.LessOrEqual(t, backoff10, config.RetryMaxDelay+config.RetryMaxDelay/10) // max + jitter
}

func TestStateMachine_EventBuffer(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)
	defer sm.Close()

	// Simulate receiving unexpected event
	unexpectedEnvelope := &events.Envelope{
		MessageID:     "msg-1",
		EventType:     "unexpected.event",
		CorrelationID: "corr1",
	}

	sm.mu.Lock()
	sm.eventBuffer = append(sm.eventBuffer, unexpectedEnvelope)
	sm.mu.Unlock()

	// Check that buffer is not empty
	assert.Equal(t, 1, len(sm.eventBuffer))

	// Now simulate waiting for this event
	expectedEnvelope := &events.Envelope{
		MessageID:     "msg-2",
		EventType:     "expected.event",
		CorrelationID: "corr1",
	}

	sm.mu.Lock()
	sm.eventBuffer = append(sm.eventBuffer, expectedEnvelope)
	sm.mu.Unlock()

	// Check buffer has both events
	assert.Equal(t, 2, len(sm.eventBuffer))

	// Clear buffer
	sm.clearEventBuffer()
	assert.Equal(t, 0, len(sm.eventBuffer))
}

func TestStateMachine_CircuitBreaker_ClusterService(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)
	defer sm.Close()

	// Simulate 5 failures to cluster-service
	publisher.PublishError = assert.AnError

	for i := 0; i < 5; i++ {
		err = sm.publishCommand(ctx, "commands:cluster-service:lock", "cluster.lock", map[string]string{})
		if err != nil {
			// Expected - circuit breaker should trip after 3 failures
		}
	}

	// Circuit breaker should be open now
	// Next call should fail immediately (without retry)
	start := time.Now()
	err = sm.publishCommand(ctx, "commands:cluster-service:lock", "cluster.lock", map[string]string{})
	elapsed := time.Since(start)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "circuit breaker is open")
	assert.Less(t, elapsed, 100*time.Millisecond) // Should be instantaneous
}

func TestStateMachine_CircuitBreaker_BatchService(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()
	subscriber := NewMockSubscriber()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, subscriber, nil, nil)
	require.NoError(t, err)
	defer sm.Close()

	// Circuit breaker for batch-service should be independent
	publisher.PublishError = assert.AnError

	err = sm.publishCommand(ctx, "commands:batch-service:install", "batch.install", map[string]string{})
	assert.Error(t, err)

	// cluster-service breaker should NOT be affected
	publisher.PublishError = nil // Reset error
	err = sm.publishCommand(ctx, "commands:cluster-service:lock", "cluster.lock", map[string]string{})
	assert.NoError(t, err)
}
