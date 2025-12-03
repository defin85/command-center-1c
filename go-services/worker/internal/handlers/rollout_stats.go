package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/commandcenter1c/commandcenter/worker/internal/metrics"
)

// RolloutStats contains current rollout statistics
type RolloutStats struct {
	EventDrivenEnabled     bool    `json:"event_driven_enabled"`
	RolloutPercent         float64 `json:"rollout_percent"`
	ActiveStateMachines    int64   `json:"active_state_machines"`
	TotalEventDriven       int64   `json:"total_event_driven,omitempty"`
	TotalHTTPSync          int64   `json:"total_http_sync,omitempty"`
	SuccessRateEventDriven float64 `json:"success_rate_event_driven,omitempty"`
	SuccessRateHTTPSync    float64 `json:"success_rate_http_sync,omitempty"`
	TimeoutsLast5Min       int64   `json:"timeouts_last_5min,omitempty"`
	CompensationsLast5Min  int64   `json:"compensations_last_5min,omitempty"`
	QueueDepthEventDriven  int64   `json:"queue_depth_event_driven,omitempty"`
	LastUpdated            string  `json:"last_updated"`
}

// RolloutStatsHandler returns current rollout statistics
// Data is sourced from Prometheus metrics and feature flags
type RolloutStatsHandler struct {
	featureFlagsGetter func() map[string]interface{}
}

// NewRolloutStatsHandler creates a new rollout stats handler
func NewRolloutStatsHandler(featureFlagsGetter func() map[string]interface{}) *RolloutStatsHandler {
	return &RolloutStatsHandler{
		featureFlagsGetter: featureFlagsGetter,
	}
}

// ServeHTTP handles the /rollout-stats endpoint
func (h *RolloutStatsHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	flags := h.featureFlagsGetter()

	enabled, _ := flags["enable_event_driven"].(bool)
	rolloutPercent, _ := flags["rollout_percentage"].(float64)

	// Get active state machine count from metrics
	activeCount := metrics.GetActiveStateMachineCount()

	stats := RolloutStats{
		EventDrivenEnabled:  enabled,
		RolloutPercent:      rolloutPercent,
		ActiveStateMachines: activeCount,
		LastUpdated:         time.Now().UTC().Format(time.RFC3339),
	}

	data, err := json.Marshal(stats)
	if err != nil {
		http.Error(w, "failed to encode response", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}
