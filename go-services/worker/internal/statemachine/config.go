package statemachine

import (
	"errors"
	"os"
	"strconv"
	"time"

	"go.uber.org/zap"
)

// Logger interface for dependency injection
type configLogger interface {
	Debug(msg string, fields ...zap.Field)
	Warn(msg string, fields ...zap.Field)
}

// Config holds state machine configuration
type Config struct {
	// Timeouts for each step
	TimeoutLockJobs     time.Duration
	TimeoutTerminate    time.Duration
	TimeoutInstall      time.Duration
	TimeoutUnlock       time.Duration
	TimeoutCompensation time.Duration

	// Retry configuration
	MaxRetries        int
	RetryInitialDelay time.Duration
	RetryMaxDelay     time.Duration
	RetryMultiplier   float64

	// State persistence
	StateTTL time.Duration

	// Deduplication
	DeduplicationTTL time.Duration
}

// DefaultConfig returns default configuration
func DefaultConfig() *Config {
	return &Config{
		// Timeouts
		TimeoutLockJobs:     30 * time.Second,
		TimeoutTerminate:    90 * time.Second,
		TimeoutInstall:      5 * time.Minute,
		TimeoutUnlock:       30 * time.Second,
		TimeoutCompensation: 2 * time.Minute,

		// Retry
		MaxRetries:        3,
		RetryInitialDelay: 1 * time.Second,
		RetryMaxDelay:     30 * time.Second,
		RetryMultiplier:   2.0,

		// Persistence
		StateTTL: 24 * time.Hour,

		// Deduplication
		DeduplicationTTL: 10 * time.Minute,
	}
}

// Validate validates configuration
func (c *Config) Validate() error {
	if c.TimeoutLockJobs <= 0 {
		return errors.New("invalid timeout for lock jobs")
	}
	if c.TimeoutTerminate <= 0 {
		return errors.New("invalid timeout for terminate sessions")
	}
	if c.TimeoutInstall <= 0 {
		return errors.New("invalid timeout for install")
	}
	if c.TimeoutUnlock <= 0 {
		return errors.New("invalid timeout for unlock")
	}
	if c.TimeoutCompensation <= 0 {
		return errors.New("invalid timeout for compensation")
	}
	if c.MaxRetries < 0 {
		return errors.New("max retries cannot be negative")
	}
	if c.RetryInitialDelay <= 0 {
		return errors.New("retry initial delay must be positive")
	}
	if c.RetryMaxDelay <= 0 {
		return errors.New("retry max delay must be positive")
	}
	if c.RetryMultiplier <= 0 {
		return errors.New("retry multiplier must be positive")
	}
	if c.StateTTL <= 0 {
		return errors.New("state TTL must be positive")
	}
	if c.DeduplicationTTL <= 0 {
		return errors.New("deduplication TTL must be positive")
	}
	return nil
}

// LoadFromEnv loads configuration from environment variables with defaults.
// Accepts optional logger for debug output; if nil, logging is skipped.
func LoadFromEnv(log configLogger) *Config {
	cfg := DefaultConfig()

	// Timeouts
	cfg.TimeoutLockJobs = getEnvDuration("SM_TIMEOUT_LOCK", cfg.TimeoutLockJobs, log)
	cfg.TimeoutTerminate = getEnvDuration("SM_TIMEOUT_TERMINATE", cfg.TimeoutTerminate, log)
	cfg.TimeoutInstall = getEnvDuration("SM_TIMEOUT_INSTALL", cfg.TimeoutInstall, log)
	cfg.TimeoutUnlock = getEnvDuration("SM_TIMEOUT_UNLOCK", cfg.TimeoutUnlock, log)
	cfg.TimeoutCompensation = getEnvDuration("SM_TIMEOUT_COMPENSATION", cfg.TimeoutCompensation, log)

	// Retry configuration
	cfg.MaxRetries = getEnvInt("SM_MAX_RETRIES", cfg.MaxRetries, log)
	cfg.RetryInitialDelay = getEnvDuration("SM_RETRY_INITIAL_DELAY", cfg.RetryInitialDelay, log)
	cfg.RetryMaxDelay = getEnvDuration("SM_RETRY_MAX_DELAY", cfg.RetryMaxDelay, log)
	cfg.RetryMultiplier = getEnvFloat64("SM_RETRY_MULTIPLIER", cfg.RetryMultiplier, log)

	// State persistence
	cfg.StateTTL = getEnvDuration("SM_STATE_TTL", cfg.StateTTL, log)

	// Deduplication
	cfg.DeduplicationTTL = getEnvDuration("SM_DEDUPLICATION_TTL", cfg.DeduplicationTTL, log)

	// Log loaded configuration summary
	if log != nil {
		log.Debug("state machine config loaded from environment",
			zap.Duration("timeout_lock", cfg.TimeoutLockJobs),
			zap.Duration("timeout_terminate", cfg.TimeoutTerminate),
			zap.Duration("timeout_install", cfg.TimeoutInstall),
			zap.Duration("timeout_unlock", cfg.TimeoutUnlock),
			zap.Duration("timeout_compensation", cfg.TimeoutCompensation),
			zap.Int("max_retries", cfg.MaxRetries),
			zap.Duration("retry_initial_delay", cfg.RetryInitialDelay),
			zap.Duration("retry_max_delay", cfg.RetryMaxDelay),
			zap.Float64("retry_multiplier", cfg.RetryMultiplier),
			zap.Duration("state_ttl", cfg.StateTTL),
			zap.Duration("deduplication_ttl", cfg.DeduplicationTTL),
		)
	}

	return cfg
}

// getEnvDuration parses duration from environment variable.
// Returns defaultValue if env var is not set or invalid.
func getEnvDuration(key string, defaultValue time.Duration, log configLogger) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}

	duration, err := time.ParseDuration(value)
	if err != nil {
		if log != nil {
			log.Warn("invalid duration in environment variable, using default",
				zap.String("key", key),
				zap.String("value", value),
				zap.Duration("default", defaultValue),
				zap.Error(err),
			)
		}
		return defaultValue
	}

	if duration <= 0 {
		if log != nil {
			log.Warn("duration must be positive, using default",
				zap.String("key", key),
				zap.Duration("value", duration),
				zap.Duration("default", defaultValue),
			)
		}
		return defaultValue
	}

	return duration
}

// getEnvInt parses integer from environment variable.
// Returns defaultValue if env var is not set or invalid.
func getEnvInt(key string, defaultValue int, log configLogger) int {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}

	intValue, err := strconv.Atoi(value)
	if err != nil {
		if log != nil {
			log.Warn("invalid integer in environment variable, using default",
				zap.String("key", key),
				zap.String("value", value),
				zap.Int("default", defaultValue),
				zap.Error(err),
			)
		}
		return defaultValue
	}

	if intValue < 0 {
		if log != nil {
			log.Warn("integer cannot be negative, using default",
				zap.String("key", key),
				zap.Int("value", intValue),
				zap.Int("default", defaultValue),
			)
		}
		return defaultValue
	}

	return intValue
}

// getEnvFloat64 parses float64 from environment variable.
// Returns defaultValue if env var is not set or invalid.
func getEnvFloat64(key string, defaultValue float64, log configLogger) float64 {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}

	floatValue, err := strconv.ParseFloat(value, 64)
	if err != nil {
		if log != nil {
			log.Warn("invalid float in environment variable, using default",
				zap.String("key", key),
				zap.String("value", value),
				zap.Float64("default", defaultValue),
				zap.Error(err),
			)
		}
		return defaultValue
	}

	if floatValue <= 0 {
		if log != nil {
			log.Warn("float must be positive, using default",
				zap.String("key", key),
				zap.Float64("value", floatValue),
				zap.Float64("default", defaultValue),
			)
		}
		return defaultValue
	}

	return floatValue
}
