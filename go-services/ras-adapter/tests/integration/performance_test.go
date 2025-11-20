// +build integration

package integration

import (
	"context"
	"sync"
	"testing"
	"time"
)

// BenchmarkLockUnlock measures lock/unlock operation performance
func BenchmarkLockUnlock(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(&testing.T{}, rasPool)
	infobaseID := GetTestInfobaseID(&testing.T{}, rasPool)

	infobaseSvc := createInfobaseService(&testing.T{}, rasPool)
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Lock
		err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		if err != nil {
			b.Fatalf("Lock failed: %v", err)
		}

		// Unlock
		err = infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		if err != nil {
			b.Fatalf("Unlock failed: %v", err)
		}
	}
	b.StopTimer()

	// Log statistics
	b.Logf("Lock/Unlock operations: %d", b.N)
	b.Logf("Average time per cycle: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// BenchmarkLock measures lock operation performance alone
func BenchmarkLock(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(&testing.T{}, rasPool)
	infobaseID := GetTestInfobaseID(&testing.T{}, rasPool)

	infobaseSvc := createInfobaseService(&testing.T{}, rasPool)
	ctx := context.Background()

	// Unlock before benchmark
	infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
		if err != nil {
			b.Fatalf("Lock failed: %v", err)
		}

		// Unlock after each lock to reset state
		infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
	}
	b.StopTimer()

	b.Logf("Lock operations: %d", b.N)
	b.Logf("Average time per lock: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// BenchmarkUnlock measures unlock operation performance alone
func BenchmarkUnlock(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(&testing.T{}, rasPool)
	infobaseID := GetTestInfobaseID(&testing.T{}, rasPool)

	infobaseSvc := createInfobaseService(&testing.T{}, rasPool)
	ctx := context.Background()

	// Lock before benchmark
	infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Lock before each unlock to reset state
		infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)

		err := infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
		if err != nil {
			b.Fatalf("Unlock failed: %v", err)
		}
	}
	b.StopTimer()

	b.Logf("Unlock operations: %d", b.N)
	b.Logf("Average time per unlock: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// BenchmarkGetClusters measures cluster discovery performance
func BenchmarkGetClusters(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterSvc := createClusterService(&testing.T{}, rasPool)
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := clusterSvc.GetClusters(ctx)
		if err != nil {
			b.Fatalf("GetClusters failed: %v", err)
		}
	}
	b.StopTimer()

	b.Logf("GetClusters operations: %d", b.N)
	b.Logf("Average time per GetClusters: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// BenchmarkGetInfobases measures infobase discovery performance
func BenchmarkGetInfobases(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(&testing.T{}, rasPool)
	infobaseSvc := createInfobaseService(&testing.T{}, rasPool)
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := infobaseSvc.GetInfobases(ctx, clusterID)
		if err != nil {
			b.Fatalf("GetInfobases failed: %v", err)
		}
	}
	b.StopTimer()

	b.Logf("GetInfobases operations: %d", b.N)
	b.Logf("Average time per GetInfobases: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// BenchmarkGetSessions measures session listing performance
func BenchmarkGetSessions(b *testing.B) {
	rasPool, redisClient, _ := setupTestEnvironment(&testing.T{})
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(&testing.T{}, rasPool)
	sessionSvc := createSessionService(&testing.T{}, rasPool)
	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := sessionSvc.GetSessions(ctx, clusterID)
		if err != nil {
			b.Fatalf("GetSessions failed: %v", err)
		}
	}
	b.StopTimer()

	b.Logf("GetSessions operations: %d", b.N)
	b.Logf("Average time per GetSessions: %.3f ms", float64(b.Elapsed().Milliseconds())/float64(b.N))
}

// TestThroughputPerformance measures operations per second
func TestThroughputPerformance(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	clusterSvc := createClusterService(t, rasPool)
	ctx := context.Background()

	t.Run("throughput_measurement", func(t *testing.T) {
		const duration = 5 * time.Second
		const concurrency = 5

		var wg sync.WaitGroup
		opCount := 0
		var mu sync.Mutex

		start := time.Now()
		deadline := start.Add(duration)

		for i := 0; i < concurrency; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()

				for time.Now().Before(deadline) {
					_, err := clusterSvc.GetClusters(ctx)
					if err == nil {
						mu.Lock()
						opCount++
						mu.Unlock()
					}
				}
			}()
		}

		wg.Wait()
		elapsed := time.Since(start)

		throughput := float64(opCount) / elapsed.Seconds()
		t.Logf("Throughput: %.1f ops/sec (total: %d ops in %.2f sec)",
			throughput, opCount, elapsed.Seconds())
	})
}

// TestP50P95P99Latency measures latency percentiles
func TestP50P95P99Latency(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("lock_unlock_latency_percentiles", func(t *testing.T) {
		const numSamples = 100
		latencies := make([]time.Duration, 0, numSamples)
		var mu sync.Mutex

		// Collect latency samples
		for i := 0; i < numSamples; i++ {
			start := time.Now()

			err := infobaseSvc.LockInfobase(ctx, clusterID, GetTestInfobaseID(t, rasPool))
			if err != nil {
				t.Fatalf("Lock failed: %v", err)
			}

			elapsed := time.Since(start)

			mu.Lock()
			latencies = append(latencies, elapsed)
			mu.Unlock()

			infobaseSvc.UnlockInfobase(ctx, clusterID, GetTestInfobaseID(t, rasPool))
		}

		// Sort latencies for percentile calculation
		sortDurations(latencies)

		// Calculate percentiles
		p50 := latencies[len(latencies)*50/100]
		p95 := latencies[len(latencies)*95/100]
		p99 := latencies[len(latencies)*99/100]
		avgLatency := calculateAverage(latencies)

		t.Logf("Lock operation latency (n=%d):", numSamples)
		t.Logf("  P50: %.2f ms", float64(p50.Microseconds())/1000.0)
		t.Logf("  P95: %.2f ms", float64(p95.Microseconds())/1000.0)
		t.Logf("  P99: %.2f ms", float64(p99.Microseconds())/1000.0)
		t.Logf("  Avg: %.2f ms", float64(avgLatency.Microseconds())/1000.0)

		// Verify performance targets
		// P95 should be < 2 seconds for lock operations
		if p95 > 2*time.Second {
			t.Logf("Warning: P95 latency (%.2f ms) exceeds target (2000 ms)",
				float64(p95.Microseconds())/1000.0)
		}
	})

	// Cleanup
	infobaseSvc.UnlockInfobase(ctx, clusterID, GetTestInfobaseID(t, rasPool))
}

// TestConcurrentLockPerformance measures concurrent lock operation performance
func TestConcurrentLockPerformance(t *testing.T) {
	rasPool, redisClient, _ := setupTestEnvironment(t)
	defer cleanupTestEnvironment(rasPool, redisClient)

	clusterID := GetTestClusterID(t, rasPool)
	infobaseID := GetTestInfobaseID(t, rasPool)
	infobaseSvc := createInfobaseService(t, rasPool)
	ctx := context.Background()

	t.Run("concurrent_lock_performance", func(t *testing.T) {
		const concurrency = 10
		const operationsPerGoroutine = 10

		var wg sync.WaitGroup
		var opCount int64
		var totalLatency time.Duration
		var mu sync.Mutex

		latencies := make([]time.Duration, 0, concurrency*operationsPerGoroutine)

		start := time.Now()

		for i := 0; i < concurrency; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()

				for j := 0; j < operationsPerGoroutine; j++ {
					opStart := time.Now()
					err := infobaseSvc.LockInfobase(ctx, clusterID, infobaseID)
					elapsed := time.Since(opStart)

					if err == nil {
						mu.Lock()
						opCount++
						totalLatency += elapsed
						latencies = append(latencies, elapsed)
						mu.Unlock()
					}

					infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
				}
			}()
		}

		wg.Wait()
		totalElapsed := time.Since(start)

		if opCount > 0 {
			avgLatency := totalLatency / time.Duration(opCount)
			throughput := float64(opCount) / totalElapsed.Seconds()

			t.Logf("Concurrent lock performance (concurrency=%d, ops/goroutine=%d):",
				concurrency, operationsPerGoroutine)
			t.Logf("  Total operations: %d", opCount)
			t.Logf("  Total time: %.2f sec", totalElapsed.Seconds())
			t.Logf("  Throughput: %.1f ops/sec", throughput)
			t.Logf("  Average latency: %.2f ms", float64(avgLatency.Microseconds())/1000.0)

			if len(latencies) > 0 {
				sortDurations(latencies)
				p95 := latencies[len(latencies)*95/100]
				t.Logf("  P95 latency: %.2f ms", float64(p95.Microseconds())/1000.0)
			}
		}
	})

	// Cleanup
	infobaseSvc.UnlockInfobase(ctx, clusterID, infobaseID)
}

// Helper functions

func sortDurations(durations []time.Duration) {
	for i := 0; i < len(durations); i++ {
		for j := i + 1; j < len(durations); j++ {
			if durations[j] < durations[i] {
				durations[i], durations[j] = durations[j], durations[i]
			}
		}
	}
}

func calculateAverage(durations []time.Duration) time.Duration {
	if len(durations) == 0 {
		return 0
	}

	var sum time.Duration
	for _, d := range durations {
		sum += d
	}

	return sum / time.Duration(len(durations))
}
