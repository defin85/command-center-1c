package performance

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

// EventEnvelope - обертка для событий (соответствует Event-Driven архитектуре)
type EventEnvelope struct {
	MessageID     string                 `json:"message_id"`
	CorrelationID string                 `json:"correlation_id"`
	EventType     string                 `json:"event_type"`
	Payload       map[string]interface{} `json:"payload"`
	Timestamp     time.Time              `json:"timestamp"`
	Source        string                 `json:"source,omitempty"`
}

// NewCommandEvent - создать command event
func NewCommandEvent(correlationID, eventType string, payload map[string]interface{}) *EventEnvelope {
	return &EventEnvelope{
		MessageID:     uuid.New().String(),
		CorrelationID: correlationID,
		EventType:     eventType,
		Payload:       payload,
		Timestamp:     time.Now(),
		Source:        "performance-test",
	}
}

// NewResponseEvent - создать response event
func NewResponseEvent(correlationID, eventType string, payload map[string]interface{}) *EventEnvelope {
	return &EventEnvelope{
		MessageID:     uuid.New().String(),
		CorrelationID: correlationID,
		EventType:     eventType,
		Payload:       payload,
		Timestamp:     time.Now(),
		Source:        "mock-service",
	}
}

// ToJSON - сериализовать в JSON
func (e *EventEnvelope) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// calculatePercentile - вычислить percentile из latency данных
func calculatePercentile(latencies []time.Duration, percentile float64) float64 {
	if len(latencies) == 0 {
		return 0
	}

	// Копируем и сортируем
	sorted := make([]time.Duration, len(latencies))
	copy(sorted, latencies)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i] < sorted[j]
	})

	// Вычисляем индекс
	idx := int(float64(len(sorted)) * percentile)
	if idx >= len(sorted) {
		idx = len(sorted) - 1
	}

	return sorted[idx].Seconds()
}

// calculateMean - вычислить среднее значение
func calculateMean(latencies []time.Duration) float64 {
	if len(latencies) == 0 {
		return 0
	}

	var sum time.Duration
	for _, l := range latencies {
		sum += l
	}

	return sum.Seconds() / float64(len(latencies))
}

// calculateMin - минимальная latency
func calculateMin(latencies []time.Duration) float64 {
	if len(latencies) == 0 {
		return 0
	}

	min := latencies[0]
	for _, l := range latencies {
		if l < min {
			min = l
		}
	}

	return min.Seconds()
}

// calculateMax - максимальная latency
func calculateMax(latencies []time.Duration) float64 {
	if len(latencies) == 0 {
		return 0
	}

	max := latencies[0]
	for _, l := range latencies {
		if l > max {
			max = l
		}
	}

	return max.Seconds()
}

// saveJSON - сохранить данные в JSON файл
func saveJSON(t *testing.T, data interface{}, filename string) {
	t.Helper()

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		t.Fatalf("Failed to marshal JSON: %v", err)
	}

	err = os.WriteFile(filename, jsonData, 0644)
	if err != nil {
		t.Fatalf("Failed to write file %s: %v", filename, err)
	}

	t.Logf("✓ Data saved to: %s", filename)
}

// printSummary - красиво вывести summary
func printSummary(t *testing.T, report *PerformanceReport) {
	t.Helper()

	t.Log("========================================")
	t.Log("      PERFORMANCE TEST SUMMARY")
	t.Log("========================================")
	t.Logf("Total Operations:    %d", report.TotalOperations)
	t.Logf("Success Count:       %d", report.SuccessCount)
	t.Logf("Failure Count:       %d", report.FailureCount)
	t.Logf("Success Rate:        %.2f%%", report.SuccessRate*100)
	t.Log("----------------------------------------")
	t.Logf("Total Duration:      %v", report.TotalDuration)
	t.Logf("Operations/sec:      %.2f", report.OpsPerSecond)
	t.Log("----------------------------------------")
	t.Log("Latency Distribution:")
	t.Logf("  Min:      %.3fs", report.LatencyMin)
	t.Logf("  Mean:     %.3fs", report.LatencyMean)
	t.Logf("  P50:      %.3fs", report.LatencyP50)
	t.Logf("  P95:      %.3fs", report.LatencyP95)
	t.Logf("  P99:      %.3fs", report.LatencyP99)
	t.Logf("  Max:      %.3fs", report.LatencyMax)
	t.Log("========================================")
}

// printComparisonSummary - вывести сравнение Event-Driven vs HTTP Sync
func printComparisonSummary(t *testing.T, comparison *ComparisonReport) {
	t.Helper()

	t.Log("========================================")
	t.Log("  EVENT-DRIVEN vs HTTP SYNC COMPARISON")
	t.Log("========================================")
	t.Logf("Metric              Event-Driven    HTTP Sync      Improvement")
	t.Log("------------------------------------------------------------------------")
	t.Logf("Throughput          %.2f ops/s     %.2f ops/s    %.1fx",
		comparison.EventDrivenOPS, comparison.HTTPSyncOPS, comparison.ThroughputImprovement)
	t.Logf("P50 Latency         %.3fs          %.3fs         %.1fx faster",
		comparison.EventDrivenP50, comparison.HTTPSyncP50, comparison.LatencyP50Improvement)
	t.Logf("P95 Latency         %.3fs          %.3fs         %.1fx faster",
		comparison.EventDrivenP95, comparison.HTTPSyncP95, comparison.LatencyP95Improvement)
	t.Logf("P99 Latency         %.3fs          %.3fs         %.1fx faster",
		comparison.EventDrivenP99, comparison.HTTPSyncP99, comparison.LatencyP99Improvement)
	t.Log("========================================")

	// Вердикт
	if comparison.ThroughputImprovement >= 10.0 {
		t.Log("✅ TARGET ACHIEVED: Event-Driven shows 10x+ improvement!")
	} else if comparison.ThroughputImprovement >= 5.0 {
		t.Log("⚠️  CLOSE: Event-Driven shows significant improvement, but below 10x target")
	} else {
		t.Log("❌ BELOW TARGET: Event-Driven improvement is below expectations")
	}
	t.Log("========================================")
}

// waitForRedis - подождать готовности Redis
func waitForRedis(t *testing.T, addr string, timeout time.Duration) error {
	t.Helper()

	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		// Попытка подключения
		client := redis.NewClient(&redis.Options{Addr: addr})
		ctx := context.Background()
		_, err := client.Ping(ctx).Result()
		client.Close()

		if err == nil {
			t.Logf("✓ Redis is ready at %s", addr)
			return nil
		}

		time.Sleep(1 * time.Second)
	}

	return fmt.Errorf("Redis at %s not ready after %v", addr, timeout)
}
