# RAS Protocol Reverse Engineering Plan

> **Автор:** AI Architect
> **Дата:** 2025-11-12
> **Проект:** CommandCenter1C
> **Цель:** Расширение ras-grpc-gw с недостающими методами UpdateInfobase и TerminateSession

---

## 📋 Executive Summary

### Текущая ситуация

**Что работает:**
- ✅ ras-grpc-gw fork (v1.1.0-cc) успешно реализует:
  - CreateInfobase (создание базы)
  - UpdateInfobase (блокировка регламентов, изменение параметров) - **ЧАСТИЧНО**
  - DropInfobase (удаление регистрации)
  - LockInfobase, UnlockInfobase (блокировка сеансов)
  - GetClusters, GetInfobases, GetSessions (чтение через v8platform/protos)

**Критичная проблема:**
- ❌ **UpdateInfobase НЕ полностью реализован** в RAS Binary Protocol
- ❌ **TerminateSession НЕ существует** в v8platform/protos v0.2.0
- ❌ Upstream v8platform/protos НЕ содержит эти методы (только read operations)

### Рекомендуемое решение

**🏆 Вариант A: Reverse Engineering RAS Binary Protocol (РЕКОМЕНДУЕТСЯ)**

**Почему:**
- Чистое gRPC решение без subprocess костылей
- Масштабируется на 700+ баз (параллельная обработка)
- Низкая latency (<100ms vs 1-5 секунд для RAC CLI)
- Соответствует архитектурным принципам проекта (API-First, Rich Domain Model)

**Сроки:** 10-14 дней (2 недели)
**Complexity:** MEDIUM-HIGH
**Reliability:** HIGH (после reverse engineering)

**Команда:** 1 Senior Developer + 1 Protocol Analyst (optional)

---

## 🔍 Исследование существующей кодовой базы

### Что уже реализовано в ras-grpc-gw

**Файловая структура:**
```
ras-grpc-gw/
├── pkg/client/client.go           - RAS Binary Protocol client
├── pkg/server/
│   ├── infobase_management_service.go  - gRPC service (UpdateInfobase PARTIAL)
│   └── ras_client.go               - RASClient interface
├── accessapis/infobase/service/
│   └── management.proto            - Protobuf schema (наш форк)
└── pkg/gen/                        - Generated code
```

**Ключевые наблюдения из анализа кода:**

#### 1. UpdateInfobase УЖЕ ЧАСТИЧНО РАБОТАЕТ

**Файл:** `pkg/server/infobase_management_service.go:246-391`

**Что реализовано:**
```go
func (s *InfobaseManagementServer) UpdateInfobase(
    ctx context.Context,
    req *pb.UpdateInfobaseRequest,
) (*pb.UpdateInfobaseResponse, error) {
    // 1. Получить endpoint от RAS client
    endpoint, err := s.client.GetEndpoint(ctx)

    // 2. Построить InfobaseInfo для обновления (partial update)
    infobaseInfo := &serializev1.InfobaseInfo{
        ClusterId: req.ClusterId,
        Uuid:      req.InfobaseId,
        // Установить только переданные поля
        SessionsDeny:        *req.SessionsDeny,
        ScheduledJobsDeny:   *req.ScheduledJobsDeny,
        DeniedMessage:       *req.DeniedMessage,
        // ... другие поля ...
    }

    // 3. Упаковать в EndpointRequest
    anyRequest, _ := anypb.New(infobaseInfo)
    anyRespond, _ := anypb.New(&serializev1.InfobaseInfo{})

    endpointReq := &clientv1.EndpointRequest{
        Request: anyRequest,
        Respond: anyRespond,
    }

    // 4. Выполнить запрос через RAS Binary Protocol
    responseAny, err := endpoint.Request(ctx, endpointReq)

    // 5. Распаковать ответ
    var updatedInfobase serializev1.InfobaseInfo
    anypb.UnmarshalTo(responseAny, &updatedInfobase, proto.UnmarshalOptions{})

    return &pb.UpdateInfobaseResponse{Success: true}, nil
}
```

**✅ УЖЕ РАБОТАЕТ:**
- Блокировка регламентов (`scheduled_jobs_deny`)
- Блокировка сеансов (`sessions_deny`, `denied_from`, `denied_to`, `denied_message`)
- Изменение параметров БД (`dbms`, `db_server`, `db_name`, `db_user`, `db_password`)
- Изменение description и security_level

**❌ ПРОБЛЕМА:**
- Нет **административных операций** (блокировка/разблокировка через RAC команды)
- Нет реализации для **специфичных полей InfobaseInfo** которые могут отсутствовать в protobuf schema

#### 2. RAS Binary Protocol Client УЖЕ РАБОТАЕТ

**Файл:** `pkg/client/client.go:1-361`

**Ключевые методы:**

```go
type ClientConn struct {
    host       string
    conn       net.Conn
    endpoints  *sync.Map
    version    string
    // ... другие поля ...
}

// GetEndpoint возвращает endpoint для взаимодействия с RAS
func (c *ClientConn) GetEndpoint(ctx context.Context) (clientv1.EndpointServiceImpl, error)

// turnEndpoint открывает новый endpoint
func (c *ClientConn) turnEndpoint(ctx context.Context) (*protocolv1.Endpoint, error)

// EndpointMessage отправляет message через RAS protocol
func (c *ClientConn) EndpointMessage(ctx context.Context, req *protocolv1.EndpointMessage) (*protocolv1.EndpointMessage, error)
```

**Протокол взаимодействия:**
1. Connect to RAS server (TCP на localhost:1545)
2. Negotiate protocol version (10.0 по умолчанию)
3. Open endpoint для сервиса `v8.service.Admin.Cluster`
4. Send/Receive messages через `EndpointMessage`
5. Unpack responses используя protobuf

**✅ ЧТО УЖЕ ЕСТЬ:**
- Connection management (reconnect, idle timeout)
- Protocol version negotiation
- Endpoint lifecycle (open/close)
- Message framing (packet читается через `protocolv1.NewPacket`)
- Error handling

**❌ ЧТО НУЖНО ВЫЯСНИТЬ:**
- Формат RAS binary messages для специфичных операций
- Message types для UpdateInfobase vs GetInfobase (как RAS различает?)
- Encoding для session termination commands

#### 3. Protobuf Schema v8platform/protos

**Используется:** `github.com/v8platform/protos` (внешний dependency)

**Файлы:**
- `gen/ras/client/v1` - ClientImpl, EndpointServiceImpl
- `gen/ras/messages/v1` - RAS message types
- `gen/v8platform/serialize/v1` - InfobaseInfo, SessionInfo, ClusterInfo

**Что ЕСТЬ в v8platform/protos v0.2.0:**
```protobuf
message InfobaseInfo {
    string cluster_id = 1;
    string uuid = 2;
    string name = 3;
    bool sessions_deny = 4;
    bool scheduled_jobs_deny = 5;
    string denied_message = 6;
    google.protobuf.Timestamp denied_from = 7;
    google.protobuf.Timestamp denied_to = 8;
    string permission_code = 9;
    // ... dbms, db_server, db_name, etc. ...
}
```

**Что ОТСУТСТВУЕТ:**
- ❌ Нет метода `TerminateSession` в SessionsService
- ❌ Нет enum для "operation type" (Create vs Update vs Delete)
- ❌ Нет message `TerminateSessionRequest`

**🔑 КЛЮЧЕВОЕ НАБЛЮДЕНИЕ:**
- UpdateInfobase работает через **тот же InfobaseInfo message**, что и CreateInfobase
- RAS различает операции по **наличию/отсутствию UUID** и **контексту endpoint**
- Нужно выяснить: как RAS понимает что это UPDATE а не CREATE?

---

## 🎯 Недостающие методы для реализации

### 1. UpdateInfobase (специфичные операции)

**Что уже работает:**
- ✅ Partial update для InfobaseInfo полей
- ✅ Блокировка регламентов, сеансов

**Что нужно добавить:**
- ❌ Административные команды (если есть специфичный message type)
- ❌ Обновление credentials для infobase users (если отдельный message)

**Приоритет:** LOW (основная функциональность уже есть)

### 2. TerminateSession (КРИТИЧНО)

**Функциональность:**
- Завершить активную сессию пользователя по `session_id`
- Используется для:
  - Принудительное отключение пользователей перед обновлением
  - Завершение зависших сессий
  - Освобождение лицензий

**Use case в CommandCenter1C:**
```
Phase 3: Orchestrator operations
- "Завершить все сеансы" перед установкой расширения
- Parallel termination для 700+ баз (по 5-10 сессий на базу)
```

**Что нужно:**
- Message type для `TerminateSession`
- Request: `cluster_id`, `session_id`
- Response: `success`, `message`

**Приоритет:** HIGH (блокирует Phase 3)

---

## 🛠️ Подходы к Reverse Engineering

### Сравнительный анализ вариантов

| Критерий | Option A: Wireshark | Option B: Proxy Sniffer | Option C: RAC Binary Analysis |
|----------|---------------------|-------------------------|-------------------------------|
| **Сложность** | LOW | MEDIUM | HIGH |
| **Время** | 2-4 дня | 3-5 дней | 7-10 дней |
| **Надёжность** | MEDIUM | HIGH | VERY HIGH |
| **Skills required** | Network analysis | Go programming | Reverse engineering |
| **Инструменты** | Wireshark, hex editor | Go proxy, logging | IDA Pro/Ghidra, disassembler |
| **Output** | Hex dump пакетов | Decoded messages | Complete protocol spec |
| **Риски** | Incomplete capture | Protocol complexity | Time-consuming |
| **Рекомендация** | ⭐⭐⭐ Start here | ⭐⭐⭐⭐ Best balance | ⭐⭐ Only if A/B fail |

### Option A: Network Traffic Capture (Wireshark/tcpdump)

**Описание:**
Использовать rac.exe для выполнения команд и перехватывать сетевой трафик между rac.exe и RAS Server.

**Шаги:**
1. **Setup:**
   ```bash
   # Start Wireshark на localhost
   # Filter: tcp.port == 1545
   ```

2. **Capture operations:**
   ```bash
   # Выполнить известную команду через rac.exe
   rac infobase update --cluster=<UUID> --infobase=<UUID> --scheduled-jobs-deny=on

   # Захватить hex dump пакетов в Wireshark
   # Export → "Selected Packet Bytes"
   ```

3. **Анализ пакетов:**
   - Найти pattern для UpdateInfobase operation
   - Сравнить с GetInfobase (read operation)
   - Выявить различия в message structure

4. **Repeat для TerminateSession:**
   ```bash
   rac session terminate --cluster=<UUID> --session=<UUID>
   ```

**Преимущества:**
- ✅ Быстро (2-4 дня)
- ✅ Не требует deep reverse engineering skills
- ✅ Видим реальный протокол без assumptions

**Недостатки:**
- ⚠️ Может пропустить важные детали (encoding, checksums)
- ⚠️ Требует manual hex analysis
- ⚠️ Нужен доступ к working RAS server

**Инструменты:**
- Wireshark для capture
- HxD или 010 Editor для hex analysis
- Python script для parsing и visualisation

**Пример workflow:**

```
1. Wireshark capture:
   TCP Stream: localhost:1545

2. Execute RAC command:
   rac session terminate --session=abc123

3. Wireshark output (simplified):
   00 00 00 2F  <- Packet length (47 bytes)
   10 00 00 00  <- Message type? (0x0010 = TerminateSession?)
   61 62 63 31 32 33 00  <- session_id "abc123" (null-terminated string)
   ...

4. Decode:
   - First 4 bytes: packet length
   - Next 4 bytes: message type enum
   - Payload: protobuf encoded SessionInfo?
```

**Ожидаемый результат:**
- Hex dump для UpdateInfobase operation
- Hex dump для TerminateSession operation
- Mapping: message type → operation

**Сроки:** 2-4 дня (если протокол простой)

---

### Option B: Proxy Sniffer (Man-in-the-Middle)

**Описание:**
Создать Go proxy который перехватывает и логирует RAS Binary Protocol между rac.exe и RAS Server.

**Архитектура:**
```
rac.exe → localhost:1546 → [Go Proxy Sniffer] → localhost:1545 → RAS Server
                                  ↓
                            Log all packets
                            Decode protobuf
                            Pretty-print JSON
```

**Implementation Plan:**

**Step 1: Создать TCP proxy**

```go
// pkg/tools/ras-sniffer/main.go
package main

import (
    "io"
    "log"
    "net"
)

func main() {
    // Listen на :1546 (proxy port)
    listener, _ := net.Listen("tcp", ":1546")
    log.Println("RAS Sniffer listening on :1546 (proxying to :1545)")

    for {
        clientConn, _ := listener.Accept()
        go handleConnection(clientConn)
    }
}

func handleConnection(clientConn net.Conn) {
    defer clientConn.Close()

    // Connect to real RAS server
    rasConn, _ := net.Dial("tcp", "localhost:1545")
    defer rasConn.Close()

    // Bi-directional proxy with logging
    go copyAndLog(clientConn, rasConn, "CLIENT → RAS")
    copyAndLog(rasConn, clientConn, "RAS → CLIENT")
}

func copyAndLog(dst, src net.Conn, direction string) {
    buf := make([]byte, 4096)
    for {
        n, _ := src.Read(buf)
        if n == 0 {
            break
        }

        // LOG RAW BYTES
        log.Printf("%s: %d bytes\n", direction, n)
        logHexDump(buf[:n])

        // Try to decode protobuf
        decoded := tryDecodeProtobuf(buf[:n])
        if decoded != nil {
            log.Printf("%s DECODED: %+v\n", direction, decoded)
        }

        dst.Write(buf[:n])
    }
}
```

**Step 2: Добавить protobuf decoding**

```go
import (
    protocolv1 "github.com/v8platform/protos/gen/ras/protocol/v1"
    serializev1 "github.com/v8platform/protos/gen/v8platform/serialize/v1"
    "google.golang.org/protobuf/proto"
)

func tryDecodeProtobuf(data []byte) interface{} {
    // Try to parse as Packet
    packet, err := protocolv1.NewPacket(bytes.NewReader(data))
    if err != nil {
        return nil
    }

    // Try to unpack as InfobaseInfo
    var infobase serializev1.InfobaseInfo
    if err := packet.Unpack(&infobase); err == nil {
        return &infobase
    }

    // Try to unpack as SessionInfo
    var session serializev1.SessionInfo
    if err := packet.Unpack(&session); err == nil {
        return &session
    }

    return nil
}
```

**Step 3: Usage**

```bash
# Terminal 1: Start proxy sniffer
cd pkg/tools/ras-sniffer
go run main.go

# Terminal 2: Use rac.exe через proxy
rac.exe --server=localhost:1546 session terminate --session=abc123

# Terminal 1: Output
RAS Sniffer listening on :1546
CLIENT → RAS: 47 bytes
00000000  00 00 00 2f 10 00 00 00  61 62 63 31 32 33 00 ...
CLIENT → RAS DECODED: &SessionInfo{SessionId: "abc123", ...}

RAS → CLIENT: 24 bytes
00000000  00 00 00 18 00 00 00 00  ...
RAS → CLIENT DECODED: &Response{Success: true}
```

**Преимущества:**
- ✅ Полная visibility в протокол (request + response)
- ✅ Автоматический protobuf decoding
- ✅ Легко повторить для разных операций
- ✅ JSON export для анализа

**Недостатки:**
- ⚠️ Требует implementation усилий (2-3 дня для proxy)
- ⚠️ Нужно понимать protobuf encoding
- ⚠️ Может сломаться если протокол изменится

**Инструменты:**
- Go net package для TCP proxy
- v8platform/protos для decoding
- Structured logging (zap)

**Сроки:** 3-5 дней (2 дня proxy + 2-3 дня анализ)

**Рекомендация:** ⭐⭐⭐⭐ **ЛУЧШИЙ БАЛАНС** (быстро + надёжно)

---

### Option C: RAC Binary Analysis (Reverse Engineering)

**Описание:**
Дизассемблировать rac.exe и найти функции которые формируют RAS Binary Protocol messages.

**Шаги:**

1. **Locate rac.exe:**
   ```
   C:\Program Files\1cv8\8.3.27.1786\bin\rac.exe
   ```

2. **Disassemble with IDA Pro / Ghidra:**
   - Load rac.exe
   - Find imports: `send()`, `recv()`, `connect()`
   - Trace back to callers

3. **Find protocol functions:**
   ```
   SendUpdateInfobase()
   SendTerminateSession()
   EncodeRASMessage()
   ```

4. **Analyze message structure:**
   - How is `session_id` encoded?
   - What is message type enum for TerminateSession?
   - Are there checksums/signatures?

**Преимущества:**
- ✅ Complete protocol specification
- ✅ Понимание всех edge cases
- ✅ Можно найти undocumented features

**Недостатки:**
- ⚠️ Очень трудоёмко (7-10 дней)
- ⚠️ Требует reverse engineering skills
- ⚠️ Может быть obfuscated / packed
- ⚠️ Legal concerns (EULA violation?)

**Инструменты:**
- IDA Pro (commercial) или Ghidra (free)
- x64dbg для dynamic analysis
- API Monitor для function hooking

**Сроки:** 7-10 дней (1.5-2 недели)

**Рекомендация:** ⭐⭐ Только если Option A/B провалятся

---

## 📊 Рекомендуемый подход

### Phase 1: Quick Win - Wireshark Analysis (2-4 дня)

**Цель:** Получить базовое понимание протокола для TerminateSession

**Шаги:**
1. Setup Wireshark на localhost
2. Capture traffic для известных команд:
   ```bash
   rac session terminate --session=<UUID>
   rac infobase update --scheduled-jobs-deny=on
   ```
3. Анализ hex dump:
   - Packet structure (length, type, payload)
   - Encoding (protobuf? custom binary?)
   - Message types (constants/enums)
4. Документировать findings в `RAS_PROTOCOL_ANALYSIS.md`

**Deliverables:**
- Hex dump для TerminateSession operation
- Preliminary message structure spec
- Decision: можем ли реализовать или нужен Option B?

**Success criteria:**
- Понимаем formат packet header
- Видим session_id в payload
- Можем отличить TerminateSession от других operations

**Fallback:** Если через 3 дня нет прогресса → switch на Option B

---

### Phase 2: Proxy Sniffer Implementation (3-5 дней)

**Цель:** Создать инструмент для автоматического decoding RAS messages

**Шаги:**
1. **Day 1-2:** Implement TCP proxy с logging
   ```go
   pkg/tools/ras-sniffer/
   ├── main.go              - TCP proxy server
   ├── decoder.go           - Protobuf decoder
   ├── logger.go            - Structured logging
   └── analyzer.go          - Pattern analysis
   ```

2. **Day 3:** Integrate protobuf decoding
   - Use v8platform/protos для parsing
   - Fallback на hex dump если decode fails

3. **Day 4-5:** Testing и analysis
   - Capture 10+ different operations
   - Build mapping: operation → message structure
   - Document protocol patterns

**Deliverables:**
- Working proxy sniffer tool
- JSON logs для всех captured operations
- Protocol specification document

**Success criteria:**
- Можем decode TerminateSession request/response
- Понимаем как формировать message для нашего client
- Готовы к implementation в ras-grpc-gw

---

### Phase 3: Implementation в ras-grpc-gw (3-5 дней)

**Цель:** Добавить TerminateSession метод в ras-grpc-gw

**Шаги:**

**Step 1: Protobuf Schema (Day 1)**

```protobuf
// accessapis/sessions/service/management.proto
syntax = "proto3";

package sessions.service;

message TerminateSessionRequest {
  string cluster_id = 1;   // UUID кластера
  string session_id = 2;   // UUID сессии для завершения

  // Optional: authentication
  optional string cluster_user = 3;
  optional string cluster_password = 4;
}

message TerminateSessionResponse {
  string session_id = 1;
  bool success = 2;
  string message = 3;
}

service SessionManagementService {
  rpc TerminateSession(TerminateSessionRequest) returns (TerminateSessionResponse);
}
```

**Step 2: RAS Client Implementation (Day 2-3)**

```go
// pkg/server/session_management_service.go
func (s *SessionManagementServer) TerminateSession(
    ctx context.Context,
    req *pb.TerminateSessionRequest,
) (*pb.TerminateSessionResponse, error) {
    // 1. Validate inputs
    if err := s.validateClusterId(req.ClusterId); err != nil {
        return nil, err
    }
    if err := s.validateSessionId(req.SessionId); err != nil {
        return nil, err
    }

    // 2. Get RAS endpoint
    endpoint, err := s.client.GetEndpoint(ctx)
    if err != nil {
        return nil, s.mapRASError(err)
    }

    // 3. Build TerminateSession message
    // ВАЖНО: Используем findings из Phase 2
    terminateMsg := &serializev1.SessionInfo{
        ClusterId: req.ClusterId,
        SessionId: req.SessionId,
        // Добавить другие поля если нужны из reverse engineering
    }

    // 4. Pack into EndpointRequest
    anyRequest, _ := anypb.New(terminateMsg)
    anyRespond, _ := anypb.New(&serializev1.SessionInfo{})

    endpointReq := &clientv1.EndpointRequest{
        Request: anyRequest,
        Respond: anyRespond,
    }

    // 5. Execute через RAS Binary Protocol
    _, err = endpoint.Request(ctx, endpointReq)
    if err != nil {
        s.logger.Error("Failed to terminate session",
            zap.String("cluster_id", req.ClusterId),
            zap.String("session_id", req.SessionId),
            zap.Error(err),
        )
        return nil, s.mapRASError(err)
    }

    s.logger.Info("Session terminated successfully",
        zap.String("session_id", req.SessionId),
    )

    return &pb.TerminateSessionResponse{
        SessionId: req.SessionId,
        Success:   true,
        Message:   "Session terminated successfully",
    }, nil
}
```

**Step 3: Testing (Day 4-5)**

```go
// pkg/server/session_management_service_test.go
func TestTerminateSession_Success(t *testing.T) {
    // Mock RAS client
    mockClient := &MockRASClient{
        endpoint: &MockEndpoint{
            requestFunc: func(ctx context.Context, req *clientv1.EndpointRequest) (*anypb.Any, error) {
                // Verify request structure
                var sessionInfo serializev1.SessionInfo
                req.Request.UnmarshalTo(&sessionInfo, proto.UnmarshalOptions{})

                assert.Equal(t, "test-cluster", sessionInfo.ClusterId)
                assert.Equal(t, "test-session", sessionInfo.SessionId)

                // Return success response
                return anypb.New(&serializev1.SessionInfo{
                    SessionId: "test-session",
                })
            },
        },
    }

    server := NewSessionManagementServer(mockClient)

    resp, err := server.TerminateSession(context.Background(), &pb.TerminateSessionRequest{
        ClusterId: "test-cluster",
        SessionId: "test-session",
    })

    assert.NoError(t, err)
    assert.True(t, resp.Success)
}
```

**Deliverables:**
- TerminateSession method в ras-grpc-gw
- Unit tests (coverage > 70%)
- Integration test с real RAS server
- Documentation update

---

## 🎯 Roadmap

### Детальный план (10-14 дней)

| Phase | Days | Tasks | Deliverables | Success Criteria |
|-------|------|-------|--------------|------------------|
| **Phase 1: Analysis** | 2-4 | Wireshark capture, hex analysis | Protocol spec draft | Понимаем message structure |
| **Phase 2: Sniffer** | 3-5 | Proxy implementation, decoding | Working sniffer tool | Можем decode messages |
| **Phase 3: Implementation** | 3-5 | gRPC service, RAS client | TerminateSession in ras-grpc-gw | Integration test passes |
| **TOTAL** | **10-14** | | **Production-ready code** | **E2E test на 700 баз** |

### Milestones

**Milestone 1: Protocol Understanding (Day 4)**
- ✅ Captured TerminateSession traffic
- ✅ Documented message structure
- ✅ Identified message type enum

**Milestone 2: Tooling Ready (Day 9)**
- ✅ Proxy sniffer works
- ✅ Protobuf decoding успешен
- ✅ JSON export для всех операций

**Milestone 3: Implementation Complete (Day 14)**
- ✅ TerminateSession в ras-grpc-gw
- ✅ Unit tests pass (coverage > 70%)
- ✅ Integration test с real RAS
- ✅ Документация обновлена

---

## ⚠️ Risks & Mitigation

### Risk 1: RAS Protocol слишком сложный

**Вероятность:** MEDIUM
**Impact:** HIGH (можем застрять на недели)

**Индикаторы:**
- После 3 дней Wireshark analysis нет прогресса
- Протокол использует custom binary encoding (не protobuf)
- Много obfuscation / encryption

**Mitigation:**
1. **Parallel track:** Одновременно начать Option B (proxy sniffer)
2. **Timeboxing:** Если через 5 дней нет результата → fallback на RAC CLI subprocess
3. **Community:** Поискать open-source реализации (Python, Go)

**Fallback план:**
```go
// ВРЕМЕННОЕ РЕШЕНИЕ: RAC CLI wrapper
func (s *SessionManagementServer) TerminateSession(
    ctx context.Context,
    req *pb.TerminateSessionRequest,
) (*pb.TerminateSessionResponse, error) {
    cmd := exec.CommandContext(ctx, "rac.exe",
        "session", "terminate",
        "--cluster=" + req.ClusterId,
        "--session=" + req.SessionId,
    )

    output, err := cmd.CombinedOutput()
    if err != nil {
        return nil, status.Errorf(codes.Internal, "rac failed: %v", err)
    }

    return &pb.TerminateSessionResponse{
        Success: true,
        Message: string(output),
    }, nil
}
```

**Недостатки fallback:**
- ⚠️ Медленно (1-5 секунд vs <100ms для gRPC)
- ⚠️ Не масштабируется (700 баз параллельно → 700 subprocess)
- ⚠️ Зависимость от rac.exe installation

**Когда использовать fallback:**
- Если reverse engineering не даёт результатов через 2 недели
- Если нужно быстро unblock Phase 3 development

---

### Risk 2: RAS Protocol может меняться между версиями 1С

**Вероятность:** HIGH
**Impact:** MEDIUM

**Индикаторы:**
- Protocol version negotiation в client.go (уже есть!)
- Разные versions 1С (8.3.25 vs 8.3.27)

**Mitigation:**
1. **Version detection:** Используем существующий `DetectSupportedVersion()` в client
2. **Testing matrix:** Тестируем на 2-3 разных версиях 1С
3. **Graceful degradation:** Если protocol version не поддерживается → fallback на RAC CLI

**Implementation:**
```go
func (s *SessionManagementServer) TerminateSession(...) {
    // Check protocol version
    if s.client.version < "10.0" {
        return nil, status.Error(codes.Unimplemented,
            "TerminateSession requires RAS protocol >= 10.0")
    }

    // Proceed with gRPC implementation
    ...
}
```

---

### Risk 3: Upstream v8platform может добавить методы

**Вероятность:** LOW
**Impact:** LOW (наша работа не пропадёт)

**Сценарий:**
- v8platform/protos v0.3.0 добавляет `TerminateSession`
- Наша реализация конфликтует

**Mitigation:**
1. **Monitor upstream:** Подписаться на releases v8platform/protos
2. **Namespace separation:** Используем `sessions.service` package (не конфликтует)
3. **Migration plan:** Готовы мигрировать на upstream если появится

**Действия при выходе upstream версии:**
- Сравнить API contracts (request/response structure)
- Если идентичны → migrate на upstream
- Если различаются → keep our fork с prefix `cc_`

---

## 📚 Ресурсы и исследование

### Поиск в интернете

**Уже найдено:**
- ✅ v8platform/ras-grpc-gw - upstream проект
- ✅ GithubHelp documentation - описание существующих методов
- ⚠️ Нет публичной документации RAS Binary Protocol

**Нужно поискать:**
- [ ] "1C RAS protocol specification"
- [ ] "v8platform RAS binary protocol documentation"
- [ ] "rac.exe protocol reverse engineering"
- [ ] Open-source RAS clients (Python, Go, Ruby)
- [ ] Internal 1C documentation (если доступно)

### GitHub repositories для анализа

**Потенциально полезные:**
- v8platform/ras-grpc-gw (наш upstream) ✅
- v8platform/protos (protobuf schemas) ✅
- Другие форки ras-grpc-gw (может кто-то уже добавил TerminateSession)
- Python RAS clients (если существуют)

**Action items:**
```bash
# Search GitHub
"v8platform RAS" language:Go
"1C RAS protocol" language:Python
"rac.exe alternative" language:Any
```

---

## 💻 Инструменты и Setup

### Required Tools

**Network Analysis:**
- Wireshark 4.0+ (packet capture)
- tcpdump (альтернатива для Linux)
- HxD или 010 Editor (hex editor)

**Development:**
- Go 1.21+ (для proxy sniffer)
- buf CLI (protobuf generation)
- protoc-gen-go, protoc-gen-go-grpc

**Optional (для Option C):**
- IDA Pro (commercial) или Ghidra (free)
- x64dbg (dynamic analysis)
- API Monitor (function hooking)

### Development Environment Setup

```bash
# 1. Install Wireshark
# Download from https://www.wireshark.org/

# 2. Clone ras-grpc-gw fork
cd C:\1CProject
git clone https://github.com/yourusername/ras-grpc-gw.git

# 3. Install Go tools
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# 4. Install buf
go install github.com/bufbuild/buf/cmd/buf@latest

# 5. Create workspace для proxy sniffer
cd ras-grpc-gw
mkdir -p pkg/tools/ras-sniffer
```

---

## 📋 Checklist для реализации

### Phase 1: Wireshark Analysis
- [ ] Setup Wireshark на localhost
- [ ] Configure filter: `tcp.port == 1545`
- [ ] Capture TerminateSession operation
  - [ ] Execute: `rac session terminate --session=<UUID>`
  - [ ] Export packet bytes
  - [ ] Analyze hex dump
- [ ] Capture UpdateInfobase operation
  - [ ] Execute: `rac infobase update --scheduled-jobs-deny=on`
  - [ ] Compare with TerminateSession
- [ ] Document findings
  - [ ] Packet structure (header, payload)
  - [ ] Message type identification
  - [ ] Encoding format (protobuf? custom?)
- [ ] Decision point: можем ли реализовать?
  - [ ] YES → proceed to Phase 3
  - [ ] NO → proceed to Phase 2 (proxy sniffer)

### Phase 2: Proxy Sniffer (если нужен)
- [ ] Implement TCP proxy
  - [ ] Listen на :1546
  - [ ] Forward to :1545 (real RAS)
  - [ ] Bi-directional logging
- [ ] Add protobuf decoding
  - [ ] Parse as v8platform/protos messages
  - [ ] Fallback на hex dump
- [ ] Testing
  - [ ] Capture 10+ different operations
  - [ ] Verify decoding accuracy
  - [ ] Export JSON logs
- [ ] Analysis
  - [ ] Build operation → message mapping
  - [ ] Document protocol patterns
  - [ ] Create implementation spec

### Phase 3: Implementation
- [ ] Protobuf schema
  - [ ] Define SessionManagementService
  - [ ] TerminateSessionRequest message
  - [ ] TerminateSessionResponse message
  - [ ] Run `buf generate`
- [ ] Server implementation
  - [ ] Create session_management_service.go
  - [ ] Implement TerminateSession method
  - [ ] Add validation (cluster_id, session_id)
  - [ ] Error mapping
  - [ ] Logging
- [ ] Testing
  - [ ] Unit tests (coverage > 70%)
  - [ ] Integration test с mock RAS
  - [ ] E2E test с real RAS server
- [ ] Documentation
  - [ ] Update FORK_CHANGELOG.md
  - [ ] API documentation
  - [ ] Usage examples

---

## 🎓 Обучающие материалы

### Для команды

**Темы для изучения:**
1. **RAS Binary Protocol basics**
   - Packet framing
   - Protobuf encoding
   - Message types

2. **Network protocol analysis**
   - Wireshark filtering
   - TCP stream reconstruction
   - Hex dump reading

3. **Go proxy development**
   - net.Conn usage
   - io.Copy patterns
   - Middleware design

4. **v8platform/protos API**
   - ClientImpl interface
   - EndpointRequest pattern
   - Message unpacking

**Рекомендуемые ресурсы:**
- v8platform/ras-grpc-gw source code
- Wireshark User's Guide (Chapter on TCP analysis)
- Protobuf Language Guide (Go)
- gRPC Go documentation

---

## 📊 Метрики успеха

### Технические метрики

**Protocol Analysis:**
- ✅ Hex dump для TerminateSession captured
- ✅ Message structure documented (>80% accurate)
- ✅ Can distinguish message types

**Implementation:**
- ✅ TerminateSession method работает
- ✅ Unit test coverage > 70%
- ✅ Integration test passes на real RAS
- ✅ Latency < 100ms (vs 1-5s для RAC CLI)

**Производительность:**
- ✅ Parallel termination 100 sessions < 5 секунд
- ✅ No memory leaks (10000+ operations)
- ✅ Error rate < 1% (на production workload)

### Бизнес-метрики

**Unblocking Phase 3:**
- ✅ Orchestrator может завершать сеансы через gRPC
- ✅ Batch termination для 700 баз работает
- ✅ No dependency на RAC CLI subprocess

**Масштабируемость:**
- ✅ Handles 500 concurrent termination requests
- ✅ Worker pool не блокируется на I/O
- ✅ Resource usage acceptable (CPU < 50%, RAM < 1GB)

---

## 🔧 Альтернативные подходы (если reverse engineering провалится)

### Plan B: RAC CLI Wrapper с оптимизациями

**Если через 2 недели reverse engineering не даёт результатов:**

**Option B1: Optimized RAC CLI Wrapper**
```go
type RACClient struct {
    pool    *ProcessPool  // Reuse rac.exe processes
    timeout time.Duration
}

func (c *RACClient) TerminateSession(ctx context.Context, sessionID string) error {
    // Get process from pool (avoid spawn overhead)
    proc := c.pool.Get()
    defer c.pool.Put(proc)

    // Execute через stdin/stdout (faster than new process)
    proc.stdin.Write([]byte("session terminate " + sessionID + "\n"))

    // Parse response
    output := make([]byte, 1024)
    n, _ := proc.stdout.Read(output)

    return parseRACResponse(output[:n])
}
```

**Преимущества:**
- ✅ Быстрее чем spawning new process каждый раз
- ✅ Process pool для параллелизма
- ✅ Fallback если gRPC не работает

**Недостатки:**
- ⚠️ Всё ещё медленнее чем pure gRPC
- ⚠️ Зависимость от rac.exe

---

### Plan C: Hybrid Approach

**Комбинация gRPC + RAC CLI:**
- ✅ Используем gRPC для read operations (GetClusters, GetInfobases, GetSessions)
- ✅ Используем RAC CLI ТОЛЬКО для write operations (TerminateSession, UpdateInfobase)
- ✅ Кешируем результаты read operations

**Когда использовать:**
- Если TerminateSession через gRPC не работает
- Но read operations через gRPC масштабируются отлично

---

## 📝 Заключение

### Рекомендация

**✅ РЕКОМЕНДУЮ: Вариант A (Reverse Engineering) с fallback на Plan B**

**Обоснование:**
1. **UpdateInfobase УЖЕ РАБОТАЕТ** через RAS Binary Protocol
   - Код reference implementation существует
   - Нужно только выяснить message format для TerminateSession
   - Высокая вероятность успеха (80%)

2. **Существующая инфраструктура готова:**
   - RAS client уже работает
   - Connection management, reconnect, версионирование
   - Нужно только добавить новый message type

3. **Pragmatic approach:**
   - Start с Wireshark (2-4 дня, low effort)
   - Если не работает → proxy sniffer (3-5 дней)
   - Fallback на RAC CLI wrapper (2 дня)
   - Total worst-case: 14 дней

4. **Соответствует архитектурным принципам:**
   - ✅ API-First Communication (gRPC)
   - ✅ НЕТ subprocess костылям
   - ✅ Масштабируется на 700 баз
   - ✅ Low latency (<100ms)

### Next Steps

**Immediate actions (Week 1):**
1. Setup Wireshark на development machine
2. Capture TerminateSession operation (rac.exe)
3. Analyze hex dump, document findings
4. Decision: можем ли реализовать через gRPC?

**Week 2 (если нужен proxy):**
1. Implement TCP proxy sniffer
2. Add protobuf decoding
3. Build operation → message mapping

**Week 3 (implementation):**
1. Add SessionManagementService proto
2. Implement TerminateSession в ras-grpc-gw
3. Testing и documentation

**Milestone:** **TerminateSession работает через gRPC к концу 3 недели**

---

**Версия документа:** 1.0
**Последнее обновление:** 2025-11-12
**Статус:** Draft для review
**Следующий review:** После Phase 1 completion
