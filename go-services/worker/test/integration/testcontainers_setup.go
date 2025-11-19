package integration

import (
	"context"
	"database/sql"
	"fmt"
	"testing"
	"time"

	_ "github.com/lib/pq" // PostgreSQL driver
	"github.com/docker/go-connections/nat"
	"github.com/redis/go-redis/v9"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

// TestEnvironment holds all test infrastructure
type TestEnvironment struct {
	// Containers
	RedisContainer     testcontainers.Container
	PostgresContainer  testcontainers.Container

	// Clients
	RedisClient *redis.Client
	DB          *sql.DB

	// Cleanup function
	cleanup func()
}

// SetupTestEnvironment creates isolated test environment with Redis and PostgreSQL
func SetupTestEnvironment(t *testing.T) *TestEnvironment {
	ctx := context.Background()

	t.Log("🚀 Setting up test environment with testcontainers...")

	// =============================================================================
	// Setup Redis Container
	// =============================================================================

	t.Log("📦 Starting Redis container...")

	redisReq := testcontainers.ContainerRequest{
		Image:        "redis:7-alpine",
		ExposedPorts: []string{"6379/tcp"},
		WaitingFor:   wait.ForListeningPort("6379/tcp").WithStartupTimeout(30 * time.Second),
	}

	redisContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: redisReq,
		Started:          true,
	})
	if err != nil {
		t.Fatalf("Failed to start Redis container: %v", err)
	}

	// Get Redis connection info
	redisHost, err := redisContainer.Host(ctx)
	if err != nil {
		redisContainer.Terminate(ctx)
		t.Fatalf("Failed to get Redis host: %v", err)
	}

	redisPort, err := redisContainer.MappedPort(ctx, "6379")
	if err != nil {
		redisContainer.Terminate(ctx)
		t.Fatalf("Failed to get Redis port: %v", err)
	}

	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort.Port())
	t.Logf("✅ Redis container started: %s", redisAddr)

	// Create Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: "",
		DB:       0,
	})

	// Test Redis connection
	if err := redisClient.Ping(ctx).Err(); err != nil {
		redisContainer.Terminate(ctx)
		t.Fatalf("Failed to ping Redis: %v", err)
	}

	t.Log("✅ Redis client connected successfully")

	// =============================================================================
	// Setup PostgreSQL Container (optional, for future tests)
	// =============================================================================

	t.Log("📦 Starting PostgreSQL container...")

	postgresReq := testcontainers.ContainerRequest{
		Image:        "postgres:15-alpine",
		ExposedPorts: []string{"5432/tcp"},
		Env: map[string]string{
			"POSTGRES_PASSWORD": "test",
			"POSTGRES_USER":     "test",
			"POSTGRES_DB":       "test",
		},
		WaitingFor: wait.ForSQL("5432/tcp", "postgres", func(host string, port nat.Port) string {
			return fmt.Sprintf("host=%s port=%s user=test password=test dbname=test sslmode=disable", host, port.Port())
		}).WithStartupTimeout(60 * time.Second),
	}

	postgresContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: postgresReq,
		Started:          true,
	})
	if err != nil {
		redisContainer.Terminate(ctx)
		t.Fatalf("Failed to start PostgreSQL container: %v", err)
	}

	// Get PostgreSQL connection info
	pgHost, err := postgresContainer.Host(ctx)
	if err != nil {
		redisContainer.Terminate(ctx)
		postgresContainer.Terminate(ctx)
		t.Fatalf("Failed to get PostgreSQL host: %v", err)
	}

	pgPort, err := postgresContainer.MappedPort(ctx, "5432")
	if err != nil {
		redisContainer.Terminate(ctx)
		postgresContainer.Terminate(ctx)
		t.Fatalf("Failed to get PostgreSQL port: %v", err)
	}

	pgConnStr := fmt.Sprintf("host=%s port=%s user=test password=test dbname=test sslmode=disable", pgHost, pgPort.Port())
	t.Logf("✅ PostgreSQL container started: %s:%s", pgHost, pgPort.Port())

	// Open PostgreSQL connection
	db, err := sql.Open("postgres", pgConnStr)
	if err != nil {
		redisContainer.Terminate(ctx)
		postgresContainer.Terminate(ctx)
		t.Fatalf("Failed to open PostgreSQL connection: %v", err)
	}

	// Test PostgreSQL connection
	if err := db.Ping(); err != nil {
		redisContainer.Terminate(ctx)
		postgresContainer.Terminate(ctx)
		t.Fatalf("Failed to ping PostgreSQL: %v", err)
	}

	t.Log("✅ PostgreSQL client connected successfully")

	// =============================================================================
	// Create Test Environment
	// =============================================================================

	env := &TestEnvironment{
		RedisContainer:    redisContainer,
		PostgresContainer: postgresContainer,
		RedisClient:       redisClient,
		DB:                db,
	}

	// Setup cleanup function
	env.cleanup = func() {
		t.Log("🧹 Cleaning up test environment...")

		if redisClient != nil {
			redisClient.Close()
		}

		if db != nil {
			db.Close()
		}

		if redisContainer != nil {
			if err := redisContainer.Terminate(ctx); err != nil {
				t.Logf("⚠️ Failed to terminate Redis container: %v", err)
			} else {
				t.Log("✅ Redis container terminated")
			}
		}

		if postgresContainer != nil {
			if err := postgresContainer.Terminate(ctx); err != nil {
				t.Logf("⚠️ Failed to terminate PostgreSQL container: %v", err)
			} else {
				t.Log("✅ PostgreSQL container terminated")
			}
		}

		t.Log("✅ Test environment cleanup completed")
	}

	// Register cleanup on test completion
	t.Cleanup(env.cleanup)

	t.Log("✅ Test environment setup completed!")

	return env
}

// Cleanup manually cleans up test environment (called automatically via t.Cleanup)
func (env *TestEnvironment) Cleanup() {
	if env.cleanup != nil {
		env.cleanup()
	}
}

// FlushRedis flushes all Redis data
func (env *TestEnvironment) FlushRedis(t *testing.T) {
	ctx := context.Background()
	if err := env.RedisClient.FlushAll(ctx).Err(); err != nil {
		t.Logf("⚠️ Failed to flush Redis: %v", err)
	} else {
		t.Log("✅ Redis flushed")
	}
}
