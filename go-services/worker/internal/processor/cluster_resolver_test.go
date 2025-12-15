// go-services/worker/internal/processor/cluster_resolver_test.go
package processor

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestClusterInfo_Fields(t *testing.T) {
	info := &ClusterInfo{
		ClusterID:  "cluster-123",
		InfobaseID: "infobase-456",
		DatabaseID: "db-789",
	}

	assert.Equal(t, "cluster-123", info.ClusterID)
	assert.Equal(t, "infobase-456", info.InfobaseID)
	assert.Equal(t, "db-789", info.DatabaseID)
}

func TestNullClusterResolver_AlwaysReturnsError(t *testing.T) {
	resolver := &NullClusterResolver{}

	info, err := resolver.Resolve(context.Background(), "any-database-id")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "ClusterInfoResolver not configured")
	assert.Contains(t, err.Error(), "any-database-id")
}

func TestOrchestratorClusterResolver_SuccessfulResolve(t *testing.T) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		assert.Equal(t, http.MethodGet, r.Method)
		assert.Contains(t, r.URL.Path, "/api/v1/databases/test-db-123/cluster-info/")
		assert.Equal(t, "application/json", r.Header.Get("Accept"))

		// Return success response
		response := map[string]string{
			"database_id": "test-db-123",
			"cluster_id":  "cluster-uuid-abc",
			"infobase_id": "infobase-uuid-def",
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	// Create resolver
	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		APIKey:          "test-api-key",
		HTTPTimeout:     5 * time.Second,
		MaxRetries:      1,
		CacheTTL:        1 * time.Minute,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// Test resolve
	info, err := resolver.Resolve(context.Background(), "test-db-123")

	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, "test-db-123", info.DatabaseID)
	assert.Equal(t, "cluster-uuid-abc", info.ClusterID)
	assert.Equal(t, "infobase-uuid-def", info.InfobaseID)
}

func TestOrchestratorClusterResolver_CachingWorks(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		response := map[string]string{
			"database_id": "cached-db",
			"cluster_id":  "cached-cluster",
			"infobase_id": "cached-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// First call should hit the server
	info1, err := resolver.Resolve(context.Background(), "cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	// Second call should use cache
	info2, err := resolver.Resolve(context.Background(), "cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount) // Still 1 - no new HTTP call

	// Results should be the same
	assert.Equal(t, info1.ClusterID, info2.ClusterID)
}

func TestOrchestratorClusterResolver_InvalidateCache(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		response := map[string]string{
			"database_id": "invalidate-db",
			"cluster_id":  "cluster-" + string(rune('0'+callCount)),
			"infobase_id": "infobase-" + string(rune('0'+callCount)),
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorClusterResolver(cfg)
	ctx := context.Background()

	// First call
	_, err := resolver.Resolve(ctx, "invalidate-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	// Invalidate cache
	resolver.InvalidateCache(ctx, "invalidate-db")

	// Next call should hit server again
	_, err = resolver.Resolve(ctx, "invalidate-db")
	require.NoError(t, err)
	assert.Equal(t, 2, callCount)
}

func TestOrchestratorClusterResolver_RetryOnFailure(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		if callCount < 3 {
			// First 2 calls fail
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		// Third call succeeds
		response := map[string]string{
			"database_id": "retry-db",
			"cluster_id":  "retry-cluster",
			"infobase_id": "retry-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		MaxRetries:      3,
		RetryDelay:      10 * time.Millisecond, // Fast retry for tests
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "retry-db")

	require.NoError(t, err)
	assert.Equal(t, 3, callCount) // Should have retried
	assert.Equal(t, "retry-cluster", info.ClusterID)
}

func TestOrchestratorClusterResolver_FailsAfterMaxRetries(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		MaxRetries:      3,
		RetryDelay:      10 * time.Millisecond,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "fail-db")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "after 3 attempts")
	assert.Equal(t, 3, callCount)
}

func TestOrchestratorClusterResolver_MissingClusterID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		response := map[string]string{
			"database_id": "missing-cluster-db",
			"cluster_id":  "", // Missing cluster_id
			"infobase_id": "some-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "missing-cluster-db")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id not available")
}

func TestOrchestratorClusterResolver_ContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Simulate slow response
		time.Sleep(100 * time.Millisecond)
		response := map[string]string{
			"database_id": "slow-db",
			"cluster_id":  "slow-cluster",
			"infobase_id": "slow-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		HTTPTimeout:     5 * time.Second,
		MaxRetries:      3,
		RetryDelay:      50 * time.Millisecond,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// Create context that will be cancelled
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	info, err := resolver.Resolve(ctx, "slow-db")

	assert.Nil(t, info)
	assert.Error(t, err)
}

func TestOrchestratorClusterResolver_DefaultConfig(t *testing.T) {
	cfg := DefaultResolverConfig()

	assert.NotEmpty(t, cfg.OrchestratorURL)
	assert.Equal(t, 10*time.Second, cfg.HTTPTimeout)
	assert.Equal(t, 3, cfg.MaxRetries)
	assert.Equal(t, 500*time.Millisecond, cfg.RetryDelay)
	assert.Equal(t, 5*time.Minute, cfg.CacheTTL)
}

func TestOrchestratorClusterResolver_WithRedisCache(t *testing.T) {
	// Skip if Redis is not available
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	defer redisClient.Close()

	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping Redis cache test")
	}

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		response := map[string]string{
			"database_id": "redis-cached-db",
			"cluster_id":  "redis-cluster",
			"infobase_id": "redis-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		RedisClient:     redisClient,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// Clean up any existing cache
	redisClient.Del(ctx, "cluster_info:redis-cached-db")

	// First call hits server
	info1, err := resolver.Resolve(ctx, "redis-cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	// Second call uses Redis cache
	info2, err := resolver.Resolve(ctx, "redis-cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	assert.Equal(t, info1.ClusterID, info2.ClusterID)

	// Clean up
	redisClient.Del(ctx, "cluster_info:redis-cached-db")
}

func TestOrchestratorClusterResolver_APIKeyHeader(t *testing.T) {
	receivedAPIKey := ""

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedAPIKey = r.Header.Get("X-API-Key")
		response := map[string]string{
			"database_id": "api-key-db",
			"cluster_id":  "api-key-cluster",
			"infobase_id": "api-key-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		APIKey:          "secret-api-key-12345",
		MaxRetries:      1,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	_, err := resolver.Resolve(context.Background(), "api-key-db")
	require.NoError(t, err)

	assert.Equal(t, "secret-api-key-12345", receivedAPIKey)
}

func TestOrchestratorClusterResolver_CacheEviction(t *testing.T) {
	// Test that cache evicts oldest entries when maxCacheSize is exceeded
	callCount := 0
	requestedDBs := make([]string, 0)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		// Extract database ID from URL path
		path := r.URL.Path
		// Path format: /api/v1/databases/{db_id}/cluster-info/
		parts := make([]string, 0)
		for _, p := range splitPath(path) {
			if p != "" {
				parts = append(parts, p)
			}
		}
		dbID := ""
		for i, p := range parts {
			if p == "databases" && i+1 < len(parts) {
				dbID = parts[i+1]
				break
			}
		}
		requestedDBs = append(requestedDBs, dbID)

		response := map[string]string{
			"database_id": dbID,
			"cluster_id":  "cluster-" + dbID,
			"infobase_id": "infobase-" + dbID,
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	// Create resolver with small cache size for testing
	maxCacheSize := 3
	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
		MaxCacheSize:    maxCacheSize,
	}
	resolver := NewOrchestratorClusterResolver(cfg)
	ctx := context.Background()

	// Add 3 entries (cache is full)
	for i := 1; i <= 3; i++ {
		dbID := "db-" + string(rune('0'+i))
		info, err := resolver.Resolve(ctx, dbID)
		require.NoError(t, err)
		assert.Equal(t, "cluster-"+dbID, info.ClusterID)
	}
	assert.Equal(t, 3, callCount, "Should have made 3 HTTP calls")

	// Cache should have all 3 entries - verify by re-requesting (no new HTTP calls)
	for i := 1; i <= 3; i++ {
		dbID := "db-" + string(rune('0'+i))
		_, err := resolver.Resolve(ctx, dbID)
		require.NoError(t, err)
	}
	assert.Equal(t, 3, callCount, "Cache should hit for all 3 entries")

	// Add 4th entry - should evict db-1 (oldest)
	info4, err := resolver.Resolve(ctx, "db-4")
	require.NoError(t, err)
	assert.Equal(t, "cluster-db-4", info4.ClusterID)
	assert.Equal(t, 4, callCount, "Should have made 1 more HTTP call for db-4")

	// db-2, db-3, db-4 should be in cache (no new HTTP calls)
	for _, dbID := range []string{"db-2", "db-3", "db-4"} {
		_, err := resolver.Resolve(ctx, dbID)
		require.NoError(t, err)
	}
	assert.Equal(t, 4, callCount, "Cache should hit for db-2, db-3, db-4")

	// db-1 was evicted - should require new HTTP call
	_, err = resolver.Resolve(ctx, "db-1")
	require.NoError(t, err)
	assert.Equal(t, 5, callCount, "db-1 was evicted, should make new HTTP call")
}

// Helper function to split path
func splitPath(path string) []string {
	result := make([]string, 0)
	current := ""
	for _, c := range path {
		if c == '/' {
			if current != "" {
				result = append(result, current)
				current = ""
			}
		} else {
			current += string(c)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}

func TestOrchestratorClusterResolver_DefaultMaxCacheSize(t *testing.T) {
	cfg := DefaultResolverConfig()

	assert.Equal(t, 1000, cfg.MaxCacheSize, "Default MaxCacheSize should be 1000")
}

func TestOrchestratorClusterResolver_StreamsDisabledWithoutRedis(t *testing.T) {
	// When RedisClient is nil, Streams should be disabled even if UseStreams is true
	cfg := ResolverConfig{
		OrchestratorURL: "http://localhost:8200",
		UseStreams:      true,
		RedisClient:     nil, // No Redis
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	assert.False(t, resolver.UseStreams(), "Streams should be disabled without Redis")
	assert.Nil(t, resolver.clusterInfoWaiter, "ClusterInfoWaiter should not be initialized")
}

func TestOrchestratorClusterResolver_StreamsEnabledWithRedis(t *testing.T) {
	// Skip if Redis is not available
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	defer redisClient.Close()

	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping Streams test")
	}

	cfg := ResolverConfig{
		OrchestratorURL: "http://localhost:8200",
		UseStreams:      true,
		RedisClient:     redisClient,
		StreamsTimeout:  5 * time.Second,
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	assert.True(t, resolver.UseStreams(), "Streams should be enabled with Redis")
	assert.NotNil(t, resolver.clusterInfoWaiter, "ClusterInfoWaiter should be initialized")
}

func TestOrchestratorClusterResolver_FallbackToHTTPWhenStreamsTimeout(t *testing.T) {
	// Skip if Redis is not available
	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	defer redisClient.Close()

	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping Streams fallback test")
	}

	httpCallCount := 0

	// Create HTTP server that always succeeds
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		httpCallCount++
		response := map[string]string{
			"database_id": "fallback-streams-db",
			"cluster_id":  "fallback-streams-cluster",
			"infobase_id": "fallback-streams-infobase",
		}
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := ResolverConfig{
		OrchestratorURL: server.URL,
		UseStreams:      true,
		RedisClient:     redisClient,
		StreamsTimeout:  100 * time.Millisecond, // Very short timeout
		MaxRetries:      1,
		CacheTTL:        1 * time.Second, // Short TTL for tests
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// Clean cache to ensure fresh test
	resolver.ClearCache(ctx)
	redisClient.Del(ctx, "cluster_info:fallback-streams-db")

	// Start streams waiter
	err := resolver.StartStreamsWaiter(ctx)
	require.NoError(t, err)
	defer resolver.StopStreamsWaiter()

	// Give waiter time to start
	time.Sleep(50 * time.Millisecond)

	// Since there's no Django handler responding, Streams will timeout and fall back to HTTP
	info, err := resolver.Resolve(ctx, "fallback-streams-db")

	require.NoError(t, err)
	assert.Equal(t, "fallback-streams-cluster", info.ClusterID)
	assert.Equal(t, 1, httpCallCount, "Should have fallen back to HTTP")
}

func TestOrchestratorClusterResolver_DefaultStreamsConfig(t *testing.T) {
	cfg := DefaultResolverConfig()

	// Streams should be enabled by default
	assert.True(t, cfg.UseStreams, "UseStreams should be true by default")
	assert.Equal(t, 5*time.Second, cfg.StreamsTimeout, "StreamsTimeout should be 5s by default")
}

func TestOrchestratorClusterResolver_StartStopStreamsWaiter(t *testing.T) {
	// Test that Start/Stop methods work correctly when Streams are disabled
	cfg := ResolverConfig{
		OrchestratorURL: "http://localhost:8200",
		UseStreams:      false, // Streams disabled
	}
	resolver := NewOrchestratorClusterResolver(cfg)

	// Start should be a no-op
	err := resolver.StartStreamsWaiter(context.Background())
	assert.NoError(t, err)

	// Stop should be a no-op
	err = resolver.StopStreamsWaiter()
	assert.NoError(t, err)
}
