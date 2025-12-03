package statemachine

import (
	"os"
	"testing"
	"time"

	"go.uber.org/zap"
)

// mockLogger implements configLogger interface for testing
type mockLogger struct {
	debugCalls []string
	warnCalls  []string
}

func (m *mockLogger) Debug(msg string, fields ...zap.Field) {
	m.debugCalls = append(m.debugCalls, msg)
}

func (m *mockLogger) Warn(msg string, fields ...zap.Field) {
	m.warnCalls = append(m.warnCalls, msg)
}

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	// Verify default timeouts
	if cfg.TimeoutLockJobs != 30*time.Second {
		t.Errorf("expected TimeoutLockJobs=30s, got %v", cfg.TimeoutLockJobs)
	}
	if cfg.TimeoutTerminate != 90*time.Second {
		t.Errorf("expected TimeoutTerminate=90s, got %v", cfg.TimeoutTerminate)
	}
	if cfg.TimeoutInstall != 5*time.Minute {
		t.Errorf("expected TimeoutInstall=5m, got %v", cfg.TimeoutInstall)
	}
	if cfg.TimeoutUnlock != 30*time.Second {
		t.Errorf("expected TimeoutUnlock=30s, got %v", cfg.TimeoutUnlock)
	}
	if cfg.TimeoutCompensation != 2*time.Minute {
		t.Errorf("expected TimeoutCompensation=2m, got %v", cfg.TimeoutCompensation)
	}

	// Verify retry defaults
	if cfg.MaxRetries != 3 {
		t.Errorf("expected MaxRetries=3, got %v", cfg.MaxRetries)
	}
	if cfg.RetryInitialDelay != 1*time.Second {
		t.Errorf("expected RetryInitialDelay=1s, got %v", cfg.RetryInitialDelay)
	}
	if cfg.RetryMaxDelay != 30*time.Second {
		t.Errorf("expected RetryMaxDelay=30s, got %v", cfg.RetryMaxDelay)
	}
	if cfg.RetryMultiplier != 2.0 {
		t.Errorf("expected RetryMultiplier=2.0, got %v", cfg.RetryMultiplier)
	}

	// Verify persistence defaults
	if cfg.StateTTL != 24*time.Hour {
		t.Errorf("expected StateTTL=24h, got %v", cfg.StateTTL)
	}
	if cfg.DeduplicationTTL != 10*time.Minute {
		t.Errorf("expected DeduplicationTTL=10m, got %v", cfg.DeduplicationTTL)
	}
}

func TestConfigValidate(t *testing.T) {
	tests := []struct {
		name        string
		modifyFn    func(*Config)
		expectError bool
		errorMsg    string
	}{
		{
			name:        "valid default config",
			modifyFn:    func(c *Config) {},
			expectError: false,
		},
		{
			name:        "invalid timeout lock",
			modifyFn:    func(c *Config) { c.TimeoutLockJobs = 0 },
			expectError: true,
			errorMsg:    "invalid timeout for lock jobs",
		},
		{
			name:        "invalid timeout terminate",
			modifyFn:    func(c *Config) { c.TimeoutTerminate = -1 },
			expectError: true,
			errorMsg:    "invalid timeout for terminate sessions",
		},
		{
			name:        "invalid timeout install",
			modifyFn:    func(c *Config) { c.TimeoutInstall = 0 },
			expectError: true,
			errorMsg:    "invalid timeout for install",
		},
		{
			name:        "invalid timeout unlock",
			modifyFn:    func(c *Config) { c.TimeoutUnlock = 0 },
			expectError: true,
			errorMsg:    "invalid timeout for unlock",
		},
		{
			name:        "invalid timeout compensation",
			modifyFn:    func(c *Config) { c.TimeoutCompensation = 0 },
			expectError: true,
			errorMsg:    "invalid timeout for compensation",
		},
		{
			name:        "negative max retries",
			modifyFn:    func(c *Config) { c.MaxRetries = -1 },
			expectError: true,
			errorMsg:    "max retries cannot be negative",
		},
		{
			name:        "zero max retries is valid",
			modifyFn:    func(c *Config) { c.MaxRetries = 0 },
			expectError: false,
		},
		{
			name:        "invalid retry initial delay",
			modifyFn:    func(c *Config) { c.RetryInitialDelay = 0 },
			expectError: true,
			errorMsg:    "retry initial delay must be positive",
		},
		{
			name:        "invalid retry max delay",
			modifyFn:    func(c *Config) { c.RetryMaxDelay = 0 },
			expectError: true,
			errorMsg:    "retry max delay must be positive",
		},
		{
			name:        "invalid retry multiplier",
			modifyFn:    func(c *Config) { c.RetryMultiplier = 0 },
			expectError: true,
			errorMsg:    "retry multiplier must be positive",
		},
		{
			name:        "invalid state TTL",
			modifyFn:    func(c *Config) { c.StateTTL = 0 },
			expectError: true,
			errorMsg:    "state TTL must be positive",
		},
		{
			name:        "invalid deduplication TTL",
			modifyFn:    func(c *Config) { c.DeduplicationTTL = 0 },
			expectError: true,
			errorMsg:    "deduplication TTL must be positive",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := DefaultConfig()
			tt.modifyFn(cfg)

			err := cfg.Validate()
			if tt.expectError {
				if err == nil {
					t.Errorf("expected error but got nil")
				} else if err.Error() != tt.errorMsg {
					t.Errorf("expected error %q, got %q", tt.errorMsg, err.Error())
				}
			} else {
				if err != nil {
					t.Errorf("expected no error but got %v", err)
				}
			}
		})
	}
}

func TestLoadFromEnv_DefaultValues(t *testing.T) {
	// Clear any existing env vars
	clearEnvVars()
	defer clearEnvVars()

	cfg := LoadFromEnv(nil)

	// Should return default config when no env vars set
	defaults := DefaultConfig()

	if cfg.TimeoutLockJobs != defaults.TimeoutLockJobs {
		t.Errorf("TimeoutLockJobs: expected %v, got %v", defaults.TimeoutLockJobs, cfg.TimeoutLockJobs)
	}
	if cfg.TimeoutTerminate != defaults.TimeoutTerminate {
		t.Errorf("TimeoutTerminate: expected %v, got %v", defaults.TimeoutTerminate, cfg.TimeoutTerminate)
	}
	if cfg.TimeoutInstall != defaults.TimeoutInstall {
		t.Errorf("TimeoutInstall: expected %v, got %v", defaults.TimeoutInstall, cfg.TimeoutInstall)
	}
	if cfg.MaxRetries != defaults.MaxRetries {
		t.Errorf("MaxRetries: expected %v, got %v", defaults.MaxRetries, cfg.MaxRetries)
	}
}

func TestLoadFromEnv_CustomValues(t *testing.T) {
	clearEnvVars()
	defer clearEnvVars()

	// Set custom values
	os.Setenv("SM_TIMEOUT_LOCK", "60s")
	os.Setenv("SM_TIMEOUT_TERMINATE", "120s")
	os.Setenv("SM_TIMEOUT_INSTALL", "10m")
	os.Setenv("SM_TIMEOUT_UNLOCK", "45s")
	os.Setenv("SM_TIMEOUT_COMPENSATION", "3m")
	os.Setenv("SM_MAX_RETRIES", "5")
	os.Setenv("SM_RETRY_INITIAL_DELAY", "2s")
	os.Setenv("SM_RETRY_MAX_DELAY", "1m")
	os.Setenv("SM_RETRY_MULTIPLIER", "1.5")
	os.Setenv("SM_STATE_TTL", "48h")
	os.Setenv("SM_DEDUPLICATION_TTL", "15m")

	log := &mockLogger{}
	cfg := LoadFromEnv(log)

	// Verify custom values are loaded
	if cfg.TimeoutLockJobs != 60*time.Second {
		t.Errorf("TimeoutLockJobs: expected 60s, got %v", cfg.TimeoutLockJobs)
	}
	if cfg.TimeoutTerminate != 120*time.Second {
		t.Errorf("TimeoutTerminate: expected 120s, got %v", cfg.TimeoutTerminate)
	}
	if cfg.TimeoutInstall != 10*time.Minute {
		t.Errorf("TimeoutInstall: expected 10m, got %v", cfg.TimeoutInstall)
	}
	if cfg.TimeoutUnlock != 45*time.Second {
		t.Errorf("TimeoutUnlock: expected 45s, got %v", cfg.TimeoutUnlock)
	}
	if cfg.TimeoutCompensation != 3*time.Minute {
		t.Errorf("TimeoutCompensation: expected 3m, got %v", cfg.TimeoutCompensation)
	}
	if cfg.MaxRetries != 5 {
		t.Errorf("MaxRetries: expected 5, got %v", cfg.MaxRetries)
	}
	if cfg.RetryInitialDelay != 2*time.Second {
		t.Errorf("RetryInitialDelay: expected 2s, got %v", cfg.RetryInitialDelay)
	}
	if cfg.RetryMaxDelay != 1*time.Minute {
		t.Errorf("RetryMaxDelay: expected 1m, got %v", cfg.RetryMaxDelay)
	}
	if cfg.RetryMultiplier != 1.5 {
		t.Errorf("RetryMultiplier: expected 1.5, got %v", cfg.RetryMultiplier)
	}
	if cfg.StateTTL != 48*time.Hour {
		t.Errorf("StateTTL: expected 48h, got %v", cfg.StateTTL)
	}
	if cfg.DeduplicationTTL != 15*time.Minute {
		t.Errorf("DeduplicationTTL: expected 15m, got %v", cfg.DeduplicationTTL)
	}

	// Verify debug logging was called
	if len(log.debugCalls) == 0 {
		t.Error("expected debug logging to be called")
	}
}

func TestLoadFromEnv_InvalidValues(t *testing.T) {
	clearEnvVars()
	defer clearEnvVars()

	// Set invalid values
	os.Setenv("SM_TIMEOUT_LOCK", "invalid")
	os.Setenv("SM_MAX_RETRIES", "not_a_number")
	os.Setenv("SM_RETRY_MULTIPLIER", "bad_float")

	log := &mockLogger{}
	cfg := LoadFromEnv(log)

	defaults := DefaultConfig()

	// Should fall back to defaults for invalid values
	if cfg.TimeoutLockJobs != defaults.TimeoutLockJobs {
		t.Errorf("TimeoutLockJobs: expected default %v, got %v", defaults.TimeoutLockJobs, cfg.TimeoutLockJobs)
	}
	if cfg.MaxRetries != defaults.MaxRetries {
		t.Errorf("MaxRetries: expected default %v, got %v", defaults.MaxRetries, cfg.MaxRetries)
	}
	if cfg.RetryMultiplier != defaults.RetryMultiplier {
		t.Errorf("RetryMultiplier: expected default %v, got %v", defaults.RetryMultiplier, cfg.RetryMultiplier)
	}

	// Verify warnings were logged
	if len(log.warnCalls) < 3 {
		t.Errorf("expected at least 3 warnings, got %d", len(log.warnCalls))
	}
}

func TestLoadFromEnv_NegativeValues(t *testing.T) {
	clearEnvVars()
	defer clearEnvVars()

	// Set negative/zero values
	os.Setenv("SM_TIMEOUT_LOCK", "-10s")
	os.Setenv("SM_MAX_RETRIES", "-1")
	os.Setenv("SM_RETRY_MULTIPLIER", "0")

	log := &mockLogger{}
	cfg := LoadFromEnv(log)

	defaults := DefaultConfig()

	// Should fall back to defaults for negative/zero values
	if cfg.TimeoutLockJobs != defaults.TimeoutLockJobs {
		t.Errorf("TimeoutLockJobs: expected default %v, got %v", defaults.TimeoutLockJobs, cfg.TimeoutLockJobs)
	}
	if cfg.MaxRetries != defaults.MaxRetries {
		t.Errorf("MaxRetries: expected default %v, got %v", defaults.MaxRetries, cfg.MaxRetries)
	}
	if cfg.RetryMultiplier != defaults.RetryMultiplier {
		t.Errorf("RetryMultiplier: expected default %v, got %v", defaults.RetryMultiplier, cfg.RetryMultiplier)
	}

	// Verify warnings were logged
	if len(log.warnCalls) < 3 {
		t.Errorf("expected at least 3 warnings, got %d", len(log.warnCalls))
	}
}

func TestLoadFromEnv_NilLogger(t *testing.T) {
	clearEnvVars()
	defer clearEnvVars()

	// Set invalid value
	os.Setenv("SM_TIMEOUT_LOCK", "invalid")

	// Should not panic with nil logger
	cfg := LoadFromEnv(nil)

	defaults := DefaultConfig()
	if cfg.TimeoutLockJobs != defaults.TimeoutLockJobs {
		t.Errorf("expected default value with nil logger")
	}
}

func TestGetEnvDuration(t *testing.T) {
	tests := []struct {
		name         string
		envValue     string
		defaultValue time.Duration
		expected     time.Duration
		expectWarn   bool
	}{
		{
			name:         "empty env returns default",
			envValue:     "",
			defaultValue: 30 * time.Second,
			expected:     30 * time.Second,
			expectWarn:   false,
		},
		{
			name:         "valid duration",
			envValue:     "1m30s",
			defaultValue: 30 * time.Second,
			expected:     90 * time.Second,
			expectWarn:   false,
		},
		{
			name:         "invalid duration returns default",
			envValue:     "not_a_duration",
			defaultValue: 30 * time.Second,
			expected:     30 * time.Second,
			expectWarn:   true,
		},
		{
			name:         "negative duration returns default",
			envValue:     "-5s",
			defaultValue: 30 * time.Second,
			expected:     30 * time.Second,
			expectWarn:   true,
		},
		{
			name:         "zero duration returns default",
			envValue:     "0s",
			defaultValue: 30 * time.Second,
			expected:     30 * time.Second,
			expectWarn:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_DURATION"
			os.Unsetenv(key)
			if tt.envValue != "" {
				os.Setenv(key, tt.envValue)
			}
			defer os.Unsetenv(key)

			log := &mockLogger{}
			result := getEnvDuration(key, tt.defaultValue, log)

			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
			if tt.expectWarn && len(log.warnCalls) == 0 {
				t.Error("expected warning to be logged")
			}
			if !tt.expectWarn && len(log.warnCalls) > 0 {
				t.Error("unexpected warning logged")
			}
		})
	}
}

func TestGetEnvInt(t *testing.T) {
	tests := []struct {
		name         string
		envValue     string
		defaultValue int
		expected     int
		expectWarn   bool
	}{
		{
			name:         "empty env returns default",
			envValue:     "",
			defaultValue: 3,
			expected:     3,
			expectWarn:   false,
		},
		{
			name:         "valid int",
			envValue:     "10",
			defaultValue: 3,
			expected:     10,
			expectWarn:   false,
		},
		{
			name:         "invalid int returns default",
			envValue:     "not_a_number",
			defaultValue: 3,
			expected:     3,
			expectWarn:   true,
		},
		{
			name:         "negative int returns default",
			envValue:     "-5",
			defaultValue: 3,
			expected:     3,
			expectWarn:   true,
		},
		{
			name:         "zero int is valid",
			envValue:     "0",
			defaultValue: 3,
			expected:     0,
			expectWarn:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_INT"
			os.Unsetenv(key)
			if tt.envValue != "" {
				os.Setenv(key, tt.envValue)
			}
			defer os.Unsetenv(key)

			log := &mockLogger{}
			result := getEnvInt(key, tt.defaultValue, log)

			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
			if tt.expectWarn && len(log.warnCalls) == 0 {
				t.Error("expected warning to be logged")
			}
			if !tt.expectWarn && len(log.warnCalls) > 0 {
				t.Error("unexpected warning logged")
			}
		})
	}
}

func TestGetEnvFloat64(t *testing.T) {
	tests := []struct {
		name         string
		envValue     string
		defaultValue float64
		expected     float64
		expectWarn   bool
	}{
		{
			name:         "empty env returns default",
			envValue:     "",
			defaultValue: 2.0,
			expected:     2.0,
			expectWarn:   false,
		},
		{
			name:         "valid float",
			envValue:     "1.5",
			defaultValue: 2.0,
			expected:     1.5,
			expectWarn:   false,
		},
		{
			name:         "invalid float returns default",
			envValue:     "not_a_float",
			defaultValue: 2.0,
			expected:     2.0,
			expectWarn:   true,
		},
		{
			name:         "negative float returns default",
			envValue:     "-1.5",
			defaultValue: 2.0,
			expected:     2.0,
			expectWarn:   true,
		},
		{
			name:         "zero float returns default",
			envValue:     "0",
			defaultValue: 2.0,
			expected:     2.0,
			expectWarn:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := "TEST_FLOAT"
			os.Unsetenv(key)
			if tt.envValue != "" {
				os.Setenv(key, tt.envValue)
			}
			defer os.Unsetenv(key)

			log := &mockLogger{}
			result := getEnvFloat64(key, tt.defaultValue, log)

			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
			if tt.expectWarn && len(log.warnCalls) == 0 {
				t.Error("expected warning to be logged")
			}
			if !tt.expectWarn && len(log.warnCalls) > 0 {
				t.Error("unexpected warning logged")
			}
		})
	}
}

// Helper to clear all SM_ env vars
func clearEnvVars() {
	envVars := []string{
		"SM_TIMEOUT_LOCK",
		"SM_TIMEOUT_TERMINATE",
		"SM_TIMEOUT_INSTALL",
		"SM_TIMEOUT_UNLOCK",
		"SM_TIMEOUT_COMPENSATION",
		"SM_MAX_RETRIES",
		"SM_RETRY_INITIAL_DELAY",
		"SM_RETRY_MAX_DELAY",
		"SM_RETRY_MULTIPLIER",
		"SM_STATE_TTL",
		"SM_DEDUPLICATION_TTL",
	}
	for _, v := range envVars {
		os.Unsetenv(v)
	}
}
