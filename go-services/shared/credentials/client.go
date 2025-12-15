// go-services/shared/credentials/client.go
package credentials

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Client fetches credentials from Orchestrator API
type Client struct {
	orchestratorURL string
	serviceToken    string // JWT token for service-to-service auth
	transportKey    []byte // AES-256 key for decrypting credentials payload
	httpClient      *http.Client
	logger          *zap.Logger

	// Cache with TTL
	cache    map[string]*cacheEntry
	cacheMu  sync.RWMutex
	cacheTTL time.Duration

	// Background cleanup
	cleanupCancel context.CancelFunc
	cleanupWg     sync.WaitGroup
}

type cacheEntry struct {
	credentials *DatabaseCredentials
	expiresAt   time.Time
}

// ClientConfig holds configuration for credentials client
type ClientConfig struct {
	OrchestratorURL string
	ServiceToken    string
	TransportKey    []byte
	CacheTTL        time.Duration // Optional: defaults to 2 minutes
	HTTPTimeout     time.Duration // Optional: defaults to 10 seconds
	Logger          *zap.Logger   // Optional: defaults to nop logger
}

// NewClient creates a new credentials client with JWT service token and transport encryption key
func NewClient(orchestratorURL, serviceToken string, transportKey []byte) *Client {
	return NewClientWithConfig(ClientConfig{
		OrchestratorURL: orchestratorURL,
		ServiceToken:    serviceToken,
		TransportKey:    transportKey,
	})
}

// NewClientWithConfig creates a new credentials client with full configuration
func NewClientWithConfig(cfg ClientConfig) *Client {
	cacheTTL := cfg.CacheTTL
	if cacheTTL == 0 {
		cacheTTL = 2 * time.Minute
	}

	httpTimeout := cfg.HTTPTimeout
	if httpTimeout == 0 {
		httpTimeout = 10 * time.Second
	}

	logger := cfg.Logger
	if logger == nil {
		logger = zap.NewNop()
	}

	ctx, cancel := context.WithCancel(context.Background())

	client := &Client{
		orchestratorURL: cfg.OrchestratorURL,
		serviceToken:    cfg.ServiceToken,
		transportKey:    cfg.TransportKey,
		httpClient: &http.Client{
			Timeout: httpTimeout,
		},
		cache:         make(map[string]*cacheEntry),
		cacheTTL:      cacheTTL,
		logger:        logger,
		cleanupCancel: cancel,
	}

	// Start background cache cleanup
	client.startCacheCleanup(ctx)

	return client
}

// Close stops the background cleanup goroutine
func (c *Client) Close() {
	if c.cleanupCancel != nil {
		c.cleanupCancel()
		c.cleanupWg.Wait()
	}
}

// Fetch fetches credentials for a database (with caching)
func (c *Client) Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	// Check cache first
	if creds := c.getFromCache(databaseID); creds != nil {
		c.logger.Debug("credentials cache hit",
			zap.String("database_id", databaseID))
		return creds, nil
	}

	// Cache miss - fetch from API
	c.logger.Debug("credentials cache miss, fetching from API",
		zap.String("database_id", databaseID))

	creds, err := c.fetchFromAPI(ctx, databaseID)
	if err != nil {
		return nil, err
	}

	// Store in cache
	c.putInCache(databaseID, creds)

	return creds, nil
}

func (c *Client) fetchFromAPI(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	url := fmt.Sprintf("%s/api/v1/databases/%s/credentials", c.orchestratorURL, databaseID)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set authorization header (JWT Bearer token)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.serviceToken))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch credentials: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return nil, fmt.Errorf("authentication failed: invalid API key")
	}

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("database %s not found", databaseID)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	// Decode encrypted response from Django Orchestrator
	var encResp EncryptedCredentialsResponse
	if err := json.NewDecoder(resp.Body).Decode(&encResp); err != nil {
		return nil, fmt.Errorf("failed to decode encrypted response: %w", err)
	}

	c.logger.Debug("received encrypted credentials",
		zap.String("database_id", databaseID),
		zap.String("encryption_version", encResp.EncryptionVersion))

	// Decrypt credentials using transport key (AES-GCM-256)
	creds, err := DecryptCredentials(encResp, c.transportKey)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt credentials: %w", err)
	}

	c.logger.Debug("credentials fetched successfully",
		zap.String("database_id", databaseID))

	return creds, nil
}

// getFromCache retrieves credentials from cache with proper expiration handling.
// Thread-safe: handles race condition by checking expiration under lock.
func (c *Client) getFromCache(databaseID string) *DatabaseCredentials {
	c.cacheMu.RLock()
	entry, ok := c.cache[databaseID]
	if !ok {
		c.cacheMu.RUnlock()
		return nil
	}

	// Check expiration while holding read lock
	if time.Now().After(entry.expiresAt) {
		c.cacheMu.RUnlock()
		// Cleanup expired entry (upgrade to write lock)
		c.cacheMu.Lock()
		// Double-check after acquiring write lock (another goroutine may have cleaned it)
		if e, exists := c.cache[databaseID]; exists && time.Now().After(e.expiresAt) {
			delete(c.cache, databaseID)
		}
		c.cacheMu.Unlock()
		return nil
	}

	// Copy credentials before releasing lock
	creds := entry.credentials
	c.cacheMu.RUnlock()
	return creds
}

func (c *Client) putInCache(databaseID string, creds *DatabaseCredentials) {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	c.cache[databaseID] = &cacheEntry{
		credentials: creds,
		expiresAt:   time.Now().Add(c.cacheTTL),
	}
}

// ClearCache clears the credentials cache
func (c *Client) ClearCache() {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	c.cache = make(map[string]*cacheEntry)
	c.logger.Info("credentials cache cleared")
}

// InvalidateCache removes a specific database from cache
func (c *Client) InvalidateCache(databaseID string) {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	delete(c.cache, databaseID)
	c.logger.Debug("credentials cache invalidated",
		zap.String("database_id", databaseID))
}

// startCacheCleanup starts background goroutine to cleanup expired entries every 5 minutes
func (c *Client) startCacheCleanup(ctx context.Context) {
	c.cleanupWg.Add(1)
	go func() {
		defer c.cleanupWg.Done()
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				c.cleanupExpiredEntries()
			}
		}
	}()
}

// cleanupExpiredEntries removes all expired entries from cache
func (c *Client) cleanupExpiredEntries() {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()

	now := time.Now()
	expiredCount := 0
	for id, entry := range c.cache {
		if now.After(entry.expiresAt) {
			delete(c.cache, id)
			expiredCount++
		}
	}

	if expiredCount > 0 {
		c.logger.Debug("credentials cache cleanup completed",
			zap.Int("expired_entries_removed", expiredCount),
			zap.Int("remaining_entries", len(c.cache)))
	}
}

// CacheSize returns the current number of entries in the cache (for testing/monitoring)
func (c *Client) CacheSize() int {
	c.cacheMu.RLock()
	defer c.cacheMu.RUnlock()
	return len(c.cache)
}
