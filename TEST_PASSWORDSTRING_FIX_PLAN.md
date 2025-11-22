# PasswordString Fix - Comprehensive Test Plan and Report

## Дата: 2025-11-23
## Версия: 1.0

---

## 1. OVERVIEW

Этот документ описывает comprehensive test suite для проверки PasswordString fix, которая решает Unlock bug на базах 1С с пустым DB паролем.

**Критичность:** ВЫСОКАЯ
**Влияние:** 700+ баз в production зависят от успешной Lock/Unlock операции

---

## 2. ROOT CAUSE AND FIX

### 2.1 Проблема (Unlock Bug)
- Unlock операция падает с ошибкой PostgreSQL: "no password supplied"
- Lock работает через rac (передает U+FFFD для пустого пароля)
- SDK передает NULL (0x00) вместо U+FFFD для пустого пароля
- RAS при NULL пытается валидировать с PostgreSQL → ошибка

### 2.2 Решение (PasswordString Implementation)
- Добавлен метод `PasswordString()` в SDK encoder (`ras-adapter/ras-client/protocol/codec/encoder.go`)
- Используется для `DbPwd` в `InfobaseInfo.Encode()` (`infobase.go`)
- Убрана глобальная модификация `String()` метода
- Локально кодирует пустой пароль как U+FFFD (0xef 0xbf 0xbd)

---

## 3. TEST COVERAGE

### 3.1 Unit Tests (encoder_test.go)

**Файл:** `go-services/ras-adapter/ras-client/protocol/codec/encoder_test.go` (НОВЫЙ)

#### Тесты:

1. **TestPasswordString_Empty**
   - Проверяет что пустой пароль кодируется как U+FFFD (0xef 0xbf 0xbd)
   - Ожидаемый output: 4 байта (1 size + 3 replacement char)
   - Статус: PASS/FAIL

2. **TestPasswordString_NonEmpty**
   - Проверяет что непустой пароль кодируется обычно
   - НЕ должен содержать replacement char
   - Должен содержать оригинальный пароль
   - Статус: PASS/FAIL

3. **TestPasswordString_VsString**
   - Сравнивает PasswordString("") vs String("")
   - PasswordString → U+FFFD
   - String → NULL (0x00)
   - Результаты ДОЛЖНЫ отличаться!
   - Статус: PASS/FAIL

4. **TestPasswordString_UTF8Replacement**
   - Проверяет правильный UTF-8 replacement char (U+FFFD)
   - Byte sequence: 0xEF 0xBF 0xBD
   - Статус: PASS/FAIL

5. **TestPasswordString_RealPasswordVsEmpty**
   - Проверяет несколько реальных паролей vs пустой
   - Пустой содержит replacement char
   - Остальные НЕ содержат
   - Статус: PASS/FAIL

6. **TestPasswordString_NullableSize**
   - Проверяет что size кодируется правильно
   - NullableSize(3) = 0x03
   - Статус: PASS/FAIL

7. **TestPasswordString_LongPassword**
   - Проверяет работу с длинными паролями
   - НЕ должен иметь replacement char
   - Статус: PASS/FAIL

8. **TestPasswordString_SpecialCharacters**
   - Тестирует спецсимволы: @#$%, кириллица, иероглифы, emoji
   - Все должны работать без replacement char
   - Статус: PASS/FAIL

**Бенчмарки:**
- BenchmarkPasswordString_Empty
- BenchmarkPasswordString_NonEmpty
- BenchmarkString_Empty

---

### 3.2 Integration Tests (client_test.go - ОБНОВЛЕНЫ)

**Файл:** `go-services/ras-adapter/internal/ras/client_test.go` (РАСШИРЕНЫ)

#### Новые тесты для PasswordString:

1. **TestClient_UnlockInfobase_EmptyPassword** (CRITICAL)
   - Тестирует Unlock с пустым DB паролем
   - Проверяет что НЕ содержит ошибку "no password supplied"
   - Подтесты:
     - Unlock with empty password
     - Unlock with provided DB credentials
     - Unlock with only username (empty password)
   - Статус: PASS/FAIL

2. **TestClient_LockInfobase_EmptyPassword**
   - Тестирует Lock с пустым DB паролем
   - Должен работать без ошибок
   - Статус: PASS/FAIL

3. **TestClient_RegInfoBase_EmptyPassword** (CRITICAL)
   - Прямой тест RegInfoBase с empty DBPwd
   - Используется Lock/Unlock internally
   - Проверяет что PasswordString() используется для empty password
   - Подтесты:
     - RegInfoBase with empty password
     - RegInfoBase with non-empty password
   - Статус: PASS/FAIL

4. **TestClient_LockUnlock_Sequence_WithEmptyPassword** (CRITICAL E2E)
   - End-to-end: Lock → Unlock с пустым паролем
   - Проверяет оба направления
   - Тестирует multiple cycles (3 раза)
   - Статус: PASS/FAIL

5. **TestClient_UnlockInfobase_PasswordStringUsage** (VALIDATION)
   - Проверяет что PasswordString() implementation применена
   - Empty password → PasswordString()
   - Non-empty password → также работает
   - Статус: PASS/FAIL

**Updated тесты (с параметрами dbUser/dbPwd):**
- TestClient_LockInfobase (все вызовы добавлены "", "")
- TestClient_UnlockInfobase (все вызовы добавлены "", "")
- TestClient_LockUnlock_Sequence (все вызовы добавлены "", "")
- TestClient_LockUnlock_WithContext (все вызовы добавлены "", "")
- BenchmarkLockInfobase (добавлены "", "")
- BenchmarkUnlockInfobase (добавлены "", "")

---

### 3.3 REST API Tests (infobases_test.go)

**Файл:** `go-services/ras-adapter/internal/api/rest/infobases_test.go` (СУЩЕСТВУЕТ)

**Существующие тесты:**
- TestLockInfobase_Success
- TestLockInfobase_MissingClusterID
- TestLockInfobase_InvalidJSON
- TestLockInfobase_EmptyInfobaseID
- TestLockInfobase_MultipleCalls
- TestLockInfobase_ResponseStructure
- TestUnlockInfobase_Success
- TestUnlockInfobase_MissingClusterID
- TestUnlockInfobase_InvalidJSON
- TestUnlockInfobase_MultipleCalls
- TestUnlockInfobase_ResponseStructure
- TestLockUnlock_Sequence
- TestGetInfobases_Success
- TestGetInfobases_MissingClusterID
- TestContentType
- BenchmarkLockInfobase_REST
- BenchmarkUnlockInfobase_REST

---

### 3.4 Event Handler Tests (unlock_handler_test.go)

**Файл:** `go-services/ras-adapter/internal/eventhandlers/unlock_handler_test.go` (СУЩЕСТВУЕТ)

**Тесты:**
- TestNewUnlockHandler
- TestUnlockHandler_HandleUnlockCommand_Success
- TestUnlockHandler_HandleUnlockCommand_InvalidPayload
- TestUnlockHandler_HandleUnlockCommand_MissingClusterID
- TestUnlockHandler_HandleUnlockCommand_MissingInfobaseID
- TestUnlockHandler_HandleUnlockCommand_ServiceError
- TestUnlockHandler_HandleUnlockCommand_IdempotentRequest
- TestUnlockHandler_HandleUnlockCommand_ContextTimeout
- TestUnlockHandler_HandleUnlockCommand_PublishingError
- TestUnlockHandler_HandleUnlockCommand_RedisNotConfigured

---

## 4. TEST EXECUTION PLAN

### 4.1 Unit Tests (Local)

```bash
cd C:/1CProject/command-center-1c/go-services/ras-adapter/ras-client/protocol/codec

# Run encoder tests
go test -v -run TestPasswordString

# Run all encoder tests
go test -v

# Check coverage
go test -v -coverprofile=coverage.out
go tool cover -html=coverage.out
```

**Ожидаемое:** 8 тестов + 3 бенчмарка PASS

---

### 4.2 Integration Tests (Local)

```bash
cd C:/1CProject/command-center-1c/go-services/ras-adapter

# Run client tests (все lock/unlock тесты)
go test -v ./internal/ras -run TestClient

# Run unlock handler tests
go test -v ./internal/eventhandlers -run TestUnlockHandler

# Run specific PasswordString tests
go test -v ./... -run EmptyPassword

# Run full suite
go test -v ./...
```

**Ожидаемое:** 5+ новых тестов PASS, все updated тесты PASS

---

### 4.3 Real RAS Testing (Optional - если RAS доступен)

#### Тестовая база:
- UUID: ae1e5ea8-96e9-45cb-8363-8e4473daa269
- Name: test_lock_unlock
- Cluster: c3e50859-3d41-4383-b0d7-4ee20272b69d
- DB: PostgreSQL localhost/test_lock_unlock (postgres/postgres with empty pwd)

#### Сценарии:

```bash
# 1. Rebuild & restart
./scripts/build.sh --service=ras-adapter
./scripts/dev/restart.sh ras-adapter
sleep 2

# 2. Health check
curl -s http://localhost:8088/health | jq .

# 3. Lock
curl -s -X POST http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269/lock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "c3e50859-3d41-4383-b0d7-4ee20272b69d"}' | jq .

# 4. Verify locked
curl -s "http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269?cluster_id=c3e50859-3d41-4383-b0d7-4ee20272b69d" \
  | jq '.infobases[0].scheduled_jobs_deny'
# Expected: true

# 5. Unlock (CRITICAL TEST)
curl -s -X POST http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269/unlock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "c3e50859-3d41-4383-b0d7-4ee20272b69d"}' | jq .
# Expected: {"success":true, "message":"...unlocked successfully..."}

# 6. Verify unlocked
curl -s "http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269?cluster_id=c3e50859-3d41-4383-b0d7-4ee20272b69d" \
  | jq '.infobases[0].scheduled_jobs_deny'
# Expected: false

# 7. Regression tests
curl -s "http://localhost:8088/api/v1/infobases?cluster_id=c3e50859-3d41-4383-b0d7-4ee20272b69d" | jq .
# Expected: 200 OK with infobases list

curl -s http://localhost:8088/api/v1/clusters | jq .
# Expected: 200 OK with clusters list
```

---

## 5. CRITICAL TEST CASES

### 5.1 Must PASS

| Test | Condition | Expected | Weight |
|------|-----------|----------|--------|
| TestPasswordString_Empty | empty pwd | U+FFFD (0xef 0xbf 0xbd) | CRITICAL |
| TestPasswordString_NonEmpty | real pwd | normal encoding | HIGH |
| TestPasswordString_VsString | "" vs "" | different outputs | CRITICAL |
| TestClient_UnlockInfobase_EmptyPassword | unlock with "" | NO "no password supplied" error | CRITICAL |
| TestClient_LockUnlock_Sequence_WithEmptyPassword | lock→unlock→lock→unlock | all succeed | CRITICAL |
| TestClient_UnlockInfobase_PasswordStringUsage | validation | PasswordString() used for empty | CRITICAL |

### 5.2 Regression Tests

| Test | Condition | Expected |
|------|-----------|----------|
| GET /infobases | normal operation | 200 OK |
| GET /clusters | normal operation | 200 OK |
| Lock with non-empty password | normal case | 200 OK |
| Unlock with non-empty password | normal case | 200 OK |
| Multiple lock/unlock cycles | stress test | all succeed |

---

## 6. SUCCESS CRITERIA

### 6.1 Unit Tests
- [ ] TestPasswordString_Empty: PASS
- [ ] TestPasswordString_NonEmpty: PASS
- [ ] TestPasswordString_VsString: PASS
- [ ] TestPasswordString_UTF8Replacement: PASS
- [ ] TestPasswordString_RealPasswordVsEmpty: PASS
- [ ] TestPasswordString_NullableSize: PASS
- [ ] TestPasswordString_LongPassword: PASS
- [ ] TestPasswordString_SpecialCharacters: PASS
- [ ] All benchmarks complete without panic

### 6.2 Integration Tests
- [ ] TestClient_UnlockInfobase_EmptyPassword: PASS
- [ ] TestClient_LockInfobase_EmptyPassword: PASS
- [ ] TestClient_RegInfoBase_EmptyPassword: PASS
- [ ] TestClient_LockUnlock_Sequence_WithEmptyPassword: PASS
- [ ] TestClient_UnlockInfobase_PasswordStringUsage: PASS
- [ ] All existing client tests PASS (with updated signatures)

### 6.3 API Tests
- [ ] GET /infobases works
- [ ] GET /clusters works
- [ ] Lock succeeds
- [ ] Unlock succeeds
- [ ] No "no password supplied" errors

### 6.4 Overall
- [ ] Code coverage > 80% for encoder.go
- [ ] Zero "no password supplied" errors in Unlock
- [ ] Backward compatibility maintained (non-empty passwords still work)
- [ ] Performance acceptable (benchmarks complete in < 100ms)

---

## 7. KNOWN ISSUES & WORKAROUNDS

### 7.1 Module Path Issue

Problem:
```
main module (github.com/commandcenter1c/commandcenter/ras-adapter) does not contain package
```

Solution:
- Run tests from ras-adapter directory: `cd go-services/ras-adapter && go test ./...`
- Use relative paths, not full module paths

### 7.2 Test Signature Mismatch

Problem:
```
client.LockInfobase: not enough arguments
want (context.Context, string, string, string, string)
have (context.Context, string, string)
```

Solution:
- Updated all test calls with "", "" for dbUser, dbPwd parameters
- Files updated:
  - internal/ras/client_test.go
  - internal/eventhandlers/lock_handler_test.go
  - internal/service/infobase_service_test.go

---

## 8. FILES MODIFIED/CREATED

### 8.1 Новые файлы
- `go-services/ras-adapter/ras-client/protocol/codec/encoder_test.go` (NEW - 300+ lines)

### 8.2 Обновленные файлы
- `go-services/ras-adapter/ras-client/protocol/codec/encoder.go` (EXISTING - PasswordString method already exists)
- `go-services/ras-adapter/internal/ras/client_test.go` (EXTENDED - 5 new tests + updated existing)
- `go-services/ras-adapter/internal/eventhandlers/unlock_handler_test.go` (EXISTING - compatible)

### 8.3 Referenced files (not modified)
- `go-services/ras-adapter/internal/ras/client.go` (LockInfobase, UnlockInfobase, RegInfoBase)
- `go-services/ras-adapter/internal/models/infobase.go` (Infobase model)
- `go-services/ras-adapter/internal/api/rest/infobases_test.go` (REST API tests)

---

## 9. IMPLEMENTATION DETAILS

### 9.1 PasswordString Method

Location: `ras-client/protocol/codec/encoder.go` (lines 171-189)

```go
// PasswordString encodes password strings with UTF-8 replacement char for empty values.
// This matches rac.exe behavior and prevents RAS from attempting PostgreSQL validation
// on metadata-only operations (Lock/Unlock).
func (e *encoder) PasswordString(val string, w io.Writer) {
	if len(val) == 0 {
		// RAS protocol expects UTF-8 replacement character for empty passwords
		replacementChar := []byte{0xef, 0xbf, 0xbd}
		e.NullableSize(len(replacementChar), w)
		e.write(w, replacementChar)
		return
	}

	b := []byte(val)
	e.NullableSize(len(b), w)
	e.write(w, b)
}
```

### 9.2 Usage in RegInfoBase

Location: `go-services/ras-adapter/internal/ras/client.go` (lines 280-290)

```go
rasInfobase := serialize.InfobaseInfo{
	UUID:              infobaseUUID,
	Name:              infobase.Name,
	Dbms:              infobase.DBMS,
	DbServer:          infobase.DBServer,
	DbName:            infobase.DBName,
	DbUser:            infobase.DBUser,
	DbPwd:             infobase.DBPwd,  // SDK handles empty passwords correctly now
	ScheduledJobsDeny: infobase.ScheduledJobsDeny,
	SessionsDeny:      infobase.SessionsDeny,
}
```

Note: SDK's UpdateInfobase uses PasswordString() internally for DbPwd field.

---

## 10. PROTOCOL DETAILS

### 10.1 RAS Protocol Expectations

For Lock/Unlock operations on database with empty password:

**WRONG (old behavior):**
- Send NULL (0x00)
- RAS attempts PostgreSQL validation
- Error: "no password supplied"

**CORRECT (new behavior):**
- Send UTF-8 replacement char (U+FFFD = 0xef 0xbf 0xbd)
- RAS skips PostgreSQL validation (knows password is unknown)
- Success

### 10.2 Byte Representation

Empty password encoding with PasswordString():
```
Size:  0x03 (3 bytes follow)
Data:  0xef 0xbf 0xbd (UTF-8 replacement character)

Total: 0x03 ef bf bd (4 bytes)
```

Regular password encoding (e.g., "test"):
```
Size:  0x04 (4 bytes follow)
Data:  0x74 0x65 0x73 0x74 (UTF-8 "test")

Total: 0x04 74 65 73 74 (5 bytes)
```

---

## 11. TESTING QUICK COMMANDS

```bash
# Navigate to project
cd C:/1CProject/command-center-1c

# Unit tests only
cd go-services/ras-adapter/ras-client/protocol/codec && go test -v

# Integration tests
cd ../../ && go test -v ./internal/ras -run TestClient_Unlock

# All tests with coverage
cd ../../ && go test -v ./... -cover

# Specific password tests
go test -v ./... -run "PasswordString|EmptyPassword"

# Build and check compilation
go build -v

# Check code formatting
go fmt ./...

# Run linter
go vet ./...
```

---

## 12. TROUBLESHOOTING

### Issue: Tests don't run/compile
Solution: Ensure working directory is `go-services/ras-adapter/`

### Issue: "no password supplied" error still appears
Solution: Verify that:
1. PasswordString() method exists in encoder.go
2. DbPwd field uses PasswordString() encoding
3. SDK is rebuilt after changes
4. Test database has empty password configured

### Issue: Benchmark fails
Solution: Ensure no other processes accessing RAS server

### Issue: Module not found
Solution: Use relative imports from ras-adapter directory

---

## REPORT TEMPLATE

**Test Execution Date:** YYYY-MM-DD
**Executor:** [Name]
**Environment:** Windows GitBash / RAS Server: localhost:1545

### Summary
- [ ] All unit tests: PASS/FAIL (X/Y)
- [ ] All integration tests: PASS/FAIL (X/Y)
- [ ] All regression tests: PASS/FAIL (X/Y)
- [ ] Performance acceptable: YES/NO
- [ ] Overall result: PASS/FAIL

### Details
```
[Test output here]
```

### Issues Found
- [ ] Critical: [none/list]
- [ ] High: [none/list]
- [ ] Medium: [none/list]

### Sign-off
- Verified by: ____________________
- Date: ____________________

---

**Version:** 1.0
**Last Updated:** 2025-11-23
**Status:** READY FOR EXECUTION
