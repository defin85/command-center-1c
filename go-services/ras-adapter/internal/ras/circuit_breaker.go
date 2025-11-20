package ras

import (
	"time"

	"github.com/sony/gobreaker"
	"go.uber.org/zap"
)

// NewCircuitBreaker creates a circuit breaker for RAS operations
func NewCircuitBreaker(logger *zap.Logger) *gobreaker.CircuitBreaker {
	settings := gobreaker.Settings{
		Name:        "RAS-Client",
		MaxRequests: 3,
		Interval:    10 * time.Second,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 3 && failureRatio >= 0.6
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			logger.Warn("Circuit breaker state changed",
				zap.String("breaker", name),
				zap.String("from", from.String()),
				zap.String("to", to.String()))
		},
	}

	return gobreaker.NewCircuitBreaker(settings)
}
