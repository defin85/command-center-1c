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
	// OData credentials
	ODataURL string `json:"odata_url"`
	Username string `json:"username"`
	Password string `json:"password"`
	// Legacy fields (for OData)
	Host     string `json:"host"`
	Port     int    `json:"port"`
	BaseName string `json:"base_name"`
	// NEW: Поля для DESIGNER подключения (из 1C Server)
	ServerAddress string `json:"server_address"`
	ServerPort    int    `json:"server_port"`
	InfobaseName  string `json:"infobase_name"`
}

// Client fetches credentials from Orchestrator API
type Client struct {
	orchestratorURL string
	serviceToken    string // JWT token for service-to-service auth
	transportKey    []byte // AES-256 key for decrypting credentials payload
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

// NewClient creates a new credentials client with JWT service token and transport encryption key
func NewClient(orchestratorURL, serviceToken string, transportKey []byte) *Client {
	return &Client{
		orchestratorURL: orchestratorURL,
		serviceToken:    serviceToken,
		transportKey:    transportKey, // NEW: для decryption
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

	logger.Debugf(
		"received encrypted credentials, database_id=%s, encryption_version=%s, expires_at=%s",
		databaseID,
		encResp.EncryptionVersion,
		encResp.ExpiresAt,
	)

	// Decrypt credentials using transport key (AES-GCM-256)
	creds, err := DecryptCredentials(encResp, c.transportKey)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt credentials: %w", err)
	}

	logger.Infof("credentials decrypted successfully, database_id=%s, odata_url=%s", databaseID, creds.ODataURL)

	return creds, nil
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
