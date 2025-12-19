// go-services/worker/internal/clusterinfo/resolver.go
package clusterinfo

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
	// RASServer is the RAS server address (host:port)
	RASServer string `json:"ras_server"`
	// ClusterUser/ClusterPwd are optional cluster admin credentials
	ClusterUser string `json:"cluster_user"`
	ClusterPwd  string `json:"cluster_pwd"`
}

// Resolver resolves cluster and infobase IDs from database ID
type Resolver interface {
	Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error)
}

// OrchestratorClusterResolver resolves cluster info via Orchestrator API or Redis Streams
type OrchestratorClusterResolver struct {
	httpClient      *http.Client
	orchestratorURL string
	apiKey          string

	redisClient *redis.Client
	cacheTTL    time.Duration

	maxRetries int
	retryDelay time.Duration

	cache        map[string]*cacheEntry
	cacheOrder   []string
	maxCacheSize int
	cacheMu      sync.RWMutex

	useStreams        bool
	streamsTimeout    time.Duration
	clusterInfoWaiter *ClusterInfoWaiter
}

type cacheEntry struct {
	info      *ClusterInfo
	expiresAt time.Time
}

type Config struct {
	OrchestratorURL string
	APIKey          string
	HTTPTimeout     time.Duration
	MaxRetries      int
	RetryDelay      time.Duration
	CacheTTL        time.Duration
	RedisClient     *redis.Client
	MaxCacheSize    int

	UseStreams     bool
	StreamsTimeout time.Duration
}

func DefaultConfig() Config {
	cfg := config.LoadFromEnv()
	return Config{
		OrchestratorURL: cfg.OrchestratorURL,
		APIKey:          cfg.WorkerAPIKey,
		HTTPTimeout:     10 * time.Second,
		MaxRetries:      3,
		RetryDelay:      500 * time.Millisecond,
		CacheTTL:        5 * time.Minute,
		RedisClient:     nil,
		MaxCacheSize:    1000,
		UseStreams:      cfg.UseStreamsClusterInfo,
		StreamsTimeout:  cfg.StreamsClusterInfoTimeout,
	}
}

func NewOrchestratorResolver(cfg Config) *OrchestratorClusterResolver {
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

	resolver := &OrchestratorClusterResolver{
		httpClient:      &http.Client{Timeout: cfg.HTTPTimeout},
		orchestratorURL: cfg.OrchestratorURL,
		apiKey:          cfg.APIKey,
		redisClient:     cfg.RedisClient,
		cacheTTL:        cfg.CacheTTL,
		maxRetries:      cfg.MaxRetries,
		retryDelay:      cfg.RetryDelay,
		cache:           make(map[string]*cacheEntry),
		cacheOrder:      make([]string, 0),
		maxCacheSize:    cfg.MaxCacheSize,
		useStreams:      cfg.UseStreams,
		streamsTimeout:  cfg.StreamsTimeout,
	}

	if cfg.UseStreams && cfg.RedisClient != nil {
		resolver.clusterInfoWaiter = NewClusterInfoWaiter(cfg.RedisClient, "")
	}

	return resolver
}

func (r *OrchestratorClusterResolver) Start(ctx context.Context) error {
	if !r.useStreams || r.clusterInfoWaiter == nil {
		return nil
	}
	return r.clusterInfoWaiter.Start(ctx)
}

func (r *OrchestratorClusterResolver) Close() error {
	if r.clusterInfoWaiter == nil {
		return nil
	}
	return r.clusterInfoWaiter.Close()
}

func (r *OrchestratorClusterResolver) Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	// Cache
	if cached := r.getFromCache(ctx, databaseID); cached != nil {
		return cached, nil
	}

	var lastErr error
	for attempt := 1; attempt <= r.maxRetries; attempt++ {
		info, err := r.fetchFromOrchestrator(ctx, databaseID)
		if err == nil {
			r.setCache(ctx, databaseID, info)
			return info, nil
		}
		lastErr = err
		if attempt < r.maxRetries {
			time.Sleep(r.retryDelay * time.Duration(attempt))
		}
	}

	return nil, fmt.Errorf("failed to resolve cluster info after %d attempts: %w", r.maxRetries, lastErr)
}

func (r *OrchestratorClusterResolver) InvalidateCache(ctx context.Context, databaseID string) {
	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)

	if r.redisClient != nil {
		_ = r.redisClient.Del(ctx, cacheKey).Err()
	}

	r.cacheMu.Lock()
	defer r.cacheMu.Unlock()
	delete(r.cache, databaseID)
}

func (r *OrchestratorClusterResolver) fetchFromOrchestrator(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	log := logger.GetLogger()

	if r.useStreams && r.clusterInfoWaiter != nil {
		info, err := r.clusterInfoWaiter.RequestClusterInfo(ctx, databaseID, r.streamsTimeout)
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

	return r.fetchViaHTTP(ctx, databaseID)
}

func (r *OrchestratorClusterResolver) fetchViaHTTP(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	url := fmt.Sprintf("%s/api/v2/internal/get-database-cluster-info?database_id=%s", r.orchestratorURL, databaseID)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	if r.apiKey != "" {
		req.Header.Set("X-Internal-Service-Token", r.apiKey)
	}

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code %d: %s", resp.StatusCode, string(body))
	}

	var apiResponse struct {
		Success     bool `json:"success"`
		ClusterInfo struct {
			DatabaseID  string `json:"database_id"`
			ClusterID   string `json:"cluster_id"`
			InfobaseID  string `json:"infobase_id"`
			RASServer   string `json:"ras_server"`
			ClusterUser string `json:"cluster_user"`
			ClusterPwd  string `json:"cluster_pwd"`
		} `json:"cluster_info"`
	}
	if err := json.Unmarshal(body, &apiResponse); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}
	if !apiResponse.Success {
		return nil, fmt.Errorf("unexpected response: %s", string(body))
	}

	if apiResponse.ClusterInfo.ClusterID == "" {
		return nil, fmt.Errorf("cluster_id not available for database %s (not configured in Orchestrator)", databaseID)
	}
	if apiResponse.ClusterInfo.InfobaseID == "" {
		return nil, fmt.Errorf("infobase_id not available for database %s", databaseID)
	}

	return &ClusterInfo{
		DatabaseID:  databaseID,
		ClusterID:   apiResponse.ClusterInfo.ClusterID,
		InfobaseID:  apiResponse.ClusterInfo.InfobaseID,
		RASServer:   apiResponse.ClusterInfo.RASServer,
		ClusterUser: apiResponse.ClusterInfo.ClusterUser,
		ClusterPwd:  apiResponse.ClusterInfo.ClusterPwd,
	}, nil
}

func (r *OrchestratorClusterResolver) getFromCache(ctx context.Context, databaseID string) *ClusterInfo {
	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)

	if r.redisClient != nil {
		val, err := r.redisClient.Get(ctx, cacheKey).Result()
		if err == nil && val != "" {
			var info ClusterInfo
			if jsonErr := json.Unmarshal([]byte(val), &info); jsonErr == nil {
				return &info
			}
		}
	}

	r.cacheMu.RLock()
	entry, ok := r.cache[databaseID]
	r.cacheMu.RUnlock()
	if !ok || entry == nil {
		return nil
	}
	if time.Now().After(entry.expiresAt) {
		r.cacheMu.Lock()
		delete(r.cache, databaseID)
		r.cacheMu.Unlock()
		return nil
	}
	return entry.info
}

func (r *OrchestratorClusterResolver) setCache(ctx context.Context, databaseID string, info *ClusterInfo) {
	if info == nil {
		return
	}

	cacheKey := fmt.Sprintf("cluster_info:%s", databaseID)
	if r.redisClient != nil {
		if b, err := json.Marshal(info); err == nil {
			_ = r.redisClient.Set(ctx, cacheKey, string(b), r.cacheTTL).Err()
		}
	}

	r.cacheMu.Lock()
	defer r.cacheMu.Unlock()

	if len(r.cache) >= r.maxCacheSize {
		if len(r.cacheOrder) > 0 {
			oldest := r.cacheOrder[0]
			r.cacheOrder = r.cacheOrder[1:]
			delete(r.cache, oldest)
		}
	}
	r.cache[databaseID] = &cacheEntry{info: info, expiresAt: time.Now().Add(r.cacheTTL)}
	r.cacheOrder = append(r.cacheOrder, databaseID)
}

// NullResolver always returns an error (useful as explicit placeholder).
type NullResolver struct{}

func (r *NullResolver) Resolve(ctx context.Context, databaseID string) (*ClusterInfo, error) {
	return nil, fmt.Errorf(
		"ClusterInfoResolver not configured: cannot resolve cluster info for database %s. "+
			"Hint: configure OrchestratorURL or enable Streams-based cluster info resolution.",
		databaseID,
	)
}
