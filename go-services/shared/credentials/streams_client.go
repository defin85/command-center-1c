package credentials

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/commandcenter1c/commandcenter/shared/events"
)

var (
	ErrStreamsRedisUnavailable     = errors.New("redis client is required for streams credentials client")
	ErrStreamsClientClosed         = errors.New("streams credentials client is closed")
	ErrStreamsCredentialsTimeout   = errors.New("credentials response timeout")
	ErrStreamsCredentialsNotFound  = errors.New("database not found in Orchestrator")
	ErrStreamsCredentialsMalformed = errors.New("malformed credentials response")
)

type credentialsResponse struct {
	CorrelationID string `json:"correlation_id"`
	DatabaseID    string `json:"database_id"`
	Success       bool   `json:"success"`
	ErrorCode     string `json:"error_code,omitempty"`
	Error         string `json:"error,omitempty"`

	EncryptedData     string `json:"encrypted_data,omitempty"`
	Nonce             string `json:"nonce,omitempty"`
	ExpiresAt         string `json:"expires_at,omitempty"`
	EncryptionVersion string `json:"encryption_version,omitempty"`
}

type StreamsClientConfig struct {
	RedisClient    *redis.Client
	TransportKey   []byte
	RequestTimeout time.Duration
	CacheTTL       time.Duration
	ConsumerGroup  string
	Logger         *zap.Logger
}

// StreamsClient fetches encrypted credentials from Orchestrator using Redis Streams (request-response).
// It keeps a small in-memory cache with TTL (same behavior as the HTTP client).
type StreamsClient struct {
	redisClient    *redis.Client
	transportKey   []byte
	requestTimeout time.Duration
	consumerGroup  string
	logger         *zap.Logger

	cache    map[string]*cacheEntry
	cacheMu  sync.RWMutex
	cacheTTL time.Duration

	pending map[string]chan *credentialsResponse
	mu      sync.RWMutex
	closed  bool

	cancel context.CancelFunc
	wg     sync.WaitGroup

	cleanupWg sync.WaitGroup
}

func NewStreamsClient(cfg StreamsClientConfig) (*StreamsClient, error) {
	if cfg.RedisClient == nil {
		return nil, ErrStreamsRedisUnavailable
	}
	if len(cfg.TransportKey) == 0 {
		return nil, fmt.Errorf("transport key is required")
	}

	cacheTTL := cfg.CacheTTL
	if cacheTTL == 0 {
		cacheTTL = 2 * time.Minute
	}

	requestTimeout := cfg.RequestTimeout
	if requestTimeout == 0 {
		requestTimeout = 5 * time.Second
	}

	consumerGroup := cfg.ConsumerGroup
	if consumerGroup == "" {
		consumerGroup = events.ConsumerGroupWorkerCredentials
	}

	logger := cfg.Logger
	if logger == nil {
		logger = zap.NewNop()
	}

	client := &StreamsClient{
		redisClient:    cfg.RedisClient,
		transportKey:   cfg.TransportKey,
		requestTimeout: requestTimeout,
		consumerGroup:  consumerGroup,
		logger:         logger,
		cache:          make(map[string]*cacheEntry),
		cacheTTL:       cacheTTL,
		pending:        make(map[string]chan *credentialsResponse),
	}

	client.start()
	return client, nil
}

func (c *StreamsClient) start() {
	ctx, cancel := context.WithCancel(context.Background())
	c.cancel = cancel

	// Ensure consumer group exists for response stream
	stream := events.StreamEventsDatabaseCredentialsResponse
	if err := c.redisClient.XGroupCreateMkStream(ctx, stream, c.consumerGroup, "0").Err(); err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		c.logger.Warn("failed to create consumer group for credentials response stream", zap.Error(err), zap.String("stream", stream))
	}

	// Start response consumer loop
	c.wg.Add(1)
	go c.consumeLoop(ctx, stream)

	// Start cache cleanup
	c.cleanupWg.Add(1)
	go c.cleanupLoop(ctx)
}

// Close stops background goroutines.
func (c *StreamsClient) Close() {
	c.mu.Lock()
	if c.closed {
		c.mu.Unlock()
		return
	}
	c.closed = true
	cancel := c.cancel
	c.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	c.wg.Wait()
	c.cleanupWg.Wait()

	// Close pending channels
	c.mu.Lock()
	for _, ch := range c.pending {
		close(ch)
	}
	c.pending = make(map[string]chan *credentialsResponse)
	c.mu.Unlock()
}

// Fetch fetches credentials for a database (with caching).
func (c *StreamsClient) Fetch(ctx context.Context, databaseID string) (*DatabaseCredentials, error) {
	if databaseID == "" {
		return nil, fmt.Errorf("database ID is required")
	}

	if creds := c.getFromCache(databaseID); creds != nil {
		return creds, nil
	}

	resp, err := c.request(ctx, databaseID)
	if err != nil {
		return nil, err
	}

	encrypted := EncryptedCredentialsResponse{
		EncryptedData:     resp.EncryptedData,
		Nonce:             resp.Nonce,
		ExpiresAt:         resp.ExpiresAt,
		EncryptionVersion: resp.EncryptionVersion,
	}

	creds, err := DecryptCredentials(encrypted, c.transportKey)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt credentials: %w", err)
	}

	c.putInCache(databaseID, creds)
	return creds, nil
}

func (c *StreamsClient) request(ctx context.Context, databaseID string) (*credentialsResponse, error) {
	c.mu.Lock()
	if c.closed {
		c.mu.Unlock()
		return nil, ErrStreamsClientClosed
	}
	correlationID := uuid.New().String()
	ch := make(chan *credentialsResponse, 1)
	c.pending[correlationID] = ch
	c.mu.Unlock()

	defer func() {
		c.mu.Lock()
		delete(c.pending, correlationID)
		close(ch)
		c.mu.Unlock()
	}()

	requestPayload := map[string]interface{}{
		"correlation_id": correlationID,
		"database_id":    databaseID,
		"timestamp":      time.Now().UTC().Format(time.RFC3339),
	}
	if requestedBy := RequestedByFromContext(ctx); requestedBy != "" {
		requestPayload["created_by"] = requestedBy
	}
	if strategy := IbAuthStrategyFromContext(ctx); strategy != "" {
		requestPayload["ib_auth_strategy"] = strategy
	}
	if strategy := DbmsAuthStrategyFromContext(ctx); strategy != "" {
		requestPayload["dbms_auth_strategy"] = strategy
	}
	if purpose := CredentialsPurposeFromContext(ctx); purpose != "" {
		requestPayload["credentials_purpose"] = purpose
	}

	// Publish request
	if err := c.redisClient.XAdd(ctx, &redis.XAddArgs{
		Stream: events.StreamCommandsGetDatabaseCredentials,
		Values: requestPayload,
	}).Err(); err != nil {
		return nil, fmt.Errorf("failed to publish credentials request: %w", err)
	}

	timeout := c.requestTimeout
	if deadline, ok := ctx.Deadline(); ok {
		remaining := time.Until(deadline)
		if remaining > 0 && remaining < timeout {
			timeout = remaining
		}
	}

	waitCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	select {
	case resp := <-ch:
		if resp == nil {
			return nil, ErrStreamsCredentialsMalformed
		}
		if !resp.Success {
			if resp.ErrorCode != "" && resp.Error != "" {
				return nil, fmt.Errorf("%w: %s: %s", ErrStreamsCredentialsNotFound, resp.ErrorCode, resp.Error)
			}
			if resp.ErrorCode != "" {
				return nil, fmt.Errorf("%w: %s", ErrStreamsCredentialsNotFound, resp.ErrorCode)
			}
			if resp.Error != "" {
				return nil, fmt.Errorf("%w: %s", ErrStreamsCredentialsNotFound, resp.Error)
			}
			return nil, ErrStreamsCredentialsNotFound
		}
		if resp.EncryptedData == "" || resp.Nonce == "" || resp.ExpiresAt == "" || resp.EncryptionVersion == "" {
			return nil, ErrStreamsCredentialsMalformed
		}
		return resp, nil
	case <-waitCtx.Done():
		if errors.Is(waitCtx.Err(), context.DeadlineExceeded) {
			return nil, fmt.Errorf("%w: correlation_id=%s", ErrStreamsCredentialsTimeout, correlationID)
		}
		return nil, waitCtx.Err()
	}
}

func (c *StreamsClient) consumeLoop(ctx context.Context, stream string) {
	defer c.wg.Done()

	consumerID := fmt.Sprintf("worker-creds-%d", time.Now().UnixNano())

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		result, err := c.redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    c.consumerGroup,
			Consumer: consumerID,
			Streams:  []string{stream, ">"},
			Count:    10,
			Block:    1 * time.Second,
		}).Result()
		if err != nil {
			if errors.Is(err, redis.Nil) {
				continue
			}
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return
			}
			c.logger.Warn("error reading credentials response stream", zap.Error(err))
			time.Sleep(100 * time.Millisecond)
			continue
		}

		for _, streamData := range result {
			for _, msg := range streamData.Messages {
				c.handleMessage(ctx, stream, msg)
			}
		}
	}
}

func (c *StreamsClient) handleMessage(ctx context.Context, streamName string, msg redis.XMessage) {
	var resp credentialsResponse

	if v, ok := msg.Values["correlation_id"].(string); ok {
		resp.CorrelationID = v
	}
	if v, ok := msg.Values["database_id"].(string); ok {
		resp.DatabaseID = v
	}
	if v, ok := msg.Values["success"].(string); ok {
		resp.Success = v == "true" || v == "True" || v == "1"
	}
	if v, ok := msg.Values["error"].(string); ok {
		resp.Error = v
	}
	if v, ok := msg.Values["error_code"].(string); ok {
		resp.ErrorCode = v
	}
	if v, ok := msg.Values["encrypted_data"].(string); ok {
		resp.EncryptedData = v
	}
	if v, ok := msg.Values["nonce"].(string); ok {
		resp.Nonce = v
	}
	if v, ok := msg.Values["expires_at"].(string); ok {
		resp.ExpiresAt = v
	}
	if v, ok := msg.Values["encryption_version"].(string); ok {
		resp.EncryptionVersion = v
	}

	// Fallback: parse JSON payload field
	if resp.CorrelationID == "" {
		if payload, ok := msg.Values["payload"].(string); ok {
			_ = json.Unmarshal([]byte(payload), &resp)
		} else if data, ok := msg.Values["data"].(string); ok {
			_ = json.Unmarshal([]byte(data), &resp)
		}
	}

	if resp.CorrelationID != "" {
		c.mu.RLock()
		ch := c.pending[resp.CorrelationID]
		c.mu.RUnlock()
		if ch != nil {
			select {
			case ch <- &resp:
			default:
			}
		}
	}

	_ = c.redisClient.XAck(ctx, streamName, c.consumerGroup, msg.ID).Err()
}

// --- cache cleanup (shared logic copied from HTTP client) ---

func (c *StreamsClient) getFromCache(databaseID string) *DatabaseCredentials {
	c.cacheMu.RLock()
	entry, ok := c.cache[databaseID]
	if !ok {
		c.cacheMu.RUnlock()
		return nil
	}
	if time.Now().After(entry.expiresAt) {
		c.cacheMu.RUnlock()
		c.cacheMu.Lock()
		if e, exists := c.cache[databaseID]; exists && time.Now().After(e.expiresAt) {
			delete(c.cache, databaseID)
		}
		c.cacheMu.Unlock()
		return nil
	}
	creds := entry.credentials
	c.cacheMu.RUnlock()
	return creds
}

func (c *StreamsClient) putInCache(databaseID string, creds *DatabaseCredentials) {
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()
	c.cache[databaseID] = &cacheEntry{
		credentials: creds,
		expiresAt:   time.Now().Add(c.cacheTTL),
	}
}

var _ Fetcher = (*StreamsClient)(nil)

// cleanupLoop periodically removes expired cache entries.
func (c *StreamsClient) cleanupLoop(ctx context.Context) {
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
}

// Reuse the same cleanup implementation as the HTTP client (in this package).
func (c *StreamsClient) cleanupExpiredEntries() {
	now := time.Now()
	c.cacheMu.Lock()
	defer c.cacheMu.Unlock()
	for k, entry := range c.cache {
		if now.After(entry.expiresAt) {
			delete(c.cache, k)
		}
	}
}
