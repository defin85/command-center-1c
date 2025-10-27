package config

import (
	"os"
	"strconv"

	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Redis        RedisConfig        `yaml:"redis"`
	OneC         OneCConfig         `yaml:"onec"`
	Executor     ExecutorConfig     `yaml:"executor"`
	Orchestrator OrchestratorConfig `yaml:"orchestrator"`
	Server       ServerConfig       `yaml:"server"`
	Logging      LoggingConfig      `yaml:"logging"`
}

// RedisConfig contains Redis connection and queue settings
type RedisConfig struct {
	Host            string `yaml:"host"`
	Port            int    `yaml:"port"`
	Password        string `yaml:"password"`
	Queue           string `yaml:"queue"`
	ProgressChannel string `yaml:"progress_channel"`
	DB              int    `yaml:"db"`
	MaxRetries      int    `yaml:"max_retries"`
	RetryDelay      int    `yaml:"retry_delay_seconds"`
}

// OneCConfig contains 1C platform settings
type OneCConfig struct {
	PlatformPath   string `yaml:"platform_path"`
	TimeoutSeconds int    `yaml:"timeout_seconds"`
	ServerName     string `yaml:"server_name"`
	KillTimeout    int    `yaml:"kill_timeout_seconds"`
}

// ExecutorConfig contains worker pool settings
type ExecutorConfig struct {
	MaxParallel            int `yaml:"max_parallel"`
	RetryAttempts          int `yaml:"retry_attempts"`
	RetryDelay             int `yaml:"retry_delay_seconds"`
	RetryBackoffMultiplier int `yaml:"retry_backoff_multiplier"`
	TaskTimeout            int `yaml:"task_timeout_seconds"`
}

// OrchestratorConfig contains orchestrator API settings
type OrchestratorConfig struct {
	APIURL         string `yaml:"api_url"`
	APIToken       string `yaml:"api_token"`
	TimeoutSeconds int    `yaml:"timeout_seconds"`
}

// ServerConfig contains HTTP server settings
type ServerConfig struct {
	HealthCheckPort int `yaml:"health_check_port"`
	ShutdownTimeout int `yaml:"shutdown_timeout_seconds"`
}

// LoggingConfig contains logging settings
type LoggingConfig struct {
	Level      string `yaml:"level"`
	File       string `yaml:"file"`
	MaxSizeMB  int    `yaml:"max_size_mb"`
	MaxBackups int    `yaml:"max_backups"`
	MaxAgeDays int    `yaml:"max_age_days"`
	Compress   bool   `yaml:"compress"`
}

// Load reads configuration from YAML file and applies environment overrides
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}

	// Environment variable overrides
	if host := os.Getenv("REDIS_HOST"); host != "" {
		cfg.Redis.Host = host
	}
	if portStr := os.Getenv("REDIS_PORT"); portStr != "" {
		if port, err := strconv.Atoi(portStr); err == nil {
			cfg.Redis.Port = port
		}
	}
	if password := os.Getenv("REDIS_PASSWORD"); password != "" {
		cfg.Redis.Password = password
	}
	if token := os.Getenv("INSTALLATION_SERVICE_TOKEN"); token != "" {
		cfg.Orchestrator.APIToken = token
	}
	if apiURL := os.Getenv("ORCHESTRATOR_API_URL"); apiURL != "" {
		cfg.Orchestrator.APIURL = apiURL
	}

	return &cfg, nil
}
