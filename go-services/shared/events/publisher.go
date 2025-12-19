package events

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill-redisstream/pkg/redisstream"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/redis/go-redis/v9"

	"github.com/commandcenter1c/commandcenter/shared/httptrace"
	"github.com/commandcenter1c/commandcenter/shared/logger"
)

// Publisher wraps Watermill Publisher with our Envelope format
type Publisher struct {
	watermill      *redisstream.Publisher
	serviceName    string
	serviceToken   string // WORKER_API_KEY for internal service authentication
	logger         watermill.LoggerAdapter
	closed         bool
	mu             sync.RWMutex
	maxPayloadSize int64
	fallbackClient *http.Client // Reusable HTTP client for fallback requests
}

// NewPublisher creates a new event publisher
func NewPublisher(redisClient *redis.Client, serviceName string, logger watermill.LoggerAdapter) (*Publisher, error) {
	if redisClient == nil {
		return nil, ErrRedisUnavailable
	}

	if serviceName == "" {
		return nil, ErrEmptyServiceName
	}

	if logger == nil {
		logger = watermill.NewStdLogger(false, false)
	}

	// Check Redis availability
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := RedisHealthCheck(ctx, redisClient); err != nil {
		logger.Error("Redis health check failed, attempting reconnect...", err, nil)

		// Wait for Redis to become available
		if err := WaitForRedis(ctx, redisClient, 3, 2*time.Second); err != nil {
			return nil, fmt.Errorf("redis unavailable: %w", err)
		}

		logger.Info("Redis reconnected successfully", nil)
	}

	// Create Watermill Redis Streams publisher
	publisher, err := redisstream.NewPublisher(
		redisstream.PublisherConfig{
			Client:     redisClient,
			Marshaller: &redisstream.DefaultMarshallerUnmarshaller{},
		},
		logger,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create watermill publisher: %w", err)
	}

	return &Publisher{
		watermill:      publisher,
		serviceName:    serviceName,
		logger:         logger,
		closed:         false,
		maxPayloadSize: DefaultMaxPayloadSize,
		fallbackClient: &http.Client{
			Timeout: 5 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        10,
				MaxIdleConnsPerHost: 5,
				IdleConnTimeout:     30 * time.Second,
			},
		},
	}, nil
}

// SetServiceToken sets the service authentication token for internal API calls
func (p *Publisher) SetServiceToken(token string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.serviceToken = token
}

// Publish publishes an event to the specified channel
// It automatically generates message_id and timestamp, and wraps the payload in an Envelope
func (p *Publisher) Publish(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string) error {
	start := time.Now()
	defer func() {
		RecordPublish(p.serviceName, channel, eventType, time.Since(start))
	}()

	p.mu.RLock()
	if p.closed {
		p.mu.RUnlock()
		return ErrPublisherClosed
	}
	p.mu.RUnlock()

	// Create envelope
	envelope, err := NewEnvelope(eventType, p.serviceName, payload, correlationID)
	if err != nil {
		p.logger.Error("Failed to create envelope", err, watermill.LogFields{
			"event_type": eventType,
			"channel":    channel,
		})
		return fmt.Errorf("failed to create envelope: %w", err)
	}

	// Validate envelope
	if err := envelope.Validate(); err != nil {
		p.logger.Error("Invalid envelope", err, watermill.LogFields{
			"event_type": eventType,
			"channel":    channel,
		})
		return fmt.Errorf("invalid envelope: %w", err)
	}

	// Marshal envelope to JSON
	envelopeBytes, err := json.Marshal(envelope)
	if err != nil {
		p.logger.Error("Failed to marshal envelope", err, watermill.LogFields{
			"event_type": eventType,
			"channel":    channel,
		})
		return fmt.Errorf("failed to marshal envelope: %w", err)
	}

	// Check payload size
	if int64(len(envelopeBytes)) > p.maxPayloadSize {
		p.logger.Error("Payload too large", ErrPayloadTooLarge, watermill.LogFields{
			"event_type":    eventType,
			"channel":       channel,
			"envelope_size": len(envelopeBytes),
			"max_size":      p.maxPayloadSize,
		})
		return fmt.Errorf("envelope size %d bytes: %w", len(envelopeBytes), ErrPayloadTooLarge)
	}

	// Create Watermill message
	msg := message.NewMessage(envelope.MessageID, envelopeBytes)
	msg.Metadata.Set("correlation_id", envelope.CorrelationID)
	msg.Metadata.Set("event_type", envelope.EventType)
	msg.Metadata.Set("service_name", envelope.ServiceName)

	// Publish message
	if err := p.watermill.Publish(channel, msg); err != nil {
		p.logger.Error("Failed to publish message", err, watermill.LogFields{
			"event_type":     eventType,
			"channel":        channel,
			"message_id":     envelope.MessageID,
			"correlation_id": envelope.CorrelationID,
		})
		return fmt.Errorf("failed to publish message: %w", err)
	}

	p.logger.Info("Message published successfully", watermill.LogFields{
		"event_type":     eventType,
		"channel":        channel,
		"message_id":     envelope.MessageID,
		"correlation_id": envelope.CorrelationID,
	})

	return nil
}

// PublishWithMetadata publishes an event with custom metadata
func (p *Publisher) PublishWithMetadata(ctx context.Context, channel string, eventType string, payload interface{}, correlationID string, metadata map[string]interface{}) error {
	start := time.Now()
	defer func() {
		RecordPublish(p.serviceName, channel, eventType, time.Since(start))
	}()

	p.mu.RLock()
	if p.closed {
		p.mu.RUnlock()
		return ErrPublisherClosed
	}
	p.mu.RUnlock()

	// Create envelope
	envelope, err := NewEnvelope(eventType, p.serviceName, payload, correlationID)
	if err != nil {
		return fmt.Errorf("failed to create envelope: %w", err)
	}

	// Add custom metadata
	for key, value := range metadata {
		envelope.SetMetadata(key, value)
	}

	// Validate envelope
	if err := envelope.Validate(); err != nil {
		return fmt.Errorf("invalid envelope: %w", err)
	}

	// Marshal envelope to JSON
	envelopeBytes, err := json.Marshal(envelope)
	if err != nil {
		return fmt.Errorf("failed to marshal envelope: %w", err)
	}

	// Check payload size
	if int64(len(envelopeBytes)) > p.maxPayloadSize {
		return fmt.Errorf("envelope size %d bytes: %w", len(envelopeBytes), ErrPayloadTooLarge)
	}

	// Create Watermill message
	msg := message.NewMessage(envelope.MessageID, envelopeBytes)
	msg.Metadata.Set("correlation_id", envelope.CorrelationID)
	msg.Metadata.Set("event_type", envelope.EventType)
	msg.Metadata.Set("service_name", envelope.ServiceName)

	// Publish message
	if err := p.watermill.Publish(channel, msg); err != nil {
		p.logger.Error("Failed to publish message", err, watermill.LogFields{
			"event_type":     eventType,
			"channel":        channel,
			"message_id":     envelope.MessageID,
			"correlation_id": envelope.CorrelationID,
		})
		return fmt.Errorf("failed to publish message: %w", err)
	}

	p.logger.Info("Message published successfully", watermill.LogFields{
		"event_type":     eventType,
		"channel":        channel,
		"message_id":     envelope.MessageID,
		"correlation_id": envelope.CorrelationID,
	})

	return nil
}

// PublishWithFallback publishes event to Redis with PostgreSQL fallback
// If Redis publish fails, stores event in PostgreSQL via Orchestrator API
func (p *Publisher) PublishWithFallback(
	ctx context.Context,
	channel string,
	eventType string,
	payload interface{},
	correlationID string,
	fallbackURL string, // Orchestrator URL, e.g., "http://localhost:8200"
) error {
	// Try Redis first
	err := p.Publish(ctx, channel, eventType, payload, correlationID)
	if err == nil {
		return nil
	}

	// Redis failed, log and fallback to PostgreSQL
	p.logger.Info("Redis publish failed, using PostgreSQL fallback",
		watermill.LogFields{
			"channel":        channel,
			"event_type":     eventType,
			"correlation_id": correlationID,
			"error":          err.Error(),
		})

	return p.storeFailedEvent(ctx, channel, eventType, payload, correlationID, fallbackURL)
}

// storeFailedEvent stores failed event in PostgreSQL via Orchestrator API
func (p *Publisher) storeFailedEvent(
	ctx context.Context,
	channel string,
	eventType string,
	payload interface{},
	correlationID string,
	fallbackURL string,
) error {
	// Serialize payload
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	fallbackPayload := map[string]interface{}{
		"channel":            channel,
		"event_type":         eventType,
		"correlation_id":     correlationID,
		"payload":            json.RawMessage(payloadBytes),
		"source_service":     p.serviceName,
		"original_timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	body, err := json.Marshal(fallbackPayload)
	if err != nil {
		return fmt.Errorf("marshal fallback: %w", err)
	}

	url := fmt.Sprintf("%s/api/v2/events/store-failed/", fallbackURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	// Add service authentication token (requires WORKER_API_KEY)
	p.mu.RLock()
	if p.serviceToken != "" {
		req.Header.Set("X-Internal-Service-Token", p.serviceToken)
	}
	p.mu.RUnlock()

	// Use reusable HTTP client for connection pooling
	start := time.Now()
	resp, err := p.fallbackClient.Do(req)
	if err != nil {
		httptrace.LogRequestError(logger.GetLogger(), req, time.Since(start), err)
		return fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	httptrace.LogRequest(logger.GetLogger(), req, resp.StatusCode, time.Since(start))

	if resp.StatusCode >= 400 {
		return fmt.Errorf("fallback API returned %d", resp.StatusCode)
	}

	p.logger.Info("Event stored in PostgreSQL fallback",
		watermill.LogFields{
			"channel":        channel,
			"event_type":     eventType,
			"correlation_id": correlationID,
		})

	return nil
}

// Close gracefully shuts down the publisher
func (p *Publisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.closed {
		return nil
	}

	p.closed = true

	if err := p.watermill.Close(); err != nil {
		p.logger.Error("Failed to close publisher", err, nil)
		return fmt.Errorf("failed to close publisher: %w", err)
	}

	p.logger.Info("Publisher closed successfully", nil)
	return nil
}
