# 🔧 Track 0 Worktree - batch-service Deadlock Fix

> **Git Worktree для параллельной работы над исправлением subprocess deadlock**

## 📍 Информация о worktree

- **Ветка:** `feature/track0-batch-service-deadlock-fix`
- **Путь:** `C:\1CProject\command-center-1c-track0`
- **Базовая ветка:** `master`
- **Создан:** 2025-11-09

## 🚨 Задача

**Критичный блокер:** Исправить subprocess deadlock в batch-service

**Проблема:**
- Integration tests зависают на 600 секунд
- Причина: `bytes.Buffer + cmd.Run()` → циклическая блокировка OS pipe buffer (64KB)

**Решение:**
- Использовать `cmd.StdoutPipe()` / `cmd.StderrPipe()` с асинхронным чтением

## 📚 Документация

В этом worktree доступны следующие руководства:

1. **`go-services/batch-service/QUICK_FIX_GUIDE.md`**
   - ⏱️ Время: 30 минут
   - Быстрое исправление проблемы

2. **`go-services/batch-service/REVIEW_FIXES_REFERENCE.md`**
   - ⏱️ Время: 4-6 часов
   - Полное исправление с code review fixes

3. **`go-services/batch-service/DEADLOCK_EXPLANATION.md`**
   - Детальное объяснение причины deadlock

## 🛠️ Как работать

### 1. Перейти в worktree

```bash
cd /c/1CProject/command-center-1c-track0
```

### 2. Проверить статус

```bash
git status
# Ожидается: On branch feature/track0-batch-service-deadlock-fix
```

### 3. Внести изменения

```bash
# Прочитать quick fix guide
cat go-services/batch-service/QUICK_FIX_GUIDE.md

# Применить исправления
# (редактировать файлы в go-services/batch-service/internal/executor/)
```

### 4. Тестирование

```bash
cd go-services/batch-service

# Запустить integration tests
go test -v ./tests/integration/...

# Если тесты проходят без timeout → успех! ✅
```

### 5. Коммит изменений

```bash
git add .
git commit -m "fix(batch-service): resolve subprocess deadlock in executor

- Replace bytes.Buffer with cmd.StdoutPipe/StderrPipe
- Add async goroutines for output reading
- Fixes integration test timeout (600s → <10s)

Closes #<issue-number>
"
```

### 6. Push в remote

```bash
git push origin feature/track0-batch-service-deadlock-fix
```

### 7. Создать Pull Request

Создать PR на GitHub:
- **Base:** `master`
- **Compare:** `feature/track0-batch-service-deadlock-fix`
- **Title:** `fix(batch-service): resolve subprocess deadlock`
- **Description:** Ссылка на PARALLEL_WORK_PLAN.md, Track 0

## 📂 Ключевые файлы для изменения

```
go-services/batch-service/
├── internal/
│   └── executor/
│       └── executor.go          ← ГЛАВНЫЙ ФАЙЛ для исправления
├── tests/
│   └── integration/
│       └── install_test.go      ← Проверить что тесты проходят
└── QUICK_FIX_GUIDE.md           ← Инструкция по исправлению
```

## ⚠️ Важные команды worktree

### Проверить все worktrees

```bash
git worktree list
```

**Ожидаемый вывод:**
```
C:/1CProject/command-center-1c         e595de8 [master]
C:/1CProject/command-center-1c-track0  e595de8 [feature/track0-batch-service-deadlock-fix]
```

### Переключиться обратно в главный worktree

```bash
cd /c/1CProject/command-center-1c
```

### Удалить worktree после завершения (НЕ ДЕЛАТЬ СЕЙЧАС!)

```bash
# ТОЛЬКО после merge PR!
cd /c/1CProject/command-center-1c
git worktree remove ../command-center-1c-track0
git branch -d feature/track0-batch-service-deadlock-fix
```

## ✅ Acceptance Criteria

**Задача считается завершенной когда:**

- ✅ Integration tests проходят без timeout
- ✅ Deadlock устранен (проверено многократным запуском тестов)
- ✅ Code review пройден
- ✅ CI/CD pipeline проходит
- ✅ PR смержен в master

## 🔗 Связанные документы

- **Общий план:** `/docs/PARALLEL_WORK_PLAN.md`
- **Roadmap:** `/docs/ROADMAP.md`
- **Batch Service Guide:** `/docs/BATCH_SERVICE_EXTENSIONS_GUIDE.md`

## 🚀 Quick Start

```bash
# 1. Перейти в worktree
cd /c/1CProject/command-center-1c-track0

# 2. Прочитать quick fix guide
cat go-services/batch-service/QUICK_FIX_GUIDE.md

# 3. Начать исправление
code go-services/batch-service/internal/executor/executor.go

# 4. После изменений - тестировать
cd go-services/batch-service
go test -v ./tests/integration/...
```

---

**Приоритет:** 🚨 КРИТИЧНО
**Время:** 30 минут - 6 часов
**Статус:** Ready to start
**Assignee:** Go Backend Developer

**Next Action:** Прочитать QUICK_FIX_GUIDE.md и начать исправление!
