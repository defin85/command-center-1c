## MODIFIED Requirements
### Requirement: App shell MUST использовать единый bootstrap read-model вместо capability probe-запросов как primary path
Система ДОЛЖНА (SHALL) предоставлять canonical bootstrap/read-model resource для shell session context, включающий как минимум:
- user identity summary;
- tenant context summary;
- access summary, необходимый для shell gating;
- UI capability flags, нужные для route/menu composition;
- i18n summary, включающий `supported_locales`, `default_locale`, `effective_locale` и optional `requested_locale`.

`MainLayout`, `AuthzProvider` и другие shell-level consumers НЕ ДОЛЖНЫ (SHALL NOT) на default path определять capability или locale доступность через набор независимых probe API calls, если тот же context доступен через bootstrap resource.

Canonical bootstrap owner ДОЛЖЕН (SHALL) монтироваться один раз на authenticated app session / shared shell runtime path и переиспользоваться между внутренними route handoff, пока не произошёл явный session reset, logout или другой documented hard-reset flow.

Route-level guards (`ProtectedRoute`, staff/capability gates и их аналоги) НЕ ДОЛЖНЫ (SHALL NOT) на обычном in-app navigation становиться независимыми owner'ами bootstrap query lifecycle для каждого route element. Они ДОЛЖНЫ (SHALL) принимать decision на базе уже инициализированного shared shell context или явного shared bootstrap provider.

`MainLayout`, `AuthzProvider`, `I18nProvider` и route-level guards НЕ ДОЛЖНЫ (SHALL NOT) каждый самостоятельно вызывать bootstrap read-model hook на default authenticated shell path. React Query cache/request dedupe МОЖЕТ (MAY) оставаться network optimization, но НЕ ДОЛЖЕН (SHALL NOT) считаться достаточным proof single-owner bootstrap architecture.

#### Scenario: Staff route загружает shell context и locale через один bootstrap contract
- **GIVEN** авторизованный staff-пользователь открывает `/decisions`
- **WHEN** frontend инициализирует shell/runtime context
- **THEN** `me`, tenant/access summary, shell capability flags и locale summary приходят через один canonical bootstrap path
- **AND** shell не делает отдельные capability или locale probe calls только для построения меню и глобальных guard'ов

#### Scenario: Shell-backed route switch переиспользует существующий bootstrap owner
- **GIVEN** авторизованный пользователь уже инициализировал shared shell context на `/service-mesh`
- **WHEN** он переходит в `/pools/master-data` внутри той же app session
- **THEN** следующий route использует уже существующий bootstrap owner и shared authz context
- **AND** normal handoff не создаёт второй независимый bootstrap read только из-за смены route element

#### Scenario: Shell consumers используют один bootstrap owner
- **GIVEN** authenticated shell runtime уже смонтировал canonical bootstrap provider
- **WHEN** `MainLayout`, authz context, locale context и capability guard принимают decisions
- **THEN** они читают shared shell context от provider'а
- **AND** не создают собственные bootstrap hook owners на default path

#### Scenario: Bootstrap locale failure даёт стабильный shell error state
- **GIVEN** bootstrap resource не может вернуть обязательный shell context, включая locale summary
- **WHEN** shell не может собрать обязательный runtime context
- **THEN** пользователь видит один стабильный shell-level failure state
- **AND** система НЕ ДОЛЖНА запускать cascade из secondary locale probe errors как substitute path
