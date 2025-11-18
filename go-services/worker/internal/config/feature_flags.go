package config

import (
	"hash/fnv"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// FeatureFlags manages feature toggles for Worker
type FeatureFlags struct {
	// Main toggle - global kill switch
	EnableEventDriven bool

	// Percentage rollout (0.0 - 1.0)
	// 0.0 = 0% Event-Driven, 1.0 = 100% Event-Driven
	RolloutPercentage float64

	// Database targeting (whitelist for early access)
	// Comma-separated list: "db1,db2,db3"
	TargetedDatabases []string

	// Operation type targeting
	EnableForExtensions bool
	EnableForBackups    bool

	// Safety switches
	MaxConcurrentEvents     int
	CircuitBreakerThreshold float64

	// A/B testing
	ExperimentID string

	// Internal state
	mu  sync.RWMutex
	rng *rand.Rand
}

// NewFeatureFlags creates new FeatureFlags instance
func NewFeatureFlags() *FeatureFlags {
	return &FeatureFlags{
		rng: rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// LoadFeatureFlagsFromEnv loads feature flags from environment variables
func LoadFeatureFlagsFromEnv() *FeatureFlags {
	ff := NewFeatureFlags()

	// Main toggle
	ff.EnableEventDriven = getBoolEnvFF("ENABLE_EVENT_DRIVEN", false)

	// Percentage rollout
	ff.RolloutPercentage = getFloat64EnvFF("EVENT_DRIVEN_ROLLOUT_PERCENT", 0.0)
	if ff.RolloutPercentage < 0.0 {
		ff.RolloutPercentage = 0.0
	}
	if ff.RolloutPercentage > 1.0 {
		ff.RolloutPercentage = 1.0
	}

	// Targeted databases
	if dbList := os.Getenv("EVENT_DRIVEN_TARGET_DBS"); dbList != "" {
		databases := strings.Split(dbList, ",")
		for i, db := range databases {
			databases[i] = strings.TrimSpace(db)
		}
		ff.TargetedDatabases = databases
	} else {
		ff.TargetedDatabases = []string{}
	}

	// Operation type targeting
	ff.EnableForExtensions = getBoolEnvFF("EVENT_DRIVEN_EXTENSIONS", true)
	ff.EnableForBackups = getBoolEnvFF("EVENT_DRIVEN_BACKUPS", false)

	// Safety switches
	ff.MaxConcurrentEvents = getIntEnvFF("EVENT_DRIVEN_MAX_CONCURRENT", 100)
	ff.CircuitBreakerThreshold = getFloat64EnvFF("EVENT_DRIVEN_CB_THRESHOLD", 0.95)

	// A/B testing
	ff.ExperimentID = os.Getenv("EVENT_DRIVEN_EXPERIMENT_ID")

	return ff
}

// ShouldUseEventDriven decides whether to use Event-Driven for an operation
func (ff *FeatureFlags) ShouldUseEventDriven(operationType string, databaseID string) bool {
	ff.mu.RLock()
	defer ff.mu.RUnlock()

	// 1. Global kill switch
	if !ff.EnableEventDriven {
		return false
	}

	// 2. Check operation type
	switch operationType {
	case "extension", "install_extension":
		if !ff.EnableForExtensions {
			return false
		}
	case "backup":
		if !ff.EnableForBackups {
			return false
		}
	default:
		// Unknown operation type - default to HTTP Sync
		return false
	}

	// 3. Check targeted databases (if configured)
	if len(ff.TargetedDatabases) > 0 {
		for _, db := range ff.TargetedDatabases {
			if db == databaseID {
				return true // Always use Event-Driven for targeted DBs
			}
		}
		// Not in whitelist - skip to percentage rollout
	}

	// 4. Percentage-based rollout
	if ff.RolloutPercentage >= 1.0 {
		return true // 100% rollout
	}

	if ff.RolloutPercentage <= 0.0 {
		return false // 0% rollout
	}

	// 5. Consistent hashing for A/B testing
	if ff.ExperimentID != "" {
		// Same database always gets same treatment
		hash := hashString(ff.ExperimentID + databaseID)
		threshold := uint32(ff.RolloutPercentage * float64(^uint32(0)))
		return hash < threshold
	}

	// 6. Random rollout (not recommended for production)
	return ff.rng.Float64() < ff.RolloutPercentage
}

// Reload hot-reloads configuration from environment
func (ff *FeatureFlags) Reload() error {
	ff.mu.Lock()
	defer ff.mu.Unlock()

	// Reload from environment
	newFF := LoadFeatureFlagsFromEnv()

	// Update fields (keeping same RNG instance)
	ff.EnableEventDriven = newFF.EnableEventDriven
	ff.RolloutPercentage = newFF.RolloutPercentage
	ff.TargetedDatabases = newFF.TargetedDatabases
	ff.EnableForExtensions = newFF.EnableForExtensions
	ff.EnableForBackups = newFF.EnableForBackups
	ff.MaxConcurrentEvents = newFF.MaxConcurrentEvents
	ff.CircuitBreakerThreshold = newFF.CircuitBreakerThreshold
	ff.ExperimentID = newFF.ExperimentID

	return nil
}

// GetConfig returns current configuration (thread-safe)
func (ff *FeatureFlags) GetConfig() map[string]interface{} {
	ff.mu.RLock()
	defer ff.mu.RUnlock()

	return map[string]interface{}{
		"enable_event_driven":        ff.EnableEventDriven,
		"rollout_percentage":         ff.RolloutPercentage,
		"targeted_databases":         ff.TargetedDatabases,
		"enable_for_extensions":      ff.EnableForExtensions,
		"enable_for_backups":         ff.EnableForBackups,
		"max_concurrent_events":      ff.MaxConcurrentEvents,
		"circuit_breaker_threshold":  ff.CircuitBreakerThreshold,
		"experiment_id":              ff.ExperimentID,
	}
}

// hashString creates consistent hash for string
func hashString(s string) uint32 {
	h := fnv.New32a()
	h.Write([]byte(s))
	return h.Sum32()
}

// Helper functions for feature flags

func getBoolEnvFF(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}

func getIntEnvFF(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getFloat64EnvFF(key string, defaultValue float64) float64 {
	if value := os.Getenv(key); value != "" {
		if floatValue, err := strconv.ParseFloat(value, 64); err == nil {
			return floatValue
		}
	}
	return defaultValue
}
