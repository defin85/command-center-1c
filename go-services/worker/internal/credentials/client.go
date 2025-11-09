// go-services/worker/internal/credentials/client.go
package credentials

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// DatabaseCredentials represents credentials for a 1C database
type DatabaseCredentials struct {
	DatabaseID string `json:"database_id"`
	ODataURL   string `json:"odata_url"`
	Username   string `json:"username"`
	Password   string `json:"password"`
}

// Client fetches credentials from Orchestrator API
type Client struct {
	orchestratorURL string
	apiKey          string
	httpClient      *http.Client

	// Cache with TTL
	cache    map[string]*cacheEntry
	cacheMu  sync.RWMutex
	cacheTTL time.Duration
}

type cacheEntry struct {
	credentials *DatabaseCredentials
	expiresAt   time.Time
}

// NewClient creates a new credentials client
func NewClient(orchestratorURL, apiKey string) *Client {
	return &Client{
		orchestratorURL: orchestratorURL,
		apiKey:          apiKey,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
		cache:    make(map[string]*cacheEntry),
		cacheTTL: 2 * time.Minute, // 2 minutes cache TTL
	}
}

// Fetch fetches credentials for a database (with caching)
func (c *Client) Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	// Check cache first
	if creds := c.getFromCache(databaseID); creds != nil {
		logger.Debugf("credentials cache hit, database_id=%s", databaseID)
		return creds, nil
	}

	// Cache miss - fetch from API
	logger.Debugf("credentials cache miss, fetching from API, database_id=%s", databaseID)

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

	// Set authorization header (API Key)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
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

	var creds DatabaseCredentials
	if err := json.NewDecoder(resp.Body).Decode(&creds); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	logger.Infof("credentials fetched successfully, database_id=%s, odata_url=%s", databaseID, creds.ODataURL)

	return &creds, nil
}

func (c *Client) getFromCache(databaseID string) *DatabaseCredentials {
	c.cacheMu.RLock()
	defer c.cacheMu.RUnlock()

	entry, exists := c.cache[databaseID]
	if !exists {
		return nil
	}

	// Check expiration
	if time.Now().After(entry.expiresAt) {
		return nil
	}

	return entry.credentials
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
	logger.Info("credentials cache cleared")
}
