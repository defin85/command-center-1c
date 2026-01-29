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
	// Internal API token for service-to-service calls to Django Orchestrator.
	// Used as `X-Internal-Token` header for `/api/v2/internal/*`.
	InternalAPIToken string

	// Jaeger configuration
	JaegerURL string

	// API v1 Deprecation configuration
	V1DeprecationEnabled bool
	// V1SunsetDate format: RFC 7231 (e.g., "Sun, 01 Mar 2026 00:00:00 GMT")
	V1SunsetDate string

	// Worker configuration
	WorkerID            string
	WorkerAPIKey        string
	WorkerPoolSize      int
	WorkerMaxRetries    int
	WorkerTimeout       time.Duration
	WorkerStreamName    string
	WorkerConsumerGroup string

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

	// Template Engine configuration
	EnableGoTemplateEngine bool
	TemplateRenderTimeout  time.Duration

	// Feature Flags
	// UseStreamsClusterInfo enables Redis Streams for cluster info resolution (primary method).
	// When enabled, Worker first tries to get cluster info via Streams, then falls back to HTTP.
	// When disabled, only HTTP is used (for rollback scenarios).
	UseStreamsClusterInfo bool
	// StreamsClusterInfoTimeout is the timeout for Streams-based cluster info requests.
	StreamsClusterInfoTimeout time.Duration

	// StreamsCredentialsTimeout is the timeout for Streams-based credentials requests.
	StreamsCredentialsTimeout time.Duration

	// Timeline recorder configuration
	TimelineQueueSize   int
	TimelineWorkerCount int
	TimelineDropOnFull  bool
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
		OrchestratorURL:  getEnv("ORCHESTRATOR_URL", "http://localhost:8200"),
		InternalAPIToken: getEnv("INTERNAL_API_TOKEN", ""),

		// Jaeger
		JaegerURL: getEnv("JAEGER_URL", "http://localhost:16686"),

		// API v1 Deprecation
		V1DeprecationEnabled: getBoolEnv("V1_DEPRECATION_ENABLED", true),
		V1SunsetDate:         getEnv("V1_SUNSET_DATE", "Sun, 01 Mar 2026 00:00:00 GMT"),

		// Worker
		WorkerID:            getEnv("WORKER_ID", "worker-1"),
		WorkerAPIKey:        getEnv("WORKER_API_KEY", "dev-worker-key-change-in-production"),
		WorkerPoolSize:      getIntEnv("WORKER_POOL_SIZE", 50),
		WorkerMaxRetries:    getIntEnv("WORKER_MAX_RETRIES", 3),
		WorkerTimeout:       getDurationEnv("WORKER_TIMEOUT", 5*time.Minute),
		WorkerStreamName:    getEnv("WORKER_STREAM_NAME", "commands:worker:operations"),
		WorkerConsumerGroup: getEnv("WORKER_CONSUMER_GROUP", "worker-state-machine"),

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

		// Template Engine - defaults to disabled (Python fallback only)
		EnableGoTemplateEngine: getBoolEnv("ENABLE_GO_TEMPLATE_ENGINE", false),
		TemplateRenderTimeout:  getDurationEnv("TEMPLATE_RENDER_TIMEOUT", 5*time.Second),

		// Feature Flags
		UseStreamsClusterInfo:     getBoolEnv("USE_STREAMS_CLUSTER_INFO", true),
		StreamsClusterInfoTimeout: getPositiveDurationEnv("STREAMS_CLUSTER_INFO_TIMEOUT", 5*time.Second),
		StreamsCredentialsTimeout: getPositiveDurationEnv("STREAMS_CREDENTIALS_TIMEOUT", 5*time.Second),

		// Timeline recorder
		TimelineQueueSize:   getIntEnv("TIMELINE_QUEUE_SIZE", 10000),
		TimelineWorkerCount: getIntEnv("TIMELINE_WORKER_COUNT", 4),
		TimelineDropOnFull:  getBoolEnv("TIMELINE_DROP_ON_FULL", true),
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

func getPositiveDurationEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil && duration > 0 {
			return duration
		}
	}
	return defaultValue
}
