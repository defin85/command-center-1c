# RAS Protocol Reverse Engineering - Executive Summary

> **TL;DR:** UpdateInfobase УЖЕ работает в ras-grpc-gw. Нужно добавить только TerminateSession. Рекомендуется Wireshark analysis (2-4 дня) с fallback на Proxy Sniffer (3-5 дней). Worst-case timeline: 14 дней.

---

## 🎯 Проблема

**Что НЕ работает:**
- ❌ TerminateSession (завершение сессий пользователей) - **КРИТИЧНО для Phase 3**
- ⚠️ UpdateInfobase - работает ЧАСТИЧНО (основная функциональность есть, но может не хватать edge cases)

**Почему критично:**
- Блокирует Phase 3: Orchestrator operations
- Нужно для установки расширений (завершить все сессии перед установкой)
- 700 баз × 5-10 сессий = 3500-7000 операций параллельно

---

## ✅ Что УЖЕ работает

**Хорошие новости из анализа кода:**

1. **UpdateInfobase УЖЕ РЕАЛИЗОВАН** в `pkg/server/infobase_management_service.go:246-391`
   - ✅ Блокировка регламентов (`scheduled_jobs_deny`)
   - ✅ Блокировка сеансов (`sessions_deny`, `denied_from/to`)
   - ✅ Изменение параметров БД
   - ✅ Working implementation через RAS Binary Protocol

2. **RAS Binary Protocol Client РАБОТАЕТ** в `pkg/client/client.go`
   - ✅ Connection management, reconnect, idle timeout
   - ✅ Protocol version negotiation (10.0 default)
   - ✅ Endpoint lifecycle
   - ✅ Message framing через `protocolv1.NewPacket`

3. **Существует REFERENCE IMPLEMENTATION:**
   ```go
   // Мы УЖЕ знаем как работать с RAS Binary Protocol!
   endpoint.Request(ctx, &clientv1.EndpointRequest{
       Request: anyRequest,  // protobuf packed InfobaseInfo
       Respond: anyRespond,  // template для response
   })
   ```

**Вывод:** Нужно только выяснить **message format для TerminateSession** - всё остальное УЖЕ есть!

---

## 🛠️ Рекомендуемое решение

### Approach: Reverse Engineering RAS Binary Protocol

**Почему НЕ RAC CLI subprocess:**
- ❌ Медленно: 1-5 секунд vs <100ms для gRPC
- ❌ Не масштабируется: 700 subprocess одновременно
- ❌ Нарушает архитектурные принципы (API-First, No Compromises)

**Почему Reverse Engineering:**
- ✅ UpdateInfobase УЖЕ работает - доказывает что это возможно
- ✅ Существующий код как reference
- ✅ Чистое gRPC решение
- ✅ Масштабируется на 700 баз параллельно
- ✅ Low latency (<100ms)

---

## 📅 Timeline: 10-14 дней (2 недели)

### Phase 1: Wireshark Analysis (2-4 дня) ⭐ START HERE

**Шаги:**
1. Setup Wireshark на localhost, filter `tcp.port == 1545`
2. Capture операцию:
   ```bash
   rac session terminate --session=<UUID>
   ```
3. Analyze hex dump:
   - Packet structure (header, type, payload)
   - Compare с UpdateInfobase operation
   - Find session_id encoding
4. Document findings

**Deliverables:**
- Hex dump для TerminateSession
- Message structure spec (preliminary)

**Decision point:**
- ✅ Понимаем протокол → Phase 3 (implementation)
- ❌ Слишком сложно → Phase 2 (proxy sniffer)

**Success criteria:** Видим session_id в payload, понимаем packet header

**Effort:** LOW, **Вероятность успеха:** MEDIUM-HIGH (80%)

---

### Phase 2: Proxy Sniffer (3-5 дней) - ЕСЛИ Phase 1 НЕ РАБОТАЕТ

**Создать Go TCP proxy:**
```
rac.exe → :1546 → [Go Proxy Sniffer] → :1545 → RAS Server
                        ↓
                  Log + Decode protobuf
```

**Функциональность:**
- Перехватывает все packets
- Decodes protobuf automatically
- Exports JSON logs
- Pretty-print для анализа

**Преимущества:**
- ✅ Полная visibility (request + response)
- ✅ Автоматический protobuf decoding
- ✅ Repeatability для разных операций

**Deliverables:**
- Working proxy sniffer tool
- JSON logs для всех операций
- Protocol specification

**Success criteria:** Можем decode TerminateSession message structure

**Effort:** MEDIUM, **Вероятность успеха:** HIGH (95%)

---

### Phase 3: Implementation (3-5 дней)

**Добавить в ras-grpc-gw:**

1. **Protobuf schema (1 день):**
   ```protobuf
   service SessionManagementService {
       rpc TerminateSession(TerminateSessionRequest)
           returns (TerminateSessionResponse);
   }
   ```

2. **Server implementation (2 дня):**
   ```go
   func (s *SessionManagementServer) TerminateSession(...) {
       // Use EXISTING code pattern from UpdateInfobase
       endpoint, _ := s.client.GetEndpoint(ctx)

       terminateMsg := &serializev1.SessionInfo{
           SessionId: req.SessionId,
           // Поля из reverse engineering
       }

       endpoint.Request(ctx, &clientv1.EndpointRequest{...})
   }
   ```

3. **Testing (2 дня):**
   - Unit tests (coverage > 70%)
   - Integration test с real RAS
   - E2E test: terminate 100 sessions < 5 seconds

**Success criteria:**
- ✅ TerminateSession works через gRPC
- ✅ Latency < 100ms
- ✅ All tests pass

---

## 📊 Comparison Matrix

| Критерий | Reverse Engineering (Recommended) | RAC CLI Subprocess (Fallback) |
|----------|-----------------------------------|-------------------------------|
| **Latency** | <100ms ✅ | 1-5 seconds ❌ |
| **Scalability** | 700 parallel ✅ | Limited by subprocess ⚠️ |
| **Architecture** | Clean gRPC ✅ | Компромисс ❌ |
| **Timeline** | 10-14 дней | 2-3 дня |
| **Complexity** | MEDIUM-HIGH | LOW |
| **Reliability** | HIGH (after RE) | MEDIUM (rac.exe dependency) |
| **Maintenance** | Low (pure gRPC) | High (subprocess management) |

**Recommendation:** ⭐⭐⭐⭐⭐ Reverse Engineering

---

## ⚠️ Risks

### Risk 1: Протокол слишком сложный

**Вероятность:** MEDIUM | **Impact:** HIGH

**Индикаторы:**
- После 3 дней Wireshark analysis нет прогресса
- Custom binary encoding (не protobuf)

**Mitigation:**
- ✅ Timeboxing: 5 дней max для Phases 1+2
- ✅ Fallback ready: RAC CLI wrapper (2 дня implementation)
- ✅ Parallel track: start proxy sniffer на Day 3 если не понятно

**Worst-case:** Switch на RAC CLI после 7 дней

---

### Risk 2: Protocol версии меняются

**Вероятность:** HIGH | **Impact:** MEDIUM

**Mitigation:**
- ✅ Version detection УЖЕ ЕСТЬ в client.go (`DetectSupportedVersion`)
- ✅ Testing matrix: 2-3 версии 1С
- ✅ Graceful degradation: fallback на RAC если version не поддерживается

---

## 🎓 Требования к команде

**Skills needed:**
- **Phase 1:** Network analysis (Wireshark), hex dump reading - BASIC
- **Phase 2:** Go programming, TCP networking - INTERMEDIATE
- **Phase 3:** gRPC, protobuf, Go - INTERMEDIATE

**Team size:** 1 Senior Developer (можно 2 для ускорения)

**Time commitment:** Full-time 2 недели

---

## 📋 Success Criteria

### Must Have (для production)
- ✅ TerminateSession работает через gRPC
- ✅ Integration test passes на real RAS server
- ✅ Latency < 100ms (single operation)
- ✅ Batch termination: 100 sessions < 5 seconds
- ✅ Unit test coverage > 70%

### Nice to Have
- ✅ Proxy sniffer tool (для future debugging)
- ✅ Protocol specification document
- ✅ Support для multiple RAS versions

### Blockers (когда fallback на RAC CLI)
- ❌ Не можем decode протокол через 7 дней
- ❌ Protocol слишком custom (не protobuf)
- ❌ Требует binary reverse engineering (IDA Pro)

---

## 🚀 Next Steps

### Week 1: Immediate Actions

**Day 1-2:**
1. Setup Wireshark на dev machine
2. Capture TerminateSession operation
3. Analyze hex dump
4. Document findings в `RAS_PROTOCOL_ANALYSIS.md`

**Day 3:**
- **Decision point:** Можем ли реализовать?
  - ✅ YES → skip Phase 2, go to Phase 3
  - ❌ NO → start Phase 2 (proxy sniffer)

**Day 4-5:**
- Если Phase 2: Implement proxy sniffer
- Если Phase 3: Start protobuf schema

### Week 2: Implementation

**Day 6-10:**
- Complete Phase 3 (implementation + testing)
- Documentation update
- Integration testing

**Day 11-14 (buffer):**
- Edge cases
- Performance tuning
- Code review

---

## 💡 Key Insights из анализа кода

### UpdateInfobase УЖЕ работает - используем как template!

**Pattern который работает:**
```go
// 1. Get endpoint
endpoint, _ := s.client.GetEndpoint(ctx)

// 2. Build message (используя v8platform/protos)
msg := &serializev1.InfobaseInfo{
    ClusterId: req.ClusterId,
    Uuid:      req.InfobaseId,
    // Поля для update
}

// 3. Pack в Any
anyRequest, _ := anypb.New(msg)
anyRespond, _ := anypb.New(&serializev1.InfobaseInfo{})

// 4. Request через RAS Binary Protocol
response, _ := endpoint.Request(ctx, &clientv1.EndpointRequest{
    Request: anyRequest,
    Respond: anyRespond,
})

// 5. Unpack response
var result serializev1.InfobaseInfo
anypb.UnmarshalTo(response, &result, proto.UnmarshalOptions{})
```

**Для TerminateSession нужно ТОЛЬКО:**
- ❓ Какой message type использовать? (`SessionInfo`?)
- ❓ Какие поля установить в message?
- ❓ Как RAS понимает что это TERMINATE а не GET?

**Эти вопросы решает Wireshark analysis!**

---

## 📚 Ресурсы

**Документация:**
- [RAS_PROTOCOL_REVERSE_ENGINEERING_PLAN.md](./RAS_PROTOCOL_REVERSE_ENGINEERING_PLAN.md) - Детальный план (90KB)
- [../ROADMAP.md](../ROADMAP.md) - Balanced Approach roadmap
- ras-grpc-gw/FORK_CHANGELOG.md - История изменений форка

**Код для reference:**
- `pkg/server/infobase_management_service.go:246-391` - UpdateInfobase implementation
- `pkg/client/client.go:92-175` - RAS client endpoint management
- `pkg/server/ras_client.go` - RASClient interface

**External:**
- v8platform/ras-grpc-gw (upstream)
- v8platform/protos (protobuf schemas)

---

## 🎯 Conclusion

**Recommendation:** ✅ **APPROVE - Start Reverse Engineering**

**Обоснование:**
1. UpdateInfobase УЖЕ работает → доказывает feasibility
2. Существующий код как reference → снижает риски
3. Timeline реалистичный: 2 недели с buffer
4. Fallback plan готов: RAC CLI (если провалится)
5. Соответствует архитектурным принципам проекта

**Key Success Factor:**
> "Мы НЕ изобретаем колесо - мы ПОВТОРЯЕМ pattern который УЖЕ работает для UpdateInfobase!"

**Expected Outcome:**
- ✅ TerminateSession в production через 2 недели
- ✅ Clean gRPC solution без subprocess костылей
- ✅ Scales to 700 databases
- ✅ Unblocks Phase 3 development

---

**Prepared by:** AI Architect
**Date:** 2025-11-12
**Status:** Ready for review
**Approver:** Project Lead
