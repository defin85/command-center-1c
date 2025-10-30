# Upstream Synchronization Procedure

Процедура синхронизации форка `command-center-1c/ras-grpc-gw` с upstream `v8platform/ras-grpc-gw`.

**Fork Repository:** https://github.com/command-center-1c/ras-grpc-gw
**Upstream Repository:** https://github.com/v8platform/ras-grpc-gw
**Document Version:** 1.0
**Last Updated:** 2025-01-17

---

## Table of Contents

1. [Sync Strategy](#sync-strategy)
2. [Frequency](#frequency)
3. [Pre-Sync Checks](#pre-sync-checks)
4. [Sync Procedure](#sync-procedure)
5. [Conflict Resolution](#conflict-resolution)
6. [Post-Sync Validation](#post-sync-validation)
7. [Rollback Procedure](#rollback-procedure)
8. [Sync History Log](#sync-history-log)

---

## Sync Strategy

### Fork Type: Hard Fork

**Обоснование:**
- Upstream неактивен 4+ года (последний коммит: 2021-09-07)
- Fork имеет критические изменения несовместимые с upstream:
  - Полное переписывание тестов (coverage 0% → 70%+)
  - Структурное изменение архитектуры (middleware, health checks, metrics)
  - Обновление зависимостей (Go 1.17 → 1.24, breaking changes)
- Нет планов на merge обратно в upstream

### Sync Policy

| Сценарий | Действие |
|----------|----------|
| Новые commits в upstream | Manual review → selective cherry-pick |
| Critical security fixes | Immediate sync (в течение 24 часов) |
| Bug fixes | Sync при следующем scheduled review |
| New features | Evaluate → decide (скорее всего skip) |
| Breaking changes | НЕ синхронизировать (форк полностью независим) |

**Ожидаемая активность upstream:** Минимальная до нулевой (проект заброшен)

---

## Frequency

### Scheduled Reviews

**Регулярная проверка:** **Ежемесячно** (каждое 1-е число месяца)

**Задачи:**
1. Проверка наличия новых commits в upstream
2. Review изменений (если есть)
3. Принятие решения о синхронизации
4. Обновление Sync History Log

### Ad-hoc Reviews

**Триггеры для внепланового review:**
- GitHub notification о новом релизе upstream
- Сообщения в issues/discussions upstream о критических багах
- Упоминание upstream в security advisories

**Timeline:** В течение 48 часов после триггера

---

## Pre-Sync Checks

### 1. Проверка upstream активности

```bash
cd ~/projects/ras-grpc-gw

# Добавить upstream remote (если ещё не добавлен)
git remote add upstream https://github.com/v8platform/ras-grpc-gw.git || true

# Обновить upstream refs
git fetch upstream

# Проверить новые коммиты
echo "=== Новые коммиты в upstream/master ==="
git log HEAD..upstream/master --oneline --graph

# Если вывод пустой - синхронизация не требуется
```

**Expected output (если нет изменений):**
```
=== Новые коммиты в upstream/master ===
(пусто)
```

### 2. Анализ изменений

Если есть новые commits:

```bash
# Детальный лог изменений
git log HEAD..upstream/master --pretty=format:"%h - %an, %ar : %s" --stat

# Diff всех изменений
git diff HEAD...upstream/master > /tmp/upstream-diff.txt

# Открыть diff в редакторе для review
code /tmp/upstream-diff.txt
```

**Критерии для синхронизации:**

| Тип изменения | Sync? | Метод |
|---------------|-------|-------|
| Security fix (CVE) | ✅ Да | Cherry-pick + test |
| Bug fix в core логике | ⚠️ Возможно | Evaluate + test |
| Новая feature | ❌ Скорее всего нет | Оценить необходимость |
| Refactoring | ❌ Нет | Форк имеет свой стиль |
| Dependency update | ❌ Нет | Форк управляет сам |
| Documentation | ⚠️ Возможно | Selective merge |

### 3. Проверка состояния форка

```bash
# Убедиться что fork чист (нет uncommitted changes)
git status

# Переключиться на main ветку
git checkout main

# Обновить локальную копию
git pull origin main

# Проверить что все тесты проходят
make test

# Проверить coverage
make coverage
```

**Requirement:** Все тесты зелёные, coverage > 70%

---

## Sync Procedure

### Метод 1: Cherry-pick (рекомендуется)

Используется для выборочной синхронизации конкретных commits.

#### Шаг 1: Создать sync ветку

```bash
# Формат: sync/upstream-YYYYMMDD-short-description
BRANCH_NAME="sync/upstream-$(date +%Y%m%d)-security-fix"

git checkout -b "$BRANCH_NAME" main
```

#### Шаг 2: Cherry-pick commits

```bash
# Найти hash коммита для синхронизации
git log upstream/master --oneline -n 20

# Cherry-pick конкретный commit
COMMIT_HASH="abc123"
git cherry-pick "$COMMIT_HASH"

# Если возникли конфликты - см. раздел Conflict Resolution
```

#### Шаг 3: Адаптировать изменения для форка

После cherry-pick проверить:
- Совместимость с новыми зависимостями (Go 1.24, gRPC 1.60)
- Соответствие code style форка (golangci-lint)
- Наличие тестов для изменений

```bash
# Запустить линтер
make lint

# Если есть ошибки - исправить
# Возможно потребуется адаптация кода
```

#### Шаг 4: Добавить тесты (если отсутствуют)

```bash
# Пример: upstream fix не имеет тестов
# Написать тест для форка

cat > pkg/adapter/rac_fix_test.go <<'EOF'
package adapter

import (
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestUpstreamSecurityFix(t *testing.T) {
    // Test для upstream fix
    adapter := NewRACAdapter("/usr/bin/rac")

    // Проверка fix
    result, err := adapter.SanitizeInput("malicious input")
    assert.NoError(t, err)
    assert.NotContains(t, result, "malicious")
}
EOF

# Запустить тесты
go test ./pkg/adapter -v -run TestUpstreamSecurityFix
```

#### Шаг 5: Обновить CHANGELOG.md

```bash
# Добавить запись в FORK_CHANGELOG.md
cat >> FORK_CHANGELOG.md <<'EOF'

### Upstream sync (YYYY-MM-DD)

- Cherry-picked commit `abc123` from upstream
  - Description: Security fix for command injection
  - Original PR: v8platform/ras-grpc-gw#42
  - Adapted for fork: Added tests, updated error handling
EOF

git add FORK_CHANGELOG.md
git commit -m "docs: update changelog with upstream sync"
```

#### Шаг 6: Создать Pull Request

```bash
# Push ветки в fork
git push origin "$BRANCH_NAME"

# Создать PR через GitHub CLI
gh pr create \
  --title "Upstream sync: Security fix from upstream@abc123" \
  --body "$(cat <<'EOF'
## Summary

Синхронизация security fix из upstream.

## Upstream Changes

- Commit: `abc123`
- PR: v8platform/ras-grpc-gw#42
- Description: Fix command injection vulnerability in RAC adapter

## Fork Adaptations

- Added unit tests (coverage +5%)
- Updated error handling to use zap logger
- Adapted to Go 1.24 syntax

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] golangci-lint clean
- [ ] Coverage > 70%

## Upstream Sync

- Based on: upstream@abc123
- Sync date: 2025-01-17
- Sync method: cherry-pick

Closes #123
EOF
)" \
  --base main \
  --head "$BRANCH_NAME"
```

### Метод 2: Rebase (НЕ рекомендуется)

**⚠️ WARNING:** Rebase НЕ используется из-за hard fork стратегии.

**Причины:**
- Форк имеет несовместимые изменения
- Rebase перепишет историю и сломает fork commits
- Cherry-pick обеспечивает больший контроль

**Исключение:** Rebase может использоваться ТОЛЬКО если:
- Upstream получил критический security patch
- Fork ещё не diverged значительно (первые недели после fork)
- **И**: получено явное одобрение от maintainer форка

---

## Conflict Resolution

### Типичные конфликты

#### Конфликт 1: go.mod

**Проблема:**
```
<<<<<<< HEAD
go 1.24
=======
go 1.17
>>>>>>> abc123 (upstream commit)
```

**Решение:**
```bash
# Оставить версию форка
git checkout --ours go.mod

# Вручную проверить зависимости upstream
# Если upstream добавил новую dependency - добавить её
go get <new-dependency>

# Mark resolved
git add go.mod
```

#### Конфликт 2: Код с разными паттернами логирования

**Проблема:**
```go
<<<<<<< HEAD
logger.Info("Starting server", zap.String("port", port))
=======
log.Printf("Starting server on port %s", port)
>>>>>>> abc123
```

**Решение:**
```bash
# Использовать fork стиль (structured logging)
# Вручную отредактировать файл

# Принять fork версию как базу
git checkout --ours file.go

# Добавить логику из upstream (если нужна)
# Но с использованием zap logger

# Mark resolved
git add file.go
```

#### Конфликт 3: Тесты

**Проблема:** Upstream добавил тесты, но с другим test framework

**Решение:**
```bash
# Переписать тесты на testify (fork стандарт)

# Принять fork версию
git checkout --ours file_test.go

# Вручную портировать логику тестов upstream
# Example:
# Upstream: if result != expected { t.Error(...) }
# Fork:     assert.Equal(t, expected, result)

# Mark resolved
git add file_test.go
```

### Общая стратегия разрешения конфликтов

1. **Всегда предпочитать fork версию** для:
   - go.mod (версии зависимостей)
   - Logging patterns (zap vs stdlib log)
   - Test framework (testify)
   - Configuration (viper vs hardcoded)

2. **Внимательно портировать upstream логику** в fork стиль:
   - Сохранить бизнес-логику upstream
   - Адаптировать к fork паттернам
   - Добавить тесты если отсутствуют

3. **Документировать изменения:**
   ```bash
   git commit -m "sync: cherry-pick upstream@abc123 with adaptations

   Original upstream change: Fix RAC command injection

   Fork adaptations:
   - Converted to zap structured logging
   - Added testify assertions
   - Updated to Go 1.24 syntax

   Upstream-commit: abc123"
   ```

---

## Post-Sync Validation

### Automated Checks (CI/CD)

После merge sync ветки в main - CI автоматически проверит:

```yaml
# .github/workflows/ci.yml
- run: make lint        # golangci-lint
- run: make test        # unit tests
- run: make coverage    # coverage > 70%
- run: make build       # компиляция без ошибок
```

**Requirement:** Все checks зелёные

### Manual Validation

После успешного CI:

```bash
# 1. Локальная сборка
make build

# 2. Запуск integration tests
make test-integration

# 3. Проверка Docker образа
make docker-build
docker run --rm ghcr.io/command-center-1c/ras-grpc-gw:dev --version

# 4. Smoke test в staging
kubectl apply -f k8s/staging/
kubectl wait --for=condition=ready pod -l app=ras-grpc-gw -n staging --timeout=60s
kubectl logs -l app=ras-grpc-gw -n staging --tail=50
```

### Regression Testing

```bash
# Запустить полный набор регрессионных тестов
make test-e2e

# Load testing (если sync затронул performance-critical код)
k6 run tests/load/smoke.js
```

**Success criteria:**
- Все E2E тесты проходят
- Latency не увеличилась (99p < 100ms)
- Error rate < 0.1%

---

## Rollback Procedure

### Сценарий 1: Проблемы обнаружены до merge

```bash
# Откатить sync ветку
git checkout main
git branch -D sync/upstream-YYYYMMDD-description

# Закрыть PR
gh pr close <PR-number>

# Опционально: создать issue для дальнейшего исследования
gh issue create \
  --title "Upstream sync rollback: <reason>" \
  --body "Sync from upstream@abc123 failed due to <reason>. Needs investigation."
```

### Сценарий 2: Проблемы обнаружены после merge в main

```bash
# Вариант A: Revert merge commit
git revert -m 1 <merge-commit-hash>
git push origin main

# Вариант B: Revert через PR (предпочтительно)
REVERT_BRANCH="revert/upstream-sync-$(date +%Y%m%d)"
git checkout -b "$REVERT_BRANCH" main
git revert -m 1 <merge-commit-hash>
git push origin "$REVERT_BRANCH"

gh pr create \
  --title "Revert upstream sync due to <reason>" \
  --body "Reverts merge #<PR-number> due to <reason>." \
  --base main \
  --head "$REVERT_BRANCH"
```

### Сценарий 3: Проблемы в production

```bash
# CRITICAL: Немедленный rollback

# 1. Откатить Kubernetes deployment
kubectl rollout undo deployment/ras-grpc-gw -n production

# 2. Проверить статус
kubectl rollout status deployment/ras-grpc-gw -n production

# 3. Создать hotfix branch для revert
git checkout -b hotfix/revert-upstream-sync main
git revert -m 1 <merge-commit-hash>
git push origin hotfix/revert-upstream-sync

# 4. Emergency merge (bypass CI если критично)
gh pr create --title "HOTFIX: Revert upstream sync" --base main --head hotfix/revert-upstream-sync
# Получить approval и merge немедленно

# 5. Redeploy
kubectl set image deployment/ras-grpc-gw \
  ras-grpc-gw=ghcr.io/command-center-1c/ras-grpc-gw:v1.0.0-cc \
  -n production
```

---

## Sync History Log

### 2025-01-17: Initial Fork Creation

**Action:** Created fork from upstream
**Upstream Commit:** `d4b5b77` (2021-09-07)
**Upstream Version:** v0.1.0-beta
**Changes Synced:** None (initial state)
**Notes:** Upstream inactive 4+ years

**Divergence:**
- Fork: 0 commits ahead, 0 commits behind
- Status: Initial state, no divergence yet

---

### Template for Future Syncs

```markdown
### YYYY-MM-DD: [Sync Type]

**Action:** [Cherry-pick | Rebase | Manual merge]
**Upstream Commits:** `<hash1>`, `<hash2>`
**Upstream Version:** [version if tagged]
**Changes Synced:**
- Description of change 1
- Description of change 2

**Fork Adaptations:**
- Adaptation 1
- Adaptation 2

**Tests:**
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] E2E tests pass
- [ ] Coverage > 70%

**Deployment:**
- [ ] Staging validated
- [ ] Production deployed
- [ ] Monitoring normal

**Notes:** Any additional context

**Divergence after sync:**
- Fork: X commits ahead, Y commits behind upstream
- Conflicts resolved: [list if any]

**PR:** #<number>
**Merged by:** @username
```

---

## Appendix A: Useful Commands

### Quick Sync Check

```bash
# One-liner для быстрой проверки
git fetch upstream && \
git log --oneline --graph HEAD..upstream/master && \
echo "Commits behind upstream: $(git rev-list --count HEAD..upstream/master)"
```

### Upstream Comparison

```bash
# Сравнить fork с upstream (файлы)
git diff --name-status HEAD...upstream/master

# Найти все изменённые Go файлы
git diff --name-only HEAD...upstream/master | grep '\.go$'

# Показать статистику изменений
git diff --stat HEAD...upstream/master
```

### Cherry-pick Range

```bash
# Cherry-pick диапазона commits (осторожно!)
git cherry-pick <start-commit>^..<end-commit>

# Interactive cherry-pick (выбрать commits вручную)
git log --oneline --graph upstream/master -n 20
# Затем cherry-pick по одному
```

### Dependency Comparison

```bash
# Сравнить go.mod с upstream
diff <(git show upstream/master:go.mod) go.mod

# Найти новые зависимости в upstream
comm -23 \
  <(git show upstream/master:go.mod | grep -E '^\s+' | sort) \
  <(grep -E '^\s+' go.mod | sort)
```

---

## Appendix B: Sync Decision Tree

```
┌─────────────────────────┐
│ Upstream has new commit │
└────────────┬────────────┘
             │
             ▼
┌────────────────────────────┐
│ Is it security fix (CVE)?  │
└────┬───────────────────┬───┘
     │ Yes               │ No
     ▼                   ▼
┌──────────────┐   ┌────────────────┐
│ Sync ASAP    │   │ Is it bug fix? │
│ (< 24 hours) │   └───┬────────┬───┘
└──────────────┘       │ Yes    │ No
                       ▼        ▼
              ┌────────────┐  ┌─────────────┐
              │ Evaluate   │  │ New feature │
              │ impact     │  └──────┬──────┘
              └─────┬──────┘         │
                    │                ▼
                    │     ┌──────────────────┐
                    │     │ Does fork need   │
                    │     │ this feature?    │
                    │     └────┬────────┬────┘
                    │          │ Yes    │ No
                    │          ▼        ▼
                    │  ┌───────────┐  ┌──────┐
                    └─>│ Cherry-   │  │ Skip │
                       │ pick +    │  └──────┘
                       │ Test      │
                       └───────────┘
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Next Review:** 2025-02-01 (first monthly check)
**Owner:** CommandCenter1C Team
**Contact:** TBD
