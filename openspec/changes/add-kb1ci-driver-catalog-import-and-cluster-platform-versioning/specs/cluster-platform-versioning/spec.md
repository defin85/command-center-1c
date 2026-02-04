# Spec Delta: cluster-platform-versioning

## ADDED Requirements
### Requirement: Effective platform version хранится по кластеру
Система ДОЛЖНА (SHALL) хранить `effective_platform_version` по кластеру, включая:
- полную версию (например `8.3.23.1709`),
- нормализованную “minor” (`8.3.23`) для выбора документации/каталогов,
- статус достоверности `ok|unknown|mixed`,
- provenance (`auto|manual`) и метаданные обновления.

#### Scenario: Версия неизвестна
- **WHEN** система не может определить платформенную версию кластера автоматически
- **THEN** `status=unknown` и требуется ручной override для маппинга документации/каталогов

#### Scenario: Кластер “mixed”
- **GIVEN** в кластере обнаружены разные minor версии платформы
- **WHEN** система сохраняет effective version
- **THEN** `status=mixed` и система требует ручной override (выбор целевой minor версии) для привязки документации/каталогов

### Requirement: Резолв активного каталога по кластеру использует minor версию
Система ДОЛЖНА (SHALL) уметь резолвить активный base catalog для `driver` с учётом `cluster.effective_platform_version_minor`.

#### Scenario: Резолв возвращает активный каталог
- **GIVEN** у кластера `effective_platform_version_minor=8.3.24`
- **AND** для `(driver=cli, platform_version=8.3.24)` выбран active base catalog
- **WHEN** UI/Backend запрашивает “effective catalog for cluster”
- **THEN** возвращается выбранный active base catalog

