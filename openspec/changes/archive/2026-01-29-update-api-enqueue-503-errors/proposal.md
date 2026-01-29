# Change: 503 + единые error codes для enqueue-failure в API v2 (execute-ibcmd-cli, dlq.retry)

## Why
Сейчас API v2 возвращает разные HTTP-коды и форматы ошибок при проблемах с enqueue в Redis Streams:
- `/api/v2/operations/execute-ibcmd-cli/` может вернуть `500` при неуспешном enqueue, хотя это по смыслу `503 Service Unavailable`.
- `/api/v2/dlq/retry/` уже возвращает `503` при ошибке чтения DLQ, но это не отражено в OpenAPI.

Это затрудняет обработку ошибок на клиенте и делает контракты (OpenAPI) несинхронизированными с реальным поведением.

## What Changes
- Для `/api/v2/operations/execute-ibcmd-cli/`: при Redis outage / ошибке XADD на enqueue возвращать `HTTP 503`, а `error.code` унифицировать как `REDIS_ERROR`.
- Для `/api/v2/dlq/retry/`: сохранить `HTTP 503` на Redis-ошибках и также использовать `error.code=REDIS_ERROR`.
- Обновить `contracts/orchestrator/openapi.yaml`, добавив `503` ответы для этих эндпоинтов.
- Ввести единый набор error codes для enqueue-failure (минимум: различать `REDIS_ERROR` от остальных ошибок enqueue).

## Non-Goals
- Не меняем бизнес-логику enqueue, формат сообщений Message Protocol v2.0 и worker streams.
- Не внедряем outbox/ретраи со стороны API (это отдельный change при необходимости).

## Impact
- Orchestrator API v2 views (ошибки/коды ответов).
- OpenAPI контракт orchestrator.
- Тесты API v2/operations, чтобы зафиксировать поведение.

