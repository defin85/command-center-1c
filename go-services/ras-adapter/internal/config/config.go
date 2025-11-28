package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Server  ServerConfig
	RAS     RASConfig
	Redis   RedisConfig
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

type RASConfig struct {
	ServerAddr     string
	ConnTimeout    time.Duration
	RequestTimeout time.Duration
	MaxConnections int
}

type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
}

type MonitorConfig struct {
	SessionMonitorInterval time.Duration
	PubSubEnabled          bool
}

type LogConfig struct {
	Level string
}

func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            getEnv("SERVER_HOST", "0.0.0.0"),
			Port:            getEnvInt("RAS_ADAPTER_PORT", 8188), // Port 8188 - outside Windows reserved range (8013-8112)
			ReadTimeout:     getEnvDuration("SERVER_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:    getEnvDuration("SERVER_WRITE_TIMEOUT", 10*time.Second),
			ShutdownTimeout: getEnvDuration("SERVER_SHUTDOWN_TIMEOUT", 30*time.Second),
		},
		RAS: RASConfig{
			ServerAddr:     getEnv("RAS_SERVER_ADDR", "localhost:1545"),
			ConnTimeout:    getEnvDuration("RAS_CONN_TIMEOUT", 5*time.Second),
			RequestTimeout: getEnvDuration("RAS_REQUEST_TIMEOUT", 10*time.Second),
			MaxConnections: getEnvInt("RAS_MAX_CONNECTIONS", 10),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost"),
			Port:     getEnv("REDIS_PORT", "6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       getEnvInt("REDIS_DB", 0),
		},
		Monitor: MonitorConfig{
			SessionMonitorInterval: getEnvDuration("SESSION_MONITOR_INTERVAL", 1*time.Second),
			PubSubEnabled:          getBoolEnv("REDIS_PUBSUB_ENABLED", true),
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
	if c.RAS.ServerAddr == "" {
		return fmt.Errorf("RAS_SERVER_ADDR is required")
	}
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("SERVER_PORT must be between 1 and 65535")
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
