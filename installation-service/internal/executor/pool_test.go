package executor

import (
	"context"
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
)

// MockPublisher is a mock implementation of ProgressPublisher for testing
type MockPublisher struct{}

func (m *MockPublisher) PublishTaskStarted(ctx context.Context, task Task) error {
	return nil
}

func (m *MockPublisher) PublishTaskCompleted(ctx context.Context, result TaskResult) error {
	return nil
}

func (m *MockPublisher) PublishTaskFailed(ctx context.Context, result TaskResult) error {
	return nil
}

func TestNewPool(t *testing.T) {
	execCfg := &config.ExecutorConfig{
		MaxParallel:   5,
		RetryAttempts: 3,
		TaskTimeout:   600,
	}

	onecCfg := &config.OneCConfig{
		PlatformPath:   "C:\\Program Files\\1cv8\\bin\\1cv8.exe",
		TimeoutSeconds: 300,
		ServerName:     "server1c",
	}

	mockPub := &MockPublisher{}
	pool := NewPool(execCfg, onecCfg, mockPub)

	if pool == nil {
		t.Fatal("Expected pool to be created, got nil")
	}

	if pool.config.MaxParallel != 5 {
		t.Errorf("Expected MaxParallel = 5, got %d", pool.config.MaxParallel)
	}
}

func TestPool_StartStop(t *testing.T) {
	execCfg := &config.ExecutorConfig{
		MaxParallel:   3,
		RetryAttempts: 2,
		TaskTimeout:   60,
	}

	onecCfg := &config.OneCConfig{
		PlatformPath:   "C:\\Program Files\\1cv8\\bin\\1cv8.exe",
		TimeoutSeconds: 300,
		ServerName:     "server1c",
	}

	mockPub := &MockPublisher{}
	pool := NewPool(execCfg, onecCfg, mockPub)
	pool.Start()

	// Give workers time to start
	time.Sleep(100 * time.Millisecond)

	// Stop pool gracefully
	pool.Stop()

	// Verify channels are closed
	select {
	case _, ok := <-pool.resultChan:
		if ok {
			t.Error("Expected result channel to be closed")
		}
	default:
		t.Error("Result channel should be closed and readable")
	}
}

func TestPool_TaskExecution(t *testing.T) {
	execCfg := &config.ExecutorConfig{
		MaxParallel:   2,
		RetryAttempts: 1,
		RetryDelay:    1,
		TaskTimeout:   60,
	}

	onecCfg := &config.OneCConfig{
		PlatformPath:   "invalid_1cv8.exe", // Invalid path for test
		TimeoutSeconds: 1,
		ServerName:     "server1c",
	}

	mockPub := &MockPublisher{}
	pool := NewPool(execCfg, onecCfg, mockPub)
	pool.Start()
	defer pool.Stop()

	// Submit a test task
	task := Task{
		TaskID:           "test-task-1",
		DatabaseID:       123,
		DatabaseName:     "TestDB",
		ConnectionString: "server1c\\TestDB",
		Username:         "Admin",
		Password:         "",
		ExtensionPath:    "test.cfe",
		ExtensionName:    "TestExt",
	}

	pool.taskChan <- task

	// Wait for result
	select {
	case result := <-pool.resultChan:
		if result.TaskID != task.TaskID {
			t.Errorf("Expected task_id = '%s', got '%s'", task.TaskID, result.TaskID)
		}
		if result.DatabaseID != task.DatabaseID {
			t.Errorf("Expected database_id = %d, got %d", task.DatabaseID, result.DatabaseID)
		}
		// Will fail because of invalid path, but that's expected
		if result.Status != "failed" {
			t.Errorf("Expected status = 'failed' (invalid path), got '%s'", result.Status)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("Timeout waiting for task result")
	}
}

func TestPool_MultipleTasksParallel(t *testing.T) {
	execCfg := &config.ExecutorConfig{
		MaxParallel:   5,
		RetryAttempts: 1,
		RetryDelay:    1,
		TaskTimeout:   60,
	}

	onecCfg := &config.OneCConfig{
		PlatformPath:   "invalid_1cv8.exe", // Invalid path for test
		TimeoutSeconds: 1,
		ServerName:     "server1c",
	}

	mockPub := &MockPublisher{}
	pool := NewPool(execCfg, onecCfg, mockPub)
	pool.Start()
	defer pool.Stop()

	// Submit multiple tasks
	taskCount := 10
	for i := 0; i < taskCount; i++ {
		task := Task{
			TaskID:           "test-task-" + string(rune('A'+i)),
			DatabaseID:       100 + i,
			DatabaseName:     "TestDB" + string(rune('A'+i)),
			ConnectionString: "server1c\\TestDB" + string(rune('A'+i)),
			Username:         "Admin",
			Password:         "",
			ExtensionPath:    "test.cfe",
			ExtensionName:    "TestExt",
		}
		pool.taskChan <- task
	}

	// Collect results
	results := make(map[string]TaskResult)
	timeout := time.After(30 * time.Second)

	for i := 0; i < taskCount; i++ {
		select {
		case result := <-pool.resultChan:
			results[result.TaskID] = result
		case <-timeout:
			t.Fatalf("Timeout waiting for results, got %d/%d", len(results), taskCount)
		}
	}

	// Verify all tasks completed
	if len(results) != taskCount {
		t.Errorf("Expected %d results, got %d", taskCount, len(results))
	}

	// All will fail due to invalid path, verify they all completed
	for taskID, result := range results {
		if result.Status != "failed" {
			t.Logf("Task %s: %s (expected 'failed' due to invalid path)", taskID, result.Status)
		}
	}
}
