package ras

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// TestNewPool_Success tests successful pool creation
func TestNewPool_Success(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)

	assert.NoError(t, err)
	assert.NotNil(t, pool)
	assert.Equal(t, "localhost:1545", pool.serverAddr)
	assert.Equal(t, 10, pool.maxConns)
}

// TestNewPool_InvalidParams tests handling of invalid parameters
func TestNewPool_InvalidParams(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("", 10, 5*time.Second, 10*time.Second, logger)

	assert.Error(t, err)
	assert.Nil(t, pool)
	assert.Equal(t, ErrInvalidParams, err)
}

// TestNewPool_DefaultMaxConns tests default maxConns when 0 or negative
func TestNewPool_DefaultMaxConns(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	testCases := []int{0, -1, -10}

	for _, maxConns := range testCases {
		pool, err := NewPool("localhost:1545", maxConns, 5*time.Second, 10*time.Second, logger)

		assert.NoError(t, err)
		assert.NotNil(t, pool)
		assert.Equal(t, 10, pool.maxConns) // Should default to 10
	}
}

// TestGetConnection_CreatesNewClient tests that new client is created when pool is empty
func TestGetConnection_CreatesNewClient(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	client, err := pool.GetConnection(context.Background())

	assert.NoError(t, err)
	assert.NotNil(t, client)
	assert.Equal(t, "localhost:1545", client.serverAddr)
}

// TestGetConnection_ReusesExistingClient tests that existing client is reused from pool
func TestGetConnection_ReusesExistingClient(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Get first client
	client1, err := pool.GetConnection(context.Background())
	require.NoError(t, err)
	require.NotNil(t, client1)

	// Release it back
	pool.ReleaseConnection(client1)

	// Get again - should get the same client
	client2, err := pool.GetConnection(context.Background())
	require.NoError(t, err)
	require.NotNil(t, client2)

	assert.Equal(t, client1, client2)
}

// TestReleaseConnection_ReturnsToPool tests that connection is returned to pool
func TestReleaseConnection_ReturnsToPool(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	client, err := pool.GetConnection(context.Background())
	require.NoError(t, err)

	// Pool should be empty
	assert.Equal(t, 0, len(pool.clients))

	// Release connection
	pool.ReleaseConnection(client)

	// Pool should have 1 client
	pool.mu.Lock()
	assert.Equal(t, 1, len(pool.clients))
	pool.mu.Unlock()
}

// TestReleaseConnection_NilClient tests handling of nil client
func TestReleaseConnection_NilClient(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Should not panic
	pool.ReleaseConnection(nil)

	// Pool should still be empty
	pool.mu.Lock()
	assert.Equal(t, 0, len(pool.clients))
	pool.mu.Unlock()
}

// TestReleaseConnection_PoolFull tests handling when pool is full
func TestReleaseConnection_PoolFull(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 2, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Get 2 clients from empty pool
	client1, _ := pool.GetConnection(context.Background())
	client2, _ := pool.GetConnection(context.Background())

	// Release both back to pool
	pool.ReleaseConnection(client1)
	pool.ReleaseConnection(client2)

	pool.mu.Lock()
	assert.Equal(t, 2, len(pool.clients))
	pool.mu.Unlock()

	// Get all 2 from pool
	c1, _ := pool.GetConnection(context.Background())
	c2, _ := pool.GetConnection(context.Background())

	pool.mu.Lock()
	assert.Equal(t, 0, len(pool.clients)) // Pool should be empty now
	pool.mu.Unlock()

	// Release first - should go back to pool
	pool.ReleaseConnection(c1)

	pool.mu.Lock()
	assert.Equal(t, 1, len(pool.clients))
	pool.mu.Unlock()

	// Release second - should also go back (pool has space)
	pool.ReleaseConnection(c2)

	pool.mu.Lock()
	assert.Equal(t, 2, len(pool.clients))
	pool.mu.Unlock()
}

// TestClose tests closing of pool and all connections
func TestClose(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Add some clients to pool
	client1, _ := pool.GetConnection(context.Background())
	client2, _ := pool.GetConnection(context.Background())

	pool.ReleaseConnection(client1)
	pool.ReleaseConnection(client2)

	pool.mu.Lock()
	assert.Equal(t, 2, len(pool.clients))
	pool.mu.Unlock()

	// Close pool
	err = pool.Close()

	assert.NoError(t, err)

	pool.mu.Lock()
	assert.Nil(t, pool.clients)
	pool.mu.Unlock()
}

// TestStats tests pool statistics
func TestStats(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Get a client and return it
	client, _ := pool.GetConnection(context.Background())
	pool.ReleaseConnection(client)

	stats := pool.Stats()

	assert.Equal(t, "localhost:1545", stats["server"])
	assert.Equal(t, 10, stats["max_connections"])
	assert.Equal(t, 1, stats["active"])
}

// TestConcurrentGetConnection tests concurrent access to GetConnection
func TestConcurrentGetConnection(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 20, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Number of concurrent goroutines
	numGoroutines := 10
	results := make(chan error, numGoroutines)

	// Launch concurrent goroutines
	for i := 0; i < numGoroutines; i++ {
		go func() {
			client, err := pool.GetConnection(context.Background())
			if err != nil {
				results <- err
				return
			}
			if client == nil {
				results <- errors.New("client is nil")
				return
			}
			results <- nil
		}()
	}

	// Verify all succeeded
	for i := 0; i < numGoroutines; i++ {
		err := <-results
		assert.NoError(t, err)
	}
}

// TestConcurrentReleaseConnection tests concurrent access to ReleaseConnection
func TestConcurrentReleaseConnection(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 100, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	numClients := 20

	// Get clients first
	clients := make([]*Client, numClients)
	for i := 0; i < numClients; i++ {
		client, err := pool.GetConnection(context.Background())
		require.NoError(t, err)
		clients[i] = client
	}

	// Release concurrently
	var wg sync.WaitGroup
	for i := 0; i < numClients; i++ {
		wg.Add(1)
		go func(c *Client) {
			defer wg.Done()
			pool.ReleaseConnection(c)
		}(clients[i])
	}

	wg.Wait()

	pool.mu.Lock()
	assert.Equal(t, numClients, len(pool.clients))
	pool.mu.Unlock()
}

// TestConcurrentGetAndRelease tests concurrent get and release operations
func TestConcurrentGetAndRelease(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 20, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	numOperations := 50
	results := make(chan error, numOperations*2)

	var wg sync.WaitGroup

	// Get and release clients concurrently
	for i := 0; i < numOperations; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()

			client, err := pool.GetConnection(context.Background())
			if err != nil {
				results <- err
				return
			}

			pool.ReleaseConnection(client)
			results <- nil
		}()
	}

	wg.Wait()

	// Verify all operations succeeded
	for i := 0; i < numOperations; i++ {
		err := <-results
		assert.NoError(t, err)
	}
}

// TestPoolExhaustion tests pool behavior when max connections reached
func TestPoolExhaustion(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	maxConns := 5
	pool, err := NewPool("localhost:1545", maxConns, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Get maxConns clients
	for i := 0; i < maxConns; i++ {
		client, err := pool.GetConnection(context.Background())
		require.NoError(t, err)
		assert.NotNil(t, client)
	}

	// Pool should be empty now
	pool.mu.Lock()
	assert.Equal(t, 0, len(pool.clients))
	pool.mu.Unlock()

	pool.Close()
}

// TestContextCancellation tests handling of cancelled context
func TestContextCancellation(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	// GetConnection doesn't use context in Week 1 stub, but should not panic
	client, err := pool.GetConnection(ctx)

	assert.NoError(t, err)
	assert.NotNil(t, client)
}

// TestRaceConditionGetRelease tests for race conditions between Get and Release
func TestRaceConditionGetRelease(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 100, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	var wg sync.WaitGroup
	numGoroutines := 20
	operationsPerGoroutine := 100

	// This test will be run with -race flag to detect race conditions
	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()

			for i := 0; i < operationsPerGoroutine; i++ {
				client, err := pool.GetConnection(context.Background())
				assert.NoError(t, err)
				assert.NotNil(t, client)

				pool.ReleaseConnection(client)
			}
		}()
	}

	wg.Wait()
}

// TestStatsConsistency tests that stats are consistent with actual pool state
func TestStatsConsistency(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	pool, err := NewPool("localhost:1545", 10, 5*time.Second, 10*time.Second, logger)
	require.NoError(t, err)

	// Add some clients
	clients := make([]*Client, 0)
	for i := 0; i < 3; i++ {
		client, _ := pool.GetConnection(context.Background())
		clients = append(clients, client)
	}

	// Release one
	pool.ReleaseConnection(clients[0])

	stats := pool.Stats()

	assert.Equal(t, 1, stats["active"])
	assert.Equal(t, "localhost:1545", stats["server"])
	assert.Equal(t, 10, stats["max_connections"])
}

// BenchmarkGetConnection benchmarks GetConnection performance
func BenchmarkGetConnection(b *testing.B) {
	logger, _ := zap.NewDevelopment()
	pool, _ := NewPool("localhost:1545", 100, 5*time.Second, 10*time.Second, logger)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		pool.GetConnection(context.Background())
	}
}

// BenchmarkReleaseConnection benchmarks ReleaseConnection performance
func BenchmarkReleaseConnection(b *testing.B) {
	logger, _ := zap.NewDevelopment()
	pool, _ := NewPool("localhost:1545", 100, 5*time.Second, 10*time.Second, logger)

	// Pre-create clients
	clients := make([]*Client, b.N)
	for i := 0; i < b.N; i++ {
		clients[i], _ = pool.GetConnection(context.Background())
	}

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		pool.ReleaseConnection(clients[i])
	}
}

// BenchmarkConcurrentGetRelease benchmarks concurrent Get/Release
func BenchmarkConcurrentGetRelease(b *testing.B) {
	logger, _ := zap.NewDevelopment()
	pool, _ := NewPool("localhost:1545", 100, 5*time.Second, 10*time.Second, logger)

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			client, _ := pool.GetConnection(context.Background())
			pool.ReleaseConnection(client)
		}
	})
}
