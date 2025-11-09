package config

import (
	"os"
	"strconv"
	"time"
)

// Config holds the application configuration
type Config struct {
	Server         ServerConfig
	GRPC           GRPCConfig
	V8             V8Config
	OrchestratorURL string
}

// ServerConfig holds HTTP server configuration
type ServerConfig struct {
	Host         string
	Port         string
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
}

// GRPCConfig holds gRPC client configuration for ras-grpc-gw
type GRPCConfig struct {
	GatewayAddr string // ras-grpc-gw address (e.g., "localhost:9999")
	Timeout     time.Duration
}

// V8Config holds 1cv8.exe configuration
type V8Config struct {
	ExePath        string        // Path to 1cv8.exe
	DefaultTimeout time.Duration // Default timeout for operations
}

// Load reads configuration from environment variables
func Load() *Config {
	return &Config{
		Server: ServerConfig{
			Host:         getEnv("SERVER_HOST", "0.0.0.0"),
			Port:         getEnv("SERVER_PORT", "8087"),
			ReadTimeout:  getDurationEnv("SERVER_READ_TIMEOUT", 30*time.Second),
			WriteTimeout: getDurationEnv("SERVER_WRITE_TIMEOUT", 30*time.Second),
		},
		GRPC: GRPCConfig{
			GatewayAddr: getEnv("GRPC_GATEWAY_ADDR", "localhost:9999"),
			Timeout:     getDurationEnv("GRPC_TIMEOUT", 30*time.Second),
		},
		V8: V8Config{
			ExePath:        getEnv("EXE_1CV8_PATH", `C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe`),
			DefaultTimeout: getDurationEnv("V8_DEFAULT_TIMEOUT", 5*time.Minute),
		},
		OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8000"),
	}
}

// getEnv returns the value of an environment variable or a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getDurationEnv returns a duration from environment variable or default
func getDurationEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if seconds, err := strconv.Atoi(value); err == nil {
			return time.Duration(seconds) * time.Second
		}
	}
	return defaultValue
}
