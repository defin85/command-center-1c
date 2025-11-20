// +build integration

package integration

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/config"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/ras"
	"github.com/commandcenter1c/commandcenter/ras-adapter/internal/service"
)

// Test environment variables
const (
	// Default RAS server address (configurable via RAS_SERVER env var)
	defaultRASServer = "localhost:1545"
	// Default Redis address (configurable via REDIS_HOST env var)
	defaultRedisAddr = "localhost:6379"
)

// Global test resources (cached)
var (
	testRASServer   string
	testRedisAddr   string
	testClusterID   string // Set in test discovery
	testInfobaseID  string // Set in test discovery
)

func init() {
	// Allow env var overrides for CI environments
	if server := os.Getenv("RAS_SERVER"); server != "" {
		testRASServer = server
	} else {
		testRASServer = defaultRASServer
	}

	if addr := os.Getenv("REDIS_HOST"); addr != "" {
		testRedisAddr = addr + ":6379"
	} else {
		testRedisAddr = defaultRedisAddr
	}
}

// setupTestEnvironment initializes test infrastructure
func setupTestEnvironment(t *testing.T) (*ras.Pool, *redis.Client, *zap.Logger) {
	logger, _ := zap.NewDevelopment()

	// Create RAS pool
	rasPool, err := ras.NewPool(
		testRASServer,
		5,                    // max connections
		10*time.Second,       // connection timeout
		30*time.Second,       // request timeout
		logger,
	)
	require.NoError(t, err, "Failed to create RAS pool - check if RAS server is running on %s", testRASServer)

	// Create Redis client
	redisClient := redis.NewClient(&redis.Options{
		Addr: testRedisAddr,
	})

	// Test Redis connection
	ctx := context.Background()
	_, err = redisClient.Ping(ctx).Result()
	require.NoError(t, err, "Failed to connect to Redis on %s - check if Redis is running", testRedisAddr)

	t.Logf("Test environment ready: RAS=%s, Redis=%s", testRASServer, testRedisAddr)

	return rasPool, redisClient, logger
}

// discoverTestResources finds first available cluster and infobase for testing
func discoverTestResources(t *testing.T, rasPool *ras.Pool) (string, string) {
	// Use cached resources if available
	if testClusterID != "" && testInfobaseID != "" {
		return testClusterID, testInfobaseID
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Get RAS client
	client, err := rasPool.GetConnection(ctx)
	require.NoError(t, err, "Failed to get RAS client")
	defer rasPool.ReleaseConnection(client)

	// Get clusters
	clusters, err := client.GetClusters(ctx)
	require.NoError(t, err, "Failed to get clusters - check RAS server configuration")
	require.NotEmpty(t, clusters, "No clusters found - configure at least one cluster in RAS")

	clusterID := clusters[0].UUID
	t.Logf("Using cluster: %s (%s)", clusterID, clusters[0].Name)

	// Get infobases
	infobases, err := client.GetInfobases(ctx, clusterID)
	require.NoError(t, err, "Failed to get infobases")
	require.NotEmpty(t, infobases, "No infobases found in cluster %s", clusterID)

	infobaseID := infobases[0].UUID
	t.Logf("Using infobase: %s (%s)", infobaseID, infobases[0].Name)

	// Cache for subsequent tests
	testClusterID = clusterID
	testInfobaseID = infobaseID

	return clusterID, infobaseID
}

// cleanupTestEnvironment closes all test resources
func cleanupTestEnvironment(rasPool *ras.Pool, redisClient *redis.Client) {
	if rasPool != nil {
		rasPool.Close()
	}
	if redisClient != nil {
		redisClient.Close()
	}
}

// createInfobaseService creates InfobaseService for testing
func createInfobaseService(t *testing.T, rasPool *ras.Pool) *service.InfobaseService {
	logger, _ := zap.NewDevelopment()
	return service.NewInfobaseService(rasPool, logger)
}

// createClusterService creates ClusterService for testing
func createClusterService(t *testing.T, rasPool *ras.Pool) *service.ClusterService {
	logger, _ := zap.NewDevelopment()
	return service.NewClusterService(rasPool, logger)
}

// createSessionService creates SessionService for testing
func createSessionService(t *testing.T, rasPool *ras.Pool) *service.SessionService {
	logger, _ := zap.NewDevelopment()
	return service.NewSessionService(rasPool, logger)
}

// TestEnvironmentSetup verifies test environment is properly configured
func TestEnvironmentSetup(t *testing.T) {
	t.Run("verify_ras_server_available", func(t *testing.T) {
		rasPool, redisClient, logger := setupTestEnvironment(t)
		defer cleanupTestEnvironment(rasPool, redisClient)

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		client, err := rasPool.GetConnection(ctx)
		require.NoError(t, err, "Failed to connect to RAS server")
		defer rasPool.ReleaseConnection(client)

		clusters, err := client.GetClusters(ctx)
		require.NoError(t, err, "Failed to get clusters from RAS")
		require.NotEmpty(t, clusters, "No clusters configured in RAS")

		t.Logf("RAS server is healthy with %d cluster(s)", len(clusters))
	})

	t.Run("verify_redis_available", func(t *testing.T) {
		rasPool, redisClient, _ := setupTestEnvironment(t)
		defer cleanupTestEnvironment(rasPool, redisClient)

		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		result, err := redisClient.Ping(ctx).Result()
		require.NoError(t, err)
		require.Equal(t, "PONG", result)

		t.Log("Redis is healthy")
	})

	t.Run("discover_test_resources", func(t *testing.T) {
		rasPool, redisClient, _ := setupTestEnvironment(t)
		defer cleanupTestEnvironment(rasPool, redisClient)

		clusterID, infobaseID := discoverTestResources(t, rasPool)
		require.NotEmpty(t, clusterID)
		require.NotEmpty(t, infobaseID)

		t.Logf("Test resources discovered: cluster=%s, infobase=%s", clusterID, infobaseID)
	})
}

// GetTestClusterID returns cached or discovers test cluster ID
func GetTestClusterID(t *testing.T, rasPool *ras.Pool) string {
	clusterID, _ := discoverTestResources(t, rasPool)
	return clusterID
}

// GetTestInfobaseID returns cached or discovers test infobase ID
func GetTestInfobaseID(t *testing.T, rasPool *ras.Pool) string {
	_, infobaseID := discoverTestResources(t, rasPool)
	return infobaseID
}
