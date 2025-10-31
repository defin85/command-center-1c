package config

import (
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoad_WithDefaults(t *testing.T) {
	// Clear environment variables
	clearEnvVars()

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Server defaults
	assert.Equal(t, "0.0.0.0", cfg.Server.Host)
	assert.Equal(t, 8088, cfg.Server.Port)
	assert.Equal(t, 10*time.Second, cfg.Server.ReadTimeout)
	assert.Equal(t, 10*time.Second, cfg.Server.WriteTimeout)
	assert.Equal(t, 30*time.Second, cfg.Server.ShutdownTimeout)

	// GRPC defaults
	assert.Equal(t, "localhost:9999", cfg.GRPC.GatewayAddr)
	assert.Equal(t, 5*time.Second, cfg.GRPC.ConnTimeout)
	assert.Equal(t, 10*time.Second, cfg.GRPC.RequestTimeout)

	// Log defaults
	assert.Equal(t, "info", cfg.Log.Level)
}

func TestLoad_WithCustomEnvVars(t *testing.T) {
	// Set custom environment variables
	os.Setenv("SERVER_HOST", "localhost")
	os.Setenv("SERVER_PORT", "9090")
	os.Setenv("SERVER_READ_TIMEOUT", "15s")
	os.Setenv("SERVER_WRITE_TIMEOUT", "20s")
	os.Setenv("SERVER_SHUTDOWN_TIMEOUT", "45s")
	os.Setenv("GRPC_GATEWAY_ADDR", "gateway:8888")
	os.Setenv("GRPC_CONN_TIMEOUT", "7s")
	os.Setenv("GRPC_REQUEST_TIMEOUT", "12s")
	os.Setenv("LOG_LEVEL", "debug")

	defer clearEnvVars()

	cfg, err := Load()
	require.NoError(t, err)
	require.NotNil(t, cfg)

	// Server custom values
	assert.Equal(t, "localhost", cfg.Server.Host)
	assert.Equal(t, 9090, cfg.Server.Port)
	assert.Equal(t, 15*time.Second, cfg.Server.ReadTimeout)
	assert.Equal(t, 20*time.Second, cfg.Server.WriteTimeout)
	assert.Equal(t, 45*time.Second, cfg.Server.ShutdownTimeout)

	// GRPC custom values
	assert.Equal(t, "gateway:8888", cfg.GRPC.GatewayAddr)
	assert.Equal(t, 7*time.Second, cfg.GRPC.ConnTimeout)
	assert.Equal(t, 12*time.Second, cfg.GRPC.RequestTimeout)

	// Log custom value
	assert.Equal(t, "debug", cfg.Log.Level)
}

func TestLoad_InvalidPort(t *testing.T) {
	os.Setenv("SERVER_PORT", "99999")
	defer clearEnvVars()

	_, err := Load()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "SERVER_PORT must be between 1 and 65535")
}

func TestLoad_EmptyGatewayAddr(t *testing.T) {
	// Создаем конфиг с пустым gateway addr напрямую для тестирования валидации
	cfg := &Config{
		Server: ServerConfig{Port: 8080},
		GRPC:   GRPCConfig{GatewayAddr: ""},
		Log:    LogConfig{Level: "info"},
	}

	err := cfg.Validate()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "GRPC_GATEWAY_ADDR is required")
}

func TestLoad_InvalidLogLevel(t *testing.T) {
	os.Setenv("LOG_LEVEL", "invalid")
	defer clearEnvVars()

	_, err := Load()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "LOG_LEVEL must be one of: debug, info, warn, error")
}

func TestValidate_Success(t *testing.T) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            "0.0.0.0",
			Port:            8080,
			ReadTimeout:     10 * time.Second,
			WriteTimeout:    10 * time.Second,
			ShutdownTimeout: 30 * time.Second,
		},
		GRPC: GRPCConfig{
			GatewayAddr:    "localhost:9999",
			ConnTimeout:    5 * time.Second,
			RequestTimeout: 10 * time.Second,
		},
		Log: LogConfig{
			Level: "info",
		},
	}

	err := cfg.Validate()
	assert.NoError(t, err)
}

func TestValidate_InvalidPort(t *testing.T) {
	tests := []struct {
		name string
		port int
	}{
		{"port too low", 0},
		{"port too high", 65536},
		{"port negative", -1},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &Config{
				Server: ServerConfig{Port: tt.port},
				GRPC:   GRPCConfig{GatewayAddr: "localhost:9999"},
				Log:    LogConfig{Level: "info"},
			}

			err := cfg.Validate()
			require.Error(t, err)
			assert.Contains(t, err.Error(), "SERVER_PORT must be between 1 and 65535")
		})
	}
}

func TestValidate_EmptyGatewayAddr(t *testing.T) {
	cfg := &Config{
		Server: ServerConfig{Port: 8080},
		GRPC:   GRPCConfig{GatewayAddr: ""},
		Log:    LogConfig{Level: "info"},
	}

	err := cfg.Validate()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "GRPC_GATEWAY_ADDR is required")
}

func TestValidate_InvalidLogLevel(t *testing.T) {
	tests := []string{"trace", "verbose", "warning", "fatal", ""}

	for _, level := range tests {
		t.Run("log_level_"+level, func(t *testing.T) {
			cfg := &Config{
				Server: ServerConfig{Port: 8080},
				GRPC:   GRPCConfig{GatewayAddr: "localhost:9999"},
				Log:    LogConfig{Level: level},
			}

			err := cfg.Validate()
			require.Error(t, err)
			assert.Contains(t, err.Error(), "LOG_LEVEL must be one of: debug, info, warn, error")
		})
	}
}

func TestValidate_AllValidLogLevels(t *testing.T) {
	validLevels := []string{"debug", "info", "warn", "error"}

	for _, level := range validLevels {
		t.Run("log_level_"+level, func(t *testing.T) {
			cfg := &Config{
				Server: ServerConfig{Port: 8080},
				GRPC:   GRPCConfig{GatewayAddr: "localhost:9999"},
				Log:    LogConfig{Level: level},
			}

			err := cfg.Validate()
			assert.NoError(t, err)
		})
	}
}

func TestGetEnv(t *testing.T) {
	tests := []struct {
		name         string
		key          string
		defaultValue string
		envValue     string
		expected     string
	}{
		{"returns default when not set", "TEST_VAR", "default", "", "default"},
		{"returns env value when set", "TEST_VAR", "default", "custom", "custom"},
		{"returns empty env value", "TEST_VAR", "default", "", "default"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.envValue != "" {
				os.Setenv(tt.key, tt.envValue)
				defer os.Unsetenv(tt.key)
			} else {
				os.Unsetenv(tt.key)
			}

			result := getEnv(tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetEnvInt(t *testing.T) {
	tests := []struct {
		name         string
		key          string
		defaultValue int
		envValue     string
		expected     int
	}{
		{"returns default when not set", "TEST_INT", 100, "", 100},
		{"returns env value when valid int", "TEST_INT", 100, "200", 200},
		{"returns default when invalid int", "TEST_INT", 100, "invalid", 100},
		{"returns default when empty", "TEST_INT", 100, "", 100},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.envValue != "" {
				os.Setenv(tt.key, tt.envValue)
				defer os.Unsetenv(tt.key)
			} else {
				os.Unsetenv(tt.key)
			}

			result := getEnvInt(tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetEnvDuration(t *testing.T) {
	tests := []struct {
		name         string
		key          string
		defaultValue time.Duration
		envValue     string
		expected     time.Duration
	}{
		{"returns default when not set", "TEST_DURATION", 10 * time.Second, "", 10 * time.Second},
		{"returns env value when valid duration", "TEST_DURATION", 10 * time.Second, "15s", 15 * time.Second},
		{"returns default when invalid duration", "TEST_DURATION", 10 * time.Second, "invalid", 10 * time.Second},
		{"returns default when empty", "TEST_DURATION", 10 * time.Second, "", 10 * time.Second},
		{"supports minutes", "TEST_DURATION", 10 * time.Second, "2m", 2 * time.Minute},
		{"supports hours", "TEST_DURATION", 10 * time.Second, "1h", 1 * time.Hour},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.envValue != "" {
				os.Setenv(tt.key, tt.envValue)
				defer os.Unsetenv(tt.key)
			} else {
				os.Unsetenv(tt.key)
			}

			result := getEnvDuration(tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// Helper function to clear all environment variables
func clearEnvVars() {
	os.Unsetenv("SERVER_HOST")
	os.Unsetenv("SERVER_PORT")
	os.Unsetenv("SERVER_READ_TIMEOUT")
	os.Unsetenv("SERVER_WRITE_TIMEOUT")
	os.Unsetenv("SERVER_SHUTDOWN_TIMEOUT")
	os.Unsetenv("GRPC_GATEWAY_ADDR")
	os.Unsetenv("GRPC_CONN_TIMEOUT")
	os.Unsetenv("GRPC_REQUEST_TIMEOUT")
	os.Unsetenv("LOG_LEVEL")
}
