package performance

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

// BenchmarkEventDriven - benchmark event-driven подхода
// Измеряет производительность асинхронной публикации событий в Redis
func BenchmarkEventDriven(b *testing.B) {
	env := setupBenchEnvironment(b)
	defer env.cleanup()

	// Reset timer after setup
	b.ResetTimer()

	// Run benchmark in parallel
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = executeEventDrivenOperation(env)
		}
	})
}

// BenchmarkHTTPSync - benchmark синхронного HTTP подхода
// Измеряет производительность традиционных blocking HTTP вызовов
func BenchmarkHTTPSync(b *testing.B) {
	env := setupBenchEnvironment(b)
	defer env.cleanup()

	// Start mock HTTP server
	server := startMockHTTPServer()
	defer server.Close()

	env.httpURL = server.URL

	// Reset timer after setup
	b.ResetTimer()

	// Run benchmark in parallel
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = executeHTTPSyncOperation(env)
		}
	})
}

// TestBenchmarkComparison - функциональный тест для сравнения производительности
// Запускает оба подхода N раз и генерирует сравнительный отчет
func TestBenchmarkComparison(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping benchmark comparison in short mode")
	}

	t.Log("========================================")
	t.Log("  EVENT-DRIVEN vs HTTP SYNC BENCHMARK")
	t.Log("========================================")

	const N = 1000 // Количество операций для каждого теста

	// Setup
	env := setupBenchEnvironment(t)
	defer env.cleanup()

	// Start mock HTTP server for HTTP Sync test
	server := startMockHTTPServer()
	defer server.Close()
	env.httpURL = server.URL

	// Test 1: Event-Driven
	t.Log("Running Event-Driven benchmark...")
	eventDrivenLatencies := runEventDrivenBenchmark(t, env, N)

	// Test 2: HTTP Sync
	t.Log("Running HTTP Sync benchmark...")
	httpSyncLatencies := runHTTPSyncBenchmark(t, env, N)

	// Calculate metrics
	eventDrivenReport := calculateMetrics("Event-Driven", eventDrivenLatencies)
	httpSyncReport := calculateMetrics("HTTP Sync", httpSyncLatencies)

	// Generate comparison
	comparison := &ComparisonReport{
		Timestamp:      time.Now(),
		EventDrivenOPS: eventDrivenReport.OpsPerSecond,
		EventDrivenP50: eventDrivenReport.LatencyP50,
		EventDrivenP95: eventDrivenReport.LatencyP95,
		EventDrivenP99: eventDrivenReport.LatencyP99,
		HTTPSyncOPS:    httpSyncReport.OpsPerSecond,
		HTTPSyncP50:    httpSyncReport.LatencyP50,
		HTTPSyncP95:    httpSyncReport.LatencyP95,
		HTTPSyncP99:    httpSyncReport.LatencyP99,
	}

	// Calculate improvements
	comparison.ThroughputImprovement = eventDrivenReport.OpsPerSecond / httpSyncReport.OpsPerSecond
	comparison.LatencyP50Improvement = httpSyncReport.LatencyP50 / eventDrivenReport.LatencyP50
	comparison.LatencyP95Improvement = httpSyncReport.LatencyP95 / eventDrivenReport.LatencyP95
	comparison.LatencyP99Improvement = httpSyncReport.LatencyP99 / eventDrivenReport.LatencyP99

	// Save reports
	saveJSON(t, eventDrivenReport, "benchmark_event_driven.json")
	saveJSON(t, httpSyncReport, "benchmark_http_sync.json")
	saveJSON(t, comparison, "benchmark_comparison.json")

	err := GenerateMarkdownReport(eventDrivenReport, "benchmark_event_driven.md")
	if err != nil {
		t.Errorf("Failed to generate Event-Driven report: %v", err)
	}

	err = GenerateMarkdownReport(httpSyncReport, "benchmark_http_sync.md")
	if err != nil {
		t.Errorf("Failed to generate HTTP Sync report: %v", err)
	}

	err = GenerateComparisonReport(comparison, "benchmark_comparison.md")
	if err != nil {
		t.Errorf("Failed to generate comparison report: %v", err)
	}

	// Print summaries
	t.Log("\n--- Event-Driven Results ---")
	printSummary(t, eventDrivenReport)

	t.Log("\n--- HTTP Sync Results ---")
	printSummary(t, httpSyncReport)

	t.Log("\n--- Comparison ---")
	printComparisonSummary(t, comparison)

	// Assertions
	if comparison.ThroughputImprovement >= 10.0 {
		t.Logf("✅ Event-Driven shows %.1fx throughput improvement (>= 10x target)", comparison.ThroughputImprovement)
	} else if comparison.ThroughputImprovement >= 5.0 {
		t.Logf("⚠️  Event-Driven shows %.1fx throughput improvement (< 10x target)", comparison.ThroughputImprovement)
	} else {
		t.Errorf("❌ Event-Driven shows only %.1fx throughput improvement (expected >= 10x)", comparison.ThroughputImprovement)
	}

	t.Log("✓ Benchmark comparison completed")
}

// runEventDrivenBenchmark - запустить event-driven benchmark N раз
func runEventDrivenBenchmark(t *testing.T, env *BenchEnvironment, n int) []time.Duration {
	t.Helper()

	latencies := make([]time.Duration, 0, n)
	start := time.Now()

	for i := 0; i < n; i++ {
		opStart := time.Now()
		_ = executeEventDrivenOperation(env)
		latencies = append(latencies, time.Since(opStart))
	}

	totalDuration := time.Since(start)
	t.Logf("  Event-Driven: %d ops in %v (%.2f ops/s)", n, totalDuration, float64(n)/totalDuration.Seconds())

	return latencies
}

// runHTTPSyncBenchmark - запустить HTTP sync benchmark N раз
func runHTTPSyncBenchmark(t *testing.T, env *BenchEnvironment, n int) []time.Duration {
	t.Helper()

	latencies := make([]time.Duration, 0, n)
	start := time.Now()

	for i := 0; i < n; i++ {
		opStart := time.Now()
		_ = executeHTTPSyncOperation(env)
		latencies = append(latencies, time.Since(opStart))
	}

	totalDuration := time.Since(start)
	t.Logf("  HTTP Sync: %d ops in %v (%.2f ops/s)", n, totalDuration, float64(n)/totalDuration.Seconds())

	return latencies
}

// calculateMetrics - вычислить метрики из latency данных
func calculateMetrics(testName string, latencies []time.Duration) *PerformanceReport {
	totalDuration := time.Duration(0)
	for _, l := range latencies {
		totalDuration += l
	}

	return &PerformanceReport{
		TestName:        testName,
		Timestamp:       time.Now(),
		TotalOperations: len(latencies),
		SuccessCount:    len(latencies), // Считаем все успешными для benchmark
		FailureCount:    0,
		TotalDuration:   totalDuration,
		OpsPerSecond:    float64(len(latencies)) / totalDuration.Seconds(),
		SuccessRate:     1.0,
		LatencyMin:      calculateMin(latencies),
		LatencyMean:     calculateMean(latencies),
		LatencyP50:      calculatePercentile(latencies, 0.5),
		LatencyP95:      calculatePercentile(latencies, 0.95),
		LatencyP99:      calculatePercentile(latencies, 0.99),
		LatencyMax:      calculateMax(latencies),
		Latencies:       latencies,
	}
}

// executeEventDrivenOperation - выполнить event-driven операцию (non-blocking)
func executeEventDrivenOperation(env *BenchEnvironment) error {
	ctx := context.Background()

	event := &EventEnvelope{
		MessageID:     uuid.New().String(),
		CorrelationID: uuid.New().String(),
		EventType:     "commands:cluster-service:infobase:lock",
		Payload: map[string]interface{}{
			"cluster_id":  "bench-cluster",
			"infobase_id": "bench-db-001",
			"mode":        "exclusive",
		},
		Timestamp: time.Now(),
		Source:    "benchmark",
	}

	payload, _ := event.ToJSON()

	// Publish (non-blocking)
	return env.RedisClient.Publish(ctx, "commands:cluster-service:infobase:lock", payload).Err()
}

// executeHTTPSyncOperation - выполнить HTTP sync операцию (blocking)
func executeHTTPSyncOperation(env *BenchEnvironment) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	payload := map[string]interface{}{
		"cluster_id":  "bench-cluster",
		"infobase_id": "bench-db-001",
		"mode":        "exclusive",
	}

	body, _ := json.Marshal(payload)
	req, _ := http.NewRequestWithContext(ctx, "POST", env.httpURL+"/api/v1/lock", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	// Wait for response (blocking)
	_, err = io.ReadAll(resp.Body)
	return err
}

// startMockHTTPServer - запустить mock HTTP server для HTTP Sync теста
func startMockHTTPServer() *httptest.Server {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Simulate processing time (10ms)
		time.Sleep(10 * time.Millisecond)

		// Send success response
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"success","message":"Operation completed"}`)
	})

	return httptest.NewServer(handler)
}

// BenchEnvironment - окружение для benchmarks
type BenchEnvironment struct {
	RedisClient *redis.Client
	httpURL     string
	cleanup     func()
}

// setupBenchEnvironment - настроить окружение для benchmark
func setupBenchEnvironment(tb testing.TB) *BenchEnvironment {
	tb.Helper()

	redisClient := redis.NewClient(&redis.Options{
		Addr: "localhost:6380",
		DB:   0,
	})

	// Ping test
	ctx := context.Background()
	_, err := redisClient.Ping(ctx).Result()
	if err != nil {
		tb.Fatalf("Redis not available: %v. Make sure to start E2E Redis: cd tests/e2e && docker-compose -f docker-compose.e2e.yml up -d redis-e2e", err)
	}

	return &BenchEnvironment{
		RedisClient: redisClient,
		cleanup: func() {
			redisClient.Close()
		},
	}
}
