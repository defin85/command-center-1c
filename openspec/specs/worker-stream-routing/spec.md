# Спецификация: worker-stream-routing

## Purpose
Фиксирует публичный контракт маршрутизации Redis Streams для Go Worker: через какие переменные окружения настраивается входной stream и consumer group, чтобы можно было разделить исполнение операций и workflow-оркестрации по разным deployment'ам.

## Requirements
### Requirement: Worker поддерживает выбор Redis Stream и consumer group через env
Система ДОЛЖНА (SHALL) позволять конфигурировать, какой Redis Stream читает Go Worker, и какую consumer group он использует, через переменные окружения (например `WORKER_STREAM_NAME`, `WORKER_CONSUMER_GROUP`).

#### Scenario: Два deployment’а worker читают разные stream’ы
- **GIVEN** подняты два deployment’а Worker с разными `WORKER_STREAM_NAME`
- **WHEN** Orchestrator публикует `execute_workflow` в stream workflows, а BatchOperation в stream operations
- **THEN** workflow сообщения обрабатываются только workflow‑воркерами
- **AND** операции продолжают исполняться ops‑воркерами без взаимной блокировки
