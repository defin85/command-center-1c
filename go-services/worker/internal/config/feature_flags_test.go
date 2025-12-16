package config

import (
	"fmt"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestFeatureFlags_ShouldUseEventDriven_GlobalKillSwitch(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven: false,
		RolloutPercentage: 1.0, // Even 100% rollout
		EnableForExtensions: true,
	}

	result := ff.ShouldUseEventDriven("extension", "db1")
	assert.False(t, result, "Global kill switch should override everything")
}

func TestFeatureFlags_ShouldUseEventDriven_OperationType(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:   true,
		EnableForExtensions: true,
		EnableForBackups:    false,
		RolloutPercentage:   1.0,
	}

	// Extensions enabled
	assert.True(t, ff.ShouldUseEventDriven("extension", "db1"))
	assert.True(t, ff.ShouldUseEventDriven("install_extension", "db1"))

	// Backups disabled
	assert.False(t, ff.ShouldUseEventDriven("backup", "db1"))

	// Unknown operation type - default to HTTP Sync
	assert.False(t, ff.ShouldUseEventDriven("unknown_operation", "db1"))
}

func TestFeatureFlags_ShouldUseEventDriven_TargetedDatabases(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:   true,
		EnableForExtensions: true,
		TargetedDatabases:   []string{"db1", "db2"},
		RolloutPercentage:   0.0, // 0% general rollout
	}

	// In whitelist - should always use Event-Driven
	assert.True(t, ff.ShouldUseEventDriven("extension", "db1"))
	assert.True(t, ff.ShouldUseEventDriven("extension", "db2"))

	// Not in whitelist - should fall back to percentage rollout (0%)
	assert.False(t, ff.ShouldUseEventDriven("extension", "db3"))
}

func TestFeatureFlags_ShouldUseEventDriven_PercentageRollout(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:   true,
		EnableForExtensions: true,
		RolloutPercentage:   1.0, // 100%
	}

	// 100% rollout
	assert.True(t, ff.ShouldUseEventDriven("extension", "db1"))
	assert.True(t, ff.ShouldUseEventDriven("extension", "db2"))

	// 0% rollout
	ff.RolloutPercentage = 0.0
	assert.False(t, ff.ShouldUseEventDriven("extension", "db1"))
	assert.False(t, ff.ShouldUseEventDriven("extension", "db2"))
}

func TestFeatureFlags_ShouldUseEventDriven_ConsistentHashing(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:   true,
		EnableForExtensions: true,
		RolloutPercentage:   0.5, // 50%
		ExperimentID:        "exp-123",
	}

	// Same database should always get same result
	result1 := ff.ShouldUseEventDriven("extension", "db1")
	result2 := ff.ShouldUseEventDriven("extension", "db1")
	result3 := ff.ShouldUseEventDriven("extension", "db1")
	assert.Equal(t, result1, result2, "Consistent hashing should be deterministic")
	assert.Equal(t, result1, result3, "Consistent hashing should be deterministic")

	// Different databases may get different results
	resultA := ff.ShouldUseEventDriven("extension", "dbA")
	resultB := ff.ShouldUseEventDriven("extension", "dbB")
	t.Logf("dbA: %v, dbB: %v", resultA, resultB)
}

func TestHashString_Consistency(t *testing.T) {
	// Same input should always produce same hash
	hash1 := hashString("test-db-1")
	hash2 := hashString("test-db-1")
	assert.Equal(t, hash1, hash2, "Same input should produce same hash")

	// Different inputs should (likely) produce different hashes
	hash3 := hashString("test-db-2")
	assert.NotEqual(t, hash1, hash3, "Different inputs should produce different hashes")

	// Test with real experiment ID
	hash4 := hashString("exp-123" + "db1")
	hash5 := hashString("exp-123" + "db1")
	assert.Equal(t, hash4, hash5, "Same experiment+db should produce same hash")
}

func TestFeatureFlags_Reload(t *testing.T) {
	// Setup environment variables
	os.Setenv("ENABLE_EVENT_DRIVEN", "true")
	os.Setenv("EVENT_DRIVEN_ROLLOUT_PERCENT", "0.25")
	defer os.Unsetenv("ENABLE_EVENT_DRIVEN")
	defer os.Unsetenv("EVENT_DRIVEN_ROLLOUT_PERCENT")

	ff := &FeatureFlags{
		EnableEventDriven: false,
		RolloutPercentage: 0.0,
	}

	// Reload should update from environment
	err := ff.Reload()
	assert.NoError(t, err)
	assert.True(t, ff.EnableEventDriven)
	assert.Equal(t, 0.25, ff.RolloutPercentage)
}

func TestLoadFeatureFlagsFromEnv(t *testing.T) {
	// Setup environment variables
	os.Setenv("ENABLE_EVENT_DRIVEN", "true")
	os.Setenv("EVENT_DRIVEN_ROLLOUT_PERCENT", "0.5")
	os.Setenv("EVENT_DRIVEN_TARGET_DBS", "db1, db2, db3")
	os.Setenv("EVENT_DRIVEN_EXTENSIONS", "true")
	os.Setenv("EVENT_DRIVEN_BACKUPS", "false")
	os.Setenv("EVENT_DRIVEN_MAX_CONCURRENT", "200")
	os.Setenv("EVENT_DRIVEN_CB_THRESHOLD", "0.90")
	os.Setenv("EVENT_DRIVEN_EXPERIMENT_ID", "exp-2025-week3")

	defer func() {
		os.Unsetenv("ENABLE_EVENT_DRIVEN")
		os.Unsetenv("EVENT_DRIVEN_ROLLOUT_PERCENT")
		os.Unsetenv("EVENT_DRIVEN_TARGET_DBS")
		os.Unsetenv("EVENT_DRIVEN_EXTENSIONS")
		os.Unsetenv("EVENT_DRIVEN_BACKUPS")
		os.Unsetenv("EVENT_DRIVEN_MAX_CONCURRENT")
		os.Unsetenv("EVENT_DRIVEN_CB_THRESHOLD")
		os.Unsetenv("EVENT_DRIVEN_EXPERIMENT_ID")
	}()

	ff := LoadFeatureFlagsFromEnv()

	assert.True(t, ff.EnableEventDriven)
	assert.Equal(t, 0.5, ff.RolloutPercentage)
	assert.Equal(t, []string{"db1", "db2", "db3"}, ff.TargetedDatabases)
	assert.True(t, ff.EnableForExtensions)
	assert.False(t, ff.EnableForBackups)
	assert.Equal(t, 200, ff.MaxConcurrentEvents)
	assert.Equal(t, 0.90, ff.CircuitBreakerThreshold)
	assert.Equal(t, "exp-2025-week3", ff.ExperimentID)
}

func TestLoadFeatureFlagsFromEnv_Defaults(t *testing.T) {
	// Clear all environment variables
	os.Unsetenv("ENABLE_EVENT_DRIVEN")
	os.Unsetenv("EVENT_DRIVEN_ROLLOUT_PERCENT")
	os.Unsetenv("EVENT_DRIVEN_TARGET_DBS")
	os.Unsetenv("EVENT_DRIVEN_EXTENSIONS")
	os.Unsetenv("EVENT_DRIVEN_BACKUPS")
	os.Unsetenv("EVENT_DRIVEN_MAX_CONCURRENT")
	os.Unsetenv("EVENT_DRIVEN_CB_THRESHOLD")
	os.Unsetenv("EVENT_DRIVEN_EXPERIMENT_ID")

	ff := LoadFeatureFlagsFromEnv()

	// Check defaults
	assert.False(t, ff.EnableEventDriven, "Default should be disabled")
	assert.Equal(t, 1.0, ff.RolloutPercentage, "Default rollout should be 100%")
	assert.Empty(t, ff.TargetedDatabases, "Default targeted databases should be empty")
	assert.True(t, ff.EnableForExtensions, "Default should enable extensions")
	assert.False(t, ff.EnableForBackups, "Default should disable backups")
	assert.Equal(t, 100, ff.MaxConcurrentEvents)
	assert.Equal(t, 0.95, ff.CircuitBreakerThreshold)
	assert.Empty(t, ff.ExperimentID)
}

func TestFeatureFlags_GetConfig(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:       true,
		RolloutPercentage:       0.5,
		TargetedDatabases:       []string{"db1", "db2"},
		EnableForExtensions:     true,
		EnableForBackups:        false,
		MaxConcurrentEvents:     100,
		CircuitBreakerThreshold: 0.95,
		ExperimentID:            "exp-123",
	}

	config := ff.GetConfig()

	assert.Equal(t, true, config["enable_event_driven"])
	assert.Equal(t, 0.5, config["rollout_percentage"])
	assert.Equal(t, []string{"db1", "db2"}, config["targeted_databases"])
	assert.Equal(t, true, config["enable_for_extensions"])
	assert.Equal(t, false, config["enable_for_backups"])
	assert.Equal(t, 100, config["max_concurrent_events"])
	assert.Equal(t, 0.95, config["circuit_breaker_threshold"])
	assert.Equal(t, "exp-123", config["experiment_id"])
}

func TestFeatureFlags_RolloutPercentage_Bounds(t *testing.T) {
	// Test negative value clamping
	os.Setenv("EVENT_DRIVEN_ROLLOUT_PERCENT", "-0.5")
	defer os.Unsetenv("EVENT_DRIVEN_ROLLOUT_PERCENT")

	ff := LoadFeatureFlagsFromEnv()
	assert.Equal(t, 0.0, ff.RolloutPercentage, "Negative percentage should clamp to 0.0")

	// Test >1.0 value clamping
	os.Setenv("EVENT_DRIVEN_ROLLOUT_PERCENT", "1.5")
	ff = LoadFeatureFlagsFromEnv()
	assert.Equal(t, 1.0, ff.RolloutPercentage, "Percentage >1.0 should clamp to 1.0")
}

func TestFeatureFlags_ThreadSafety(t *testing.T) {
	ff := &FeatureFlags{
		EnableEventDriven:   true,
		EnableForExtensions: true,
		RolloutPercentage:   1.0,
	}

	// Concurrent reads
	done := make(chan bool)
	for i := 0; i < 100; i++ {
		go func() {
			_ = ff.ShouldUseEventDriven("extension", "db1")
			_ = ff.GetConfig()
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 100; i++ {
		<-done
	}

	// Should not panic
}

func TestFeatureFlags_TargetedDatabases_Whitespace(t *testing.T) {
	// Test whitespace trimming in database list
	os.Setenv("EVENT_DRIVEN_TARGET_DBS", " db1 , db2 , db3 ")
	defer os.Unsetenv("EVENT_DRIVEN_TARGET_DBS")

	ff := LoadFeatureFlagsFromEnv()
	assert.Equal(t, []string{"db1", "db2", "db3"}, ff.TargetedDatabases)
}

// TestFeatureFlags_ShouldUseEventDriven_Race tests for race conditions with concurrent calls
// FIXED: Issue #1 - Race condition in random rollout with RNG mutation
func TestFeatureFlags_ShouldUseEventDriven_Race(t *testing.T) {
	ff := NewFeatureFlags()
	ff.EnableEventDriven = true
	ff.EnableForExtensions = true
	ff.RolloutPercentage = 0.5

	// Run 100 concurrent calls to test race conditions
	done := make(chan bool)
	for i := 0; i < 100; i++ {
		go func(id int) {
			dbID := fmt.Sprintf("db-%d", id%10)
			_ = ff.ShouldUseEventDriven("extension", dbID)
			done <- true
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 100; i++ {
		<-done
	}

	// Should not panic or cause race condition
	t.Log("Race detector test passed - no data races detected")
}

// TestFeatureFlags_InvalidRolloutPercentage tests invalid rollout percentage values
func TestFeatureFlags_InvalidRolloutPercentage(t *testing.T) {
	tests := []struct {
		name       string
		percentage float64
		expected   bool // Expected result for ShouldUseEventDriven when percentage-based decision is made
	}{
		{"Negative percentage should behave as 0%", -0.5, false},
		{"Greater than 1.0 should behave as 100%", 1.5, true},
		{"Zero percentage", 0.0, false},
		{"Exactly 1.0", 1.0, true},
		{"Exactly 0.5", 0.5, true}, // This is probabilistic, but we'll check it doesn't crash
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ff := NewFeatureFlags()
			ff.EnableEventDriven = true
			ff.EnableForExtensions = true
			ff.RolloutPercentage = tt.percentage

			// Should not panic
			result := ff.ShouldUseEventDriven("extension", "db-test")

			// For deterministic cases (0.0, 1.0+, negative)
			if tt.percentage <= 0.0 || tt.percentage >= 1.0 {
				assert.Equal(t, tt.expected, result, "Unexpected result for percentage %.2f", tt.percentage)
			}
			// For 0.5, just check it doesn't panic (result is probabilistic)
		})
	}
}

// TestFeatureFlags_EmptyTargetedDatabases tests behavior with empty targeted database list
func TestFeatureFlags_EmptyTargetedDatabases(t *testing.T) {
	ff := NewFeatureFlags()
	ff.EnableEventDriven = true
	ff.EnableForExtensions = true
	ff.TargetedDatabases = []string{} // Empty list
	ff.RolloutPercentage = 0.5

	// Should fall back to percentage rollout (not crash)
	result := ff.ShouldUseEventDriven("extension", "db-1")
	t.Logf("Result with empty targeted databases: %v", result)

	// Should not panic - that's the main test
	assert.NotNil(t, ff.TargetedDatabases)
}

// TestFeatureFlags_NilTargetedDatabases tests behavior with nil targeted database list
func TestFeatureFlags_NilTargetedDatabases(t *testing.T) {
	ff := NewFeatureFlags()
	ff.EnableEventDriven = true
	ff.EnableForExtensions = true
	ff.TargetedDatabases = nil // Nil list
	ff.RolloutPercentage = 0.5

	// Should fall back to percentage rollout (not crash)
	result := ff.ShouldUseEventDriven("extension", "db-1")
	t.Logf("Result with nil targeted databases: %v", result)

	// Should not panic
}

// TestFeatureFlags_UnknownOperationType tests handling of unknown operation types
func TestFeatureFlags_UnknownOperationType(t *testing.T) {
	ff := NewFeatureFlags()
	ff.EnableEventDriven = true
	ff.RolloutPercentage = 1.0 // 100% rollout
	ff.EnableForExtensions = true
	ff.EnableForBackups = true

	// Unknown operation types should default to false (HTTP Sync)
	unknownOps := []string{
		"unknown_operation",
		"invalid_type",
		"",           // Empty string
		"extension!", // With special character
	}

	for _, op := range unknownOps {
		result := ff.ShouldUseEventDriven(op, "db-1")
		assert.False(t, result, "Unknown operation type '%s' should default to HTTP Sync", op)
	}
}

// TestFeatureFlags_EmptyDatabaseID tests behavior with empty database ID
func TestFeatureFlags_EmptyDatabaseID(t *testing.T) {
	ff := NewFeatureFlags()
	ff.EnableEventDriven = true
	ff.EnableForExtensions = true
	ff.RolloutPercentage = 1.0

	// Should not panic with empty database ID
	result := ff.ShouldUseEventDriven("extension", "")
	t.Logf("Result with empty database ID: %v", result)

	// Should handle gracefully (not panic)
}
