package statemachine

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockPublisher implements EventPublisher for testing
type mockPublisher struct {
	publishedEvents []publishedEvent
}

type publishedEvent struct {
	channel       string
	eventType     string
	payload       interface{}
	correlationID string
}

func (m *mockPublisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	m.publishedEvents = append(m.publishedEvents, publishedEvent{
		channel:       channel,
		eventType:     eventType,
		payload:       payload,
		correlationID: correlationID,
	})
	return nil
}

func (m *mockPublisher) Close() error {
	return nil
}

func setupTestWatchdog(t *testing.T) (*Watchdog, *miniredis.Miniredis, *mockPublisher) {
	// Create miniredis
	mr, err := miniredis.Run()
	require.NoError(t, err)

	// Create Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})

	// Create mock publisher
	publisher := &mockPublisher{
		publishedEvents: make([]publishedEvent, 0),
	}

	// Create watchdog with short intervals for testing
	config := &WatchdogConfig{
		CheckInterval:    100 * time.Millisecond,
		StuckThreshold:   1 * time.Second,
		MaxRecoveryBatch: 5,
	}

	watchdog := NewWatchdog(redisClient, publisher, "http://localhost:8200", nil, config)

	return watchdog, mr, publisher
}

func TestDefaultWatchdogConfig(t *testing.T) {
	config := DefaultWatchdogConfig()

	assert.Equal(t, 5*time.Minute, config.CheckInterval)
	assert.Equal(t, 30*time.Minute, config.StuckThreshold)
	assert.Equal(t, 10, config.MaxRecoveryBatch)
}

func TestNewWatchdog(t *testing.T) {
	watchdog, mr, _ := setupTestWatchdog(t)
	defer mr.Close()

	assert.NotNil(t, watchdog)
	assert.NotNil(t, watchdog.redisClient)
	assert.NotNil(t, watchdog.config)
	assert.NotNil(t, watchdog.publisher)
	assert.NotNil(t, watchdog.smConfig)
}

func TestNewWatchdog_WithNilConfig(t *testing.T) {
	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	redisClient := redis.NewClient(&redis.Options{
		Addr: mr.Addr(),
	})
	publisher := &mockPublisher{}

	watchdog := NewWatchdog(redisClient, publisher, "http://localhost:8200", nil, nil)

	assert.NotNil(t, watchdog.config)
	assert.Equal(t, 5*time.Minute, watchdog.config.CheckInterval)
}

func TestIsStuck(t *testing.T) {
	watchdog, mr, _ := setupTestWatchdog(t)
	defer mr.Close()

	tests := []struct {
		name     string
		state    *stateData
		expected bool
	}{
		{
			name: "final state completed - not stuck",
			state: &stateData{
				State:        StateCompleted,
				LastActivity: time.Now().Add(-1 * time.Hour),
			},
			expected: false,
		},
		{
			name: "final state failed - not stuck",
			state: &stateData{
				State:        StateFailed,
				LastActivity: time.Now().Add(-1 * time.Hour),
			},
			expected: false,
		},
		{
			name: "recent activity - not stuck",
			state: &stateData{
				State:        StateJobsLocked,
				LastActivity: time.Now(),
			},
			expected: false,
		},
		{
			name: "old activity - stuck",
			state: &stateData{
				State:        StateJobsLocked,
				LastActivity: time.Now().Add(-5 * time.Second), // > 1 second threshold
			},
			expected: true,
		},
		{
			name: "init state with old activity - stuck",
			state: &stateData{
				State:        StateInit,
				LastActivity: time.Now().Add(-5 * time.Second),
			},
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := watchdog.isStuck(tt.state)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestBuildCompensationStackFromState(t *testing.T) {
	watchdog, mr, _ := setupTestWatchdog(t)
	defer mr.Close()

	tests := []struct {
		name          string
		state         InstallState
		expectedCount int
	}{
		{
			name:          "init state - no compensations",
			state:         StateInit,
			expectedCount: 0,
		},
		{
			name:          "jobs locked - needs unlock",
			state:         StateJobsLocked,
			expectedCount: 1,
		},
		{
			name:          "sessions closed - needs unlock",
			state:         StateSessionsClosed,
			expectedCount: 1,
		},
		{
			name:          "extension installed - needs unlock",
			state:         StateExtensionInstalled,
			expectedCount: 1,
		},
		{
			name:          "compensating - needs unlock",
			state:         StateCompensating,
			expectedCount: 1,
		},
		{
			name:          "completed - no compensations needed (but handled by isStuck)",
			state:         StateCompleted,
			expectedCount: 0,
		},
		{
			name:          "failed - no compensations needed (but handled by isStuck)",
			state:         StateFailed,
			expectedCount: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			state := &stateData{
				State:         tt.state,
				ClusterID:     "cluster-1",
				InfobaseID:    "infobase-1",
				CorrelationID: "corr-123",
			}

			compensations := watchdog.buildCompensationStackFromState(state)
			assert.Len(t, compensations, tt.expectedCount)

			if tt.expectedCount > 0 {
				assert.Equal(t, "unlock_infobase", compensations[0].Name)
			}
		})
	}
}

func TestRecoverWorkflow(t *testing.T) {
	watchdog, mr, publisher := setupTestWatchdog(t)
	defer mr.Close()

	ctx := context.Background()

	// Create stuck workflow state in Redis
	state := &stateData{
		State:         StateJobsLocked,
		OperationID:   "op-123",
		DatabaseID:    "db-456",
		CorrelationID: "corr-789",
		ClusterID:     "cluster-1",
		InfobaseID:    "infobase-1",
		LastActivity:  time.Now().Add(-1 * time.Hour),
	}

	key := "workflow:corr-789:state"
	stateBytes, err := json.Marshal(state)
	require.NoError(t, err)

	mr.Set(key, string(stateBytes))

	// Recover workflow
	err = watchdog.recoverWorkflow(ctx, state, key)
	require.NoError(t, err)

	// Verify Redis key was deleted
	exists := mr.Exists(key)
	assert.False(t, exists)

	// Verify events were published
	assert.Len(t, publisher.publishedEvents, 2) // unlock command + recovery event

	// Check unlock command
	unlockEvent := publisher.publishedEvents[0]
	assert.Equal(t, "commands:cluster-service:infobase:unlock", unlockEvent.channel)
	assert.Equal(t, "cluster.infobase.unlock", unlockEvent.eventType)
	assert.Equal(t, "corr-789", unlockEvent.correlationID)

	// Check recovery event
	recoveryEvent := publisher.publishedEvents[1]
	assert.Equal(t, "events:orchestrator:workflow:recovered", recoveryEvent.channel)
	assert.Equal(t, "orchestrator.workflow.recovered", recoveryEvent.eventType)
	assert.Equal(t, "corr-789", recoveryEvent.correlationID)

	payload := recoveryEvent.payload.(map[string]interface{})
	assert.Equal(t, "op-123", payload["operation_id"])
	assert.Equal(t, "db-456", payload["database_id"])
	assert.Equal(t, "jobs_locked", payload["recovered_from_state"])
	assert.True(t, payload["all_succeeded"].(bool))
}

func TestCheckStuckWorkflows(t *testing.T) {
	watchdog, mr, publisher := setupTestWatchdog(t)
	defer mr.Close()

	ctx := context.Background()

	// Create multiple workflows - some stuck, some not
	stuckState := &stateData{
		State:         StateJobsLocked,
		OperationID:   "op-stuck",
		DatabaseID:    "db-stuck",
		CorrelationID: "corr-stuck",
		ClusterID:     "cluster-1",
		InfobaseID:    "infobase-1",
		LastActivity:  time.Now().Add(-1 * time.Hour), // definitely stuck
	}

	activeState := &stateData{
		State:         StateSessionsClosed,
		OperationID:   "op-active",
		DatabaseID:    "db-active",
		CorrelationID: "corr-active",
		ClusterID:     "cluster-2",
		InfobaseID:    "infobase-2",
		LastActivity:  time.Now(), // just now - not stuck
	}

	completedState := &stateData{
		State:         StateCompleted,
		OperationID:   "op-completed",
		DatabaseID:    "db-completed",
		CorrelationID: "corr-completed",
		ClusterID:     "cluster-3",
		InfobaseID:    "infobase-3",
		LastActivity:  time.Now().Add(-1 * time.Hour), // old but final - not stuck
	}

	// Store states in Redis
	stuckBytes, _ := json.Marshal(stuckState)
	activeBytes, _ := json.Marshal(activeState)
	completedBytes, _ := json.Marshal(completedState)

	mr.Set("workflow:corr-stuck:state", string(stuckBytes))
	mr.Set("workflow:corr-active:state", string(activeBytes))
	mr.Set("workflow:corr-completed:state", string(completedBytes))

	// Run check
	watchdog.checkStuckWorkflows(ctx)

	// Verify only stuck workflow was recovered
	assert.False(t, mr.Exists("workflow:corr-stuck:state"))
	assert.True(t, mr.Exists("workflow:corr-active:state"))
	assert.True(t, mr.Exists("workflow:corr-completed:state"))

	// Verify events for stuck workflow
	assert.Len(t, publisher.publishedEvents, 2) // unlock + recovery for one workflow
}

func TestCheckStuckWorkflows_MaxBatch(t *testing.T) {
	watchdog, mr, publisher := setupTestWatchdog(t)
	defer mr.Close()

	// Set max batch to 2
	watchdog.config.MaxRecoveryBatch = 2

	ctx := context.Background()

	// Create 5 stuck workflows
	for i := 0; i < 5; i++ {
		state := &stateData{
			State:         StateJobsLocked,
			OperationID:   "op-" + string(rune('A'+i)),
			DatabaseID:    "db-" + string(rune('A'+i)),
			CorrelationID: "corr-" + string(rune('A'+i)),
			ClusterID:     "cluster-1",
			InfobaseID:    "infobase-1",
			LastActivity:  time.Now().Add(-1 * time.Hour),
		}

		stateBytes, _ := json.Marshal(state)
		key := "workflow:corr-" + string(rune('A'+i)) + ":state"
		mr.Set(key, string(stateBytes))
	}

	// Run check
	watchdog.checkStuckWorkflows(ctx)

	// Verify only MaxRecoveryBatch workflows were recovered
	// Each recovery publishes 2 events (unlock + recovery)
	assert.Equal(t, 4, len(publisher.publishedEvents)) // 2 workflows * 2 events
}

func TestWatchdogRun_GracefulShutdown(t *testing.T) {
	watchdog, mr, _ := setupTestWatchdog(t)
	defer mr.Close()

	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan struct{})
	go func() {
		watchdog.Run(ctx)
		close(done)
	}()

	// Cancel context after short delay
	time.Sleep(50 * time.Millisecond)
	cancel()

	// Wait for shutdown with timeout
	select {
	case <-done:
		// Success - watchdog shut down gracefully
	case <-time.After(1 * time.Second):
		t.Fatal("Watchdog did not shut down gracefully")
	}
}
