//go:build integration

package statemachine

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

// setupRedisForTest creates a Redis client for tests.
// Tries localhost:6380 first (docker-compose.test.yml), then 6379, falls back to testcontainers.
func setupRedisForTest(t *testing.T, ctx context.Context) *redis.Client {
	// Try localhost Redis on test port first (docker-compose.test.yml)
	ports := []string{"6380", "6379"}

	for _, port := range ports {
		localClient := redis.NewClient(&redis.Options{
			Addr: "127.0.0.1:" + port,
			DB:   1, // Use DB 1 for tests to avoid conflicts
		})

		pingCtx, pingCancel := context.WithTimeout(ctx, 2*time.Second)
		err := localClient.Ping(pingCtx).Err()
		pingCancel()

		if err == nil {
			t.Logf("Using local Redis on localhost:%s", port)

			// Flush test DB
			if err := localClient.FlushDB(ctx).Err(); err != nil {
				t.Logf("Warning: Failed to flush test DB: %v", err)
			}

			t.Cleanup(func() {
				localClient.Close()
			})

			return localClient
		}

		localClient.Close()
	}

	// Fallback to testcontainers
	t.Log("Local Redis not available on ports 6380/6379, starting testcontainers...")

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
		t.Skipf("Cannot start Redis container: %v. Start test Redis: docker-compose -f docker-compose.test.yml up -d redis-test", err)
	}

	t.Cleanup(func() {
		if err := redisContainer.Terminate(ctx); err != nil {
			t.Logf("Warning: Failed to terminate Redis container: %v", err)
		}
	})

	redisHost, err := redisContainer.Host(ctx)
	require.NoError(t, err)

	redisPort, err := redisContainer.MappedPort(ctx, "6379")
	require.NoError(t, err)

	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort.Port())
	t.Logf("Redis container started: %s", redisAddr)

	client := redis.NewClient(&redis.Options{
		Addr: redisAddr,
		DB:   0,
	})

	// Verify connection
	require.NoError(t, client.Ping(ctx).Err())

	t.Cleanup(func() {
		client.Close()
	})

	return client
}
