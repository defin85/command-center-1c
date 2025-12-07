package jobs

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"
)

func TestCleanupReplayedEventsJob_Name(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 7, logger)

	assert.Equal(t, CleanupReplayedEventsJobName, job.Name())
	assert.Equal(t, "cleanup_old_replayed_events", job.Name())
}

func TestCleanupReplayedEventsJob_Execute_Success(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 7, logger)

	// Setup mock to return 5 deleted events
	mockClient.On("CleanupOldEvents", mock.Anything, 7).Return(5, nil)

	// Execute
	err := job.Execute(context.Background())

	// Assert
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)
}

func TestCleanupReplayedEventsJob_Execute_ZeroDeleted(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 30, logger)

	// Setup mock to return 0 deleted events
	mockClient.On("CleanupOldEvents", mock.Anything, 30).Return(0, nil)

	// Execute
	err := job.Execute(context.Background())

	// Assert
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)
}

func TestCleanupReplayedEventsJob_Execute_Error(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 7, logger)

	// Setup mock to return error
	mockClient.On("CleanupOldEvents", mock.Anything, 7).Return(0, errors.New("orchestrator unavailable"))

	// Execute
	err := job.Execute(context.Background())

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to cleanup replayed events")
	assert.Contains(t, err.Error(), "orchestrator unavailable")
	mockClient.AssertExpectations(t)
}

func TestCleanupReplayedEventsJob_Execute_LargeDeleteCount(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 7, logger)

	// Setup mock to return many deleted events
	mockClient.On("CleanupOldEvents", mock.Anything, 7).Return(1000, nil)

	// Execute
	err := job.Execute(context.Background())

	// Assert
	assert.NoError(t, err)
	mockClient.AssertExpectations(t)
}

func TestNewCleanupReplayedEventsJob_RetentionDaysValidation(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	tests := []struct {
		name             string
		inputDays        int
		expectedDays     int
	}{
		{"zero becomes default", 0, 7},
		{"negative becomes default", -5, 7},
		{"normal value", 30, 30},
		{"min value 1", 1, 1},
		{"max value 365", 365, 365},
		{"over max becomes max", 400, 365},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			job := NewCleanupReplayedEventsJob(mockClient, tt.inputDays, logger)
			assert.Equal(t, tt.expectedDays, job.retentionDays)
		})
	}
}

func TestCleanupReplayedEventsJob_ContextCancellation(t *testing.T) {
	mockClient := new(MockEventReplayClient)
	logger := testLogger()

	job := NewCleanupReplayedEventsJob(mockClient, 7, logger)

	// Create cancelled context
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	// Setup mock to return context error
	mockClient.On("CleanupOldEvents", mock.Anything, 7).Return(0, ctx.Err())

	// Execute
	err := job.Execute(ctx)

	// Assert
	assert.Error(t, err)
	mockClient.AssertExpectations(t)
}

func TestCleanupStatusHistoryJob_Name(t *testing.T) {
	// Use a simple stub client for status history job
	logger, _ := zap.NewDevelopment()
	stubClient := NewHTTPOrchestratorClient("http://localhost:8200", logger)

	job := NewCleanupStatusHistoryJob(stubClient, 7, logger)

	assert.Equal(t, CleanupStatusHistoryJobName, job.Name())
	assert.Equal(t, "cleanup_old_status_history", job.Name())
}

func TestCleanupStatusHistoryJob_Execute_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	stubClient := NewHTTPOrchestratorClient("http://localhost:8200", logger)

	job := NewCleanupStatusHistoryJob(stubClient, 30, logger)

	// Execute (stub always succeeds)
	err := job.Execute(context.Background())

	// Assert
	assert.NoError(t, err)
}

// TestCleanupMetricsSingleton verifies that metrics are singleton
func TestCleanupMetricsSingleton(t *testing.T) {
	metrics1 := getCleanupMetrics()
	metrics2 := getCleanupMetrics()

	assert.Same(t, metrics1, metrics2, "getCleanupMetrics should return same instance")
}
