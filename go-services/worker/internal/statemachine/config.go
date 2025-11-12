package statemachine

import (
	"errors"
	"time"
)

// Config holds state machine configuration
type Config struct {
	// Timeouts for each step
	TimeoutLockJobs      time.Duration
	TimeoutTerminate     time.Duration
	TimeoutInstall       time.Duration
	TimeoutUnlock        time.Duration
	TimeoutCompensation  time.Duration

	// Retry configuration
	MaxRetries        int
	RetryInitialDelay time.Duration
	RetryMaxDelay     time.Duration
	RetryMultiplier   float64

	// State persistence
	StateTTL          time.Duration

	// Deduplication
	DeduplicationTTL  time.Duration
}

// DefaultConfig returns default configuration
func DefaultConfig() *Config {
	return &Config{
		// Timeouts
		TimeoutLockJobs:      30 * time.Second,
		TimeoutTerminate:     90 * time.Second,
		TimeoutInstall:       5 * time.Minute,
		TimeoutUnlock:        30 * time.Second,
		TimeoutCompensation:  2 * time.Minute,

		// Retry
		MaxRetries:        3,
		RetryInitialDelay: 1 * time.Second,
		RetryMaxDelay:     30 * time.Second,
		RetryMultiplier:   2.0,

		// Persistence
		StateTTL:          24 * time.Hour,

		// Deduplication
		DeduplicationTTL:  10 * time.Minute,
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
	if c.MaxRetries < 0 {
		return errors.New("max retries cannot be negative")
	}
	return nil
}
