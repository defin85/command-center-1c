# Code Review - Navigation Index

> Навигация по документам code review для batch-service Sprint 1

**Дата:** 2025-11-08
**Reviewer:** Claude Code (Senior Code Reviewer)
**Статус:** ❌ НЕ ГОТОВО К PRODUCTION (критичный баг найден)

---

## 📋 Быстрый старт

**Если у вас мало времени (5 минут):**
1. Читай: **`CODE_REVIEW_SUMMARY.md`** - краткий отчет
2. Исправляй: **`QUICK_FIX_GUIDE.md`** - copy-paste решения

**Если нужны детали (20 минут):**
1. Читай: **`CODE_REVIEW_SUMMARY.md`** - понять проблемы
2. Понимай: **`DEADLOCK_EXPLANATION.md`** - почему deadlock
3. Применяй: **`REVIEW_FIXES_REFERENCE.md`** - полный код
4. Исправляй: **`QUICK_FIX_GUIDE.md`** - быстрое применение

---

## 📚 Документы

### 1. CODE_REVIEW_SUMMARY.md (7KB)

**Краткий отчет code review**

**Содержит:**
- ✅ TL;DR с root cause
- ✅ Оценка качества (1-10)
- ✅ Критичные проблемы (3 штуки)
- ✅ Важные проблемы (3 штуки)
- ✅ Положительные моменты
- ✅ Action items с приоритетами

**Читать когда:**
- Нужно быстро понять что не так
- Готовишься к обсуждению в команде
- Планируешь время на исправления

**Время чтения:** 5 минут

---

### 2. DEADLOCK_EXPLANATION.md (15KB)

**Подробное объяснение subprocess deadlock**

**Содержит:**
- ✅ Визуализация deadlock (ASCII art)
- ✅ Сравнение: текущий vs исправленный код
- ✅ Почему происходит deadlock
- ✅ Почему StdoutPipe решает проблему
- ✅ Реальные примеры из stacktrace
- ✅ Частые заблуждения
- ✅ Best practices checklist

**Читать когда:**
- Не понимаешь почему deadlock происходит
- Хочешь глубоко разобраться в проблеме
- Нужно объяснить проблему другим разработчикам
- Хочешь избежать подобных ошибок в будущем

**Время чтения:** 15-20 минут

---

### 3. REVIEW_FIXES_REFERENCE.md (16KB)

**Полный reference код для всех исправлений**

**Содержит:**
- ✅ Исправленный extension_deleter.go (полный код)
- ✅ Исправленный extension_lister.go (полный код)
- ✅ Новый validation.go с input validation
- ✅ Улучшенный Django client с retry
- ✅ Prometheus metrics (опционально)
- ✅ Checklist перед merge
- ✅ Команды для тестирования

**Использовать когда:**
- Готов применять исправления
- Нужен полный working code
- Пишешь новый service с subprocess
- Нужен reference для best practices

**Время применения:** 4-6 часов

---

### 4. QUICK_FIX_GUIDE.md (4KB)

**Быстрый гайд для copy-paste исправлений**

**Содержит:**
- ✅ Минимальный набор изменений
- ✅ Copy-paste ready код
- ✅ Точные строки для замены
- ✅ Checklist для проверки
- ✅ Команды тестирования

**Использовать когда:**
- Нужно СРОЧНО исправить баг
- Нет времени читать длинные документы
- Хочешь быстро проверить что исправления работают
- Нужен минимальный diff для review

**Время применения:** 30 минут

---

## 🎯 Рекомендуемый порядок действий

### Шаг 1: Понять проблему (10 минут)

```
1. Читай CODE_REVIEW_SUMMARY.md
   └─→ Понимаешь: Что не так, насколько критично

2. Читай DEADLOCK_EXPLANATION.md (секция "Визуализация")
   └─→ Понимаешь: Почему происходит deadlock
```

### Шаг 2: Планирование (5 минут)

```
1. Посмотри Action Items в CODE_REVIEW_SUMMARY.md
   └─→ Что MUST FIX, что SHOULD FIX, что NICE TO HAVE

2. Оцени время:
   - Минимальные исправления: 30 мин (QUICK_FIX_GUIDE)
   - Полные исправления: 4-6 часов (REVIEW_FIXES_REFERENCE)
```

### Шаг 3: Исправление (30 мин - 6 часов)

**Вариант A: Быстрое исправление (30 мин)**
```bash
# Следуй QUICK_FIX_GUIDE.md
cd go-services/batch-service
# ... copy-paste code из гайда
go test -v -timeout 30s ./tests/integration/
```

**Вариант B: Полное исправление (4-6 часов)**
```bash
# Следуй REVIEW_FIXES_REFERENCE.md
# Применяй все исправления:
# - extension_deleter.go
# - extension_lister.go
# - validation.go (новый)
# - Django client retry
# - Metrics (опционально)
```

### Шаг 4: Тестирование (15 минут)

```bash
# Unit tests
go test -race -v ./...

# Integration tests
go test -v -timeout 30s ./tests/integration/

# Memory leak check
go test -v -memprofile=mem.out ./internal/service/
go tool pprof mem.out

# Build verification
go build -o bin/cc1c-batch-service.exe ./cmd/main.go
```

### Шаг 5: Повторный review (30 минут)

```
1. Проверь checklist в REVIEW_FIXES_REFERENCE.md
2. Убедись что все MUST FIX исправлены
3. Запроси повторный code review
4. Merge в master
```

---

## 🚨 Критичные находки

### Блокирующие проблемы (3 штуки):

1. **Subprocess Deadlock** → timeout 600s
   - Файлы: extension_deleter.go, extension_lister.go
   - Приоритет: 🔴 КРИТИЧНО
   - Решение: StdoutPipe + async reading

2. **Context Cancellation** → subprocess не убивается
   - Файлы: extension_deleter.go, extension_lister.go
   - Приоритет: 🔴 КРИТИЧНО
   - Решение: select на errChan vs ctx.Done()

3. **Zombie Processes** → resource leak
   - Файлы: extension_deleter.go, extension_lister.go
   - Приоритет: 🔴 КРИТИЧНО
   - Решение: defer cmd.Process.Kill()

### Важные проблемы (3 штуки):

4. **No Rate Limiting** → 700 subprocess одновременно
   - Решение: semaphore (max 10 concurrent)

5. **Django Callback No Retry** → потеря callback
   - Решение: retry с exponential backoff

6. **Command Injection Risk** → unsafe input
   - Решение: ValidateExtensionName()

---

## 📊 Статистика

**Code Quality:** 7/10
**Security:** 8/10
**Performance:** 5/10
**Test Coverage:** 8/10
**Production Ready:** 4/10 ❌

**Блокеров:** 3
**Важных проблем:** 3
**Минорных проблем:** 4

**Время на исправление:**
- Минимум (quick fix): 30 минут
- Рекомендуемое (full fix): 4-6 часов
- Тестирование: 30 минут
- **ИТОГО:** ~6 часов

---

## 🎓 Что делать дальше?

### Сейчас (в течение дня):

1. ✅ Прочитай CODE_REVIEW_SUMMARY.md
2. ✅ Примени QUICK_FIX_GUIDE.md
3. ✅ Запусти tests - убедись что проходят
4. ✅ Commit исправления

### Потом (в течение недели):

5. ✅ Примени полные исправления из REVIEW_FIXES_REFERENCE.md
6. ✅ Добавь validation, retry, semaphore
7. ✅ Добавь metrics (опционально)
8. ✅ Повторный review
9. ✅ Merge в master

---

## 💡 Полезные ссылки

**Внутренние документы:**
- `README.md` - описание batch-service
- `tests/integration/endpoints_test.go` - integration tests
- `internal/service/` - service layer код

**Внешние ресурсы:**
- Go exec package: https://pkg.go.dev/os/exec
- Subprocess best practices: https://github.com/golang/go/issues/9382

---

## ❓ FAQ

**Q: Насколько критична проблема?**
A: Очень критична. Integration tests зависают на 600 секунд. Production использование невозможно.

**Q: Можно ли отложить исправления?**
A: НЕТ. Это блокирующие баги. Без исправлений нельзя мержить в master.

**Q: Сколько времени займет исправление?**
A: Минимум 30 минут (quick fix), рекомендуемое 4-6 часов (full fix).

**Q: Какие файлы нужно менять?**
A: `extension_deleter.go`, `extension_lister.go`, создать `validation.go`, обновить `client.go`.

**Q: Как проверить что исправления работают?**
A: `go test -v -timeout 30s ./tests/integration/` - должно пройти за < 10 секунд.

---

**Контакты:**
- Reviewer: Claude Code
- Дата: 2025-11-08
- Версия: 1.0
