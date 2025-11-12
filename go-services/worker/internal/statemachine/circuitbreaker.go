package statemachine

import (
	"fmt"
	"strings"
	"time"

	"github.com/sony/gobreaker"
)

// createCircuitBreakers creates circuit breakers for external services
func createCircuitBreakers() (clusterServiceBreaker, batchServiceBreaker *gobreaker.CircuitBreaker) {
	settings := gobreaker.Settings{
		Name:        "cluster-service",
		MaxRequests: 3,                      // Max requests in half-open state
		Interval:    10 * time.Second,       // Reset success/failure counts
		Timeout:     30 * time.Second,       // Duration in open state before half-open
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 3 && failureRatio >= 0.6
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			fmt.Printf("[CircuitBreaker] %s state changed: %s -> %s\n", name, from, to)
		},
	}

	clusterServiceBreaker = gobreaker.NewCircuitBreaker(settings)

	batchSettings := settings
	batchSettings.Name = "batch-service"
	batchSettings.Timeout = 5 * time.Minute // Longer timeout for batch operations
	batchServiceBreaker = gobreaker.NewCircuitBreaker(batchSettings)

	return clusterServiceBreaker, batchServiceBreaker
}

// getCircuitBreaker returns appropriate circuit breaker based on channel name
func (sm *ExtensionInstallStateMachine) getCircuitBreaker(channel string) *gobreaker.CircuitBreaker {
	if strings.Contains(channel, "cluster-service") {
		return sm.clusterServiceBreaker
	}
	if strings.Contains(channel, "batch-service") {
		return sm.batchServiceBreaker
	}
	return nil // No breaker for other channels
}
