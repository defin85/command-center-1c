package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Server      ServerConfig
	RAS         RASConfig
	Redis       RedisConfig
	Monitor     MonitorConfig
	Log         LogConfig
	Credentials CredentialsConfig
}

type ServerConfig struct {
	Host            string
	Port            int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

type RASConfig struct {
	ServerAddr     string
	ConnTimeout    time.Duration
	RequestTimeout time.Duration
	MaxConnections int
}

type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
}

type MonitorConfig struct {
	SessionMonitorInterval time.Duration
	PubSubEnabled          bool
}

type LogConfig struct {
	Level string
}

type CredentialsConfig struct {
	OrchestratorURL string
	JWTSecret       string
	JWTIssuer       string
	TransportKey    string // 32-byte hex key for AES-GCM-256
}

func Load() (*Config, error) {
	cfg := &Config{
		Server: ServerConfig{
			Host:            getEnv("SERVER_HOST", "0.0.0.0"),
			Port:            getEnvInt("RAS_ADAPTER_PORT", 8188), // Port 8188 - outside Windows reserved range (8013-8112)
			ReadTimeout:     getEnvDuration("SERVER_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:    getEnvDuration("SERVER_WRITE_TIMEOUT", 10*time.Second),
			ShutdownTimeout: getEnvDuration("SERVER_SHUTDOWN_TIMEOUT", 30*time.Second),
		},
		RAS: RASConfig{
			ServerAddr:     getEnv("RAS_SERVER_ADDR", "localhost:1545"),
			ConnTimeout:    getEnvDuration("RAS_CONN_TIMEOUT", 5*time.Second),
			RequestTimeout: getEnvDuration("RAS_REQUEST_TIMEOUT", 10*time.Second),
			MaxConnections: getEnvInt("RAS_MAX_CONNECTIONS", 10),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost"),
			Port:     getEnv("REDIS_PORT", "6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       getEnvInt("REDIS_DB", 0),
		},
		Monitor: MonitorConfig{
			SessionMonitorInterval: getEnvDuration("SESSION_MONITOR_INTERVAL", 1*time.Second),
			PubSubEnabled:          getBoolEnv("REDIS_PUBSUB_ENABLED", false), // Default false for safety
		},
		Log: LogConfig{
			Level: getEnv("LOG_LEVEL", "info"),
		},
		Credentials: CredentialsConfig{
			OrchestratorURL: getEnv("ORCHESTRATOR_URL", "http://localhost:8200"),
			JWTSecret:       getEnv("JWT_SECRET", ""),
			JWTIssuer:       getEnv("JWT_ISSUER", "commandcenter"),
			TransportKey:    getEnv("CREDENTIALS_TRANSPORT_KEY", ""),
		},
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}

	return cfg, nil
}

func (c *Config) Validate() error {
	if c.RAS.ServerAddr == "" {
		return fmt.Errorf("RAS_SERVER_ADDR is required")
	}
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("SERVER_PORT must be between 1 and 65535")
	}
	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[c.Log.Level] {
		return fmt.Errorf("LOG_LEVEL must be one of: debug, info, warn, error")
	}

	// Validate credentials config if transport key is provided
	if c.Credentials.TransportKey != "" {
		if _, err := validateTransportKeyHex(c.Credentials.TransportKey); err != nil {
			return fmt.Errorf("invalid CREDENTIALS_TRANSPORT_KEY: %w", err)
		}
	}

	return nil
}

// validateTransportKeyHex validates hex-encoded transport key format.
// Returns decoded key length or error.
func validateTransportKeyHex(hexKey string) (int, error) {
	if hexKey == "" {
		return 0, fmt.Errorf("transport key is required")
	}

	// Check if valid hex
	decoded := make([]byte, len(hexKey)/2)
	n, err := decodeHex(decoded, []byte(hexKey))
	if err != nil {
		return 0, fmt.Errorf("invalid hex encoding: %w", err)
	}

	if n < 32 {
		return 0, fmt.Errorf("key too short: %d bytes (need 32)", n)
	}

	return n, nil
}

// decodeHex decodes hex string to bytes (simple implementation to avoid import cycle)
func decodeHex(dst, src []byte) (int, error) {
	if len(src)%2 != 0 {
		return 0, fmt.Errorf("odd length hex string")
	}

	for i := 0; i < len(src)/2; i++ {
		a, ok := fromHexChar(src[i*2])
		if !ok {
			return 0, fmt.Errorf("invalid hex char at position %d", i*2)
		}
		b, ok := fromHexChar(src[i*2+1])
		if !ok {
			return 0, fmt.Errorf("invalid hex char at position %d", i*2+1)
		}
		dst[i] = (a << 4) | b
	}

	return len(src) / 2, nil
}

func fromHexChar(c byte) (byte, bool) {
	switch {
	case '0' <= c && c <= '9':
		return c - '0', true
	case 'a' <= c && c <= 'f':
		return c - 'a' + 10, true
	case 'A' <= c && c <= 'F':
		return c - 'A' + 10, true
	}
	return 0, false
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
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
