package progress

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"

	"github.com/commandcenter1c/commandcenter/installation-service/internal/config"
	"github.com/commandcenter1c/commandcenter/installation-service/internal/executor"
)

func setupMiniRedis(t *testing.T) (*miniredis.Miniredis, *config.RedisConfig) {
	t.Helper()

	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("Failed to start miniredis: %v", err)
	}

	cfg := &config.RedisConfig{
		Host:            mr.Host(),
		Port:            mr.Server().Addr().Port,
		ProgressChannel: "test_progress",
		DB:              0,
	}

	return mr, cfg
}

func TestNewPublisher(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	if pub == nil {
		t.Error("NewPublisher returned nil")
	}

	if pub.channel != cfg.ProgressChannel {
		t.Errorf("Expected channel %s, got %s", cfg.ProgressChannel, pub.channel)
	}
}

func TestPublisher_Ping(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	ctx := context.Background()
	if err := pub.Ping(ctx); err != nil {
		t.Errorf("Ping failed: %v", err)
	}
}

func TestPublisher_PublishTaskStarted(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	task := executor.Task{
		TaskID:       "test-task-1",
		DatabaseID:   123,
		DatabaseName: "TestDB",
	}

	ctx := context.Background()
	if err := pub.PublishTaskStarted(ctx, task); err != nil {
		t.Errorf("PublishTaskStarted failed: %v", err)
	}

	// Verify message was published (miniredis doesn't support pub/sub easily,
	// but we can check that no error occurred)
}

func TestPublisher_PublishTaskCompleted(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	result := executor.TaskResult{
		TaskID:          "test-task-1",
		DatabaseID:      123,
		DatabaseName:    "TestDB",
		Status:          "success",
		DurationSeconds: 45,
	}

	ctx := context.Background()
	if err := pub.PublishTaskCompleted(ctx, result); err != nil {
		t.Errorf("PublishTaskCompleted failed: %v", err)
	}
}

func TestPublisher_PublishTaskFailed(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	result := executor.TaskResult{
		TaskID:          "test-task-1",
		DatabaseID:      123,
		DatabaseName:    "TestDB",
		Status:          "failed",
		DurationSeconds: 30,
		ErrorMessage:    "Test error message",
	}

	ctx := context.Background()
	if err := pub.PublishTaskFailed(ctx, result); err != nil {
		t.Errorf("PublishTaskFailed failed: %v", err)
	}
}

func TestPublisher_PublishTaskProgress(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	task := executor.Task{
		TaskID:       "test-task-1",
		DatabaseID:   123,
		DatabaseName: "TestDB",
	}

	ctx := context.Background()
	if err := pub.PublishTaskProgress(ctx, task, 50); err != nil {
		t.Errorf("PublishTaskProgress failed: %v", err)
	}
}

func TestProgressEvent_Marshal(t *testing.T) {
	event := ProgressEvent{
		Event:           EventTaskCompleted,
		TaskID:          "test-123",
		DatabaseID:      456,
		DatabaseName:    "TestDB",
		Status:          "success",
		DurationSeconds: 60,
		Timestamp:       time.Now().Format(time.RFC3339),
		Metadata: map[string]interface{}{
			"test_key": "test_value",
		},
	}

	data, err := json.Marshal(event)
	if err != nil {
		t.Errorf("Failed to marshal ProgressEvent: %v", err)
	}

	// Verify JSON can be unmarshaled
	var decoded ProgressEvent
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Errorf("Failed to unmarshal ProgressEvent: %v", err)
	}

	if decoded.TaskID != event.TaskID {
		t.Errorf("Expected TaskID %s, got %s", event.TaskID, decoded.TaskID)
	}

	if decoded.Status != event.Status {
		t.Errorf("Expected Status %s, got %s", event.Status, decoded.Status)
	}
}

func TestPublisher_Close(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)

	if err := pub.Close(); err != nil {
		t.Errorf("Close failed: %v", err)
	}

	// After close, ping should fail
	ctx := context.Background()
	if err := pub.Ping(ctx); err == nil {
		t.Error("Expected error after Close, got nil")
	}
}

func TestPublisher_ContextCancellation(t *testing.T) {
	mr, cfg := setupMiniRedis(t)
	defer mr.Close()

	pub := NewPublisher(cfg)
	defer pub.Close()

	task := executor.Task{
		TaskID:       "test-task-1",
		DatabaseID:   123,
		DatabaseName: "TestDB",
	}

	// Create context with immediate cancellation
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	// Publishing with cancelled context should handle gracefully
	// (may or may not error depending on timing)
	_ = pub.PublishTaskStarted(ctx, task)
}

func TestProgressEvent_AllFields(t *testing.T) {
	tests := []struct {
		name  string
		event ProgressEvent
	}{
		{
			name: "task_started event",
			event: ProgressEvent{
				Event:        EventTaskStarted,
				TaskID:       "task-1",
				DatabaseID:   1,
				DatabaseName: "DB1",
				Status:       "in_progress",
				Timestamp:    time.Now().Format(time.RFC3339),
			},
		},
		{
			name: "task_completed event",
			event: ProgressEvent{
				Event:           EventTaskCompleted,
				TaskID:          "task-2",
				DatabaseID:      2,
				DatabaseName:    "DB2",
				Status:          "success",
				DurationSeconds: 120,
				Timestamp:       time.Now().Format(time.RFC3339),
			},
		},
		{
			name: "task_failed event",
			event: ProgressEvent{
				Event:           EventTaskFailed,
				TaskID:          "task-3",
				DatabaseID:      3,
				DatabaseName:    "DB3",
				Status:          "failed",
				DurationSeconds: 90,
				ErrorMessage:    "Connection timeout",
				Timestamp:       time.Now().Format(time.RFC3339),
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			data, err := json.Marshal(tt.event)
			if err != nil {
				t.Errorf("Failed to marshal event: %v", err)
			}

			var decoded ProgressEvent
			if err := json.Unmarshal(data, &decoded); err != nil {
				t.Errorf("Failed to unmarshal event: %v", err)
			}

			if decoded.Event != tt.event.Event {
				t.Errorf("Expected Event %s, got %s", tt.event.Event, decoded.Event)
			}

			if decoded.TaskID != tt.event.TaskID {
				t.Errorf("Expected TaskID %s, got %s", tt.event.TaskID, decoded.TaskID)
			}

			if decoded.Status != tt.event.Status {
				t.Errorf("Expected Status %s, got %s", tt.event.Status, decoded.Status)
			}
		})
	}
}
