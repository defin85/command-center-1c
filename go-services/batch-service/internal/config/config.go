package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds the application configuration
type Config struct {
	Server                ServerConfig
	GRPC                  GRPCConfig
	V8                    V8Config
	Storage               StorageConfig
	Backup                BackupConfig
	Redis                 RedisConfig
	OrchestratorURL       string
	ClusterServiceURL     string
	ClusterRequestTimeout time.Duration
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

// StorageConfig holds extension storage configuration
type StorageConfig struct {
	Path              string // Path to extensions storage directory
	RetentionVersions int    // Number of versions to keep (retention policy)
}

// BackupConfig holds backup configuration
type BackupConfig struct {
	Path             string // Path to backups directory
	RetentionBackups int    // Number of backups to keep per extension
}

// RedisConfig holds Redis configuration
type RedisConfig struct {
	Host          string
	Port          string
	Password      string
	DB            int
	PubSubEnabled bool // Feature toggle for Redis Pub/Sub event handlers
}

// Load reads configuration from environment variables
func Load() *Config {
	return &Config{
		Server: ServerConfig{
			Host:         getEnv("SERVER_HOST", "0.0.0.0"),
			Port:         getEnv("BATCH_SERVICE_PORT", "8187"), // Port 8187 - outside Windows reserved range (8013-8112)
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
		Storage: StorageConfig{
			Path:              getEnv("EXTENSION_STORAGE_PATH", "./storage/extensions"),
			RetentionVersions: getIntEnv("RETENTION_VERSIONS", 3),
		},
		Backup: BackupConfig{
			Path:             getEnv("BACKUP_PATH", "./backups"),
			RetentionBackups: getIntEnv("RETENTION_BACKUPS", 5),
		},
		Redis: RedisConfig{
			Host:          getEnv("REDIS_HOST", "localhost"),
			Port:          getEnv("REDIS_PORT", "6379"),
			Password:      getEnv("REDIS_PASSWORD", ""),
			DB:            getIntEnv("REDIS_DB", 0),
			PubSubEnabled: getBoolEnv("REDIS_PUBSUB_ENABLED", false), // Feature toggle, default: false
		},
		OrchestratorURL:       getEnv("ORCHESTRATOR_URL", "http://localhost:8200"),
		ClusterServiceURL:     getEnv("CLUSTER_SERVICE_URL", "http://localhost:8188"), // Port 8188 - outside Windows reserved range
		ClusterRequestTimeout: getDurationEnv("CLUSTER_REQUEST_TIMEOUT", 30*time.Second),
	}
}

// getEnv returns the value of an environment variable or a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getIntEnv returns an int from environment variable or default
func getIntEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
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

// getBoolEnv returns a bool from environment variable or default
// Uses strconv.ParseBool for standard boolean parsing
func getBoolEnv(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		switch strings.ToLower(strings.TrimSpace(value)) {
		case "yes", "y", "on":
			return true
		case "no", "n", "off":
			return false
		}
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}
