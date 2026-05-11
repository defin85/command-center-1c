## Context
Текущий gateway применяет один rate-limit bucket ко всему JWT-protected `/api/v2` трафику, кроме небольшого списка unlimited streaming routes. В checked-in коде это выглядит как `RateLimitMiddleware(100, time.Minute)` для всего `v2Limited` и key по `user_id` с fallback на IP.

Практический эффект уже виден на live contour:
- тяжёлые background surfaces (`Sync`, ранее `Dashboard`) дают mount-time fanout из нескольких запросов;
- несколько tabs/browser sessions одного пользователя делят тот же bucket;
- `429` приходит не только на noisy route, но и на shell bootstrap/control traffic;
- suppression одного источника amplification (например telemetry retry) уменьшает шум, но не устраняет cross-surface starvation.

Одновременно у проекта уже есть зафиксированные ограничения:
- нельзя считать повышение global limit primary solution;
- deterministic `4xx`/`429` не должны blindly retry на frontend;
- `/system/bootstrap/` остаётся canonical shell read-model.

## Goals / Non-Goals
- Goals:
  - изолировать shell-critical, interactive, background-heavy и telemetry budgets вместо одного shared user bucket;
  - сделать route classification explicit и source-controlled;
  - публиковать machine-readable `429` diagnostics;
  - зафиксировать runtime expectation, что heavy route не starving'ит unrelated shell/bootstrap traffic как normal behavior.
- Non-Goals:
  - ослабить gateway защиту до effectively unlimited режима;
  - переписать весь frontend data runtime за один change;
  - заменять existing stream/session contract из `database-realtime-streaming`.

## Decisions

### 1. Gateway budgets становятся class-aware, а не purely user-wide
Gateway должен считать budget key как минимум по:
- `tenant_id` (если доступен из request context);
- `user_id` или IP fallback;
- `budget_class`.

Минимальный набор `budget_class`:
- `shell_critical`
- `interactive`
- `background_heavy`
- `telemetry`
- `streaming` (existing special path)

Это не устраняет shared ownership полностью внутри одного класса, но убирает главную проблему: background-heavy traffic больше не расходует тот же budget, что shell/bootstrap.

### 2. Route classification должна быть явной и checked-in
Gateway не должен определять “важность” route неявно только по методу или path prefix. Нужна checked-in классификация рядом с route registration.

Первый implementation step может использовать code-owned mapping рядом с `RegisterOrchestratorRoutes`. Если позже команда захочет двигаться к OpenAPI-driven contract, change может разрешить эволюцию к spec extension, но initial rollout не должен зависеть от полного contract regeneration.

Неизвестный route НЕ ДОЛЖЕН попадать в unlimited path. Он должен идти в documented bounded default class.

### 3. `/system/bootstrap/` получает reserved shell-critical budget, но не unlimited exemption
`/system/bootstrap/` и другой shell/control traffic не должны делить budget с heavy route reads, но это не повод делать их unlimited. Нужен собственный bounded class, который защищает shell path от starvation и при этом сохраняет abuse guardrail.

Это важно, потому что unlimited exemption для shell path решает только текущий symptom, но не даёт observability и не масштабируется на другие control surfaces.

### 4. Telemetry идёт в bounded best-effort class
`/ui/incident-telemetry/ingest/` не должна жить в том же budget, что shell или interactive actions.

Правильная модель:
- frontend drop/fail-closed на `429`;
- gateway даёт отдельный маленький `telemetry` budget;
- telemetry overflow не ломает shell bootstrap и operator actions.

### 5. `429` contract становится machine-readable
Gateway `429` должен публиковать минимум:
- `rate_limit_class`
- `retry_after_seconds`
- `budget_scope`
- `request_id`

Это нужно не только UI, но и live incident diagnostics: по логам и telemetry должен быть виден exact starvation class, а не только generic `Rate limit exceeded`.

### 6. Frontend heavy routes должны вписываться в background-heavy budget
Budget isolation закрывает cross-surface starvation, но не отменяет route shaping. Heavy route всё ещё может само себе создать плохой UX внутри собственного `background_heavy` класса.

Поэтому change должен включать хотя бы один confirmed heavy surface (`Pool Master Data Sync`) как pilot:
- staged secondary reads;
- или consolidated workspace bootstrap;
- или иной bounded способ сократить mount-time fanout.

## Alternatives Considered

### Вариант A: Просто поднять global limit
Плюсы:
- быстро.

Минусы:
- не отделяет shell-critical traffic от heavy background traffic;
- лишь откладывает starvation threshold;
- противоречит уже зафиксированному project intent.

Итог: отклонён.

### Вариант B: Unlimited exemption только для `/system/bootstrap/`
Плюсы:
- быстро гасит самый заметный симптом.

Минусы:
- не решает starvation для других shell/control surfaces;
- не даёт class-aware observability;
- создаёт ещё один ad hoc exception вместо runtime model.

Итог: недостаточно как primary solution.

### Вариант C: Лечить только frontend route bursts
Плюсы:
- полезно само по себе;
- уменьшает нагрузку.

Минусы:
- не защищает shell path от другого noisy surface или multi-session burst;
- оставляет gateway with one shared bucket.

Итог: нужен как complement, но не как единственный change.

### Вариант D: Делать primary key по browser/client session
Плюсы:
- сильнее изолирует parallel sessions одного пользователя.

Минусы:
- требует отдельного client-session contract на gateway boundary;
- сегодня у API routes такого contract нет;
- больше scope, чем нужно для первого безопасного шага.

Итог: можно оставить как future extension, но не как минимальный rollout.

## Risks / Trade-offs
- Route classification drift:
  - mitigation: checked-in mapping + tests на critical paths.
- Новые budget classes могут быть выбраны неудачно по числам:
  - mitigation: rollout через explicit config values и class-aware metrics.
- Frontend team может воспринять gateway isolation как excuse не уменьшать heavy route bursts:
  - mitigation: включить `Sync` pilot прямо в tasks и spec delta.
- Existing logs/tests могут ожидать generic `Rate limit exceeded` без metadata:
  - mitigation: additive contract, не ломать базовые correlation fields.

## Migration Plan
1. Зафиксировать spec contract и tasks.
2. Ввести config + class resolution + additive `429` metadata.
3. Перевести limiter на isolated buckets.
4. Добавить metrics/log fields.
5. Подтянуть pilot heavy route (`Pool Master Data Sync`) под новый budget model.
6. Закрыть browser/live starvation smoke.

## Open Questions
- Нужен ли отдельный `control_plane` class помимо `shell_critical`, или пока достаточно одного класса для bootstrap/control reads?
- Должен ли `budget_scope` в `429` contract явно включать `tenant_id`, или достаточно semantic label без tenant echo?
