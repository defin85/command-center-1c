package events

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisHealthCheck checks if Redis is available
func RedisHealthCheck(ctx context.Context, client *redis.Client) error {
	return client.Ping(ctx).Err()
}

// WaitForRedis waits for Redis to become available with exponential backoff
func WaitForRedis(ctx context.Context, client *redis.Client, maxRetries int, interval time.Duration) error {
	retries := 0
	backoff := interval

	for {
		if err := RedisHealthCheck(ctx, client); err == nil {
			return nil
		}

		retries++
		if maxRetries > 0 && retries >= maxRetries {
			return fmt.Errorf("failed to connect to Redis after %d retries", retries)
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(backoff):
			// Exponential backoff with max 30 seconds
			backoff = backoff * 2
			if backoff > 30*time.Second {
				backoff = 30 * time.Second
			}
		}
	}
}
