package scheduler

import (
	"os"
	"strconv"
	"time"
)

// SchedulerConfig holds scheduler configuration
type SchedulerConfig struct {
	// Feature flag - global enable/disable for scheduler
	Enabled bool

	// Cron expressions for jobs
	CleanupHistoryCron string // cleanup_old_status_history
	CleanupEventsCron  string // cleanup_old_replayed_events
	BatchHealthCron    string // periodic_batch_service_health
	ClusterHealthCron  string // periodic_cluster_health_check
	DatabaseHealthCron string // periodic_database_health_check
	EventReplayCron    string // replay_failed_events

	// Lock configuration
	LockTTL        time.Duration // TTL for distributed locks
	LockRetryDelay time.Duration // Delay between lock acquisition retries
	LockMaxRetries int           // Max retries for lock acquisition

	// Orchestrator Internal API configuration
	OrchestratorURL string

	// Job-specific settings
	CleanupHistoryRetentionDays int // Days to keep status history
	CleanupEventsRetentionDays  int // Days to keep replayed events

	// Event Replay settings
	EventReplayBatchSize int  // Number of events to replay per batch
	EventReplayEnabled   bool // Feature flag for event replay job

	// RAS Adapter configuration
	RASAdapterURL string // URL for RAS Adapter service
}

// DefaultConfig returns scheduler configuration with defaults
func DefaultConfig() *SchedulerConfig {
	return &SchedulerConfig{
		Enabled:                     false,
		CleanupHistoryCron:          "0 3 * * *",   // Daily at 3:00 AM
		CleanupEventsCron:           "0 4 * * *",   // Daily at 4:00 AM
		BatchHealthCron:             "@every 30s",  // Every 30 seconds
		ClusterHealthCron:           "@every 60s",  // Every 60 seconds
		DatabaseHealthCron:          "@every 120s", // Every 120 seconds
		EventReplayCron:             "@every 60s",  // Every 60 seconds
		LockTTL:                     5 * time.Minute,
		LockRetryDelay:              100 * time.Millisecond,
		LockMaxRetries:              3,
		OrchestratorURL:             "http://localhost:8200",
		CleanupHistoryRetentionDays: 30,
		CleanupEventsRetentionDays:  7,
		EventReplayBatchSize:        100,
		EventReplayEnabled:          false, // Disabled by default
		RASAdapterURL:               "http://localhost:8188",
	}
}

// LoadConfigFromEnv loads scheduler configuration from environment variables
func LoadConfigFromEnv() *SchedulerConfig {
	cfg := DefaultConfig()

	// Feature flag
	cfg.Enabled = getBoolEnv("ENABLE_GO_SCHEDULER", false)

	// Cron expressions
	if v := os.Getenv("SCHEDULER_CLEANUP_HISTORY"); v != "" {
		cfg.CleanupHistoryCron = v
	}
	if v := os.Getenv("SCHEDULER_CLEANUP_EVENTS"); v != "" {
		cfg.CleanupEventsCron = v
	}
	if v := os.Getenv("SCHEDULER_BATCH_HEALTH"); v != "" {
		cfg.BatchHealthCron = v
	}
	if v := os.Getenv("SCHEDULER_CLUSTER_HEALTH"); v != "" {
		cfg.ClusterHealthCron = v
	}
	if v := os.Getenv("SCHEDULER_DATABASE_HEALTH"); v != "" {
		cfg.DatabaseHealthCron = v
	}
	if v := os.Getenv("SCHEDULER_EVENT_REPLAY"); v != "" {
		cfg.EventReplayCron = v
	}

	// Lock configuration
	if v := getIntEnv("SCHEDULER_LOCK_TTL_SECONDS", 0); v > 0 {
		cfg.LockTTL = time.Duration(v) * time.Second
	}
	if v := getIntEnv("SCHEDULER_LOCK_RETRY_DELAY_MS", 0); v > 0 {
		cfg.LockRetryDelay = time.Duration(v) * time.Millisecond
	}
	if v := getIntEnv("SCHEDULER_LOCK_MAX_RETRIES", 0); v > 0 {
		cfg.LockMaxRetries = v
	}

	// Orchestrator URL
	if v := os.Getenv("ORCHESTRATOR_URL"); v != "" {
		cfg.OrchestratorURL = v
	}

	// Retention settings
	if v := getIntEnv("CLEANUP_HISTORY_RETENTION_DAYS", 0); v > 0 {
		cfg.CleanupHistoryRetentionDays = v
	}
	if v := getIntEnv("CLEANUP_EVENTS_RETENTION_DAYS", 0); v > 0 {
		cfg.CleanupEventsRetentionDays = v
	}

	// RAS Adapter URL
	if v := os.Getenv("RAS_ADAPTER_URL"); v != "" {
		cfg.RASAdapterURL = v
	}

	// Event Replay settings
	if v := getIntEnv("EVENT_REPLAY_BATCH_SIZE", 0); v > 0 {
		cfg.EventReplayBatchSize = v
	}
	cfg.EventReplayEnabled = getBoolEnv("ENABLE_GO_EVENT_REPLAY", false)

	return cfg
}

// Helper functions

func getBoolEnv(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}

func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}
