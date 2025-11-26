# Workflow Engine Load Tests

Locust-based load tests for Workflow Engine REST API.

## Prerequisites

1. **Install Locust:**
   ```bash
   pip install locust
   ```

2. **Create test user in Django:**
   ```bash
   cd orchestrator
   python manage.py shell -c "
   from django.contrib.auth import get_user_model
   User = get_user_model()
   if not User.objects.filter(username='loadtest').exists():
       User.objects.create_user('loadtest', 'loadtest@test.com', 'loadtest123', is_staff=True)
       print('User created')
   else:
       print('User already exists')
   "
   ```

3. **Ensure services are running:**
   ```bash
   ./scripts/dev/start-all.sh
   ./scripts/dev/health-check.sh
   ```

## Running Load Tests

### Interactive Mode (Web UI)

```bash
cd orchestrator
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000
```

Open http://localhost:8089 in browser to configure and start the test.

### Headless Mode (CI/CD)

```bash
cd orchestrator

# Light load (10 users)
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000 \
    --headless -u 10 -r 2 -t 1m --csv=results/light_load

# Medium load (50 users)
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000 \
    --headless -u 50 -r 5 -t 2m --csv=results/medium_load

# Heavy load (100 users)
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m --csv=results/heavy_load
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `-u` / `--users` | Number of concurrent users |
| `-r` / `--spawn-rate` | Users spawned per second |
| `-t` / `--run-time` | Test duration (e.g., `1m`, `30s`, `1h`) |
| `--csv` | CSV output prefix for results |
| `--html` | Generate HTML report |

## Load Profiles

| Profile | Users | Spawn Rate | Wait Time | Description |
|---------|-------|------------|-----------|-------------|
| Light | 10 | 2/s | 2-5s | Normal daily usage |
| Medium | 50 | 5/s | 1-3s | Peak usage simulation |
| Heavy | 100 | 10/s | 0.5-1.5s | Stress test |
| Burst | - | - | 0.3-0.8s | Concurrent execution focus |

## Test Tasks

The load test performs these operations with different weights:

| Task | Weight | Description |
|------|--------|-------------|
| `list_templates` | 10 | List workflow templates |
| `execute_workflow` | 20 | Execute workflow (async) |
| `check_execution_status` | 15 | Poll execution status |
| `create_simple_workflow` | 5 | Create simple 3-node workflow |
| `create_complex_workflow` | 3 | Create complex 10-node workflow |
| `list_executions` | 3 | List executions |
| `cancel_execution` | 2 | Cancel running execution |
| `get_template_detail` | 1 | Get template details |
| `clone_template` | 1 | Clone template |

## Output Files

When using `--csv` option, Locust generates:

- `*_stats.csv` - Request statistics
- `*_failures.csv` - Failed requests
- `*_stats_history.csv` - Statistics over time
- `*_exceptions.csv` - Python exceptions

## Custom Metrics

The test collects additional metrics for bottleneck analysis:

- **execution_times** - End-to-end workflow execution duration
- **template_create_times** - Template creation latency
- **execution_start_times** - Time to start execution
- **status_poll_times** - Status polling latency
- **errors_by_type** - Error breakdown
- **max_concurrent_executions** - Peak concurrent executions

## Bottleneck Analysis

After test completion, the script outputs hints:

| Symptom | Possible Bottleneck | Action |
|---------|-------------------|--------|
| High execution start latency (>1s p95) | Celery workers | Increase worker count |
| High status poll latency (>0.5s p95) | Database queries | Add indexes, optimize queries |
| High template creation latency (>2s p95) | Database writes | Check PostgreSQL performance |
| High concurrent executions (>50) | Worker pool | Increase pool size |
| Rate limiting triggered | API rate limits | Increase limits or spread load |

## Troubleshooting

### Authentication Failures

1. Verify test user exists:
   ```bash
   python manage.py shell -c "
   from django.contrib.auth import get_user_model
   User = get_user_model()
   print(User.objects.filter(username='loadtest').exists())
   "
   ```

2. Check JWT settings in `config/settings.py`

### Connection Errors

1. Verify services are running:
   ```bash
   ./scripts/dev/health-check.sh
   ```

2. Check Orchestrator logs:
   ```bash
   ./scripts/dev/logs.sh orchestrator
   ```

### Rate Limiting

If seeing 429 errors, check Django REST Framework throttling settings:

```python
# config/settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/min',
        'workflow_execute': '30/min',
    }
}
```

## Example Results

```
Name                       # reqs    Avg    Min    Max  Median    req/s
-----------------------------------------------------------------------------
[Templates] List              523     45     12    312      35    8.72
[Workflows] Execute          1041    156     23   1523     125   17.35
[Executions] Status          1562     28      8    245      22   26.03
[Templates] Create Simple     261    234     45   2156     189    4.35
-----------------------------------------------------------------------------
Aggregated                   3387     89      8   2156      45   56.45
```

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Run Load Tests
  run: |
    cd orchestrator
    pip install locust
    locust -f tests/load/workflow_load_test.py \
      --host=http://localhost:8000 \
      --headless -u 10 -r 2 -t 30s \
      --csv=load_test_results \
      --exit-code-on-error 1

- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: load-test-results
    path: orchestrator/load_test_results*.csv
```
