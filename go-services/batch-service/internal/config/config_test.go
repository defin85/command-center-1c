package config

import (
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// TestLoadDefaultClusterRequestTimeout verifies default timeout is 30 seconds
func TestLoadDefaultClusterRequestTimeout(t *testing.T) {
	// Clear any existing env vars
	os.Unsetenv("CLUSTER_REQUEST_TIMEOUT")

	cfg := Load()

	assert.Equal(t, 30*time.Second, cfg.ClusterRequestTimeout,
		"Default CLUSTER_REQUEST_TIMEOUT should be 30 seconds")
	t.Log("Default timeout correctly set to 30s")
}

// TestLoadCustomClusterRequestTimeout verifies custom timeout from env var
func TestLoadCustomClusterRequestTimeout(t *testing.T) {
	testCases := []struct {
		name      string
		envValue  string
		expected  time.Duration
	}{
		{
			name:     "10 seconds",
			envValue: "10",
			expected: 10 * time.Second,
		},
		{
			name:     "60 seconds",
			envValue: "60",
			expected: 60 * time.Second,
		},
		{
			name:     "5 seconds",
			envValue: "5",
			expected: 5 * time.Second,
		},
		{
			name:     "300 seconds",
			envValue: "300",
			expected: 300 * time.Second,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Set env var
			os.Setenv("CLUSTER_REQUEST_TIMEOUT", tc.envValue)
			defer os.Unsetenv("CLUSTER_REQUEST_TIMEOUT")

			cfg := Load()

			assert.Equal(t, tc.expected, cfg.ClusterRequestTimeout,
				"CLUSTER_REQUEST_TIMEOUT=%s should be parsed as %v", tc.envValue, tc.expected)
		})
	}
}

// TestLoadCircuitBreakerTimeoutIsDouble verifies circuit breaker timeout is 2x request timeout
// This test is informational - the actual circuit breaker timeout is set in client.go
func TestLoadCircuitBreakerTimeoutCalculation(t *testing.T) {
	os.Setenv("CLUSTER_REQUEST_TIMEOUT", "30")
	defer os.Unsetenv("CLUSTER_REQUEST_TIMEOUT")

	cfg := Load()

	requestTimeout := cfg.ClusterRequestTimeout
	expectedCircuitBreakerTimeout := requestTimeout * 2

	assert.Equal(t, 30*time.Second, requestTimeout)
	assert.Equal(t, 60*time.Second, expectedCircuitBreakerTimeout,
		"Circuit breaker timeout should be 2x request timeout")

	t.Logf("Request timeout: %v, Circuit breaker timeout: %v",
		requestTimeout, expectedCircuitBreakerTimeout)
}

// TestGetDurationEnv tests duration parsing from environment
func TestGetDurationEnv(t *testing.T) {
	testCases := []struct {
		name          string
		envVar        string
		envValue      string
		defaultValue  time.Duration
		expectedValue time.Duration
	}{
		{
			name:          "env var set to 10",
			envVar:        "TEST_TIMEOUT_1",
			envValue:      "10",
			defaultValue:  30 * time.Second,
			expectedValue: 10 * time.Second,
		},
		{
			name:          "env var not set, use default",
			envVar:        "TEST_TIMEOUT_2_NOT_SET",
			envValue:      "",
			defaultValue:  45 * time.Second,
			expectedValue: 45 * time.Second,
		},
		{
			name:          "env var invalid, use default",
			envVar:        "TEST_TIMEOUT_3",
			envValue:      "invalid",
			defaultValue:  50 * time.Second,
			expectedValue: 50 * time.Second,
		},
		{
			name:          "env var zero",
			envVar:        "TEST_TIMEOUT_4",
			envValue:      "0",
			defaultValue:  60 * time.Second,
			expectedValue: 0 * time.Second,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Set or clear env var
			if tc.envValue != "" {
				os.Setenv(tc.envVar, tc.envValue)
			} else {
				os.Unsetenv(tc.envVar)
			}
			defer os.Unsetenv(tc.envVar)

			result := getDurationEnv(tc.envVar, tc.defaultValue)

			assert.Equal(t, tc.expectedValue, result,
				"getDurationEnv(%s=%q, %v) should return %v",
				tc.envVar, tc.envValue, tc.defaultValue, tc.expectedValue)
		})
	}
}

// TestLoadAllRequiredConfigs verifies all required configs are loaded
func TestLoadAllRequiredConfigs(t *testing.T) {
	cfg := Load()

	// Verify all required fields are set
	assert.NotEmpty(t, cfg.Server.Host)
	assert.NotEmpty(t, cfg.Server.Port)
	assert.NotEmpty(t, cfg.OrchestratorURL)
	assert.NotEmpty(t, cfg.ClusterServiceURL)
	assert.NotEqual(t, 0, cfg.ClusterRequestTimeout)
	assert.NotEmpty(t, cfg.V8.ExePath)
	assert.NotEqual(t, 0, cfg.V8.DefaultTimeout)

	t.Log("All required configs loaded successfully")
}

// TestLoadDefaultValues verifies sensible defaults
func TestLoadDefaultValues(t *testing.T) {
	// Clear relevant env vars
	os.Unsetenv("CLUSTER_REQUEST_TIMEOUT")
	os.Unsetenv("CLUSTER_SERVICE_URL")
	os.Unsetenv("SERVER_PORT")

	cfg := Load()

	// Verify defaults (ras-adapter on port 8188, not deprecated cluster-service on 8088)
	assert.Equal(t, "http://localhost:8188", cfg.ClusterServiceURL,
		"Default CLUSTER_SERVICE_URL should be http://localhost:8188 (ras-adapter)")
	assert.Equal(t, "8187", cfg.Server.Port,
		"Default SERVER_PORT should be 8187")
	assert.Equal(t, 30*time.Second, cfg.ClusterRequestTimeout,
		"Default CLUSTER_REQUEST_TIMEOUT should be 30s")

	t.Log("Defaults correctly applied")
}

// TestLoadServerConfiguration verifies server config
func TestLoadServerConfiguration(t *testing.T) {
	// Clear env vars
	os.Unsetenv("SERVER_HOST")
	os.Unsetenv("SERVER_PORT")
	os.Unsetenv("SERVER_READ_TIMEOUT")
	os.Unsetenv("SERVER_WRITE_TIMEOUT")

	cfg := Load()

	assert.NotEmpty(t, cfg.Server.Host)
	assert.NotEmpty(t, cfg.Server.Port)
	assert.NotEqual(t, 0, cfg.Server.ReadTimeout)
	assert.NotEqual(t, 0, cfg.Server.WriteTimeout)

	t.Log("Server configuration loaded successfully")
}

// TestClusterServiceURLConfiguration verifies cluster service configuration
func TestClusterServiceURLConfiguration(t *testing.T) {
	testCases := []struct {
		name        string
		envValue    string
		expectedURL string
	}{
		{
			name:        "default URL",
			envValue:    "",
			expectedURL: "http://localhost:8188",
		},
		{
			name:        "custom localhost with different port",
			envValue:    "http://localhost:9000",
			expectedURL: "http://localhost:9000",
		},
		{
			name:        "remote host",
			envValue:    "http://cluster-service.example.com:8088",
			expectedURL: "http://cluster-service.example.com:8088",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.envValue != "" {
				os.Setenv("CLUSTER_SERVICE_URL", tc.envValue)
			} else {
				os.Unsetenv("CLUSTER_SERVICE_URL")
			}
			defer os.Unsetenv("CLUSTER_SERVICE_URL")

			cfg := Load()

			assert.Equal(t, tc.expectedURL, cfg.ClusterServiceURL,
				"CLUSTER_SERVICE_URL configuration should be %s", tc.expectedURL)
		})
	}
}

// TestStorageConfiguration verifies storage configuration
func TestStorageConfiguration(t *testing.T) {
	cfg := Load()

	assert.NotEmpty(t, cfg.Storage.Path)
	assert.Greater(t, cfg.Storage.RetentionVersions, 0)

	t.Logf("Storage configured at: %s (retention: %d versions)",
		cfg.Storage.Path, cfg.Storage.RetentionVersions)
}

// TestBackupConfiguration verifies backup configuration
func TestBackupConfiguration(t *testing.T) {
	cfg := Load()

	assert.NotEmpty(t, cfg.Backup.Path)
	assert.Greater(t, cfg.Backup.RetentionBackups, 0)

	t.Logf("Backups configured at: %s (retention: %d backups)",
		cfg.Backup.Path, cfg.Backup.RetentionBackups)
}

// TestV8ExecutorConfiguration verifies v8 executor configuration
func TestV8ExecutorConfiguration(t *testing.T) {
	cfg := Load()

	assert.NotEmpty(t, cfg.V8.ExePath, "V8 exe path should not be empty")
	assert.NotEqual(t, 0, cfg.V8.DefaultTimeout, "V8 default timeout should not be zero")
	assert.Greater(t, cfg.V8.DefaultTimeout, time.Minute, "V8 timeout should be > 1 minute")

	t.Logf("V8 Executor configured: %s (timeout: %v)",
		cfg.V8.ExePath, cfg.V8.DefaultTimeout)
}

// TestGetEnvFunction verifies string environment variable loading
func TestGetEnvFunction(t *testing.T) {
	testCases := []struct {
		name         string
		envVar       string
		envValue     string
		defaultValue string
		expected     string
	}{
		{
			name:         "env var set",
			envVar:       "TEST_STRING_1",
			envValue:     "custom-value",
			defaultValue: "default-value",
			expected:     "custom-value",
		},
		{
			name:         "env var not set",
			envVar:       "TEST_STRING_2_NOT_SET",
			envValue:     "",
			defaultValue: "default-value",
			expected:     "default-value",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.envValue != "" {
				os.Setenv(tc.envVar, tc.envValue)
			} else {
				os.Unsetenv(tc.envVar)
			}
			defer os.Unsetenv(tc.envVar)

			result := getEnv(tc.envVar, tc.defaultValue)

			assert.Equal(t, tc.expected, result,
				"getEnv(%s, %q) should return %q", tc.envVar, tc.defaultValue, tc.expected)
		})
	}
}

// TestGetIntEnvFunction verifies integer environment variable loading
func TestGetIntEnvFunction(t *testing.T) {
	testCases := []struct {
		name         string
		envVar       string
		envValue     string
		defaultValue int
		expected     int
	}{
		{
			name:         "env var set to 42",
			envVar:       "TEST_INT_1",
			envValue:     "42",
			defaultValue: 10,
			expected:     42,
		},
		{
			name:         "env var not set",
			envVar:       "TEST_INT_2_NOT_SET",
			envValue:     "",
			defaultValue: 10,
			expected:     10,
		},
		{
			name:         "env var invalid",
			envVar:       "TEST_INT_3",
			envValue:     "not-a-number",
			defaultValue: 10,
			expected:     10,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.envValue != "" {
				os.Setenv(tc.envVar, tc.envValue)
			} else {
				os.Unsetenv(tc.envVar)
			}
			defer os.Unsetenv(tc.envVar)

			result := getIntEnv(tc.envVar, tc.defaultValue)

			assert.Equal(t, tc.expected, result,
				"getIntEnv(%s, %d) should return %d", tc.envVar, tc.defaultValue, tc.expected)
		})
	}
}

// TestClusterRequestTimeoutEdgeCases tests edge cases for timeout configuration
func TestClusterRequestTimeoutEdgeCases(t *testing.T) {
	testCases := []struct {
		name     string
		envValue string
		expected time.Duration
	}{
		{
			name:     "very short timeout (1s)",
			envValue: "1",
			expected: 1 * time.Second,
		},
		{
			name:     "very long timeout (3600s = 1h)",
			envValue: "3600",
			expected: 3600 * time.Second,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			os.Setenv("CLUSTER_REQUEST_TIMEOUT", tc.envValue)
			defer os.Unsetenv("CLUSTER_REQUEST_TIMEOUT")

			cfg := Load()

			assert.Equal(t, tc.expected, cfg.ClusterRequestTimeout,
				"CLUSTER_REQUEST_TIMEOUT=%s should be %v", tc.envValue, tc.expected)
		})
	}
}

// TestGetBoolEnvFunction verifies boolean environment variable loading
func TestGetBoolEnvFunction(t *testing.T) {
	testCases := []struct {
		name         string
		envVar       string
		envValue     string
		defaultValue bool
		expected     bool
	}{
		{
			name:         "env var set to true",
			envVar:       "TEST_BOOL_1",
			envValue:     "true",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "env var set to TRUE",
			envVar:       "TEST_BOOL_2",
			envValue:     "TRUE",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "env var set to 1",
			envVar:       "TEST_BOOL_3",
			envValue:     "1",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "env var set to yes",
			envVar:       "TEST_BOOL_4",
			envValue:     "yes",
			defaultValue: false,
			expected:     true,
		},
		{
			name:         "env var set to false",
			envVar:       "TEST_BOOL_5",
			envValue:     "false",
			defaultValue: true,
			expected:     false,
		},
		{
			name:         "env var set to 0",
			envVar:       "TEST_BOOL_6",
			envValue:     "0",
			defaultValue: true,
			expected:     false,
		},
		{
			name:         "env var set to no",
			envVar:       "TEST_BOOL_7",
			envValue:     "no",
			defaultValue: true,
			expected:     false,
		},
		{
			name:         "env var not set, use default true",
			envVar:       "TEST_BOOL_8_NOT_SET",
			envValue:     "",
			defaultValue: true,
			expected:     true,
		},
		{
			name:         "env var not set, use default false",
			envVar:       "TEST_BOOL_9_NOT_SET",
			envValue:     "",
			defaultValue: false,
			expected:     false,
		},
		{
			name:         "env var invalid, use default",
			envVar:       "TEST_BOOL_10",
			envValue:     "invalid",
			defaultValue: true,
			expected:     true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.envValue != "" {
				os.Setenv(tc.envVar, tc.envValue)
			} else {
				os.Unsetenv(tc.envVar)
			}
			defer os.Unsetenv(tc.envVar)

			result := getBoolEnv(tc.envVar, tc.defaultValue)

			assert.Equal(t, tc.expected, result,
				"getBoolEnv(%s=%q, %v) should return %v", tc.envVar, tc.envValue, tc.defaultValue, tc.expected)
		})
	}
}

// TestRedisPubSubEnabledConfiguration verifies Redis Pub/Sub feature toggle
func TestRedisPubSubEnabledConfiguration(t *testing.T) {
	testCases := []struct {
		name     string
		envValue string
		expected bool
	}{
		{
			name:     "default (disabled)",
			envValue: "",
			expected: false,
		},
		{
			name:     "explicitly enabled",
			envValue: "true",
			expected: true,
		},
		{
			name:     "enabled with 1",
			envValue: "1",
			expected: true,
		},
		{
			name:     "explicitly disabled",
			envValue: "false",
			expected: false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.envValue != "" {
				os.Setenv("REDIS_PUBSUB_ENABLED", tc.envValue)
			} else {
				os.Unsetenv("REDIS_PUBSUB_ENABLED")
			}
			defer os.Unsetenv("REDIS_PUBSUB_ENABLED")

			cfg := Load()

			assert.Equal(t, tc.expected, cfg.Redis.PubSubEnabled,
				"REDIS_PUBSUB_ENABLED=%q should result in PubSubEnabled=%v", tc.envValue, tc.expected)
		})
	}
}
