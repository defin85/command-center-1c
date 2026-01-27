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

func TestStateMachine_HappyPath(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	// Create test context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Setup Redis
	redisClient := helpers.SetupTestRedis(t)

	// Setup Event Bus
	publisher, responderSubscriber := helpers.SetupEventBus(t, redisClient)

	// Generate unique correlation ID for this test
	correlationID := fmt.Sprintf("test-happy-%d", time.Now().UnixNano())

	t.Logf("Starting Happy Path test (correlation_id=%s)", correlationID)

	// Create and start Mock Responder
	responder := helpers.NewMockEventResponder(
		publisher,
		responderSubscriber,
		helpers.HappyPathBehaviors(),
	)
	responder.SetVerbose(testing.Verbose())

	// Run responder in background
	responderCtx, responderCancel := context.WithCancel(ctx)
	defer responderCancel()

	responderDone := make(chan error, 1)
	go func() {
		responderDone <- responder.Run(responderCtx)
	}()

	// Give responder time to start and subscribe
	time.Sleep(500 * time.Millisecond)

	// Create State Machine (with its OWN subscriber)
	sm, err := statemachine.NewStateMachine(
		ctx,
		"op-123",
		"db-456",
		correlationID,
		publisher,
		redisClient,
		helpers.TestConfig(),
	)
	require.NoError(t, err, "Failed to create State Machine")

	// Set workflow data (required for commands)
	sm.ClusterID = "cluster-001"
	sm.InfobaseID = "ib-001"
	sm.ExtensionPath = "/test/extension.cfe"
	sm.ExtensionName = "TestExtension"

	// Run State Machine
	t.Log("Starting State Machine execution...")
	startTime := time.Now()

	err = sm.Run(ctx)
	duration := time.Since(startTime)

	// Assert no errors
	require.NoError(t, err, "State Machine should complete successfully")

	// Assert final state
	assert.Equal(t, statemachine.StateCompleted, sm.State, "State should be Completed")

	// Note: We can't check compensation stack directly as it's private
	// But we can verify the state is Completed (which implies no compensations were triggered)

	t.Logf("✅ Happy path completed successfully in %v", duration)
	t.Logf("Final state: %s", sm.State)

	// Stop responder
	responderCancel()
	select {
	case <-responderDone:
	case <-time.After(2 * time.Second):
		t.Log("Warning: Responder did not stop gracefully")
	}
}
