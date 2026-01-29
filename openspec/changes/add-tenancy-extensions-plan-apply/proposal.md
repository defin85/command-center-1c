# Change: Tenancy + schema-driven snapshots + plan/apply (MVP: extensions)

## Why
Сейчас добавление новых driver endpoints приводит к “жёсткой” логике и моделям на фронте/бэке/в БД под каждый кейс. Это масштабируется плохо.

Цель — перейти к более универсальному контуру:
- **Tenant-scoped конфигурации и оверрайды** (user выбирает tenant в UI).
- **Snapshot-driven инвентаризация** (сохранение результатов команд как воспроизводимых снимков).
- **Plan/apply с drift check** (детерминированность: план строится от известного состояния, apply проверяет что состояние не изменилось).

MVP ограничиваем **только** на сущности `extensions` (инвентаризация расширений ИБ), но закладываем платформенную основу для дальнейших сущностей.

## What Changes
- Ввести сущность `Tenant` и membership для пользователей; UI-переключатель tenant.
- Сделать `Cluster`/`Database` принадлежащими ровно одному tenant (все существующие данные мигрируются в `default` tenant).
- Runtime settings остаются **глобальными**, но добавляются **overrides per-tenant** (включая `ui.action_catalog`).
- Добавить универсальное хранение “command result snapshots” (append-only) + быстрые latest-проекции (как сейчас для `DatabaseExtensionsSnapshot`).
- Реализовать **plan/apply + drift check** для extensions, используя snapshot и action catalog.

## Non-Goals
- Не делаем сразу поддержку множества сущностей кроме `extensions`.
- Не делаем полноценный reconcile-операторный цикл для всех ресурсов (можно позже).
- Не делаем “произвольный код” в маппингах (только ограниченный детерминированный DSL).

## Open Questions (для согласования до реализации)
1) Drift check “strict” vs “observed”:
   - **strict**: на apply выполняется preflight `extensions.list` и сравнивается hash (дороже, но честно ловит внешний дрейф).
   - **observed**: сравнивается только сохранённый snapshot hash/updated_at (дешевле, но не ловит изменения вне системы).
   **Предлагаемый default: strict.**
2) Desired state для MVP extensions:
   - MVP: apply исполняет настроенный action `extensions.sync` (идемпотентный sync), а plan фиксирует preconditions и preview.
   - Позже: явный desired state (набор расширений) и diff-план.
