// go-services/worker/internal/processor/cluster_resolver.go
package processor

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/config"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// ClusterInfo contains cluster and infobase identifiers for RAS operations
type ClusterInfo struct {
	// ClusterID is the UUID of the 1C cluster in RAS
	ClusterID string `json:"cluster_id"`
	// InfobaseID is the UUID of the infobase in RAS
	InfobaseID string `json:"infobase_id"`
	// DatabaseID is the original database ID from the request
	DatabaseID string `json:"database_id"`
}

// ClusterInfoResolver resolves cluster and infobase IDs from database ID
type ClusterInfoResolver interface {
	// Resolve fetches ClusterInfo for the given database ID
	// Returns error if resolution fails or data is not available
	Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error)
}

// OrchestratorClusterResolver resolves cluster info via Orchestrator API or Redis Streams
type OrchestratorClusterResolver struct {
	// HTTP client with configured timeout
	httpClient *http.Client
	// Base URL of Orchestrator API
	orchestratorURL string
	// API key for authentication
	apiKey string
	// Redis client for caching (optional)
	redisClient *redis.Client
	// Cache TTL duration
	cacheTTL time.Duration
	// Retry configuration
	maxRetries int
	retryDelay time.Duration
	// Internal cache for in-memory fallback
	cache        map[string]*cacheEntry
	cacheOrder   []string // Tracks insertion order for LRU eviction
	maxCacheSize int      // Maximum cache entries
	cacheMu      sync.RWMutex

	// Streams-based resolution
	// useStreams enables Redis Streams as primary method (with HTTP fallback)
	useStreams bool
	// streamsTimeout is the timeout for Streams-based requests
	streamsTimeout time.Duration
	// clusterInfoWaiter handles Streams request-response pattern
	clusterInfoWaiter *ClusterInfoWaiter
}

// cacheEntry holds cached ClusterInfo with expiration
type cacheEntry struct {
	info      *ClusterInfo
	expiresAt time.Time
}

// ResolverConfig holds configuration for OrchestratorClusterResolver
type ResolverConfig struct {
	// OrchestratorURL is the base URL (e.g., "http://localhost:8200")
	OrchestratorURL string
	// APIKey for authentication (X-Internal-Service-Token header)
	APIKey string
	// HTTPTimeout for requests (default: 10s)
	HTTPTimeout time.Duration
	// MaxRetries for failed requests (default: 3)
	MaxRetries int
	// RetryDelay between retries (default: 500ms, uses exponential backoff)
	RetryDelay time.Duration
	// CacheTTL for cached results (default: 5 minutes)
	CacheTTL time.Duration
	// RedisClient for distributed caching (optional, uses in-memory if nil)
	// Also required for Streams-based resolution
	RedisClient *redis.Client
	// MaxCacheSize limits in-memory cache entries (default: 1000)
	// When exceeded, oldest entries are evicted (LRU-like policy)
	MaxCacheSize int

	// Streams configuration
	// UseStreams enables Redis Streams as primary method (with HTTP fallback)
	// Requires RedisClient to be set
	UseStreams bool
	// StreamsTimeout is the timeout for Streams-based requests (default: 5s)
	StreamsTimeout time.Duration
}

// DefaultResolverConfig returns configuration with sensible defaults
func DefaultResolverConfig() ResolverConfig {
	cfg := config.LoadFromEnv()
	return ResolverConfig{
		OrchestratorURL: cfg.OrchestratorURL,
		APIKey:          cfg.WorkerAPIKey,
		HTTPTimeout:     10 * time.Second,
		MaxRetries:      3,
		RetryDelay:      500 * time.Millisecond,
		CacheTTL:        5 * time.Minute,
		RedisClient:     nil,
		MaxCacheSize:    1000, // Default: 1000 entries (suitable for 700+ databases)
		UseStreams:      cfg.UseStreamsClusterInfo,
		StreamsTimeout:  cfg.StreamsClusterInfoTimeout,
	}
}

// NewOrchestratorClusterResolver creates a new resolver instance
func NewOrchestratorClusterResolver(cfg ResolverConfig) *OrchestratorClusterResolver {
	if cfg.HTTPTimeout == 0 {
		cfg.HTTPTimeout = 10 * time.Second
	}
	if cfg.MaxRetries == 0 {
		cfg.MaxRetries = 3
	}
	if cfg.RetryDelay == 0 {
		cfg.RetryDelay = 500 * time.Millisecond
	}
	if cfg.CacheTTL == 0 {
		cfg.CacheTTL = 5 * time.Minute
	}
	if cfg.MaxCacheSize == 0 {
		cfg.MaxCacheSize = 1000
	}
	if cfg.StreamsTimeout == 0 {
		cfg.StreamsTimeout = 5 * time.Second
	}

	// Disable Streams if RedisClient is not available
	useStreams := cfg.UseStreams && cfg.RedisClient != nil

	resolver := &OrchestratorClusterResolver{
		httpClient: &http.Client{
			Timeout: cfg.HTTPTimeout,
		},
		orchestratorURL: cfg.OrchestratorURL,
		apiKey:          cfg.APIKey,
		redisClient:     cfg.RedisClient,
		cacheTTL:        cfg.CacheTTL,
		maxRetries:      cfg.MaxRetries,
		retryDelay:      cfg.RetryDelay,
		cache:           make(map[string]*cacheEntry),
		cacheOrder:      make([]string, 0, cfg.MaxCacheSize),
		maxCacheSize:    cfg.MaxCacheSize,
		useStreams:      useStreams,
		streamsTimeout:  cfg.StreamsTimeout,
	}

	// Initialize ClusterInfoWaiter if Streams are enabled
	if useStreams {
		resolver.clusterInfoWaiter = NewClusterInfoWaiter(cfg.RedisClient, "")
	}

	return resolver
}

// StartStreamsWaiter starts the ClusterInfoWaiter goroutine.
// Must be called after NewOrchestratorClusterResolver if Streams are enabled.
// Returns nil if Streams are disabled.
func (r *OrchestratorClusterResolver) StartStreamsWaiter(ctx context.Context) error {
	if r.clusterInfoWaiter == nil {
		return nil
	}
	return r.clusterInfoWaiter.Start(ctx)
}

// StopStreamsWaiter stops the ClusterInfoWaiter goroutine.
// Safe to call even if Streams are disabled.
func (r *OrchestratorClusterResolver) StopStreamsWaiter() error {
	if r.clusterInfoWaiter == nil {
		return nil
	}
	return r.clusterInfoWaiter.Close()
}

// Resolve fetches ClusterInfo for the given database ID
// It first checks cache, then calls Orchestrator API if not cached
func (r *OrchestratorClusterResolver) Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	log := logger.GetLogger()

	// 1. Check cache first
	if info := r.getFromCache(ctx, databaseID); info != nil {
		log.Debug("cluster info cache hit",
			zap.String("database_id", databaseID),
			zap.String("cluster_id", info.ClusterID),
		)
		return info, nil
	}

	// 2. Fetch from Orchestrator API with retries
	var lastErr error
	for attempt := 1; attempt <= r.maxRetries; attempt++ {
		info, err := r.fetchFromOrchestrator(ctx, databaseID)
		if err == nil {
			// Cache successful result
			r.setToCache(ctx, databaseID, info)
			log.Info("cluster info resolved",
				zap.String("database_id", databaseID),
				zap.String("cluster_id", info.ClusterID),
				zap.String("infobase_id", info.InfobaseID),
				zap.Int("attempt", attempt),
			)
			return info, nil
		}

		lastErr = err
		log.Warn("failed to resolve cluster info, retrying",
			zap.String("database_id", databaseID),
			zap.Int("attempt", attempt),
			zap.Int("max_retries", r.maxRetries),
			zap.Error(err),
		)

		// Don't sleep on last attempt
		if attempt < r.maxRetries {
			// Exponential backoff
			sleepDuration := r.retryDelay * time.Duration(1<<uint(attempt-1))
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(sleepDuration):
			}
		}
	}

	log.Error("failed to resolve cluster info after all retries",
		zap.String("database_id", databaseID),
		zap.Int("attempts", r.maxRetries),
		zap.Error(lastErr),
	)

	return nil, fmt.Errorf("failed to resolve cluster info for database %s after %d attempts: %w",
		databaseID, r.maxRetries, lastErr)
}

// fetchFromOrchestrator fetches cluster info from Orchestrator.
// If Streams are enabled, it tries Streams first, then falls back to HTTP.
// If Streams are disabled, it uses HTTP directly.
func (r *OrchestratorClusterResolver) fetchFromOrchestrator(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	log := logger.GetLogger()

	// 1. Try Streams first (if enabled)
	if r.useStreams && r.clusterInfoWaiter != nil {
		info, err := r.fetchViaStreams(ctx, databaseID)
		if err == nil {
			log.Debug("cluster info resolved via Streams",
				zap.String("database_id", databaseID),
				zap.String("cluster_id", info.ClusterID),
			)
			return info, nil
		}

		log.Warn("streams fetch failed, falling back to HTTP",
			zap.String("database_id", databaseID),
			zap.Error(err),
		)
	}

	// 2. Fallback to HTTP
	return r.fetchViaHTTP(ctx, databaseID)
}

// fetchViaStreams requests cluster info via Redis Streams.
func (r *OrchestratorClusterResolver) fetchViaStreams(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	if r.clusterInfoWaiter == nil {
		return nil, fmt.Errorf("cluster info waiter not initialized")
	}

	return r.clusterInfoWaiter.RequestClusterInfo(ctx, databaseID, r.streamsTimeout)
}

// fetchViaHTTP makes HTTP request to Orchestrator API.
func (r *OrchestratorClusterResolver) fetchViaHTTP(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	// Internal v2 endpoint (v1 removed).
	url := fmt.Sprintf("%s/api/v2/internal/get-database-cluster-info?database_id=%s", r.orchestratorURL, databaseID)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if r.apiKey != "" {
		// Internal API supports X-Internal-Service-Token (legacy) and JWT.
		req.Header.Set("X-Internal-Service-Token", r.apiKey)
	}

	// Execute request
	resp, err := r.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// Check status code
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var apiResponse struct {
		Success     bool `json:"success"`
		ClusterInfo struct {
			DatabaseID string `json:"database_id"`
			ClusterID  string `json:"cluster_id"`
			InfobaseID string `json:"infobase_id"`
		} `json:"cluster_info"`
	}

	if err := json.Unmarshal(body, &apiResponse); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}
	if !apiResponse.Success {
		return nil, fmt.Errorf("unexpected response: %s", string(body))
	}

	// Validate required fields
	if apiResponse.ClusterInfo.ClusterID == "" {
		return nil, fmt.Errorf("cluster_id not available for database %s (not configured in Orchestrator)", databaseID)
	}
	if apiResponse.ClusterInfo.InfobaseID == "" {
		return nil, fmt.Errorf("infobase_id not available for database %s", databaseID)
	}

	return &ClusterInfo{
		DatabaseID: databaseID,
		ClusterID:  apiResponse.ClusterInfo.ClusterID,
		InfobaseID: apiResponse.ClusterInfo.InfobaseID,
	}, nil
}

// UseStreams returns whether Streams-based resolution is enabled.
func (r *OrchestratorClusterResolver) UseStreams() bool {
	return r.useStreams
}

// getFromCache retrieves ClusterInfo from cache
func (r *OrchestratorClusterResolver) getFromCache(ctx context.Context, databaseID string) *ClusterInfo {
	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)

	// Try Redis first if available
	if r.redisClient != nil {
		data, err := r.redisClient.Get(ctx, cacheKey).Bytes()
		if err == nil {
			var info ClusterInfo
			if json.Unmarshal(data, &info) == nil {
				return &info
			}
		}
	}

	// Fallback to in-memory cache
	r.cacheMu.RLock()
	defer r.cacheMu.RUnlock()

	entry, exists := r.cache[databaseID]
	if !exists || time.Now().After(entry.expiresAt) {
		return nil
	}

	return entry.info
}

// setToCache stores ClusterInfo in cache
func (r *OrchestratorClusterResolver) setToCache(ctx context.Context, databaseID string, info *ClusterInfo) {
	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)

	// Store in Redis if available
	if r.redisClient != nil {
		data, err := json.Marshal(info)
		if err == nil {
			r.redisClient.Set(ctx, cacheKey, data, r.cacheTTL)
		}
	}

	// Also store in in-memory cache as fallback
	r.cacheMu.Lock()
	defer r.cacheMu.Unlock()

	// Check if already exists (update case - move to end of order)
	if _, exists := r.cache[databaseID]; exists {
		// Remove from current position in order
		for i, id := range r.cacheOrder {
			if id == databaseID {
				r.cacheOrder = append(r.cacheOrder[:i], r.cacheOrder[i+1:]...)
				break
			}
		}
	} else {
		// New entry - check if we need to evict oldest entries
		for len(r.cache) >= r.maxCacheSize && len(r.cacheOrder) > 0 {
			// Evict oldest (first) entry
			oldestID := r.cacheOrder[0]
			r.cacheOrder = r.cacheOrder[1:]
			delete(r.cache, oldestID)
		}
	}

	// Add entry
	r.cache[databaseID] = &cacheEntry{
		info:      info,
		expiresAt: time.Now().Add(r.cacheTTL),
	}
	r.cacheOrder = append(r.cacheOrder, databaseID)
}

// InvalidateCache removes cached entry for database
func (r *OrchestratorClusterResolver) InvalidateCache(ctx context.Context, databaseID string) {
	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)

	// Remove from Redis
	if r.redisClient != nil {
		r.redisClient.Del(ctx, cacheKey)
	}

	// Remove from in-memory cache
	r.cacheMu.Lock()
	defer r.cacheMu.Unlock()
	delete(r.cache, databaseID)

	// Remove from order tracking
	for i, id := range r.cacheOrder {
		if id == databaseID {
			r.cacheOrder = append(r.cacheOrder[:i], r.cacheOrder[i+1:]...)
			break
		}
	}
}

// ClearCache removes all cached entries
func (r *OrchestratorClusterResolver) ClearCache(ctx context.Context) {
	// Clear in-memory cache
	r.cacheMu.Lock()
	defer r.cacheMu.Unlock()
	r.cache = make(map[string]*cacheEntry)
	r.cacheOrder = make([]string, 0, r.maxCacheSize)

	// Note: Redis cache entries will expire naturally based on TTL
	// Full Redis cache clear would require pattern-based deletion
}

// NullClusterResolver is a no-op resolver that always returns error
// Used when resolver is not configured
type NullClusterResolver struct{}

// Resolve always returns an error indicating resolver is not configured
func (r *NullClusterResolver) Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	return nil, fmt.Errorf("ClusterInfoResolver not configured: cannot resolve cluster info for database %s. "+
		"Configure OrchestratorClusterResolver with valid OrchestratorURL to enable Event-Driven mode", databaseID)
}
