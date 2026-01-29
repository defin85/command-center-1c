# Спецификация: worker-stream-routing

## Purpose
Фиксирует публичный контракт маршрутизации Redis Streams для Go Worker: через какие переменные окружения настраивается входной stream и consumer group, чтобы можно было разделить исполнение операций и workflow-оркестрации по разным deployment'ам.

## Requirements
### Requirement: Worker поддерживает выбор Redis Stream и consumer group через env
Система ДОЛЖНА (SHALL) позволять конфигурировать, какой Redis Stream читает Go Worker, и какую consumer group он использует, через переменные окружения (например `WORKER_STREAM_NAME`, `WORKER_CONSUMER_GROUP`).

#### Scenario: Два deployment’а worker читают разные stream’ы
- **GIVEN** подняты два deployment’а Worker с разными `WORKER_STREAM_NAME` (например `commands:worker:operations` и `commands:worker:workflows`)
- **WHEN** Orchestrator публикует `execute_workflow` в stream workflows, а BatchOperation в stream operations
- **THEN** workflow сообщения обрабатываются только workflow‑воркерами
- **AND** операции продолжают исполняться ops‑воркерами без взаимной блокировки

#### Scenario: docker-compose запускает два worker сервиса (ops + workflows)
- **GIVEN** используется docker-compose и один Redis
- **WHEN** запущены два сервиса worker с разными `WORKER_STREAM_NAME` и `WORKER_CONSUMER_GROUP`
- **THEN** ops и workflows очереди обрабатываются независимо

```yaml
# docker-compose.yml (fragment)
services:
  worker-ops:
    image: ghcr.io/commandcenter1c/worker:latest
    environment:
      WORKER_ID: worker-ops
      WORKER_STREAM_NAME: commands:worker:operations
      WORKER_CONSUMER_GROUP: worker-ops
      ORCHESTRATOR_URL: http://orchestrator:8200
      WORKER_API_KEY: ${WORKER_API_KEY}
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_DB: "0"

  worker-workflows:
    image: ghcr.io/commandcenter1c/worker:latest
    environment:
      WORKER_ID: worker-workflows
      WORKER_STREAM_NAME: commands:worker:workflows
      WORKER_CONSUMER_GROUP: worker-workflows
      ORCHESTRATOR_URL: http://orchestrator:8200
      WORKER_API_KEY: ${WORKER_API_KEY}
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_DB: "0"
```
