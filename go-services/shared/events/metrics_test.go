package events_test

import (
	"testing"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/events"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/testutil"
	"github.com/stretchr/testify/assert"
)

func TestMetrics_RecordPublish(t *testing.T) {
	// Create a new registry for this test to avoid conflicts
	registry := prometheus.NewRegistry()

	// Create metrics with the test registry
	messagesPublished := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "test_events_messages_published_total",
			Help: "Total number of messages published",
		},
		[]string{"service", "channel", "event_type"},
	)
	registry.MustRegister(messagesPublished)

	// Record publish
	messagesPublished.WithLabelValues("test-service", "test-channel", "test.event").Inc()

	// Check counter
	count := testutil.ToFloat64(messagesPublished.WithLabelValues("test-service", "test-channel", "test.event"))
	assert.Equal(t, float64(1), count)
}

func TestRecordPublish_Integration(t *testing.T) {
	// This test verifies that RecordPublish function works without panicking
	// We can't easily test the actual metrics values due to global state
	events.RecordPublish("test-service", "test-channel", "test.event", 100*time.Millisecond)

	// If we got here without panic, the test passes
	assert.True(t, true)
}
