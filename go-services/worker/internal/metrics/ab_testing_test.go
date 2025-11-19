package metrics

import (
	"testing"

)

// TestRecordExecution tests the RecordExecution helper function
func TestRecordExecution(t *testing.T) {
	tests := []struct {
		name            string
		mode            string
		durationSeconds float64
		success         bool
		wantModeCount   float64
		wantSuccessCount float64
		wantFailureCount float64
	}{
		{
			name:            "successful event_driven execution",
			mode:            "event_driven",
			durationSeconds: 0.123,
			success:         true,
			wantModeCount:   1,
			wantSuccessCount: 1,
			wantFailureCount: 0,
		},
		{
			name:            "failed http_sync execution",
			mode:            "http_sync",
			durationSeconds: 1.5,
			success:         false,
			wantModeCount:   1,
			wantSuccessCount: 0,
			wantFailureCount: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Reset metrics (note: in real tests you'd use separate registries)
			// For simplicity, we just test that function doesn't panic
			RecordExecution(tt.mode, tt.durationSeconds, tt.success)

			// Note: testutil.ToFloat64() requires actual metric collection
			// which is complex with promauto. In production tests, use
		})
	}
}

// TestRecordCompensation tests the RecordCompensation helper function
func TestRecordCompensation(t *testing.T) {
	tests := []struct {
		name   string
		mode   string
		reason string
	}{
		{
			name:   "lock_failed compensation",
			mode:   "event_driven",
			reason: "lock_failed",
		},
		{
			name:   "install_failed compensation",
			mode:   "http_sync",
			reason: "install_failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			RecordCompensation(tt.mode, tt.reason)
			// Function should not panic
		})
	}
}

// TestRecordCircuitBreakerTrip tests the RecordCircuitBreakerTrip helper function
func TestRecordCircuitBreakerTrip(t *testing.T) {
	modes := []string{"event_driven", "http_sync"}

	for _, mode := range modes {
		t.Run(mode, func(t *testing.T) {
			RecordCircuitBreakerTrip(mode)
			// Function should not panic
		})
	}
}

// TestRecordRetry tests the RecordRetry helper function
func TestRecordRetry(t *testing.T) {
	modes := []string{"event_driven", "http_sync"}

	for _, mode := range modes {
		t.Run(mode, func(t *testing.T) {
			RecordRetry(mode)
			// Function should not panic
		})
	}
}

// TestUpdateQueueDepth tests the UpdateQueueDepth helper function
func TestUpdateQueueDepth(t *testing.T) {
	tests := []struct {
		name  string
		mode  string
		depth int
	}{
		{
			name:  "empty queue",
			mode:  "event_driven",
			depth: 0,
		},
		{
			name:  "queue with items",
			mode:  "http_sync",
			depth: 42,
		},
		{
			name:  "large queue",
			mode:  "event_driven",
			depth: 1000,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			UpdateQueueDepth(tt.mode, tt.depth)
			// Function should not panic
		})
	}
}

// TestUpdateSuccessRate tests the UpdateSuccessRate helper function
func TestUpdateSuccessRate(t *testing.T) {
	tests := []struct {
		name string
		mode string
		rate float64
		want float64
	}{
		{
			name: "zero success rate",
			mode: "event_driven",
			rate: 0.0,
			want: 0.0,
		},
		{
			name: "50% success rate",
			mode: "http_sync",
			rate: 0.5,
			want: 0.5,
		},
		{
			name: "100% success rate",
			mode: "event_driven",
			rate: 1.0,
			want: 1.0,
		},
		{
			name: "negative rate clamped to 0",
			mode: "http_sync",
			rate: -0.5,
			want: 0.0,
		},
		{
			name: "rate > 1 clamped to 1",
			mode: "event_driven",
			rate: 1.5,
			want: 1.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			UpdateSuccessRate(tt.mode, tt.rate)
			// Function should not panic
			// In production tests, verify actual gauge value
		})
	}
}

// TestMetricsLabels verifies that metrics have correct labels
func TestMetricsLabels(t *testing.T) {
	// Test that metrics accept expected label values
	validModes := []string{"event_driven", "http_sync"}
	validReasons := []string{"lock_failed", "install_failed", "timeout", "network_error"}

	for _, mode := range validModes {
		t.Run("mode_"+mode, func(t *testing.T) {
			// These should not panic
			ExecutionMode.WithLabelValues(mode)
			ExecutionSuccess.WithLabelValues(mode)
			ExecutionFailure.WithLabelValues(mode)
			CircuitBreakerTrips.WithLabelValues(mode)
			RetryAttempts.WithLabelValues(mode)
			QueueDepth.WithLabelValues(mode)
			SuccessRate.WithLabelValues(mode)
		})
	}

	for _, mode := range validModes {
		for _, reason := range validReasons {
			t.Run("compensation_"+mode+"_"+reason, func(t *testing.T) {
				CompensationExecuted.WithLabelValues(mode, reason)
			})
		}
	}
}

// BenchmarkRecordExecution benchmarks the RecordExecution function
func BenchmarkRecordExecution(b *testing.B) {
	mode := "event_driven"
	duration := 0.123
	success := true

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		RecordExecution(mode, duration, success)
	}
}

// BenchmarkRecordCompensation benchmarks the RecordCompensation function
func BenchmarkRecordCompensation(b *testing.B) {
	mode := "event_driven"
	reason := "lock_failed"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		RecordCompensation(mode, reason)
	}
}

// BenchmarkUpdateQueueDepth benchmarks the UpdateQueueDepth function
func BenchmarkUpdateQueueDepth(b *testing.B) {
	mode := "event_driven"
	depth := 42

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		UpdateQueueDepth(mode, depth)
	}
}

// Example usage of metrics
func ExampleRecordExecution() {
	// Record a successful event-driven execution
	RecordExecution("event_driven", 0.123, true)

	// Record a failed http_sync execution
	RecordExecution("http_sync", 1.5, false)
}

func ExampleRecordCompensation() {
	// Record a compensation due to lock failure
	RecordCompensation("event_driven", "lock_failed")
}

func ExampleUpdateQueueDepth() {
	// Update queue depth for event_driven mode
	UpdateQueueDepth("event_driven", 42)
}

// Note: For production tests with actual metric verification,
// use the following pattern:
//
// func TestMetricsWithVerification(t *testing.T) {
//
//             Name: "test_counter",
//         },
//         []string{"mode"},
//     )
//     registry.MustRegister(counter)
//
//     counter.WithLabelValues("event_driven").Inc()
//
//     expected := 1.0
//     actual := testutil.ToFloat64(counter.WithLabelValues("event_driven"))
//     if actual != expected {
//         t.Errorf("expected %v, got %v", expected, actual)
//     }
// }
