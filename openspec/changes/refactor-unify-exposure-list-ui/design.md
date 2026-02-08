## Context
Текущий `/templates` формально объединяет surfaces, но технически разделён на tabs, где `action_catalog` рендерится как отдельный `ActionCatalogPage`.
Это оставляет дублирование page-level state, query логики и UI потоков для одной сущности `operation_exposure`.

## Goals / Non-Goals
- Goals:
  - Один экран и один список exposure для `template` и `action_catalog`.
  - Один редактор (единый modal shell) для create/edit.
  - Явный `surface` filter с URL-синхронизацией.
- Non-Goals:
  - Изменение backend API-контуров в этой фазе.
  - Удаление legacy endpoints и контрактная де-прекация (это отдельная фаза/change).

## Decisions
- Decision 1: `surface` как фильтр, а не как tabs/page split
  - `/templates` хранит выбранный surface в query-параметре.
  - Переключение `surface` перерисовывает один и тот же list shell.
- Decision 2: Единый editor shell для обеих поверхностей
  - `OperationExposureEditorModal` остаётся единственным modal-компонентом.
  - Surface-specific поля и ограничения настраиваются в рамках одного editor pipeline.
- Decision 3: Fail-closed RBAC в UI
  - Если non-staff указывает `?surface=action_catalog`, UI откатывает фильтр к `template`.
  - Action management query paths не должны вызываться для non-staff.

## Migration Plan
1. Обновить OpenSpec дельты (`operation-templates`, `ui-action-catalog-editor`).
2. Переписать `/templates` на filter-based UI без tabs.
3. Перенести/встроить текущий action management flow в единый list shell.
4. Обновить browser тесты на filter-based UX и RBAC fallback.

## Risks / Trade-offs
- Риск: регрессии в behavior list/table из-за объединения двух page-level потоков.
  - Митигация: целевые browser-тесты для staff/non-staff + deep-link сценарии.
- Риск: смешение surface-specific UI сигналов (тексты, кнопки, пустые состояния).
  - Митигация: явный `surface`-driven mapping для labels/actions и контрактных ограничений.
