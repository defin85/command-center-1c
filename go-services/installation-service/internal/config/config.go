package config

import (
	"fmt"
	"os"
	"strconv"

	"gopkg.in/yaml.v3"
)

// RACConfig holds RAC CLI configuration
type RACConfig struct {
	Path           string `yaml:"path"`
	TimeoutSeconds int    `yaml:"timeout_seconds"`
}

// APIServerConfig holds HTTP API server configuration
type APIServerConfig struct {
	Port                   int `yaml:"port"`
	ShutdownTimeoutSeconds int `yaml:"shutdown_timeout_seconds"`
}

// Config holds application configuration
type Config struct {
	// RAC configuration
	RAC RACConfig `yaml:"rac"`

	// API Server configuration
	APIServer APIServerConfig `yaml:"api_server"`

	// Logging configuration
	LogLevel  string `yaml:"log_level"`
	LogFormat string `yaml:"log_format"`
}

// LoadFromFile loads configuration from YAML file
func LoadFromFile(filename string) (*Config, error) {
	data, err := os.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	// Override with environment variables if present
	cfg.applyEnvOverrides()

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &cfg, nil
}

// LoadFromEnv loads configuration from environment variables with defaults
func LoadFromEnv() *Config {
	cfg := &Config{
		RAC: RACConfig{
			Path:           getEnv("RAC_PATH", "C:\\Program Files\\1cv8\\8.3.27.1786\\bin\\rac.exe"),
			TimeoutSeconds: getIntEnv("RAC_TIMEOUT_SECONDS", 180),
		},
		APIServer: APIServerConfig{
			Port:                   getIntEnv("API_SERVER_PORT", 8085),
			ShutdownTimeoutSeconds: getIntEnv("API_SERVER_SHUTDOWN_TIMEOUT", 30),
		},
		LogLevel:  getEnv("LOG_LEVEL", "info"),
		LogFormat: getEnv("LOG_FORMAT", "text"),
	}

	return cfg
}

// applyEnvOverrides applies environment variable overrides to the config
func (c *Config) applyEnvOverrides() {
	if val := os.Getenv("RAC_PATH"); val != "" {
		c.RAC.Path = val
	}
	if val := os.Getenv("RAC_TIMEOUT_SECONDS"); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			c.RAC.TimeoutSeconds = intVal
		}
	}
	if val := os.Getenv("API_SERVER_PORT"); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			c.APIServer.Port = intVal
		}
	}
	if val := os.Getenv("API_SERVER_SHUTDOWN_TIMEOUT"); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			c.APIServer.ShutdownTimeoutSeconds = intVal
		}
	}
	if val := os.Getenv("LOG_LEVEL"); val != "" {
		c.LogLevel = val
	}
	if val := os.Getenv("LOG_FORMAT"); val != "" {
		c.LogFormat = val
	}
}

// Validate validates the configuration
func (c *Config) Validate() error {
	if c.RAC.Path == "" {
		return fmt.Errorf("RAC path is required")
	}
	if c.RAC.TimeoutSeconds <= 0 {
		return fmt.Errorf("RAC timeout must be positive")
	}
	if c.APIServer.Port <= 0 || c.APIServer.Port > 65535 {
		return fmt.Errorf("API server port must be between 1 and 65535")
	}
	if c.APIServer.ShutdownTimeoutSeconds <= 0 {
		return fmt.Errorf("API server shutdown timeout must be positive")
	}
	return nil
}

// Helper functions

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}
