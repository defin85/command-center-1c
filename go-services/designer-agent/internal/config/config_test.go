package config

import (
	"os"
	"testing"
	"time"
)

func TestLoad(t *testing.T) {
	// Save original env
	originalEnv := map[string]string{
		"SERVER_HOST":          os.Getenv("SERVER_HOST"),
		"DESIGNER_AGENT_PORT":  os.Getenv("DESIGNER_AGENT_PORT"),
		"REDIS_HOST":           os.Getenv("REDIS_HOST"),
		"REDIS_PORT":           os.Getenv("REDIS_PORT"),
		"REDIS_PASSWORD":       os.Getenv("REDIS_PASSWORD"),
		"REDIS_DB":             os.Getenv("REDIS_DB"),
		"SSH_MAX_CONNECTIONS":  os.Getenv("SSH_MAX_CONNECTIONS"),
		"SSH_CONNECT_TIMEOUT":  os.Getenv("SSH_CONNECT_TIMEOUT"),
		"SSH_COMMAND_TIMEOUT":  os.Getenv("SSH_COMMAND_TIMEOUT"),
		"REDIS_PUBSUB_ENABLED": os.Getenv("REDIS_PUBSUB_ENABLED"),
		"LOG_LEVEL":            os.Getenv("LOG_LEVEL"),
	}

	// Restore env after test
	defer func() {
		for k, v := range originalEnv {
			if v == "" {
				os.Unsetenv(k)
			} else {
				os.Setenv(k, v)
			}
		}
	}()

	tests := []struct {
		name    string
		envVars map[string]string
		wantErr bool
		check   func(*testing.T, *Config)
	}{
		{
			name: "default values",
			envVars: map[string]string{
				"SERVER_HOST":         "",
				"DESIGNER_AGENT_PORT": "",
				"REDIS_HOST":          "",
				"REDIS_PORT":          "",
				"LOG_LEVEL":           "",
			},
			wantErr: false,
			check: func(t *testing.T, cfg *Config) {
				if cfg.Server.Host != "0.0.0.0" {
					t.Errorf("Server.Host = %s, want 0.0.0.0", cfg.Server.Host)
				}
				if cfg.Server.Port != 8190 {
					t.Errorf("Server.Port = %d, want 8190", cfg.Server.Port)
				}
				if cfg.Redis.Host != "localhost" {
					t.Errorf("Redis.Host = %s, want localhost", cfg.Redis.Host)
				}
				if cfg.Redis.Port != "6379" {
					t.Errorf("Redis.Port = %s, want 6379", cfg.Redis.Port)
				}
				if cfg.SSH.MaxConnections != 5 {
					t.Errorf("SSH.MaxConnections = %d, want 5", cfg.SSH.MaxConnections)
				}
				if cfg.Log.Level != "info" {
					t.Errorf("Log.Level = %s, want info", cfg.Log.Level)
				}
			},
		},
		{
			name: "custom values",
			envVars: map[string]string{
				"SERVER_HOST":          "127.0.0.1",
				"DESIGNER_AGENT_PORT":  "9000",
				"REDIS_HOST":           "redis.example.com",
				"REDIS_PORT":           "6380",
				"REDIS_PASSWORD":       "secret",
				"REDIS_DB":             "1",
				"SSH_MAX_CONNECTIONS":  "10",
				"SSH_CONNECT_TIMEOUT":  "60s",
				"SSH_COMMAND_TIMEOUT":  "600s",
				"REDIS_PUBSUB_ENABLED": "true",
				"LOG_LEVEL":            "debug",
			},
			wantErr: false,
			check: func(t *testing.T, cfg *Config) {
				if cfg.Server.Host != "127.0.0.1" {
					t.Errorf("Server.Host = %s, want 127.0.0.1", cfg.Server.Host)
				}
				if cfg.Server.Port != 9000 {
					t.Errorf("Server.Port = %d, want 9000", cfg.Server.Port)
				}
				if cfg.Redis.Host != "redis.example.com" {
					t.Errorf("Redis.Host = %s, want redis.example.com", cfg.Redis.Host)
				}
				if cfg.Redis.Port != "6380" {
					t.Errorf("Redis.Port = %s, want 6380", cfg.Redis.Port)
				}
				if cfg.Redis.Password != "secret" {
					t.Errorf("Redis.Password = %s, want secret", cfg.Redis.Password)
				}
				if cfg.Redis.DB != 1 {
					t.Errorf("Redis.DB = %d, want 1", cfg.Redis.DB)
				}
				if cfg.SSH.MaxConnections != 10 {
					t.Errorf("SSH.MaxConnections = %d, want 10", cfg.SSH.MaxConnections)
				}
				if cfg.SSH.ConnectTimeout != 60*time.Second {
					t.Errorf("SSH.ConnectTimeout = %v, want 60s", cfg.SSH.ConnectTimeout)
				}
				if cfg.SSH.CommandTimeout != 600*time.Second {
					t.Errorf("SSH.CommandTimeout = %v, want 600s", cfg.SSH.CommandTimeout)
				}
				if !cfg.Monitor.PubSubEnabled {
					t.Error("Monitor.PubSubEnabled should be true")
				}
				if cfg.Log.Level != "debug" {
					t.Errorf("Log.Level = %s, want debug", cfg.Log.Level)
				}
			},
		},
		{
			name: "invalid port - too low",
			envVars: map[string]string{
				"DESIGNER_AGENT_PORT": "0",
			},
			wantErr: true,
		},
		{
			name: "invalid port - too high",
			envVars: map[string]string{
				"DESIGNER_AGENT_PORT": "70000",
			},
			wantErr: true,
		},
		{
			name: "invalid ssh max connections",
			envVars: map[string]string{
				"SSH_MAX_CONNECTIONS": "0",
			},
			wantErr: true,
		},
		{
			name: "invalid ssh max connections - too high",
			envVars: map[string]string{
				"SSH_MAX_CONNECTIONS": "200",
			},
			wantErr: true,
		},
		{
			name: "invalid ssh connect timeout",
			envVars: map[string]string{
				"SSH_CONNECT_TIMEOUT": "1s",
			},
			wantErr: true,
		},
		{
			name: "invalid log level",
			envVars: map[string]string{
				"LOG_LEVEL": "invalid",
			},
			wantErr: true,
		},
		{
			name: "invalid keepalive interval",
			envVars: map[string]string{
				"SSH_KEEPALIVE_INTERVAL": "5s",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Clear env
			for k := range originalEnv {
				os.Unsetenv(k)
			}

			// Set test env
			for k, v := range tt.envVars {
				if v != "" {
					os.Setenv(k, v)
				}
			}

			cfg, err := Load()
			if (err != nil) != tt.wantErr {
				t.Errorf("Load() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr && tt.check != nil {
				tt.check(t, cfg)
			}
		})
	}
}

func TestConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  *Config
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid config",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: false,
		},
		{
			name: "invalid port - too low",
			config: &Config{
				Server: ServerConfig{
					Port: 0,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SERVER_PORT must be between 1 and 65535",
		},
		{
			name: "invalid port - too high",
			config: &Config{
				Server: ServerConfig{
					Port: 70000,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SERVER_PORT must be between 1 and 65535",
		},
		{
			name: "invalid ssh max connections - too low",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    0,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SSH_MAX_CONNECTIONS must be between 1 and 100",
		},
		{
			name: "invalid ssh max connections - too high",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    150,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SSH_MAX_CONNECTIONS must be between 1 and 100",
		},
		{
			name: "invalid ssh connect timeout",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    2 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SSH_CONNECT_TIMEOUT must be at least 5 seconds",
		},
		{
			name: "invalid keepalive interval",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 5 * time.Second,
				},
				Log: LogConfig{
					Level: "info",
				},
			},
			wantErr: true,
			errMsg:  "SSH_KEEPALIVE_INTERVAL must be at least 10 seconds",
		},
		{
			name: "invalid log level",
			config: &Config{
				Server: ServerConfig{
					Port: 8190,
				},
				SSH: SSHConfig{
					MaxConnections:    5,
					ConnectTimeout:    30 * time.Second,
					KeepAliveInterval: 30 * time.Second,
				},
				Log: LogConfig{
					Level: "invalid",
				},
			},
			wantErr: true,
			errMsg:  "LOG_LEVEL must be one of: debug, info, warn, error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if tt.wantErr && tt.errMsg != "" && err.Error() != tt.errMsg {
				t.Errorf("Validate() error message = %v, want %v", err.Error(), tt.errMsg)
			}
		})
	}
}

func TestRedisConfig_Addr(t *testing.T) {
	tests := []struct {
		name   string
		config RedisConfig
		want   string
	}{
		{
			name: "default",
			config: RedisConfig{
				Host: "localhost",
				Port: "6379",
			},
			want: "localhost:6379",
		},
		{
			name: "custom host and port",
			config: RedisConfig{
				Host: "redis.example.com",
				Port: "6380",
			},
			want: "redis.example.com:6380",
		},
		{
			name: "ip address",
			config: RedisConfig{
				Host: "192.168.1.100",
				Port: "6379",
			},
			want: "192.168.1.100:6379",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.config.Addr()
			if got != tt.want {
				t.Errorf("Addr() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestDefaultValues(t *testing.T) {
	// Clear all env variables
	envVars := []string{
		"SERVER_HOST", "DESIGNER_AGENT_PORT", "REDIS_HOST", "REDIS_PORT",
		"SSH_MAX_CONNECTIONS", "SSH_CONNECT_TIMEOUT", "SSH_COMMAND_TIMEOUT",
		"SSH_KEEPALIVE_INTERVAL", "SSH_KEEPALIVE_TIMEOUT", "SSH_IDLE_TIMEOUT",
		"SSH_CLEANUP_INTERVAL", "REDIS_PUBSUB_ENABLED", "LOG_LEVEL",
	}

	for _, k := range envVars {
		os.Unsetenv(k)
	}

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() failed: %v", err)
	}

	// Check default values
	if cfg.Server.ReadTimeout != 10*time.Second {
		t.Errorf("Server.ReadTimeout = %v, want 10s", cfg.Server.ReadTimeout)
	}

	if cfg.Server.WriteTimeout != 300*time.Second {
		t.Errorf("Server.WriteTimeout = %v, want 300s", cfg.Server.WriteTimeout)
	}

	if cfg.Server.ShutdownTimeout != 30*time.Second {
		t.Errorf("Server.ShutdownTimeout = %v, want 30s", cfg.Server.ShutdownTimeout)
	}

	if cfg.SSH.ConnectTimeout != 30*time.Second {
		t.Errorf("SSH.ConnectTimeout = %v, want 30s", cfg.SSH.ConnectTimeout)
	}

	if cfg.SSH.CommandTimeout != 300*time.Second {
		t.Errorf("SSH.CommandTimeout = %v, want 300s", cfg.SSH.CommandTimeout)
	}

	if cfg.SSH.KeepAliveInterval != 30*time.Second {
		t.Errorf("SSH.KeepAliveInterval = %v, want 30s", cfg.SSH.KeepAliveInterval)
	}

	if cfg.SSH.KeepAliveTimeout != 15*time.Second {
		t.Errorf("SSH.KeepAliveTimeout = %v, want 15s", cfg.SSH.KeepAliveTimeout)
	}

	if cfg.SSH.IdleTimeout != 10*time.Minute {
		t.Errorf("SSH.IdleTimeout = %v, want 10m", cfg.SSH.IdleTimeout)
	}

	if cfg.SSH.CleanupInterval != 1*time.Minute {
		t.Errorf("SSH.CleanupInterval = %v, want 1m", cfg.SSH.CleanupInterval)
	}

	if cfg.Monitor.PubSubEnabled {
		t.Error("Monitor.PubSubEnabled should be false by default")
	}

	if cfg.Redis.DB != 0 {
		t.Errorf("Redis.DB = %d, want 0", cfg.Redis.DB)
	}
}
