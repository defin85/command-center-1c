package events

import (
	"encoding/json"
	"time"

	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	messagesPublished = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "events_messages_published_total",
			Help: "Total number of messages published",
		},
		[]string{"service", "channel", "event_type"},
	)

	messagesProcessed = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "events_messages_processed_total",
			Help: "Total number of messages processed",
		},
		[]string{"channel", "event_type", "status"}, // status: success/error
	)

	processingDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "events_processing_duration_seconds",
			Help:    "Message processing duration in seconds",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
		},
		[]string{"channel", "event_type"},
	)

	publishDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "events_publish_duration_seconds",
			Help:    "Message publish duration in seconds",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1},
		},
		[]string{"service", "channel", "event_type"},
	)

	concurrentHandlers = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "events_concurrent_handlers",
			Help: "Current number of concurrent message handlers",
		},
		[]string{"consumer_group"},
	)
)

// WithMetrics adds Prometheus metrics tracking middleware
func WithMetrics(consumerGroup string) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) ([]*message.Message, error) {
			start := time.Now()

			// Increment concurrent handlers
			concurrentHandlers.WithLabelValues(consumerGroup).Inc()
			defer concurrentHandlers.WithLabelValues(consumerGroup).Dec()

			// Parse envelope for labels
			var envelope Envelope
			_ = json.Unmarshal(msg.Payload, &envelope) // Ignore error, use defaults

			channel := msg.Metadata.Get("channel")
			if channel == "" {
				channel = "unknown"
			}
			eventType := envelope.EventType
			if eventType == "" {
				eventType = "unknown"
			}

			// Process message
			messages, err := h(msg)

			// Record metrics
			duration := time.Since(start).Seconds()
			status := "success"
			if err != nil {
				status = "error"
			}

			messagesProcessed.WithLabelValues(channel, eventType, status).Inc()
			processingDuration.WithLabelValues(channel, eventType).Observe(duration)

			return messages, err
		}
	}
}

// RecordPublish records publish metrics (call from publisher)
func RecordPublish(serviceName, channel, eventType string, duration time.Duration) {
	publishDuration.WithLabelValues(serviceName, channel, eventType).Observe(duration.Seconds())
	messagesPublished.WithLabelValues(serviceName, channel, eventType).Inc()
}
