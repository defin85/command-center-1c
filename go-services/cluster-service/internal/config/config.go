package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Server ServerConfig
	GRPC   GRPCConfig
	Log    LogConfig
}

type ServerConfig struct {
	Host            string
	Port            int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

type GRPCConfig struct {
	GatewayAddr    string
	ConnTimeout    time.Duration
	RequestTimeout time.Duration
}

type LogConfig struct {
	Level string
}

func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            getEnv("SERVER_HOST", "0.0.0.0"),
			Port:            getEnvInt("SERVER_PORT", 8088),
			ReadTimeout:     getEnvDuration("SERVER_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:    getEnvDuration("SERVER_WRITE_TIMEOUT", 10*time.Second),
			ShutdownTimeout: getEnvDuration("SERVER_SHUTDOWN_TIMEOUT", 30*time.Second),
		},
		GRPC: GRPCConfig{
			GatewayAddr:    getEnv("GRPC_GATEWAY_ADDR", "localhost:9999"),
			ConnTimeout:    getEnvDuration("GRPC_CONN_TIMEOUT", 5*time.Second),
			RequestTimeout: getEnvDuration("GRPC_REQUEST_TIMEOUT", 10*time.Second),
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
	if c.GRPC.GatewayAddr == "" {
		return fmt.Errorf("GRPC_GATEWAY_ADDR is required")
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
