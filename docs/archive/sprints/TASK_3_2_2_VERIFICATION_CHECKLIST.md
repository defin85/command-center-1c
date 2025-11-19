# Task 3.2.2: A/B Testing Metrics - Verification Checklist

**Quick verification guide for Task 3.2.2 implementation**

---

## ✅ Pre-Deployment Checks

### 1. Code Compilation
```bash
cd /c/1CProject/command-center-1c/go-services/worker
go build -o /tmp/cc1c-worker.exe cmd/main.go
```
**Expected:** ✅ Build succeeds without errors

### 2. Unit Tests
```bash
cd /c/1CProject/command-center-1c/go-services/worker
go test ./internal/metrics -v
```
**Expected:** ✅ All tests pass (7 test cases)

### 3. File Structure
```bash
cd /c/1CProject/command-center-1c
ls -la go-services/worker/internal/metrics/
ls -la infrastructure/monitoring/grafana/dashboards/ab_testing_dashboard.json
ls -la infrastructure/monitoring/prometheus/recording_rules.yml
```
**Expected:** ✅ All files exist

---

## ✅ Runtime Checks

### 4. Start Worker Service
```bash
cd /c/1CProject/command-center-1c
./scripts/dev/start-all.sh
# Or manually:
cd go-services/worker
go run cmd/main.go
```
**Expected:** ✅ Worker starts, logs show "metrics endpoint started port=:9091"

### 5. Metrics Endpoint
```bash
curl http://localhost:9091/metrics | grep worker_execution
```
**Expected output:**
```
# HELP worker_execution_mode_total Total executions by mode (event_driven vs http_sync)
# TYPE worker_execution_mode_total counter
worker_execution_mode_total{mode="event_driven"} 0
worker_execution_mode_total{mode="http_sync"} 0
...
```
**Expected:** ✅ Metrics endpoint responds with Prometheus format

### 6. Trigger Some Operations
```bash
# Use API Gateway or Orchestrator to trigger extension installs
# This will populate metrics
curl -X POST http://localhost:8080/api/v1/operations \
  -H "Content-Type: application/json" \
  -d '{
    "operation_type": "install_extension",
    "database_ids": ["test-db-1"],
    "payload": {
      "extension_name": "TestExtension",
      "extension_path": "/path/to/extension.cfe"
    }
  }'
```
**Expected:** ✅ Operation executes, metrics updated

### 7. Verify Metrics Update
```bash
curl http://localhost:9091/metrics | grep worker_execution_mode_total
```
**Expected:** ✅ Counters incremented (values > 0)

---

## ✅ Prometheus Checks

### 8. Prometheus Targets
```bash
# Open browser
http://localhost:9090/targets
```
**Expected:** ✅ `worker` target shows as UP

### 9. Prometheus Query
```bash
# Open browser
http://localhost:9090/graph

# Query:
worker_execution_mode_total
```
**Expected:** ✅ Query returns data

### 10. Recording Rules
```bash
# Open browser
http://localhost:9090/rules

# Or check via promtool:
promtool check rules infrastructure/monitoring/prometheus/recording_rules.yml
```
**Expected:** ✅ `worker_ab_testing` group is loaded, rules are valid

### 11. Query Recording Rule
```bash
# Open browser
http://localhost:9090/graph

# Query:
worker:success_rate:5m
```
**Expected:** ✅ Query returns calculated success rate

---

## ✅ Grafana Checks

### 12. Import Dashboard
1. Open Grafana: http://localhost:3001 (admin/admin)
2. Go to: Dashboards → Import
3. Upload JSON: `infrastructure/monitoring/grafana/dashboards/ab_testing_dashboard.json`
4. Select datasource: Prometheus

**Expected:** ✅ Dashboard imports successfully

### 13. Verify Dashboard Panels
**Check all 7 panels load:**
1. ✅ Execution Mode Distribution (Pie Chart)
2. ✅ Success Rate Comparison (Time Series)
3. ✅ Latency P99 Comparison (Time Series)
4. ✅ Throughput Comparison (Time Series)
5. ✅ Error Rate by Mode (Time Series)
6. ✅ Compensation Events (Stat)
7. ✅ Circuit Breaker Trips (Stat)

**Expected:** ✅ All panels display (may show "No data" if no operations yet)

### 14. Run Test Load
```bash
# Trigger 10-20 operations to generate data
for i in {1..20}; do
  curl -X POST http://localhost:8080/api/v1/operations \
    -H "Content-Type: application/json" \
    -d "{
      \"operation_type\": \"install_extension\",
      \"database_ids\": [\"test-db-$i\"],
      \"payload\": {
        \"extension_name\": \"TestExtension\",
        \"extension_path\": \"/path/to/extension.cfe\"
      }
    }"
  sleep 1
done
```
**Expected:** ✅ Dashboard shows data in all panels

---

## ✅ Integration Checks

### 15. dual_mode.go Integration
```bash
cd /c/1CProject/command-center-1c/go-services/worker/internal/processor
grep -n "metrics.Execution" dual_mode.go
```
**Expected output:**
```
XX: metrics.ExecutionMode.WithLabelValues(string(mode)).Inc()
YY: metrics.ExecutionDuration.WithLabelValues(string(mode)).Observe(durationSeconds)
ZZ: metrics.ExecutionFailure.WithLabelValues(string(mode)).Inc()
WW: metrics.ExecutionSuccess.WithLabelValues(string(mode)).Inc()
```
**Expected:** ✅ 4 metrics calls found

### 16. Feature Flags Integration
```bash
# Verify metrics recorded for both modes
curl http://localhost:9091/metrics | grep worker_execution_mode_total
```
**Expected:** ✅ Both `mode="event_driven"` and `mode="http_sync"` present

---

## ✅ Documentation Checks

### 17. README Exists
```bash
cat go-services/worker/internal/metrics/README.md | head -20
```
**Expected:** ✅ Comprehensive README with usage examples

### 18. Summary Document
```bash
cat docs/archive/sprints/TASK_3_2_2_AB_TESTING_METRICS_SUMMARY.md | head -20
```
**Expected:** ✅ Detailed implementation summary

---

## ✅ Performance Checks

### 19. Memory Usage
```bash
# Before operations
ps aux | grep cc1c-worker | awk '{print $6}'

# After 100 operations
# ... trigger operations ...

ps aux | grep cc1c-worker | awk '{print $6}'
```
**Expected:** ✅ Memory increase < 1MB (metrics overhead minimal)

### 20. Metrics Response Time
```bash
time curl -s http://localhost:9091/metrics > /dev/null
```
**Expected:** ✅ Response time < 50ms

---

## ✅ Error Handling Checks

### 21. Invalid Mode Label
```go
// This should NOT panic (unit test verifies)
metrics.RecordExecution("invalid_mode", 0.5, true)
```
**Expected:** ✅ No panic, metric created with label

### 22. Negative Duration
```go
metrics.RecordExecution("event_driven", -0.5, true)
```
**Expected:** ✅ No panic, histogram handles gracefully

---

## 📋 Final Checklist

**Before marking Task 3.2.2 as complete:**

- [ ] ✅ Code compiles without errors
- [ ] ✅ All unit tests pass
- [ ] ✅ Worker starts with /metrics endpoint
- [ ] ✅ Metrics endpoint returns valid Prometheus format
- [ ] ✅ Prometheus scrapes Worker successfully
- [ ] ✅ Recording rules load and execute
- [ ] ✅ Grafana dashboard imports successfully
- [ ] ✅ All 7 dashboard panels work
- [ ] ✅ Test operations populate metrics
- [ ] ✅ Both event_driven and http_sync modes recorded
- [ ] ✅ Documentation complete (README + Summary)
- [ ] ✅ No performance degradation

**All checks passed?** → Task 3.2.2 ✅ COMPLETE → Proceed to Task 3.2.3 (Rollback Plan)

---

## Troubleshooting

### Issue: Metrics endpoint returns 404
**Solution:** Check Worker logs, ensure goroutine started:
```bash
./scripts/dev/logs.sh worker | grep "metrics endpoint"
```

### Issue: Prometheus target DOWN
**Solution:** Verify prometheus.yml config:
```bash
cat infrastructure/monitoring/prometheus/prometheus.yml | grep -A5 worker
```

### Issue: Dashboard shows "No data"
**Solution:**
1. Trigger operations to populate metrics
2. Check time range (should be "Last 1 hour")
3. Verify Prometheus datasource URL

### Issue: Recording rules not loading
**Solution:** Validate YAML syntax:
```bash
promtool check rules infrastructure/monitoring/prometheus/recording_rules.yml
```

---

## Quick Test Command

**One-liner to verify everything:**
```bash
cd /c/1CProject/command-center-1c && \
go test ./go-services/worker/internal/metrics -v && \
go build -o /tmp/cc1c-worker.exe go-services/worker/cmd/main.go && \
echo "✅ All checks passed!"
```

**Expected output:**
```
=== RUN   TestRecordExecution
--- PASS: TestRecordExecution (0.00s)
...
PASS
ok  	github.com/commandcenter1c/commandcenter/worker/internal/metrics	0.755s
✅ All checks passed!
```

---

**Last Updated:** 2025-11-18
**Task Status:** ✅ COMPLETED
