# Мониторинг - Prometheus & Grafana

## Быстрый старт

### Запуск мониторинга

```bash
# Запустить Prometheus + Grafana
./scripts/dev/start-monitoring.sh
```

**Доступ:**
- 📊 Prometheus: http://localhost:9090
- 📈 Grafana: http://localhost:3001 (admin/admin)

**Проверка статуса:**
```bash
./scripts/dev/health-check.sh
# Теперь включает секцию "[6] Проверка мониторинга (опционально)"
```

**Интеграция с start-all.sh:**
- Мониторинг теперь **запускается автоматически** при выполнении `./scripts/dev/start-all.sh`
- Запуск происходит на шаге [1/12] вместе с остальной Docker инфраструктурой
- Если нужно запустить мониторинг отдельно, используйте `./scripts/dev/start-monitoring.sh`

### Остановка мониторинга

**Вариант 1: Отдельная остановка мониторинга**
```bash
./scripts/dev/stop-monitoring.sh
```

**Вариант 2: Остановка всех сервисов (включая мониторинг)**
```bash
./scripts/dev/stop-all.sh
# Теперь останавливает ВСЕ сервисы: application + infrastructure + monitoring
```

**Важно:** `stop-all.sh` теперь автоматически останавливает Prometheus и Grafana вместе с остальными сервисами.

---

## Полный запуск системы с мониторингом

### Простой запуск (рекомендуется)

```bash
# Всё в одной команде - мониторинг включен автоматически
./scripts/dev/start-all.sh

# Проверка всех сервисов (включая мониторинг)
./scripts/dev/health-check.sh
```

**Что запустится:**
- Docker Infrastructure: PostgreSQL, Redis
- Docker Monitoring: Prometheus, Grafana ← **автоматически!**
- Application Services: orchestrator, celery-worker, celery-beat, api-gateway, worker, ras, ras-grpc-gw, cluster-service, batch-service, frontend

### Ручной запуск (если нужен контроль)

```bash
# 1. Инфраструктура + мониторинг запускаются автоматически в start-all.sh
# Если нужен только мониторинг отдельно:
./scripts/dev/start-monitoring.sh

# 2. RAS gRPC Gateway (если есть 1C RAS)
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545 &
cd ../command-center-1c

# 3. Все сервисы
./scripts/dev/start-all.sh

# 4. Проверка
./scripts/dev/health-check.sh
```

---

## Dashboards в Grafana

После запуска Grafana автоматически загрузит:

### ✅ Системные дашборды:
- **System Overview** - общий обзор системы
- **PostgreSQL Metrics** - метрики базы данных
- **Redis Metrics** - метрики очереди

### ✅ Event-Driven дашборды (NEW!):
- **A/B Testing Dashboard** - сравнение Event-Driven vs HTTP Sync
  - Traffic split (pie chart)
  - Performance comparison (latency, throughput)
  - Success rate comparison
  - Error rate comparison

Откройте: http://localhost:3001/d/ab-testing-event-driven

---

## Prometheus Alerts

**8 alert rules** для автоматического rollback detection:

### Critical Alerts (PagerDuty):
1. **EventDrivenSuccessRateLow** - success rate < 95% (5 min)
2. **EventDrivenLatencyHigh** - P99 latency > 1s (3 min)
3. **EventDrivenRedisUnavailable** - Redis down (1 min)

### Warning Alerts (Slack):
4. **EventDrivenCompensationHigh** - compensation rate > 10% (5 min)
5. **EventDrivenCircuitBreakerTripped** - circuit breaker trips
6. **EventDrivenRetryRateHigh** - retry rate > 15% (5 min)
7. **EventDrivenQueueDepthGrowing** - queue depth растет
8. **EventDrivenModeDisabled** - Event-Driven выключен (info)

Alerts конфигурация: `infrastructure/monitoring/prometheus/alerts/rollback_alerts.yml`

---

## Метрики Event-Driven

### Worker Execution Mode

```promql
# Total operations by mode
worker_execution_mode_total{mode="event_driven"}
worker_execution_mode_total{mode="http_sync"}

# Success rate
rate(worker_execution_success_total{mode="event_driven"}[5m]) /
rate(worker_execution_mode_total{mode="event_driven"}[5m])

# Latency percentiles
histogram_quantile(0.99,
  rate(worker_execution_duration_seconds_bucket{mode="event_driven"}[5m])
)
```

### Компоненты Event-Driven

```promql
# Event publishing
event_publish_duration_seconds
event_publish_errors_total

# State Machine transitions
state_machine_transitions_total{workflow="extension_install"}
state_machine_timeout_total

# Compensation
saga_compensation_executions_total
saga_manual_action_required_total
```

---

## Troubleshooting

### Prometheus не стартует

```bash
# Проверить логи
docker logs cc1c-prometheus-local

# Проверить конфиг
docker exec cc1c-prometheus-local promtool check config /etc/prometheus/prometheus.yml

# Перезапустить
docker restart cc1c-prometheus-local
```

### Grafana не показывает данные

```bash
# 1. Проверить что Prometheus работает
curl http://localhost:9090/-/healthy

# 2. Проверить datasource в Grafana
curl http://localhost:3001/api/datasources

# 3. Проверить логи Grafana
docker logs cc1c-grafana-local

# 4. Пересоздать Grafana
docker-compose -f docker-compose.local.monitoring.yml up -d --force-recreate grafana
```

### Dashboard не загрузился

```bash
# Проверить что файлы существуют
ls -la infrastructure/monitoring/grafana/dashboards/ab_testing_dashboard.json

# Проверить provisioning config
ls -la infrastructure/monitoring/grafana/provisioning/

# Reload provisioning
curl -X POST http://admin:admin@localhost:3001/api/admin/provisioning/dashboards/reload
```

### Alerts не работают

```bash
# Проверить alerts в Prometheus
curl http://localhost:9090/api/v1/rules

# Проверить alerts файлы
ls -la infrastructure/monitoring/prometheus/alerts/

# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload
```

---

## Полезные команды

### Prometheus

```bash
# Health check
curl http://localhost:9090/-/healthy

# Config reload
curl -X POST http://localhost:9090/-/reload

# Metrics
curl http://localhost:9090/metrics

# Targets status
curl http://localhost:9090/api/v1/targets
```

### Grafana

```bash
# Health check
curl http://localhost:3001/api/health

# List datasources
curl http://admin:admin@localhost:3001/api/datasources

# List dashboards
curl http://admin:admin@localhost:3001/api/search

# Reload dashboards
curl -X POST http://admin:admin@localhost:3001/api/admin/provisioning/dashboards/reload
```

---

## Архитектура

```
Application Services (host machine)
    ↓ expose metrics on /metrics
Prometheus (Docker :9090)
    ↓ scrapes metrics every 15s
    ↓ evaluates alerts every 30s
    ↓ stores time-series data
Grafana (Docker :3001)
    ↓ queries Prometheus
    ↓ visualizes dashboards
User (browser)
```

---

## См. также

- [EVENT_DRIVEN_ROLLBACK_PLAN.md](EVENT_DRIVEN_ROLLBACK_PLAN.md) - Rollback procedure
- [EVENT_DRIVEN_PRODUCTION_ROLLOUT.md](EVENT_DRIVEN_PRODUCTION_ROLLOUT.md) - Production rollout guide
- [FEATURE_FLAGS.md](FEATURE_FLAGS.md) - Feature flags configuration
- [Prometheus docs](https://prometheus.io/docs/)
- [Grafana docs](https://grafana.com/docs/)
