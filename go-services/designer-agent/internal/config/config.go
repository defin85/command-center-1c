package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// Config holds all configuration for the designer-agent service.
type Config struct {
	Server  ServerConfig
	Redis   RedisConfig
	SSH     SSHConfig
	Monitor MonitorConfig
	Log     LogConfig
}

// ServerConfig holds HTTP server configuration.
type ServerConfig struct {
	Host            string
	Port            int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

// RedisConfig holds Redis connection configuration.
type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
}

// SSHConfig holds SSH connection pool configuration.
type SSHConfig struct {
	// MaxConnections is the maximum number of SSH connections per host:port
	MaxConnections int

	// ConnectTimeout is the timeout for establishing SSH connection
	ConnectTimeout time.Duration

	// CommandTimeout is the default timeout for executing commands
	CommandTimeout time.Duration

	// KeepAliveInterval is the interval for sending keep-alive packets
	KeepAliveInterval time.Duration

	// KeepAliveTimeout is the timeout for keep-alive response
	KeepAliveTimeout time.Duration

	// IdleTimeout is the duration after which idle connections are closed
	IdleTimeout time.Duration

	// CleanupInterval is the interval for running idle connection cleanup
	CleanupInterval time.Duration
}

// MonitorConfig holds monitoring configuration.
type MonitorConfig struct {
	PubSubEnabled bool
}

// LogConfig holds logging configuration.
type LogConfig struct {
	Level string
}

// Load loads configuration from environment variables.
func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            getEnv("SERVER_HOST", "0.0.0.0"),
			Port:            getEnvInt("DESIGNER_AGENT_PORT", 8190),
			ReadTimeout:     getEnvDuration("SERVER_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:    getEnvDuration("SERVER_WRITE_TIMEOUT", 300*time.Second), // Long for designer operations
			ShutdownTimeout: getEnvDuration("SERVER_SHUTDOWN_TIMEOUT", 30*time.Second),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost"),
			Port:     getEnv("REDIS_PORT", "6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       getEnvInt("REDIS_DB", 0),
		},
		SSH: SSHConfig{
			MaxConnections:    getEnvInt("SSH_MAX_CONNECTIONS", 5),
			ConnectTimeout:    getEnvDuration("SSH_CONNECT_TIMEOUT", 30*time.Second),
			CommandTimeout:    getEnvDuration("SSH_COMMAND_TIMEOUT", 300*time.Second), // 5 min for long operations
			KeepAliveInterval: getEnvDuration("SSH_KEEPALIVE_INTERVAL", 30*time.Second),
			KeepAliveTimeout:  getEnvDuration("SSH_KEEPALIVE_TIMEOUT", 15*time.Second),
			IdleTimeout:       getEnvDuration("SSH_IDLE_TIMEOUT", 10*time.Minute),
			CleanupInterval:   getEnvDuration("SSH_CLEANUP_INTERVAL", 1*time.Minute),
		},
		Monitor: MonitorConfig{
			PubSubEnabled: getBoolEnv("REDIS_PUBSUB_ENABLED", false),
		},
		Log: LogConfig{
			Level: getEnv("LOG_LEVEL", "info"),
		},
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

// Validate validates the configuration.
func (c *Config) Validate() error {
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("SERVER_PORT must be between 1 and 65535")
	}

	if c.SSH.MaxConnections < 1 || c.SSH.MaxConnections > 100 {
		return fmt.Errorf("SSH_MAX_CONNECTIONS must be between 1 and 100")
	}

	if c.SSH.ConnectTimeout < 5*time.Second {
		return fmt.Errorf("SSH_CONNECT_TIMEOUT must be at least 5 seconds")
	}

	if c.SSH.KeepAliveInterval < 10*time.Second {
		return fmt.Errorf("SSH_KEEPALIVE_INTERVAL must be at least 10 seconds")
	}

	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[c.Log.Level] {
		return fmt.Errorf("LOG_LEVEL must be one of: debug, info, warn, error")
	}

	return nil
}

// RedisAddr returns the Redis address string.
func (c *RedisConfig) Addr() string {
	return fmt.Sprintf("%s:%s", c.Host, c.Port)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}

func getBoolEnv(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}
