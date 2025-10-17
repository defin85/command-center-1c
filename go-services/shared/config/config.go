package config

import (
	"os"
	"strconv"
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

	// Worker configuration
	WorkerPoolSize    int
	WorkerMaxRetries  int
	WorkerTimeout     time.Duration

	// Logging configuration
	LogLevel  string
	LogFormat string

	// Metrics configuration
	MetricsEnabled bool
	MetricsPort    string
}

// LoadFromEnv loads configuration from environment variables
func LoadFromEnv() *Config {
	return &Config{
		// Server
		ServerHost: getEnv("SERVER_HOST", "0.0.0.0"),
		ServerPort: getEnv("SERVER_PORT", "8080"),

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

		// Orchestrator
		OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8000"),

		// Worker
		WorkerPoolSize:   getIntEnv("WORKER_POOL_SIZE", 50),
		WorkerMaxRetries: getIntEnv("WORKER_MAX_RETRIES", 3),
		WorkerTimeout:    getDurationEnv("WORKER_TIMEOUT", 5*time.Minute),

		// Logging
		LogLevel:  getEnv("LOG_LEVEL", "info"),
		LogFormat: getEnv("LOG_FORMAT", "text"),

		// Metrics
		MetricsEnabled: getBoolEnv("METRICS_ENABLED", true),
		MetricsPort:    getEnv("METRICS_PORT", "9090"),
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
