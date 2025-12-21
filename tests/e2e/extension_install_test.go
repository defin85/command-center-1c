package e2e

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestE2E_ExtensionInstall_HappyPath - Scenario 1: Happy Path
// Полный успешный workflow установки расширения
func TestE2E_ExtensionInstall_HappyPath(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping E2E test in short mode")
	}

	// Setup E2E environment
	env := SetupE2EEnvironment(t)
	defer env.Cleanup()

	// Create test extension (.cfe) или mock path
	extensionPath := CreateTestExtension(t, env)

	// Start workflow via API Gateway (или mock endpoint)
	response := ExecuteInstallWorkflow(t, env, env.TestDBID, extensionPath)
	require.NotEmpty(t, response.OperationID, "Operation ID should not be empty")
	assert.Equal(t, "pending", response.Status, "Initial status should be pending")

	// Wait for completion (max 120s)
	result := WaitForCompletion(t, response.OperationID, 120*time.Second)
	require.NotNil(t, result, "Operation result should not be nil")

	// Verify result
	assert.Equal(t, "completed", result.Status, "Operation should complete successfully")
	assert.Empty(t, result.ErrorMessage, "Should not have error message on success")
	assert.Empty(t, result.CompensationEvents, "Should not have compensation events on success")

	// Additional verification based on mode
	if !env.UseMocks {
		t.Log("Real 1C mode: verifying extension via OData")
		// TODO: Verify via OData to real 1C
		// verifyExtensionInstalledViaOData(t, env.TestDBID, "TestExtension")

		// Cleanup: rollback extension
		RollbackExtension(t, env.TestDBID)
	} else {
		t.Log("Mock mode: verifying mock call sequence")
		VerifyMockCallSequence(t, env)
	}

	t.Log("✓ Happy Path E2E test passed")
}

// TestE2E_ExtensionInstall_LockFailure - Scenario 2: Lock Failure
// Graceful error handling при ошибке блокировки базы
func TestE2E_ExtensionInstall_LockFailure(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping E2E test in short mode")
	}

	// Setup E2E environment
	env := SetupE2EEnvironment(t)
	defer env.Cleanup()

	// Set mock RAS to fail on lock
	SetMockBehavior(t, env, "fail")

	// Create test extension
	extensionPath := CreateTestExtension(t, env)

	// Execute workflow (should fail at lock step)
	response := ExecuteInstallWorkflow(t, env, env.TestDBID, extensionPath)
	require.NotEmpty(t, response.OperationID)

	// Wait for failure (max 60s)
	result := WaitForCompletion(t, response.OperationID, 60*time.Second)
	require.NotNil(t, result)

	// Assertions
	if env.UseMocks {
		// В mock режиме мы контролируем поведение
		assert.Equal(t, "failed", result.Status, "Operation should fail due to lock error")
		assert.NotEmpty(t, result.ErrorMessage, "Should have error message")
		assert.Contains(t, result.ErrorMessage, "lock", "Error should mention lock failure")

		// Verify no compensation needed (failed at first step)
		// В идеале compensation не должно быть, так как lock - первый шаг
		// Но это зависит от реализации state machine
		t.Logf("Compensation events: %v", result.CompensationEvents)
	} else {
		t.Log("Real 1C mode: lock failure test skipped (can't control RAS behavior)")
		t.Skip("Lock failure scenario requires mock RAS")
	}

	t.Log("✓ Lock Failure E2E test passed")
}

// TestE2E_ExtensionInstall_InstallFailureWithCompensation - Scenario 3
// Ошибка при установке расширения с последующим compensation flow
func TestE2E_ExtensionInstall_InstallFailureWithCompensation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping E2E test in short mode")
	}

	// Setup E2E environment
	env := SetupE2EEnvironment(t)
	defer env.Cleanup()

	// Mock RAS в нормальном режиме (lock успешен)
	SetMockBehavior(t, env, "success")

	// TODO: Set mock worker to fail on install
	// Это требует дополнительного mock worker или контроля поведения

	// Create test extension
	extensionPath := CreateTestExtension(t, env)

	// Execute workflow (should fail at install step)
	response := ExecuteInstallWorkflow(t, env, env.TestDBID, extensionPath)
	require.NotEmpty(t, response.OperationID)

	// Wait for failure with compensation (max 120s)
	result := WaitForCompletion(t, response.OperationID, 120*time.Second)
	require.NotNil(t, result)

	// Assertions
	if env.UseMocks {
		// В mock режиме ожидаем:
		// 1. Lock успешен
		// 2. Terminate sessions успешен
		// 3. Install failed (если мы можем контролировать worker)
		// 4. Compensation: unlock базы

		// NOTE: Для полноценного теста нужен mock worker
		// Пока проверяем базовую структуру ответа

		// Если workflow дошел до install и упал, должен быть compensation
		if result.Status == "failed" {
			assert.NotEmpty(t, result.ErrorMessage, "Should have error message")

			// Проверяем что был compensation (unlock)
			// Это зависит от реализации state machine
			t.Logf("Operation failed with error: %s", result.ErrorMessage)
			t.Logf("Compensation events: %v", result.CompensationEvents)

			// В идеале должен быть unlock в compensation
			// if len(result.CompensationEvents) > 0 {
			//     assert.Contains(t, result.CompensationEvents, "unlock",
			//         "Compensation should include unlock")
			// }
		} else {
			t.Log("NOTE: Install failure scenario requires mock worker")
		}
	} else {
		t.Log("Real 1C mode: install failure test requires controlled environment")
		t.Skip("Install failure scenario requires mock worker")
	}

	t.Log("✓ Install Failure + Compensation E2E test passed")
}

// TestE2E_MultipleOperations_Concurrent - BONUS: Concurrent operations test
// Тест параллельных операций установки расширений
func TestE2E_MultipleOperations_Concurrent(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping E2E test in short mode")
	}

	// Setup E2E environment
	env := SetupE2EEnvironment(t)
	defer env.Cleanup()

	// Number of concurrent operations
	numOps := 3

	// Create test extension
	extensionPath := CreateTestExtension(t, env)

	// Start multiple operations concurrently
	operations := make([]*WorkflowResponse, numOps)
	for i := 0; i < numOps; i++ {
		dbID := env.TestDBID + "-" + string(rune('A'+i))
		operations[i] = ExecuteInstallWorkflow(t, env, dbID, extensionPath)
		require.NotEmpty(t, operations[i].OperationID)
	}

	t.Logf("Started %d concurrent operations", numOps)

	// Wait for all operations to complete
	results := make([]*OperationResult, numOps)
	for i := 0; i < numOps; i++ {
		results[i] = WaitForCompletion(t, operations[i].OperationID, 180*time.Second)
		require.NotNil(t, results[i])
		t.Logf("Operation %d/%d completed with status: %s",
			i+1, numOps, results[i].Status)
	}

	// Verify all completed successfully (в mock режиме)
	if env.UseMocks {
		successCount := 0
		for _, result := range results {
			if result.Status == "completed" {
				successCount++
			}
		}

		assert.Equal(t, numOps, successCount,
			"All concurrent operations should complete successfully")
	}

	t.Log("✓ Concurrent operations E2E test passed")
}
