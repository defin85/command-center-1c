package config

import (
	"os"
	"testing"
)

func TestLoad_ValidConfig(t *testing.T) {
	// Create temporary config file
	tmpFile := "test_config.yaml"
	content := `
redis:
  host: "test-host"
  port: 6380
  queue: "test_queue"
  progress_channel: "test_progress"
  db: 1

onec:
  platform_path: "C:\\Test\\1cv8.exe"
  timeout_seconds: 120
  server_name: "test_server"

executor:
  max_parallel: 5
  retry_attempts: 2

orchestrator:
  api_url: "http://test:8000"
  api_token: "test-token"

server:
  health_check_port: 5556

logging:
  level: "debug"
  file: "test.log"
`
	if err := os.WriteFile(tmpFile, []byte(content), 0644); err != nil {
		t.Fatalf("Failed to create test config: %v", err)
	}
	defer os.Remove(tmpFile)

	cfg, err := Load(tmpFile)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	// Verify values
	if cfg.Redis.Host != "test-host" {
		t.Errorf("Expected redis.host = 'test-host', got '%s'", cfg.Redis.Host)
	}
	if cfg.Redis.Port != 6380 {
		t.Errorf("Expected redis.port = 6380, got %d", cfg.Redis.Port)
	}
	if cfg.Executor.MaxParallel != 5 {
		t.Errorf("Expected executor.max_parallel = 5, got %d", cfg.Executor.MaxParallel)
	}
	if cfg.Server.HealthCheckPort != 5556 {
		t.Errorf("Expected server.health_check_port = 5556, got %d", cfg.Server.HealthCheckPort)
	}
}

func TestLoad_EnvironmentOverrides(t *testing.T) {
	// Create temporary config file
	tmpFile := "test_config_env.yaml"
	content := `
redis:
  host: "original-host"
  port: 6379

orchestrator:
  api_url: "http://localhost:8000"
  api_token: "original-token"
`
	if err := os.WriteFile(tmpFile, []byte(content), 0644); err != nil {
		t.Fatalf("Failed to create test config: %v", err)
	}
	defer os.Remove(tmpFile)

	// Set environment variables
	os.Setenv("REDIS_HOST", "env-host")
	os.Setenv("INSTALLATION_SERVICE_TOKEN", "env-token")
	defer os.Unsetenv("REDIS_HOST")
	defer os.Unsetenv("INSTALLATION_SERVICE_TOKEN")

	cfg, err := Load(tmpFile)
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	// Verify environment overrides
	if cfg.Redis.Host != "env-host" {
		t.Errorf("Expected redis.host to be overridden to 'env-host', got '%s'", cfg.Redis.Host)
	}
	if cfg.Orchestrator.APIToken != "env-token" {
		t.Errorf("Expected orchestrator.api_token to be overridden to 'env-token', got '%s'", cfg.Orchestrator.APIToken)
	}
}

func TestLoad_InvalidFile(t *testing.T) {
	_, err := Load("nonexistent_file.yaml")
	if err == nil {
		t.Error("Expected error when loading non-existent file, got nil")
	}
}
