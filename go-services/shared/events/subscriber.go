package events

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill-redisstream/pkg/redisstream"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/redis/go-redis/v9"
)

// HandlerFunc is a function that handles an event
// It receives the envelope and returns an error if processing failed
type HandlerFunc func(ctx context.Context, envelope *Envelope) error

// Subscriber wraps Watermill Subscriber with our Envelope format
type Subscriber struct {
	watermill     *redisstream.Subscriber
	router        *message.Router
	logger        watermill.LoggerAdapter
	consumerGroup string
	closed        bool
	mu            sync.RWMutex
	semaphore     chan struct{}
}

// NewSubscriber creates a new event subscriber
func NewSubscriber(redisClient *redis.Client, consumerGroup string, logger watermill.LoggerAdapter) (*Subscriber, error) {
	if redisClient == nil {
		return nil, ErrRedisUnavailable
	}

	if consumerGroup == "" {
		return nil, ErrEmptyConsumerGroup
	}

	if logger == nil {
		logger = watermill.NewStdLogger(false, false)
	}

	// Check Redis availability
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := RedisHealthCheck(ctx, redisClient); err != nil {
		logger.Error("Redis health check failed, attempting reconnect...", err, nil)

		if err := WaitForRedis(ctx, redisClient, 3, 2*time.Second); err != nil {
			return nil, fmt.Errorf("redis unavailable: %w", err)
		}

		logger.Info("Redis reconnected successfully", nil)
	}

	// Create Watermill Redis Streams subscriber
	subscriber, err := redisstream.NewSubscriber(
		redisstream.SubscriberConfig{
			Client:        redisClient,
			Unmarshaller:  &redisstream.DefaultMarshallerUnmarshaller{},
			ConsumerGroup: consumerGroup,
		},
		logger,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create watermill subscriber: %w", err)
	}

	// Create message router
	router, err := message.NewRouter(message.RouterConfig{}, logger)
	if err != nil {
		return nil, fmt.Errorf("failed to create message router: %w", err)
	}

	maxConcurrency := 100 // Default, can be configured via config

	return &Subscriber{
		watermill:     subscriber,
		router:        router,
		logger:        logger,
		consumerGroup: consumerGroup,
		closed:        false,
		semaphore:     make(chan struct{}, maxConcurrency),
	}, nil
}

// Subscribe registers a handler for a specific channel
// Multiple handlers can be registered for different channels
func (s *Subscriber) Subscribe(channel string, handler HandlerFunc) error {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.closed {
		return ErrSubscriberClosed
	}

	// Add metrics middleware to router (only once)
	s.router.AddMiddleware(WithMetrics(s.consumerGroup))

	// Create a unique handler name for this subscription
	handlerName := fmt.Sprintf("%s-%s", s.consumerGroup, channel)

	// Add handler to router
	s.router.AddHandler(
		handlerName,
		channel,
		s.watermill,
		channel, // We don't republish, so topic is same as channel
		nil,     // No publisher needed (not republishing)
		s.createWatermillHandler(handler),
	)

	s.logger.Info("Handler registered", watermill.LogFields{
		"channel":      channel,
		"handler_name": handlerName,
	})

	return nil
}

// createWatermillHandler wraps our HandlerFunc into Watermill's handler format
func (s *Subscriber) createWatermillHandler(handler HandlerFunc) message.HandlerFunc {
	return func(msg *message.Message) ([]*message.Message, error) {
		// Acquire semaphore (backpressure)
		select {
		case s.semaphore <- struct{}{}:
			defer func() { <-s.semaphore }()
		case <-msg.Context().Done():
			return nil, msg.Context().Err()
		}

		// Parse envelope from message
		var envelope Envelope
		if err := json.Unmarshal(msg.Payload, &envelope); err != nil {
			s.logger.Error("Failed to unmarshal envelope", err, watermill.LogFields{
				"message_id": msg.UUID,
			})
			// Return error to NACK the message
			return nil, fmt.Errorf("%w: %v", ErrMalformedMessage, err)
		}

		// Validate envelope
		if err := envelope.Validate(); err != nil {
			s.logger.Error("Invalid envelope", err, watermill.LogFields{
				"message_id": msg.UUID,
				"event_type": envelope.EventType,
			})
			// Return error to NACK the message
			return nil, fmt.Errorf("invalid envelope: %w", err)
		}

		// Create context with correlation ID
		ctx := msg.Context()

		// Handle with panic recovery
		var handlerErr error
		func() {
			defer func() {
				if r := recover(); r != nil {
					s.logger.Error("Handler panic", ErrHandlerPanic, watermill.LogFields{
						"message_id":     envelope.MessageID,
						"correlation_id": envelope.CorrelationID,
						"event_type":     envelope.EventType,
						"panic":          r,
					})
					handlerErr = fmt.Errorf("%w: %v", ErrHandlerPanic, r)
				}
			}()

			// Call the actual handler
			handlerErr = handler(ctx, &envelope)
		}()

		if handlerErr != nil {
			s.logger.Error("Handler failed", handlerErr, watermill.LogFields{
				"message_id":     envelope.MessageID,
				"correlation_id": envelope.CorrelationID,
				"event_type":     envelope.EventType,
			})
			// Return error to NACK the message (will be retried by Watermill)
			return nil, handlerErr
		}

		s.logger.Info("Message processed successfully", watermill.LogFields{
			"message_id":     envelope.MessageID,
			"correlation_id": envelope.CorrelationID,
			"event_type":     envelope.EventType,
		})

		// Return nil to ACK the message
		return nil, nil
	}
}

// Run starts the subscriber and blocks until context is cancelled
// This should be called after all handlers are registered
func (s *Subscriber) Run(ctx context.Context) error {
	s.mu.RLock()
	if s.closed {
		s.mu.RUnlock()
		return ErrSubscriberClosed
	}
	s.mu.RUnlock()

	s.logger.Info("Starting subscriber", watermill.LogFields{
		"consumer_group": s.consumerGroup,
	})

	// Run the router (blocking)
	if err := s.router.Run(ctx); err != nil {
		s.logger.Error("Router stopped with error", err, nil)
		return fmt.Errorf("router error: %w", err)
	}

	s.logger.Info("Subscriber stopped", nil)
	return nil
}

// Close gracefully shuts down the subscriber
func (s *Subscriber) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.closed {
		return nil
	}

	s.closed = true

	if !s.router.IsRunning() {
		if err := s.watermill.Close(); err != nil {
			s.logger.Error("Failed to close subscriber", err, nil)
			return fmt.Errorf("failed to close subscriber: %w", err)
		}
		s.logger.Info("Subscriber closed successfully", nil)
		return nil
	}

	// Close router (this will stop all handlers)
	if err := s.router.Close(); err != nil {
		s.logger.Error("Failed to close router", err, nil)
		return fmt.Errorf("failed to close router: %w", err)
	}

	// Close subscriber
	if err := s.watermill.Close(); err != nil {
		s.logger.Error("Failed to close subscriber", err, nil)
		return fmt.Errorf("failed to close subscriber: %w", err)
	}

	s.logger.Info("Subscriber closed successfully", nil)
	return nil
}

// Router returns the underlying message router for middleware configuration
// This allows tests and advanced users to add middleware
func (s *Subscriber) Router() *message.Router {
	return s.router
}

// SetMaxConcurrency sets the maximum concurrent handlers
func (s *Subscriber) SetMaxConcurrency(max int) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.closed {
		return
	}

	s.semaphore = make(chan struct{}, max)
}
