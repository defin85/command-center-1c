## MODIFIED Requirements

### Requirement: App shell MUST использовать единый bootstrap read-model вместо capability probe-запросов как primary path

Система ДОЛЖНА (SHALL) предоставлять canonical bootstrap/read-model resource для shell session context, включающий как минимум:
- user identity summary;
- tenant context summary;
- access summary, необходимый для shell gating;
- UI capability flags, нужные для route/menu composition;
- i18n summary, включающий `supported_locales`, `default_locale`, `effective_locale` и optional `requested_locale`.

`MainLayout`, `AuthzProvider` и другие shell-level consumers НЕ ДОЛЖНЫ (SHALL NOT) на default path определять capability или locale доступность через набор независимых probe API calls, если тот же context доступен через bootstrap resource.

#### Scenario: Staff route загружает shell context и locale через один bootstrap contract

- **GIVEN** авторизованный staff-пользователь открывает `/decisions`
- **WHEN** frontend инициализирует shell/runtime context
- **THEN** `me`, tenant/access summary, shell capability flags и locale summary приходят через один canonical bootstrap path
- **AND** shell не делает отдельные capability или locale probe calls только для построения меню и глобальных guard'ов

#### Scenario: Bootstrap locale failure даёт стабильный shell error state

- **GIVEN** bootstrap resource не может вернуть обязательный shell context, включая locale summary
- **WHEN** shell не может собрать обязательный runtime context
- **THEN** пользователь видит один стабильный shell-level failure state
- **AND** система НЕ ДОЛЖНА запускать cascade из secondary locale probe errors как substitute path
