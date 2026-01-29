# Спецификация: redis-streams-event-processing

## Purpose
Фиксирует требования к обработке Redis Streams событий в Orchestrator (EventSubscriber):
- семантика доставки **at-least-once**;
- идемпотентность на границе Postgres (dedup/receipt по `(stream, group, message_id)`);
- reclaim pending (PEL) для предотвращения “зависших” сообщений после крэшей/рестартов.

## Requirements
### Requirement: Orchestrator EventSubscriber обеспечивает at-least-once + идемпотентность на границе БД
Система ДОЛЖНА (SHALL) обрабатывать события из Redis Streams с семантикой **at-least-once**, обеспечивая при этом идемпотентность на границе Postgres: повторная доставка одного и того же сообщения НЕ ДОЛЖНА (SHALL NOT) приводить к повторному применению бизнес‑эффектов в БД.

#### Scenario: Повторная доставка сообщения не дублирует DB эффекты
- **GIVEN** сообщение с `message_id=M` было успешно обработано и зафиксировано в БД
- **WHEN** то же сообщение `M` снова доставляется subscriber’у (pending/claim/retry)
- **THEN** subscriber не применяет бизнес‑изменения повторно
- **AND** subscriber ACK’ает `M`, чтобы погасить повтор

### Requirement: EventSubscriber умеет reclaim pending (PEL) для предотвращения “зависших” сообщений
Система ДОЛЖНА (SHALL) обнаруживать и “забирать” (claim) сообщения, оставшиеся в Pending Entries List (PEL) consumer group’ы дольше заданного порога, и доводить их до обработки/ACK.

#### Scenario: Сообщение pending после крэша всё равно обрабатывается
- **GIVEN** subscriber прочитал сообщение и упал до ACK, и оно осталось в PEL
- **WHEN** subscriber перезапущен (consumer_name изменился)
- **THEN** subscriber reclaim’ит pending сообщение и обрабатывает его
- **AND** состояние в Postgres становится консистентным
