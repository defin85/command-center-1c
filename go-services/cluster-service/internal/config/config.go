package config

import (
	"os"
)

// Config holds application configuration
type Config struct {
	// HTTP Server
	ServerHost string
	ServerPort string

	// gRPC Gateway (ras-grpc-gw)
	GRPCGatewayAddr string

	// Logging
	LogLevel string
}

// Load loads configuration from environment variables
func Load() *Config {
	// TODO: Implement proper configuration loading
	// - Add validation
	// - Add defaults
	return &Config{
		ServerHost:      getEnv("SERVER_HOST", "0.0.0.0"),
		ServerPort:      getEnv("SERVER_PORT", "8088"),
		GRPCGatewayAddr: getEnv("GRPC_GATEWAY_ADDR", "localhost:9999"),
		LogLevel:        getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
