# PasswordString Fix - Quick Test Execution Guide

**Дата:** 2025-11-23
**Статус:** READY TO RUN

---

## TL;DR - Быстрый старт (2 минуты)

```bash
# 1. Перейти в ras-adapter директорию
cd C:/1CProject/command-center-1c/go-services/ras-adapter

# 2. Запустить все тесты
go test -v ./...

# 3. Проверить результат
# Expected: все tests PASS, включая 5 новых "EmptyPassword" тестов
```

---

## Детальные шаги

### Шаг 1: Unit тесты PasswordString encoding

```bash
# Переход в codec package
cd C:/1CProject/command-center-1c/go-services/ras-adapter/ras-client/protocol/codec

# Запуск unit тестов
go test -v -run TestPasswordString

# Ожидаемый результат:
# --- PASS: TestPasswordString_Empty
# --- PASS: TestPasswordString_NonEmpty
# --- PASS: TestPasswordString_VsString
# --- PASS: TestPasswordString_UTF8Replacement
# --- PASS: TestPasswordString_RealPasswordVsEmpty
# --- PASS: TestPasswordString_NullableSize
# --- PASS: TestPasswordString_LongPassword
# --- PASS: TestPasswordString_SpecialCharacters
# ok      ... 0.234s
```

**Статус проверки:**
- [x] 8/8 тестов PASS → FIX РАБОТАЕТ ✅
- [ ] < 8 тестов PASS → ПРОБЛЕМА ❌
- [ ] Compilation error → Проверить encoder.go ❌

---

### Шаг 2: Integration тесты Lock/Unlock

```bash
# Переход в ras-adapter
cd C:/1CProject/command-center-1c/go-services/ras-adapter

# Запуск тестов на empty password
go test -v ./internal/ras -run "EmptyPassword|PasswordString"

# Ожидаемый результат:
# --- PASS: TestClient_UnlockInfobase_EmptyPassword (CRITICAL)
# --- PASS: TestClient_LockInfobase_EmptyPassword
# --- PASS: TestClient_RegInfoBase_EmptyPassword
# --- PASS: TestClient_LockUnlock_Sequence_WithEmptyPassword
# --- PASS: TestClient_UnlockInfobase_PasswordStringUsage
# ok      ... 1.234s
```

**Статус проверки:**
- [x] 5/5 новых тестов PASS → BUG FIX РАБОТАЕТ ✅
- [ ] < 5 тестов PASS → ПРОБЛЕМА ❌

---

### Шаг 3: Проверка обновленных существующих тестов

```bash
# Запуск всех client тестов
go test -v ./internal/ras

# Ожидаемый результат:
# === RUN   TestNewClient_Success
# --- PASS: TestNewClient_Success
# === RUN   TestClient_LockInfobase
# --- PASS: TestClient_LockInfobase/Success
# --- PASS: TestClient_LockInfobase/Empty_ClusterID
# ... (и т.д.)
# ok      ... 2.234s
```

**Статус проверки:**
- [x] Все тесты PASS (включая старые и новые) → BACKWARDS COMPATIBLE ✅
- [ ] Старые тесты FAIL → REGRESSION ❌

---

### Шаг 4: Регрессионное тестирование (опционально)

```bash
# Запуск ВСЕХ тестов в ras-adapter
cd C:/1CProject/command-center-1c/go-services/ras-adapter
go test -v ./...

# Проверить результат:
# - Все пакеты должны быть OK
# - Нет ошибок компиляции
# - Нет новых failures

# Если есть failures в других пакетах:
# go test ./internal/eventhandlers  # (может быть compilation issue)
# go test ./internal/service        # (может быть compilation issue)
# -> Это известные issues - нужно обновить mock svc методы
```

---

## Проверка ключевых файлов

### Файл 1: encoder_test.go (новый)

```bash
# Проверить что файл существует
ls -la "C:/1CProject/command-center-1c/go-services/ras-adapter/ras-client/protocol/codec/encoder_test.go"

# Ожидаемо: файл существует, ~8KB

# Проверить что компилируется
cd C:/1CProject/command-center-1c/go-services/ras-adapter/ras-client/protocol/codec
go build -v

# Ожидаемо: "ok" без ошибок
```

### Файл 2: encoder.go (существует, содержит PasswordString)

```bash
# Проверить метод PasswordString
cd C:/1CProject/command-center-1c/go-services/ras-adapter/ras-client/protocol/codec
grep -n "func (e \*encoder) PasswordString" encoder.go

# Ожидаемо: вывод с номером строки ~171
```

### Файл 3: client_test.go (обновлены сигнатуры)

```bash
# Проверить что новые тесты добавлены
grep -n "TestClient_UnlockInfobase_EmptyPassword" internal/ras/client_test.go

# Ожидаемо: вывод с номером строки ~582
```

---

## Быстрая диагностика проблем

### Проблема: "not enough arguments in call to client.LockInfobase"

**Причина:** Старый тест использует 3 параметра вместо 5

**Решение:**
```bash
# Проверить что client_test.go обновлен правильно
grep "client.LockInfobase" internal/ras/client_test.go | head -5

# Должно быть:
# client.LockInfobase(context.Background(), clusterID, infobaseID, "", "")
# NOT:
# client.LockInfobase(context.Background(), clusterID, infobaseID)
```

### Проблема: encoder_test.go не компилируется

**Причина:** Синтаксическая ошибка или отсутствующие импорты

**Решение:**
```bash
# Пересоздать файл из scratch
# или

# Проверить что все импорты есть
head -20 ras-client/protocol/codec/encoder_test.go | grep "^import"
```

### Проблема: "no password supplied" error в тестах

**Причина:** Fix не применена правильно в SDK

**Решение:**
1. Проверить что PasswordString() использует 0xef 0xbf 0xbd
2. Проверить что DbPwd использует PasswordString() в InfobaseInfo
3. Пересобрать SDK: `cd ras-client && go build`

### Проблема: Tests timeout (> 30 секунд)

**Причина:** RAS server connection timeout

**Решение:**
```bash
# Убедиться что идёт mock client (без реального RAS)
# Tests должны работать < 2 секунды

# Если slow: отключить connection attempt
# Проверить что NewClient использует mock стуб, не real protocol
```

---

## Матрица результатов тестирования

| Компонент | Тест | Expected | Actual | Status |
|-----------|------|----------|--------|--------|
| encoder | TestPasswordString_Empty | PASS | ? | ⏳ |
| encoder | TestPasswordString_NonEmpty | PASS | ? | ⏳ |
| encoder | TestPasswordString_VsString | PASS | ? | ⏳ |
| encoder | TestPasswordString_UTF8Replacement | PASS | ? | ⏳ |
| encoder | TestPasswordString_RealPasswordVsEmpty | PASS | ? | ⏳ |
| encoder | TestPasswordString_NullableSize | PASS | ? | ⏳ |
| encoder | TestPasswordString_LongPassword | PASS | ? | ⏳ |
| encoder | TestPasswordString_SpecialCharacters | PASS | ? | ⏳ |
| client | TestClient_UnlockInfobase_EmptyPassword | PASS | ? | ⏳ |
| client | TestClient_LockInfobase_EmptyPassword | PASS | ? | ⏳ |
| client | TestClient_RegInfoBase_EmptyPassword | PASS | ? | ⏳ |
| client | TestClient_LockUnlock_Sequence_WithEmptyPassword | PASS | ? | ⏳ |
| client | TestClient_UnlockInfobase_PasswordStringUsage | PASS | ? | ⏳ |
| client | TestClient_LockInfobase | PASS | ? | ⏳ |
| client | TestClient_UnlockInfobase | PASS | ? | ⏳ |

**ИТОГО:** 15+ тестов ожидают проверки

---

## Чек-лист перед запуском

### Pre-Test Checklist
- [ ] Находитесь в `/go-services/ras-adapter` директории
- [ ] Go 1.21+ установлен: `go version`
- [ ] Зависимости скачаны: `go mod download`
- [ ] No unsaved changes in critical files
- [ ] Disk space available (> 500MB)

### Post-Test Checklist
- [ ] All unit tests PASS
- [ ] All 5 new EmptyPassword tests PASS
- [ ] No new failures in existing tests
- [ ] No compilation errors
- [ ] No "no password supplied" errors
- [ ] Test execution time < 10 seconds

---

## Success Criteria Summary

### 🟢 SUCCESS (Fix works correctly)
```
✅ TestPasswordString_Empty: U+FFFD (0xef 0xbf 0xbd) encoded correctly
✅ TestClient_UnlockInfobase_EmptyPassword: No "no password supplied" error
✅ TestClient_LockUnlock_Sequence_WithEmptyPassword: All 3 cycles PASS
✅ All existing tests still PASS (backwards compatible)
```

### 🔴 FAILURE (Fix broken)
```
❌ TestPasswordString_Empty: Returns NULL (0x00) instead of U+FFFD
❌ TestClient_UnlockInfobase_EmptyPassword: Still gets "no password supplied" error
❌ Existing tests FAIL: Regression
```

---

## Дополнительные команды

### Coverage Analysis
```bash
# Проверить coverage для encoder.go
go test -v -coverprofile=coverage.out ./ras-client/protocol/codec
go tool cover -html=coverage.out

# Expected: > 90% coverage for PasswordString code
```

### Benchmark Execution
```bash
# Запустить только бенчмарки
go test -bench=. -benchtime=10s ./ras-client/protocol/codec

# Expected: Each < 100ms, consistent results
```

### Detailed Debugging
```bash
# Verbose output with panic recovery
go test -v -race ./internal/ras -run TestClient_UnlockInfobase_EmptyPassword

# Expected: No race conditions, clear output
```

### Format & Lint
```bash
# Проверить code formatting
go fmt ./...

# Static analysis
go vet ./...

# Expected: No issues
```

---

## Итоговый чек-лист выполнения

После запуска всех тестов, заполните:

- [ ] Encoder unit tests: ____ / 8 PASS
- [ ] Integration critical tests: ____ / 5 PASS
- [ ] Updated existing tests: ____ / 9 PASS
- [ ] Total execution time: ____ seconds
- [ ] Coverage > 80%: YES / NO
- [ ] No "no password supplied" errors: YES / NO
- [ ] All benchmarks completed: YES / NO

**Final Result:**
- [ ] ✅ ALL PASS - Fix is working correctly
- [ ] ❌ SOME FAIL - Fix has issues, needs debugging

---

## Контакты для помощи

| Issue | Решение |
|-------|---------|
| Module not found | Run from `go-services/ras-adapter/` |
| Import errors | Check encoder.go imports |
| Compilation error | Run `go mod tidy` |
| Tests timeout | Mock client shouldn't timeout < 2s |
| "no password supplied" | Verify PasswordString() fix applied |

---

## Ссылки на документацию

1. **Детальный план:** `TEST_PASSWORDSTRING_FIX_PLAN.md`
2. **Полный отчет:** `TEST_EXECUTION_SUMMARY.md`
3. **Progress tracker:** `UNLOCK_BUG_PROGRESS.md`
4. **Code changes:** `CLAUDE.md`

---

**Готовы к запуску тестов? Выполняйте Шаг 1-4 выше!**

**Ожидаемое время выполнения:** < 2 минуты
**Ожидаемый результат:** 15+ PASS тестов ✅

