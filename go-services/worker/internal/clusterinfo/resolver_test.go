// go-services/worker/internal/clusterinfo/resolver_test.go
package clusterinfo

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
		RASServer:  "localhost:1545",
	}

	assert.Equal(t, "cluster-123", info.ClusterID)
	assert.Equal(t, "infobase-456", info.InfobaseID)
	assert.Equal(t, "db-789", info.DatabaseID)
	assert.Equal(t, "localhost:1545", info.RASServer)
}

func TestNullResolver_AlwaysReturnsError(t *testing.T) {
	resolver := &NullResolver{}

	info, err := resolver.Resolve(context.Background(), "any-database-id")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "ClusterInfoResolver not configured")
	assert.Contains(t, err.Error(), "any-database-id")
}

func TestOrchestratorResolver_SuccessfulResolve(t *testing.T) {
	// Create test server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		assert.Equal(t, http.MethodGet, r.Method)
		assert.Equal(t, "/api/v2/internal/get-database-cluster-info", r.URL.Path)
		assert.Equal(t, "test-db-123", r.URL.Query().Get("database_id"))
		assert.Equal(t, "application/json", r.Header.Get("Accept"))
		assert.Equal(t, "test-api-key", r.Header.Get("X-Internal-Service-Token"))

		// Return success response
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"cluster_info": map[string]string{
				"database_id":  "test-db-123",
				"cluster_id":   "cluster-uuid-abc",
				"infobase_id":  "infobase-uuid-def",
				"ras_server":   "localhost:1545",
				"cluster_user": "",
				"cluster_pwd":  "",
			},
		})
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		APIKey:          "test-api-key",
		HTTPTimeout:     5 * time.Second,
		MaxRetries:      1,
		CacheTTL:        1 * time.Minute,
	}
	resolver := NewOrchestratorResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "test-db-123")

	require.NoError(t, err)
	require.NotNil(t, info)
	assert.Equal(t, "test-db-123", info.DatabaseID)
	assert.Equal(t, "cluster-uuid-abc", info.ClusterID)
	assert.Equal(t, "infobase-uuid-def", info.InfobaseID)
	assert.Equal(t, "localhost:1545", info.RASServer)
}

func TestOrchestratorResolver_CachingWorks(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"cluster_info": map[string]string{
				"database_id": "cached-db",
				"cluster_id":  "cached-cluster",
				"infobase_id": "cached-infobase",
				"ras_server":  "localhost:1545",
			},
		})
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorResolver(cfg)

	info1, err := resolver.Resolve(context.Background(), "cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	info2, err := resolver.Resolve(context.Background(), "cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	assert.Equal(t, info1.ClusterID, info2.ClusterID)
}

func TestOrchestratorResolver_InvalidateCache(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"cluster_info": map[string]string{
				"database_id": "invalidate-db",
				"cluster_id":  "cluster-" + string(rune('0'+callCount)),
				"infobase_id": "infobase-" + string(rune('0'+callCount)),
				"ras_server":  "localhost:1545",
			},
		})
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorResolver(cfg)
	ctx := context.Background()

	_, err := resolver.Resolve(ctx, "invalidate-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	resolver.InvalidateCache(ctx, "invalidate-db")

	_, err = resolver.Resolve(ctx, "invalidate-db")
	require.NoError(t, err)
	assert.Equal(t, 2, callCount)
}

func TestOrchestratorResolver_FailsAfterMaxRetries(t *testing.T) {
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		MaxRetries:      3,
		RetryDelay:      10 * time.Millisecond,
	}
	resolver := NewOrchestratorResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "fail-db")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "after 3 attempts")
	assert.Equal(t, 3, callCount)
}

func TestOrchestratorResolver_MissingClusterID(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"cluster_info": map[string]string{
				"database_id": "missing-cluster-db",
				"cluster_id":  "",
				"infobase_id": "some-infobase",
				"ras_server":  "localhost:1545",
			},
		})
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		MaxRetries:      1,
	}
	resolver := NewOrchestratorResolver(cfg)

	info, err := resolver.Resolve(context.Background(), "missing-cluster-db")

	assert.Nil(t, info)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cluster_id not available")
}

func TestOrchestratorResolver_RedisCacheRoundtrip(t *testing.T) {
	redisClient := redis.NewClient(&redis.Options{Addr: "localhost:6379", DB: 15})
	ctx := context.Background()
	if err := redisClient.Ping(ctx).Err(); err != nil {
		t.Skip("Redis not available, skipping test")
	}
	defer redisClient.Close()
	_ = redisClient.FlushDB(ctx).Err()

	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"cluster_info": map[string]string{
				"database_id": "redis-cached-db",
				"cluster_id":  "redis-cluster",
				"infobase_id": "redis-infobase",
				"ras_server":  "localhost:1545",
			},
		})
	}))
	defer server.Close()

	cfg := Config{
		OrchestratorURL: server.URL,
		CacheTTL:        1 * time.Minute,
		MaxRetries:      1,
		RedisClient:     redisClient,
	}
	resolver := NewOrchestratorResolver(cfg)

	_, err := resolver.Resolve(ctx, "redis-cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	_, err = resolver.Resolve(ctx, "redis-cached-db")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)
}
