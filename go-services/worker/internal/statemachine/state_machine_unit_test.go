package statemachine

import (
	"context"
	"testing"
	"time"

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

	sm, err := NewStateMachine(
		ctx,
		"op-123",
		"db-456",
		"corr-789",
		publisher,
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
		state   InstallState
		isFinal bool
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

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
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

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
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

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
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

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
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

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
	require.NoError(t, err)

	err = sm.publishCommand(ctx, "test-channel", "test.event", map[string]string{})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to publish command")
}

func TestStateMachine_Close_Idempotent(t *testing.T) {
	ctx := context.Background()
	publisher := NewMockPublisher()

	sm, err := NewStateMachine(ctx, "op1", "db1", "corr1", publisher, nil, nil)
	require.NoError(t, err)

	// First close
	err = sm.Close()
	assert.NoError(t, err)

	// Second close (idempotent)
	err = sm.Close()
	assert.NoError(t, err)
}
