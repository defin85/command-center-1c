package performance

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
)

// PerfEnvironment - окружение для performance тестов
type PerfEnvironment struct {
	RedisClient *redis.Client
	Ctx         context.Context
	Cancel      context.CancelFunc

	// Cleanup resources
	cleanupFuncs []func()
	t            *testing.T
}

// SetupPerfEnvironment - инициализация окружения для performance тестов
// Использует тот же Redis что и E2E тесты (localhost:6380)
func SetupPerfEnvironment(t *testing.T) *PerfEnvironment {
	t.Helper()

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)

	env := &PerfEnvironment{
		t:      t,
		Ctx:    ctx,
		Cancel: cancel,
	}

	// Connect to Redis (E2E test instance)
	env.RedisClient = redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   0,
	})

	// Ping test
	_, err := env.RedisClient.Ping(ctx).Result()
	if err != nil {
		t.Fatalf("Redis not available: %v. Make sure to start E2E Redis: cd tests/e2e && docker-compose -f docker-compose.e2e.yml up -d redis-e2e", err)
	}

	t.Log("✓ Performance environment initialized")
	t.Logf("  - Redis: localhost:6380")
	t.Logf("  - Context timeout: 10 minutes")

	// Cleanup Redis before tests
	env.cleanupRedis(t)

	return env
}

// addCleanup - добавить функцию cleanup
func (env *PerfEnvironment) addCleanup(fn func()) {
	env.cleanupFuncs = append(env.cleanupFuncs, fn)
}

// Cleanup - очистка ресурсов
func (env *PerfEnvironment) Cleanup() {
	env.t.Log("Cleaning up performance environment...")

	// Execute cleanup functions in reverse order
	for i := len(env.cleanupFuncs) - 1; i >= 0; i-- {
		env.cleanupFuncs[i]()
	}

	// Close Redis
	if env.RedisClient != nil {
		env.RedisClient.Close()
	}

	// Cancel context
	if env.Cancel != nil {
		env.Cancel()
	}

	env.t.Log("✓ Performance environment cleaned up")
}

// cleanupRedis - очистить Redis перед тестами
func (env *PerfEnvironment) cleanupRedis(t *testing.T) {
	t.Helper()

	// Flush test database (DB 0)
	err := env.RedisClient.FlushDB(env.Ctx).Err()
	if err != nil {
		t.Logf("Warning: failed to flush Redis DB: %v", err)
	} else {
		t.Log("✓ Redis DB flushed")
	}
}

// PublishEvent - publish event to Redis stream
func (env *PerfEnvironment) PublishEvent(channel string, payload map[string]interface{}) error {
	return env.RedisClient.Publish(env.Ctx, channel, payload).Err()
}

// WaitForEvent - ждать событие в Redis stream/channel
func (env *PerfEnvironment) WaitForEvent(channel string, timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(env.Ctx, timeout)
	defer cancel()

	pubsub := env.RedisClient.Subscribe(ctx, channel)
	defer pubsub.Close()

	select {
	case msg := <-pubsub.Channel():
		return msg.Payload, nil
	case <-ctx.Done():
		return "", fmt.Errorf("timeout waiting for event on channel %s", channel)
	}
}

// GetMetric - получить метрику из Redis
func (env *PerfEnvironment) GetMetric(key string) (int64, error) {
	val, err := env.RedisClient.Get(env.Ctx, key).Int64()
	if err == redis.Nil {
		return 0, nil
	}
	return val, err
}

// IncrMetric - увеличить метрику в Redis
func (env *PerfEnvironment) IncrMetric(key string) error {
	return env.RedisClient.Incr(env.Ctx, key).Err()
}

// SetMetric - установить значение метрики в Redis
func (env *PerfEnvironment) SetMetric(key string, value int64) error {
	return env.RedisClient.Set(env.Ctx, key, value, 0).Err()
}
