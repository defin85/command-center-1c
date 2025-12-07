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

	// Lock configuration
	LockTTL         time.Duration // TTL for distributed locks
	LockRetryDelay  time.Duration // Delay between lock acquisition retries
	LockMaxRetries  int           // Max retries for lock acquisition

	// Orchestrator Internal API configuration
	OrchestratorURL string

	// Job-specific settings
	CleanupHistoryRetentionDays int // Days to keep status history
	CleanupEventsRetentionDays  int // Days to keep replayed events
}

// DefaultConfig returns scheduler configuration with defaults
func DefaultConfig() *SchedulerConfig {
	return &SchedulerConfig{
		Enabled:                     false,
		CleanupHistoryCron:          "0 3 * * *",   // Daily at 3:00 AM
		CleanupEventsCron:           "0 4 * * *",   // Daily at 4:00 AM
		BatchHealthCron:             "@every 30s", // Every 30 seconds
		LockTTL:                     5 * time.Minute,
		LockRetryDelay:              100 * time.Millisecond,
		LockMaxRetries:              3,
		OrchestratorURL:             "http://localhost:8200",
		CleanupHistoryRetentionDays: 30,
		CleanupEventsRetentionDays:  7,
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
