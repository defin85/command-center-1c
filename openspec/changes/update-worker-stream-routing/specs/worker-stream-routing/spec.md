## ADDED Requirements
### Requirement: Worker поддерживает выбор Redis Stream и consumer group через env
Система ДОЛЖНА (SHALL) позволять конфигурировать, какой Redis Stream читает Go Worker, и какую consumer group он использует, через переменные окружения (например `WORKER_STREAM_NAME`, `WORKER_CONSUMER_GROUP`).

#### Scenario: Два deployment’а worker читают разные stream’ы
- **GIVEN** подняты два deployment’а Worker с разными `WORKER_STREAM_NAME`
- **WHEN** Orchestrator публикует `execute_workflow` в stream workflows, а BatchOperation в stream operations
- **THEN** workflow сообщения обрабатываются только workflow‑воркерами
- **AND** операции продолжают исполняться ops‑воркерами без взаимной блокировки

