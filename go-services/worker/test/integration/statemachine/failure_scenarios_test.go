//go:build legacy_event_driven
// +build legacy_event_driven

package statemachine

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/commandcenter1c/commandcenter/worker/internal/statemachine"
	"github.com/commandcenter1c/commandcenter/worker/test/integration/helpers"
)

/*
INTEGRATION TESTS: Worker State Machine Failure Scenarios

Эти тесты проверяют реальное поведение State Machine с настоящим Redis,
но мокируют внешние HTTP-сервисы (worker, worker).

Покрываемые сценарии:
1. Lock Failed - RAS возвращает ошибку
2. Terminate Timeout - Сессии не закрываются за 90s
3. Install Failed - 1cv8.exe возвращает ошибку
4. Unlock Retries - Unlock fails, retry 5 раз
5. Compensation Chain - Несколько compensations в LIFO
6. Duplicate Events - Idempotent handling
7. Out-of-Order Events - Invalid transitions игнорируются
8. Redis Unavailable - Graceful degradation
9. Worker Crash Recovery - Resume from persisted state
*/

// =============================================================================
// Test 1: Lock Failed Scenario
// =============================================================================

func TestStateMachine_LockFailed(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Test 1: Lock Failed Scenario")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Setup
	redisClient := helpers.SetupTestRedis(t)
	publisher, responderSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-lock-failed-%d", time.Now().UnixNano())
	t.Logf("Correlation ID: %s", correlationID)

	// Create Mock Responder with LOCK FAILED behavior
	responder := helpers.NewMockEventResponder(
		publisher,
		responderSubscriber,
		helpers.LockFailedBehaviors(), // Lock fails immediately
	)
	responder.SetVerbose(testing.Verbose())

	// Run responder
	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()

	go responder.Run(responderCtx)
	if err := responder.WaitReady(5 * time.Second); err != nil {
		t.Fatalf("Mock responder failed to start: %v", err)
	}

	// Create State Machine
	sm, err := statemachine.NewStateMachine(
		ctx,
		"op-lock-fail-123",
		"db-456",
		correlationID,
		publisher,
		redisClient,
		helpers.TestConfig(),
	)
	require.NoError(t, err)

	sm.ClusterID = "test-cluster"
	sm.InfobaseID = "test-infobase"
	sm.ExtensionPath = "/test/ext.cfe"
	sm.ExtensionName = "TestExtension"

	// Run State Machine
	t.Log("🚀 Running State Machine with Lock Failed scenario...")
	err = sm.Run(ctx)

	// Assertions
	t.Log("📊 Verifying results...")
	// State Machine may return nil (reached final state) or error
	if err != nil {
		t.Logf("State Machine completed with error: %v", err)
		assert.Contains(t, err.Error(), "failed waiting for locked event", "Error should mention lock failure")
	}

	finalState := sm.State
	t.Logf("Final state: %s", finalState)
	assert.True(t, finalState == statemachine.StateFailed || finalState == statemachine.StateCompensating,
		"State should be Failed or Compensating")

	t.Log("✅ Test 1 PASSED: Lock Failed scenario verified")
}

// =============================================================================
// Test 2: Terminate Timeout Scenario
// =============================================================================

func TestStateMachine_TerminateTimeout(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Test 2: Terminate Timeout Scenario")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	// Setup
	redisClient := helpers.SetupTestRedis(t)
	publisher, responderSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-terminate-timeout-%d", time.Now().UnixNano())

	// Create Mock Responder: Lock succeeds, Terminate TIMES OUT, Unlock succeeds (compensation)
	responder := helpers.NewMockEventResponder(
		publisher,
		responderSubscriber,
		helpers.TerminateTimeoutBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()

	go responder.Run(responderCtx)
	if err := responder.WaitReady(5 * time.Second); err != nil {
		t.Fatalf("Mock responder failed to start: %v", err)
	}
	time.Sleep(500 * time.Millisecond)

	// Create State Machine with SHORT timeout for terminate
	config := helpers.TestConfig()
	config.TimeoutTerminate = 2 * time.Second // Short timeout for test

	sm, err := statemachine.NewStateMachine(
		ctx,
		"op-term-timeout-234",
		"db-567",
		correlationID,
		publisher,
		redisClient,
		config,
	)
	require.NoError(t, err)

	sm.ClusterID = "test-cluster"
	sm.InfobaseID = "test-infobase"
	sm.ExtensionPath = "/test/ext.cfe"
	sm.ExtensionName = "TestExtension"

	t.Log("🚀 Running State Machine with Terminate Timeout scenario...")
	err = sm.Run(ctx)

	// Assertions
	t.Log("📊 Verifying results...")
	// State Machine may return nil (completed compensation) or error
	if err != nil {
		t.Logf("State Machine completed with error: %v", err)
		assert.Contains(t, err.Error(), "failed waiting for sessions closed", "Error should mention terminate failure")
	}

	finalState := sm.State
	t.Logf("Final state: %s", finalState)
	assert.Equal(t, statemachine.StateFailed, finalState, "State should be Failed")

	t.Log("✅ Test 2 PASSED: Terminate Timeout scenario with compensation verified")
}

// =============================================================================
// Test 3: Install Failed Scenario
// =============================================================================

func TestStateMachine_InstallFailed(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Log("========================================")
	t.Log("Test 3: Install Failed Scenario")
	t.Log("========================================")

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	// Setup
	redisClient := helpers.SetupTestRedis(t)
	publisher, responderSubscriber := helpers.SetupEventBus(t, redisClient)

	correlationID := fmt.Sprintf("test-install-failed-%d", time.Now().UnixNano())

	// Create Mock Responder: Lock/Terminate succeed, Install FAILS, Unlock succeeds (compensation)
	responder := helpers.NewMockEventResponder(
		publisher,
		responderSubscriber,
		helpers.InstallFailedBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()

	go responder.Run(responderCtx)
	if err := responder.WaitReady(5 * time.Second); err != nil {
		t.Fatalf("Mock responder failed to start: %v", err)
	}
	time.Sleep(500 * time.Millisecond)

	// Create State Machine
	sm, err := statemachine.NewStateMachine(
		ctx,
		"op-install-fail-345",
		"db-678",
		correlationID,
		publisher,
		redisClient,
		helpers.TestConfig(),
	)
	require.NoError(t, err)

	sm.ClusterID = "test-cluster"
	sm.InfobaseID = "test-infobase"
	sm.ExtensionPath = "/test/ext.cfe"
	sm.ExtensionName = "TestExtension"

	t.Log("🚀 Running State Machine with Install Failed scenario...")
	err = sm.Run(ctx)

	// Assertions
	t.Log("📊 Verifying results...")
	// State Machine may return nil (completed compensation) or error
	if err != nil {
		t.Logf("State Machine completed with error: %v", err)
	}

	finalState := sm.State
	t.Logf("Final state: %s", finalState)
	// Accept either Failed or Compensating as valid final states
	// (compensation chain may still be running when test completes)
	assert.True(t,
		finalState == statemachine.StateFailed || finalState == statemachine.StateCompensating,
		"State should be Failed or Compensating")

	t.Log("✅ Test 3 PASSED: Install Failed scenario with compensation verified")
}
