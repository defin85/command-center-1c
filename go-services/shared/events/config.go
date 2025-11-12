package events

import "time"

// Config contains configuration for event publishing and subscribing
type Config struct {
	// RedisAddr is the Redis server address (e.g., "localhost:6379")
	RedisAddr string

	// RedisPassword is the password for Redis authentication (optional)
	RedisPassword string

	// RedisDB is the Redis database number (default: 0)
	RedisDB int

	// ConsumerGroup is the name of the consumer group for subscribers
	// Multiple subscribers in the same group will load-balance messages
	ConsumerGroup string

	// MaxRetries is the maximum number of retry attempts for failed messages
	MaxRetries int

	// RetryDelay is the delay between retry attempts
	RetryDelay time.Duration

	// MessageTTL is the time-to-live for messages in Redis Streams
	MessageTTL time.Duration

	// MaxLength is the maximum number of messages to keep in a stream (0 = unlimited)
	MaxLength int64

	// ApproximateMaxLength allows Redis to trim the stream approximately
	// This is more efficient than exact trimming
	ApproximateMaxLength bool

	// MaxPayloadSize is the maximum payload size in bytes (default: 1MB)
	MaxPayloadSize int64

	// MaxConcurrentHandlers is the maximum concurrent message handlers (default: 100)
	MaxConcurrentHandlers int

	// EnableAutoReconnect enables automatic reconnection to Redis
	EnableAutoReconnect bool

	// ReconnectInterval is the interval between reconnect attempts
	ReconnectInterval time.Duration

	// MaxReconnectRetries is the maximum reconnect retries (0 = infinite)
	MaxReconnectRetries int
}

// DefaultConfig returns a Config with sensible defaults
func DefaultConfig() *Config {
	return &Config{
		RedisAddr:             "localhost:6379",
		RedisPassword:         "",
		RedisDB:               0,
		ConsumerGroup:         "commandcenter1c",
		MaxRetries:            3,
		RetryDelay:            time.Second * 5,
		MessageTTL:            time.Hour * 24,       // 24 hours
		MaxLength:             10000,                // Keep last 10k messages per stream
		ApproximateMaxLength:  true,
		MaxPayloadSize:        1 * 1024 * 1024,      // 1MB default
		MaxConcurrentHandlers: 100,                  // For 700+ databases, allow 100 concurrent handlers
		EnableAutoReconnect:   true,
		ReconnectInterval:     5 * time.Second,
		MaxReconnectRetries:   0, // Infinite retries
	}
}

// Validate checks if the configuration is valid
func (c *Config) Validate() error {
	if c.RedisAddr == "" {
		return ErrRedisUnavailable
	}

	if c.ConsumerGroup == "" {
		return ErrEmptyConsumerGroup
	}

	if c.MaxRetries < 0 {
		c.MaxRetries = 0
	}

	if c.RetryDelay < 0 {
		c.RetryDelay = 0
	}

	if c.MaxPayloadSize <= 0 {
		c.MaxPayloadSize = 1 * 1024 * 1024 // Default to 1MB
	}

	if c.MaxConcurrentHandlers <= 0 {
		c.MaxConcurrentHandlers = 100 // Default to 100
	}

	return nil
}
