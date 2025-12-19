package statemachine

import (
	"testing"
	"time"
)

func TestPrometheusMetricsRecorder_RecordCompensation(t *testing.T) {
	recorder := NewPrometheusMetricsRecorder()

	tests := []struct {
		name     string
		compName string
		success  bool
		duration time.Duration
		attempts int
	}{
		{
			name:     "successful compensation",
			compName: "rollback_transaction",
			success:  true,
			duration: 2 * time.Second,
			attempts: 1,
		},
		{
			name:     "failed compensation after retries",
			compName: "cleanup_resources",
			success:  false,
			duration: 15 * time.Second,
			attempts: 3,
		},
		{
			name:     "timeout compensation",
			compName: "cancel_operation",
			success:  false,
			duration: 30 * time.Second,
			attempts: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Should not panic
			recorder.RecordCompensation(tt.compName, tt.success, tt.duration, tt.attempts)
		})
	}
}

func TestPrometheusMetricsRecorder_RecordStuckWorkflow(t *testing.T) {
	// Should not panic
	RecordStuckWorkflowRecovered()
	RecordStuckWorkflowRecovered()
}

func TestPrometheusMetricsRecorder_RecordFailedEvents(t *testing.T) {
	tests := []struct {
		name string
		fn   func()
	}{
		{
			name: "store failed event",
			fn:   RecordFailedEventStored,
		},
		{
			name: "replay failed event",
			fn:   RecordFailedEventReplayed,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Should not panic
			tt.fn()
		})
	}
}

func TestNewPrometheusMetricsRecorder(t *testing.T) {
	recorder := NewPrometheusMetricsRecorder()
	if recorder == nil {
		t.Fatal("expected non-nil recorder")
	}
}

func TestMetricsRecorder_Interface(t *testing.T) {
	// Verify that PrometheusMetricsRecorder implements MetricsRecorder interface
	var _ MetricsRecorder = (*PrometheusMetricsRecorder)(nil)
}
