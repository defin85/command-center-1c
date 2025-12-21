package performance

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestPerformance_100ParallelOperations - Load test: 100 параллельных операций
// Проверяет throughput, latency и success rate при высокой нагрузке
func TestPerformance_100ParallelOperations(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping performance test in short mode")
	}

	t.Log("========================================")
	t.Log("   100 PARALLEL OPERATIONS LOAD TEST")
	t.Log("========================================")

	// Setup
	env := SetupPerfEnvironment(t)
	defer env.Cleanup()

	// Start mock responder (симулирует worker responses)
	stopResponder := startMockResponder(t, env)
	defer stopResponder()

	// Metrics collectors
	var (
		totalOps   int32
		successOps int32
		failedOps  int32
	)

	// Latency collector
	latencies := make([]time.Duration, 0, 100)
	var latenciesMu sync.Mutex

	// Execute 100 parallel operations
	var wg sync.WaitGroup
	start := time.Now()

	t.Log("Starting 100 parallel operations...")

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(opID int) {
			defer wg.Done()

			opStart := time.Now()
			err := executeTestOperation(t, env, opID)
			duration := time.Since(opStart)

			// Record latency
			latenciesMu.Lock()
			latencies = append(latencies, duration)
			latenciesMu.Unlock()

			atomic.AddInt32(&totalOps, 1)

			if err != nil {
				atomic.AddInt32(&failedOps, 1)
				t.Logf("Operation %d failed: %v", opID, err)
			} else {
				atomic.AddInt32(&successOps, 1)
			}

			// Progress indicator
			if (opID+1)%10 == 0 {
				t.Logf("Progress: %d/100 operations completed", opID+1)
			}
		}(i)
	}

	wg.Wait()
	totalDuration := time.Since(start)

	t.Logf("✓ All operations completed in %v", totalDuration)

	// Generate report
	report := &PerformanceReport{
		TestName:        "100_Parallel_Operations",
		Timestamp:       time.Now(),
		TotalOperations: int(totalOps),
		SuccessCount:    int(successOps),
		FailureCount:    int(failedOps),
		TotalDuration:   totalDuration,
		OpsPerSecond:    float64(totalOps) / totalDuration.Seconds(),
		SuccessRate:     float64(successOps) / float64(totalOps),
		Latencies:       latencies,
	}

	// Calculate percentiles
	report.LatencyMin = calculateMin(latencies)
	report.LatencyMean = calculateMean(latencies)
	report.LatencyP50 = calculatePercentile(latencies, 0.5)
	report.LatencyP95 = calculatePercentile(latencies, 0.95)
	report.LatencyP99 = calculatePercentile(latencies, 0.99)
	report.LatencyMax = calculateMax(latencies)

	// Save reports
	saveJSON(t, report, "performance_report_100ops.json")
	err := GenerateMarkdownReport(report, "performance_report_100ops.md")
	require.NoError(t, err, "Should generate markdown report")

	// Print summary
	printSummary(t, report)

	// Assertions
	assert.LessOrEqual(t, totalDuration, 60*time.Second, "Should complete in <= 60s")
	assert.GreaterOrEqual(t, report.SuccessRate, 0.95, "Success rate should be >= 95%")
	assert.Less(t, report.LatencyP99, 10.0, "P99 latency should be < 10 seconds")
	assert.Greater(t, report.OpsPerSecond, 10.0, "Throughput should be > 10 ops/sec")

	t.Log("✓ 100 Parallel Operations test PASSED")
}

// executeTestOperation - выполнить одну тестовую операцию (event-driven workflow)
func executeTestOperation(t *testing.T, env *PerfEnvironment, opID int) error {
	t.Helper()

	correlationID := fmt.Sprintf("perf-test-%d-%s", opID, uuid.New().String())

	// Step 1: Publish lock command
	lockEvent := NewCommandEvent(correlationID, "commands:worker:infobase:lock", map[string]interface{}{
		"cluster_id":  "test-cluster-001",
		"infobase_id": fmt.Sprintf("test-db-%03d", opID%10), // 10 unique databases
		"mode":        "exclusive",
		"timeout":     60,
	})

	payload, _ := lockEvent.ToJSON()
	err := env.RedisClient.Publish(env.Ctx, "commands:worker:infobase:lock", payload).Err()
	if err != nil {
		return fmt.Errorf("failed to publish lock command: %w", err)
	}

	// Wait for lock response (mock responder will send it)
	lockResponse, err := waitForResponse(env, correlationID, "lock", 5*time.Second)
	if err != nil {
		return fmt.Errorf("lock response timeout: %w", err)
	}
	if lockResponse.Payload["status"] != "success" {
		return fmt.Errorf("lock failed: %v", lockResponse.Payload["error"])
	}

	// Step 2: Publish terminate sessions command
	terminateEvent := NewCommandEvent(correlationID, "commands:worker:sessions:terminate", map[string]interface{}{
		"cluster_id":  "test-cluster-001",
		"infobase_id": fmt.Sprintf("test-db-%03d", opID%10),
		"timeout":     30,
	})

	payload, _ = terminateEvent.ToJSON()
	err = env.RedisClient.Publish(env.Ctx, "commands:worker:sessions:terminate", payload).Err()
	if err != nil {
		return fmt.Errorf("failed to publish terminate command: %w", err)
	}

	// Wait for terminate response
	terminateResponse, err := waitForResponse(env, correlationID, "terminate", 5*time.Second)
	if err != nil {
		return fmt.Errorf("terminate response timeout: %w", err)
	}
	if terminateResponse.Payload["status"] != "success" {
		return fmt.Errorf("terminate failed: %v", terminateResponse.Payload["error"])
	}

	// Step 3: Publish install extension command (mock worker)
	installEvent := NewCommandEvent(correlationID, "commands:worker:extension:install", map[string]interface{}{
		"database_id":    fmt.Sprintf("test-db-%03d", opID%10),
		"extension_path": "/tmp/test-extension.cfe",
		"extension_name": "TestExtension",
	})

	payload, _ = installEvent.ToJSON()
	err = env.RedisClient.Publish(env.Ctx, "commands:worker:extension:install", payload).Err()
	if err != nil {
		return fmt.Errorf("failed to publish install command: %w", err)
	}

	// Wait for install response
	installResponse, err := waitForResponse(env, correlationID, "install", 5*time.Second)
	if err != nil {
		return fmt.Errorf("install response timeout: %w", err)
	}
	if installResponse.Payload["status"] != "success" {
		return fmt.Errorf("install failed: %v", installResponse.Payload["error"])
	}

	// Step 4: Publish unlock command
	unlockEvent := NewCommandEvent(correlationID, "commands:worker:infobase:unlock", map[string]interface{}{
		"cluster_id":  "test-cluster-001",
		"infobase_id": fmt.Sprintf("test-db-%03d", opID%10),
	})

	payload, _ = unlockEvent.ToJSON()
	err = env.RedisClient.Publish(env.Ctx, "commands:worker:infobase:unlock", payload).Err()
	if err != nil {
		return fmt.Errorf("failed to publish unlock command: %w", err)
	}

	// Wait for unlock response
	unlockResponse, err := waitForResponse(env, correlationID, "unlock", 5*time.Second)
	if err != nil {
		return fmt.Errorf("unlock response timeout: %w", err)
	}
	if unlockResponse.Payload["status"] != "success" {
		return fmt.Errorf("unlock failed: %v", unlockResponse.Payload["error"])
	}

	// Success!
	return nil
}

// waitForResponse - ждать response event с определенным correlation_id
func waitForResponse(env *PerfEnvironment, correlationID, step string, timeout time.Duration) (*EventEnvelope, error) {
	ctx, cancel := context.WithTimeout(env.Ctx, timeout)
	defer cancel()

	// Subscribe to response channel
	responseChannel := fmt.Sprintf("responses:%s", correlationID)
	pubsub := env.RedisClient.Subscribe(ctx, responseChannel)
	defer pubsub.Close()

	select {
	case msg := <-pubsub.Channel():
		var envelope EventEnvelope
		err := json.Unmarshal([]byte(msg.Payload), &envelope)
		if err != nil {
			return nil, fmt.Errorf("failed to unmarshal response: %w", err)
		}
		return &envelope, nil

	case <-ctx.Done():
		return nil, fmt.Errorf("timeout waiting for %s response (correlation_id: %s)", step, correlationID)
	}
}

// startMockResponder - запустить mock responder который симулирует ответы сервисов
// В реальной системе это будут worker и worker
// FIXED: Issue #4 - Goroutine leak - use WaitGroup for proper cleanup
func startMockResponder(t *testing.T, env *PerfEnvironment) func() {
	t.Helper()

	ctx, cancel := context.WithCancel(env.Ctx)

	var wg sync.WaitGroup
	wg.Add(1)

	// Goroutine для обработки команд и отправки ответов
	go func() {
		defer wg.Done() // Guarantee completion tracking

		// Subscribe to all command channels
		pubsub := env.RedisClient.PSubscribe(ctx, "commands:*")
		defer pubsub.Close()

		t.Log("✓ Mock responder started")

		for {
			select {
			case msg := <-pubsub.Channel():
				if msg == nil {
					continue
				}

				// Parse command
				var command EventEnvelope
				err := json.Unmarshal([]byte(msg.Payload), &command)
				if err != nil {
					t.Logf("Warning: failed to parse command: %v", err)
					continue
				}

				// Simulate processing delay (10ms)
				time.Sleep(10 * time.Millisecond)

				// Send response
				response := NewResponseEvent(command.CorrelationID, "response", map[string]interface{}{
					"status":         "success",
					"command_type":   command.EventType,
					"correlation_id": command.CorrelationID,
					"timestamp":      time.Now().Format(time.RFC3339),
				})

				responsePayload, _ := response.ToJSON()
				responseChannel := fmt.Sprintf("responses:%s", command.CorrelationID)

				err = env.RedisClient.Publish(ctx, responseChannel, responsePayload).Err()
				if err != nil {
					t.Logf("Warning: failed to publish response: %v", err)
				}

			case <-ctx.Done():
				t.Log("✓ Mock responder stopped")
				return
			}
		}
	}()

	// Wait for responder to start
	time.Sleep(100 * time.Millisecond)

	// Return stop function with proper wait
	return func() {
		cancel()
		wg.Wait() // Wait for goroutine to exit
		t.Log("✓ Mock responder cleanup complete")
	}
}
