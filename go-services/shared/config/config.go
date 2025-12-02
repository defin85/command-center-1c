package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds application configuration
type Config struct {
	// Server configuration
	ServerHost string
	ServerPort string

	// JWT configuration
	JWTSecret     string
	JWTExpireTime time.Duration
	JWTIssuer     string

	// Redis configuration
	RedisHost     string
	RedisPort     string
	RedisPassword string
	RedisDB       int

	// PostgreSQL configuration
	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string
	DBSSLM     string

	// Orchestrator configuration
	OrchestratorURL string

	// Batch Service configuration
	BatchServiceURL string

	// Cluster Service configuration
	ClusterServiceURL string

	// RAS Adapter configuration
	RASAdapterURL string

	// Jaeger configuration
	JaegerURL string

	// API v1 Deprecation configuration
	V1DeprecationEnabled bool
	// V1SunsetDate format: RFC 7231 (e.g., "Sun, 01 Mar 2026 00:00:00 GMT")
	V1SunsetDate string

	// Worker configuration
	WorkerID         string
	WorkerAPIKey     string
	WorkerPoolSize   int
	WorkerMaxRetries int
	WorkerTimeout    time.Duration

	// Logging configuration
	LogLevel  string
	LogFormat string

	// Metrics configuration
	MetricsEnabled bool
	MetricsPort    string

	// Credentials Transport Encryption (AES-256)
	// ВАЖНО: Должен совпадать с Django CREDENTIALS_TRANSPORT_KEY!
	CredentialsTransportKey string

	// CORS configuration
	CORSAllowedOrigins []string
}

// LoadFromEnv loads configuration from environment variables
func LoadFromEnv() *Config {
	return &Config{
		// Server (Port 8180 - outside Windows reserved ranges 7913-8012, 8013-8112)
		ServerHost: getEnv("SERVER_HOST", "0.0.0.0"),
		ServerPort: getEnv("SERVER_PORT", "8180"),

		// JWT
		JWTSecret:     getEnv("JWT_SECRET", "your-secret-key-change-in-production"),
		JWTExpireTime: getDurationEnv("JWT_EXPIRE_TIME", 24*time.Hour),
		JWTIssuer:     getEnv("JWT_ISSUER", "commandcenter1c"),

		// Redis
		RedisHost:     getEnv("REDIS_HOST", "localhost"),
		RedisPort:     getEnv("REDIS_PORT", "6379"),
		RedisPassword: getEnv("REDIS_PASSWORD", ""),
		RedisDB:       getIntEnv("REDIS_DB", 0),

		// PostgreSQL
		DBHost:     getEnv("DB_HOST", "localhost"),
		DBPort:     getEnv("DB_PORT", "5432"),
		DBUser:     getEnv("DB_USER", "commandcenter"),
		DBPassword: getEnv("DB_PASSWORD", "password"),
		DBName:     getEnv("DB_NAME", "commandcenter"),
		DBSSLM:     getEnv("DB_SSLMODE", "disable"),

		// Orchestrator (Port 8200 - outside Windows reserved ranges 7913-8012, 8013-8112)
		OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8200"),

		// Batch Service (Port 8187 - outside Windows reserved range 8013-8112)
		BatchServiceURL: getEnv("BATCH_SERVICE_URL", "http://localhost:8187"),

		// Cluster Service (Port 8188 - outside Windows reserved range 8013-8112)
		ClusterServiceURL: getEnv("CLUSTER_SERVICE_URL", "http://localhost:8188"),

		// RAS Adapter (Port 8188 - outside Windows reserved range 8013-8112)
		RASAdapterURL: getEnv("RAS_ADAPTER_URL", "http://localhost:8188"),

		// Jaeger
		JaegerURL: getEnv("JAEGER_URL", "http://localhost:16686"),

		// API v1 Deprecation
		V1DeprecationEnabled: getBoolEnv("V1_DEPRECATION_ENABLED", true),
		V1SunsetDate:         getEnv("V1_SUNSET_DATE", "Sun, 01 Mar 2026 00:00:00 GMT"),

		// Worker
		WorkerID:         getEnv("WORKER_ID", "worker-1"),
		WorkerAPIKey:     getEnv("WORKER_API_KEY", "dev-worker-key-change-in-production"),
		WorkerPoolSize:   getIntEnv("WORKER_POOL_SIZE", 50),
		WorkerMaxRetries: getIntEnv("WORKER_MAX_RETRIES", 3),
		WorkerTimeout:    getDurationEnv("WORKER_TIMEOUT", 5*time.Minute),

		// Logging
		LogLevel:  getEnv("LOG_LEVEL", "info"),
		LogFormat: getEnv("LOG_FORMAT", "text"),

		// Metrics
		MetricsEnabled: getBoolEnv("METRICS_ENABLED", true),
		MetricsPort:    getEnv("METRICS_PORT", "9090"),

		// Credentials Transport Encryption
		CredentialsTransportKey: getEnv("CREDENTIALS_TRANSPORT_KEY", ""),

		// CORS - default allows localhost frontend
		CORSAllowedOrigins: getStringSliceEnv("CORS_ALLOWED_ORIGINS", []string{
			"http://localhost:5173",
			"http://127.0.0.1:5173",
		}),
	}
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

func getBoolEnv(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}

func getDurationEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}

func getStringSliceEnv(key string, defaultValue []string) []string {
	if value := os.Getenv(key); value != "" {
		// Split by comma and trim whitespace
		parts := make([]string, 0)
		for _, part := range strings.Split(value, ",") {
			trimmed := strings.TrimSpace(part)
			if trimmed != "" {
				parts = append(parts, trimmed)
			}
		}
		if len(parts) > 0 {
			return parts
		}
	}
	return defaultValue
}
