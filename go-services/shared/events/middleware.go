package events

import (
	"context"
	"fmt"
	"math/rand"
	"time"

	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/redis/go-redis/v9"
)

// WithLogging adds logging middleware to track message processing
func WithLogging(logger watermill.LoggerAdapter) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) ([]*message.Message, error) {
			logger.Info("Processing message", watermill.LogFields{
				"message_id": msg.UUID,
			})

			start := time.Now()
			messages, err := h(msg)
			duration := time.Since(start)

			if err != nil {
				logger.Error("Message processing failed", err, watermill.LogFields{
					"message_id": msg.UUID,
					"duration":   duration.String(),
				})
			} else {
				logger.Info("Message processing completed", watermill.LogFields{
					"message_id": msg.UUID,
					"duration":   duration.String(),
				})
			}

			return messages, err
		}
	}
}

// WithRetry adds retry logic with exponential backoff
func WithRetry(maxRetries int, initialDelay time.Duration, logger watermill.LoggerAdapter) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) ([]*message.Message, error) {
			var lastErr error

			for attempt := 0; attempt <= maxRetries; attempt++ {
				messages, err := h(msg)
				if err == nil {
					// Success
					if attempt > 0 {
						logger.Info("Message processed after retry", watermill.LogFields{
							"message_id": msg.UUID,
							"attempt":    attempt,
						})
					}
					return messages, nil
				}

				lastErr = err

				// Don't retry if it's the last attempt
				if attempt < maxRetries {
					// Calculate delay with exponential backoff and jitter
					baseDelay := initialDelay * time.Duration(1<<uint(attempt))
					jitter := time.Duration(rand.Int63n(int64(baseDelay) / 10)) // ±10% jitter
					delay := baseDelay + jitter
					logger.Info("Retrying message processing", watermill.LogFields{
						"message_id": msg.UUID,
						"attempt":    attempt + 1,
						"max_retries": maxRetries,
						"delay":      delay.String(),
						"error":      err.Error(),
					})

					// Wait before retry
					time.Sleep(delay)
				}
			}

			logger.Error("Message processing failed after all retries", lastErr, watermill.LogFields{
				"message_id": msg.UUID,
				"attempts":   maxRetries + 1,
			})

			return nil, lastErr
		}
	}
}

// WithIdempotency ensures that messages with the same idempotency key are only processed once
// It uses Redis to store processed message IDs with TTL
func WithIdempotency(redisClient *redis.Client, ttl time.Duration, logger watermill.LoggerAdapter) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) ([]*message.Message, error) {
			// Try to parse envelope to get idempotency key
			var envelope Envelope
			if err := envelope.UnmarshalJSON(msg.Payload); err != nil {
				// If we can't parse envelope, skip idempotency check
				logger.Error("Cannot parse envelope for idempotency check", err, watermill.LogFields{
					"message_id": msg.UUID,
				})
				return h(msg)
			}

			idempotencyKey := envelope.GetIdempotencyKey()
			if idempotencyKey == "" {
				// No idempotency key, process normally
				return h(msg)
			}

			// Create Redis key for idempotency
			redisKey := fmt.Sprintf("idempotency:%s", idempotencyKey)

			// Check if already processed
			ctx := msg.Context()
			exists, err := redisClient.Exists(ctx, redisKey).Result()
			if err != nil {
				logger.Error("Failed to check idempotency", err, watermill.LogFields{
					"message_id":      msg.UUID,
					"idempotency_key": idempotencyKey,
				})
				// On error, process the message anyway (fail open)
				return h(msg)
			}

			if exists > 0 {
				// Already processed, skip
				logger.Info("Message already processed (idempotent)", watermill.LogFields{
					"message_id":      msg.UUID,
					"idempotency_key": idempotencyKey,
				})
				return nil, nil
			}

			// Process the message
			messages, err := h(msg)
			if err != nil {
				// Don't mark as processed if handler failed
				return messages, err
			}

			// Mark as processed
			if err := redisClient.Set(ctx, redisKey, msg.UUID, ttl).Err(); err != nil {
				logger.Error("Failed to set idempotency key", err, watermill.LogFields{
					"message_id":      msg.UUID,
					"idempotency_key": idempotencyKey,
				})
				// Message was processed successfully, so return success even if we couldn't set the key
			}

			return messages, nil
		}
	}
}

// WithRecovery recovers from panics in handlers
func WithRecovery(logger watermill.LoggerAdapter) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) (messages []*message.Message, err error) {
			defer func() {
				if r := recover(); r != nil {
					logger.Error("Recovered from panic in handler", ErrHandlerPanic, watermill.LogFields{
						"message_id": msg.UUID,
						"panic":      r,
					})
					err = fmt.Errorf("%w: %v", ErrHandlerPanic, r)
				}
			}()

			return h(msg)
		}
	}
}

// WithTimeout adds a timeout to message processing
func WithTimeout(timeout time.Duration, logger watermill.LoggerAdapter) message.HandlerMiddleware {
	return func(h message.HandlerFunc) message.HandlerFunc {
		return func(msg *message.Message) ([]*message.Message, error) {
			ctx, cancel := context.WithTimeout(msg.Context(), timeout)
			defer cancel()

			// Create a new message with timeout context
			msgWithTimeout := msg.Copy()
			msgWithTimeout.SetContext(ctx)

			done := make(chan struct{})
			var messages []*message.Message
			var err error

			go func() {
				messages, err = h(msgWithTimeout)
				close(done)
			}()

			select {
			case <-done:
				return messages, err
			case <-ctx.Done():
				logger.Error("Message processing timeout", ctx.Err(), watermill.LogFields{
					"message_id": msg.UUID,
					"timeout":    timeout.String(),
				})
				return nil, fmt.Errorf("message processing timeout after %s", timeout)
			}
		}
	}
}
