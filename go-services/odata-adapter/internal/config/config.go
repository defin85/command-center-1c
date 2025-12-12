package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Server  ServerConfig
	Redis   RedisConfig
	OData   ODataConfig
	Monitor MonitorConfig
	Log     LogConfig
}

type ServerConfig struct {
	Host            string
	Port            int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
}

type ODataConfig struct {
	DefaultTimeout  time.Duration
	MaxBatchSize    int
	MaxBatchTimeout time.Duration
}

type MonitorConfig struct {
	PubSubEnabled bool
}

type LogConfig struct {
	Level string
}

func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            getEnv("SERVER_HOST", "0.0.0.0"),
			Port:            getEnvInt("ODATA_ADAPTER_PORT", 8189),
			ReadTimeout:     getEnvDuration("SERVER_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:    getEnvDuration("SERVER_WRITE_TIMEOUT", 15*time.Second),
			ShutdownTimeout: getEnvDuration("SERVER_SHUTDOWN_TIMEOUT", 30*time.Second),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost"),
			Port:     getEnv("REDIS_PORT", "6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       getEnvInt("REDIS_DB", 0),
		},
		OData: ODataConfig{
			DefaultTimeout:  getEnvDuration("ODATA_DEFAULT_TIMEOUT", 10*time.Second),
			MaxBatchSize:    getEnvInt("ODATA_MAX_BATCH_SIZE", 500),
			MaxBatchTimeout: getEnvDuration("ODATA_MAX_BATCH_TIMEOUT", 14*time.Second), // Critical: < 15s for 1C transactions
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

func (c *Config) Validate() error {
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("SERVER_PORT must be between 1 and 65535")
	}
	if c.OData.MaxBatchSize < 1 || c.OData.MaxBatchSize > 1000 {
		return fmt.Errorf("ODATA_MAX_BATCH_SIZE must be between 1 and 1000")
	}
	if c.OData.MaxBatchTimeout >= 15*time.Second {
		return fmt.Errorf("ODATA_MAX_BATCH_TIMEOUT must be less than 15 seconds (1C transaction limit)")
	}
	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[c.Log.Level] {
		return fmt.Errorf("LOG_LEVEL must be one of: debug, info, warn, error")
	}
	return nil
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
