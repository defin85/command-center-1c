# Инструкции по созданию и настройке форка ras-grpc-gw

Пошаговое руководство для пользователя как создать fork репозитория `v8platform/ras-grpc-gw` и настроить его для использования в проекте CommandCenter1C.

**Target Audience:** Разработчики CommandCenter1C Team
**Estimated Time:** 30-45 минут
**Document Version:** 1.0
**Last Updated:** 2025-01-17

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Шаг 1: Создание форка на GitHub](#шаг-1-создание-форка-на-github)
3. [Шаг 2: Клонирование форка](#шаг-2-клонирование-форка)
4. [Шаг 3: Настройка upstream](#шаг-3-настройка-upstream)
5. [Шаг 4: Копирование документации](#шаг-4-копирование-документации)
6. [Шаг 5: Настройка CI/CD](#шаг-5-настройка-cicd)
7. [Шаг 6: Первая синхронизация](#шаг-6-первая-синхронизация)
8. [Шаг 7: Проверка готовности](#шаг-7-проверка-готовности)
9. [Next Steps](#next-steps)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Необходимые инструменты

**Required:**
- [x] GitHub аккаунт с доступом к organization `command-center-1c`
- [x] Git 2.30+
- [x] GitHub CLI (`gh`) - рекомендуется для упрощения работы

**Optional:**
- [ ] SSH ключ настроен для GitHub (быстрее чем HTTPS)
- [ ] GoLand или VSCode с Go extension (для дальнейшей разработки)

### Проверка инструментов

```bash
# Проверить Git
git --version
# Ожидается: git version 2.30.0 или выше

# Проверить GitHub CLI (опционально)
gh --version
# Ожидается: gh version 2.0.0 или выше

# Проверить SSH доступ к GitHub (если используете SSH)
ssh -T git@github.com
# Ожидается: Hi YOUR-USERNAME! You've successfully authenticated...
```

### Права доступа

**Необходимо:**
- Membership в GitHub organization `command-center-1c`
- Права на создание репозиториев в organization
- Права на настройку GitHub Actions secrets

**Проверка:**
```bash
gh api /orgs/command-center-1c/members --jq '.[].login' | grep $(gh api /user --jq '.login')
# Если вывод содержит ваш username - доступ есть
```

---

## Шаг 1: Создание форка на GitHub

### Вариант A: Через Web UI (рекомендуется для первого раза)

1. **Открыть upstream репозиторий:**
   ```
   https://github.com/v8platform/ras-grpc-gw
   ```

2. **Нажать кнопку "Fork"** (правый верхний угол)

3. **Настроить fork:**
   - **Owner:** Выбрать `command-center-1c` (НЕ личный аккаунт!)
   - **Repository name:** Оставить `ras-grpc-gw`
   - **Description:** `gRPC gateway for 1C Remote Administration Server (CommandCenter1C fork)`
   - **Copy the main branch only:** ✅ Отметить (нам не нужны все ветки)

4. **Нажать "Create fork"**

5. **Дождаться создания** (обычно < 1 минуты)

**Expected result:**
```
Repository created: https://github.com/command-center-1c/ras-grpc-gw
```

### Вариант B: Через GitHub CLI (для опытных)

```bash
gh repo fork v8platform/ras-grpc-gw \
  --org command-center-1c \
  --fork-name ras-grpc-gw \
  --clone=false

# Expected output:
# ✓ Created fork command-center-1c/ras-grpc-gw
```

### Проверка создания

```bash
# Проверить что fork существует
gh repo view command-center-1c/ras-grpc-gw

# Должен показать:
# name: ras-grpc-gw
# description: gRPC gateway for 1C Remote Administration Server (CommandCenter1C fork)
# parent: v8platform/ras-grpc-gw
```

---

## Шаг 2: Клонирование форка

### Выбор директории

```bash
# Рекомендуемая структура:
# ~/projects/
#   ├── command-center-1c/      # Monorepo
#   └── ras-grpc-gw/            # Fork (отдельно)

# Создать директорию для проектов (если нет)
mkdir -p ~/projects
cd ~/projects
```

### Клонирование

**Вариант A: HTTPS (проще для начала):**
```bash
git clone https://github.com/command-center-1c/ras-grpc-gw.git
cd ras-grpc-gw
```

**Вариант B: SSH (быстрее, требует настройки ключей):**
```bash
git clone git@github.com:command-center-1c/ras-grpc-gw.git
cd ras-grpc-gw
```

**Вариант C: GitHub CLI (автоматически настраивает upstream):**
```bash
gh repo clone command-center-1c/ras-grpc-gw
cd ras-grpc-gw
```

### Проверка клонирования

```bash
# Проверить remote
git remote -v

# Expected output:
# origin  https://github.com/command-center-1c/ras-grpc-gw.git (fetch)
# origin  https://github.com/command-center-1c/ras-grpc-gw.git (push)

# Проверить ветку
git branch

# Expected output:
# * master

# Проверить коммиты
git log --oneline -n 5

# Expected output (upstream commits):
# d4b5b77 (HEAD -> master, origin/master) Last commit from upstream
# ...
```

---

## Шаг 3: Настройка upstream

Добавим upstream remote для возможности синхронизации с оригинальным репозиторием.

### Добавление upstream remote

```bash
# Добавить upstream
git remote add upstream https://github.com/v8platform/ras-grpc-gw.git

# Проверить remotes
git remote -v

# Expected output:
# origin    https://github.com/command-center-1c/ras-grpc-gw.git (fetch)
# origin    https://github.com/command-center-1c/ras-grpc-gw.git (push)
# upstream  https://github.com/v8platform/ras-grpc-gw.git (fetch)
# upstream  https://github.com/v8platform/ras-grpc-gw.git (push)
```

### Первичный fetch upstream

```bash
# Скачать refs из upstream
git fetch upstream

# Expected output:
# remote: Enumerating objects: 15, done.
# remote: Counting objects: 100% (15/15), done.
# ...
# From https://github.com/v8platform/ras-grpc-gw
#  * [new branch]      master     -> upstream/master
```

### Проверка синхронизации

```bash
# Сравнить fork с upstream
git log --oneline HEAD..upstream/master

# Expected output (если upstream не обновлялся с момента fork):
# (пусто)

# Это значит fork актуален с upstream
```

---

## Шаг 4: Копирование документации

Скопируем подготовленные документы из monorepo CommandCenter1C в fork.

### Структура документации в форке

```
ras-grpc-gw/
├── docs/
│   ├── FORK_AUDIT.md         # Audit upstream
│   ├── FORK_CHANGELOG.md     # История изменений форка
│   ├── UPSTREAM_SYNC.md      # Процедура синхронизации
│   ├── PRODUCTION_GUIDE.md   # Production deployment
│   └── CONTRIBUTING.md       # Development guidelines
└── README.md                 # Main README (обновим позже)
```

### Копирование файлов

```bash
# Убедитесь что находитесь в директории форка
cd ~/projects/ras-grpc-gw

# Создать директорию docs (если нет)
mkdir -p docs

# Скопировать документы из monorepo
cp ~/projects/command-center-1c/docs/fork-templates/FORK_AUDIT.md docs/
cp ~/projects/command-center-1c/docs/fork-templates/FORK_CHANGELOG.md docs/
cp ~/projects/command-center-1c/docs/fork-templates/UPSTREAM_SYNC.md docs/
cp ~/projects/command-center-1c/docs/fork-templates/PRODUCTION_GUIDE.md docs/
cp ~/projects/command-center-1c/docs/fork-templates/CONTRIBUTING.md docs/

# Проверить что файлы скопировались
ls -lh docs/

# Expected output:
# total 120K
# -rw-r--r-- 1 user user  15K Jan 17 10:00 CONTRIBUTING.md
# -rw-r--r-- 1 user user  25K Jan 17 10:00 FORK_AUDIT.md
# -rw-r--r-- 1 user user  18K Jan 17 10:00 FORK_CHANGELOG.md
# -rw-r--r-- 1 user user  30K Jan 17 10:00 PRODUCTION_GUIDE.md
# -rw-r--r-- 1 user user  20K Jan 17 10:00 UPSTREAM_SYNC.md
```

### Commit документации

```bash
# Добавить файлы в git
git add docs/

# Проверить что будет закоммичено
git status

# Expected output:
# On branch master
# Changes to be committed:
#   new file:   docs/CONTRIBUTING.md
#   new file:   docs/FORK_AUDIT.md
#   new file:   docs/FORK_CHANGELOG.md
#   new file:   docs/PRODUCTION_GUIDE.md
#   new file:   docs/UPSTREAM_SYNC.md

# Создать commit
git commit -m "docs: add fork documentation

Added comprehensive documentation for CommandCenter1C fork:
- FORK_AUDIT.md: upstream audit report
- FORK_CHANGELOG.md: fork change tracking
- UPSTREAM_SYNC.md: sync procedure
- PRODUCTION_GUIDE.md: production deployment guide
- CONTRIBUTING.md: development guidelines"

# Push в fork
git push origin master
```

### Проверка на GitHub

```bash
# Открыть fork в браузере
gh repo view command-center-1c/ras-grpc-gw --web

# Или вручную открыть:
# https://github.com/command-center-1c/ras-grpc-gw

# Проверить:
# - Папка docs/ существует
# - Все 5 файлов присутствуют
# - Commit "docs: add fork documentation" в истории
```

---

## Шаг 5: Настройка CI/CD

### Создание GitHub Actions workflows

```bash
# Создать директорию для workflows
mkdir -p .github/workflows
```

### Workflow 1: Continuous Integration

```bash
# Создать .github/workflows/ci.yml
cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
  push:
    branches: [master, main, develop]
  pull_request:
    branches: [master, main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24'

      - name: golangci-lint
        uses: golangci/golangci-lint-action@v4
        with:
          version: latest

  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24'

      - name: Run tests
        run: |
          go test -v -race -coverprofile=coverage.out ./...
          go tool cover -func=coverage.out

      - name: Check coverage
        run: |
          coverage=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | sed 's/%//')
          echo "Total coverage: ${coverage}%"
          if (( $(echo "$coverage < 70" | bc -l) )); then
            echo "Coverage ${coverage}% is below 70% threshold"
            exit 1
          fi

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.out

  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24'

      - name: Build
        run: go build -v ./cmd/...

      - name: Build Docker image
        run: docker build -t ras-grpc-gw:test .
EOF
```

### Workflow 2: Release

```bash
# Создать .github/workflows/release.yml
cat > .github/workflows/release.yml <<'EOF'
name: Release

on:
  push:
    tags:
      - 'v*-cc'

permissions:
  contents: write
  packages: write

jobs:
  release:
    name: Release
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24'

      - name: Run tests
        run: go test -v ./...

      - name: Run GoReleaser
        uses: goreleaser/goreleaser-action@v5
        with:
          distribution: goreleaser
          version: latest
          args: release --clean
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/command-center-1c/ras-grpc-gw:latest
            ghcr.io/command-center-1c/ras-grpc-gw:${{ github.ref_name }}
EOF
```

### Commit workflows

```bash
# Добавить workflows
git add .github/

# Commit
git commit -m "ci: add GitHub Actions workflows

Added CI/CD pipelines:
- ci.yml: lint, test (coverage > 70%), build
- release.yml: GoReleaser + Docker image publish"

# Push
git push origin master
```

### Проверка CI/CD

```bash
# Открыть Actions tab
gh repo view command-center-1c/ras-grpc-gw --web

# Перейти на вкладку "Actions"
# Должен запуститься workflow "CI" для commit workflows

# Ожидаемый результат:
# ✅ CI workflow завершён успешно (или с ожидаемыми ошибками если нет тестов)
```

### Настройка Branch Protection (рекомендуется)

```bash
# Настроить через UI:
# Settings → Branches → Add branch protection rule

# Или через GitHub CLI:
gh api repos/command-center-1c/ras-grpc-gw/branches/master/protection \
  --method PUT \
  --field 'required_status_checks[strict]=true' \
  --field 'required_status_checks[contexts][]=lint' \
  --field 'required_status_checks[contexts][]=test' \
  --field 'required_status_checks[contexts][]=build' \
  --field 'enforce_admins=true' \
  --field 'required_pull_request_reviews[required_approving_review_count]=1'
```

---

## Шаг 6: Первая синхронизация

Проверим процедуру синхронизации с upstream (должна показать что изменений нет).

### Проверка upstream обновлений

```bash
# Fetch upstream
git fetch upstream

# Проверить новые commits (не должно быть)
git log --oneline HEAD..upstream/master

# Expected output:
# (пусто)

# Если пусто - upstream не обновлялся с момента fork
# Это ожидаемо, т.к. upstream неактивен с 2021 года
```

### Документирование sync в логе

```bash
# Обновить UPSTREAM_SYNC.md с первой записью
cat >> docs/UPSTREAM_SYNC.md <<'EOF'

---

### $(date +%Y-%m-%d): Initial Fork Setup

**Action:** Fork created and initial setup completed
**Upstream Commit:** `d4b5b77` (2021-09-07)
**Upstream Version:** v0.1.0-beta
**Changes Synced:** None (initial state)
**Notes:**
- Fork created in command-center-1c organization
- Documentation added
- CI/CD configured
- No upstream activity since 2021

**Divergence:**
- Fork: 2 commits ahead (docs, ci), 0 commits behind
- Status: Setup complete, ready for development
EOF

# Commit sync log
git add docs/UPSTREAM_SYNC.md
git commit -m "docs: update sync log with initial setup"
git push origin master
```

---

## Шаг 7: Проверка готовности

### Checklist готовности форка

Проверьте что всё настроено корректно:

- [ ] **Fork создан** в `command-center-1c/ras-grpc-gw`
- [ ] **Локальная копия** клонирована в `~/projects/ras-grpc-gw`
- [ ] **Upstream remote** настроен и работает
- [ ] **Документация** скопирована в `docs/` (5 файлов)
- [ ] **CI/CD workflows** добавлены и работают
- [ ] **Branch protection** настроен (опционально)
- [ ] **Sync log** обновлён с initial setup

### Автоматическая проверка

```bash
#!/bin/bash
# check-fork-setup.sh

echo "=== Fork Setup Verification ==="
echo

# Check 1: Fork exists
echo "✓ Checking fork exists..."
gh repo view command-center-1c/ras-grpc-gw > /dev/null 2>&1 && \
  echo "  ✅ Fork exists" || \
  { echo "  ❌ Fork not found"; exit 1; }

# Check 2: Upstream remote
echo "✓ Checking upstream remote..."
git remote | grep upstream > /dev/null && \
  echo "  ✅ Upstream configured" || \
  { echo "  ❌ Upstream not configured"; exit 1; }

# Check 3: Documentation
echo "✓ Checking documentation..."
required_docs=(
  "docs/FORK_AUDIT.md"
  "docs/FORK_CHANGELOG.md"
  "docs/UPSTREAM_SYNC.md"
  "docs/PRODUCTION_GUIDE.md"
  "docs/CONTRIBUTING.md"
)
for doc in "${required_docs[@]}"; do
  if [ -f "$doc" ]; then
    echo "  ✅ $doc"
  else
    echo "  ❌ $doc missing"
    exit 1
  fi
done

# Check 4: CI/CD
echo "✓ Checking CI/CD workflows..."
[ -f ".github/workflows/ci.yml" ] && echo "  ✅ ci.yml" || { echo "  ❌ ci.yml missing"; exit 1; }
[ -f ".github/workflows/release.yml" ] && echo "  ✅ release.yml" || { echo "  ❌ release.yml missing"; exit 1; }

echo
echo "=== ✅ Fork setup verification PASSED ==="
```

**Запуск проверки:**
```bash
# Сохранить скрипт
curl -o check-fork-setup.sh https://raw.githubusercontent.com/command-center-1c/ras-grpc-gw/main/scripts/check-fork-setup.sh
chmod +x check-fork-setup.sh

# Запустить
./check-fork-setup.sh

# Expected output:
# === Fork Setup Verification ===
# ✓ Checking fork exists...
#   ✅ Fork exists
# ✓ Checking upstream remote...
#   ✅ Upstream configured
# ✓ Checking documentation...
#   ✅ docs/FORK_AUDIT.md
#   ✅ docs/FORK_CHANGELOG.md
#   ✅ docs/UPSTREAM_SYNC.md
#   ✅ docs/PRODUCTION_GUIDE.md
#   ✅ docs/CONTRIBUTING.md
# ✓ Checking CI/CD workflows...
#   ✅ ci.yml
#   ✅ release.yml
# === ✅ Fork setup verification PASSED ===
```

---

## Next Steps

### Сразу после setup

1. **Прочитать документацию:**
   ```bash
   # Ознакомиться с документами форка
   cat docs/FORK_AUDIT.md        # Понять текущее состояние upstream
   cat docs/CONTRIBUTING.md      # Изучить процесс разработки
   cat docs/PRODUCTION_GUIDE.md  # Узнать о deployment
   ```

2. **Настроить development окружение:**
   ```bash
   # Установить инструменты
   make install-tools

   # Установить зависимости
   make deps

   # Запустить тесты (если есть)
   make test
   ```

3. **Создать первую feature branch:**
   ```bash
   git checkout -b feature/setup-testing-infrastructure
   # ... начать работу над тестами ...
   ```

### Долгосрочный план (из FORK_CHANGELOG.md)

**Week 1-2: Foundation**
- [ ] Обновить Go dependencies (1.17 → 1.24)
- [ ] Добавить structured logging (zap)
- [ ] Реализовать graceful shutdown

**Week 3-4: Testing**
- [ ] Написать unit tests (coverage > 70%)
- [ ] Создать integration tests
- [ ] Настроить coverage reporting

**Week 5-6: Production Readiness**
- [ ] Добавить health checks (gRPC + HTTP)
- [ ] Реализовать Prometheus metrics
- [ ] Создать Docker образ

**Week 7-8: Deployment**
- [ ] Kubernetes manifests
- [ ] Load testing
- [ ] Production deployment

**Детальный план:** См. `docs/FORK_CHANGELOG.md` секция "Unreleased"

---

## Troubleshooting

### Проблема 1: Не могу создать fork в organization

**Симптомы:**
```
Error: You do not have permission to create repositories in command-center-1c
```

**Решение:**
1. Проверить membership:
   ```bash
   gh api /orgs/command-center-1c/members --jq '.[].login'
   ```
2. Если нет в списке - попросить owner добавить вас
3. Проверить настройки organization:
   - Settings → Member privileges → Repository creation: Allow members to create repositories

### Проблема 2: Git remote upstream не работает

**Симптомы:**
```
fatal: 'upstream' does not appear to be a git repository
```

**Решение:**
```bash
# Проверить remotes
git remote -v

# Если upstream нет - добавить
git remote add upstream https://github.com/v8platform/ras-grpc-gw.git

# Проверить что работает
git fetch upstream
```

### Проблема 3: CI workflow падает

**Симптомы:**
```
Error: golangci-lint: command not found
```

**Решение:**
1. Проверить версию Go в workflow:
   ```yaml
   # .github/workflows/ci.yml
   - name: Set up Go
     uses: actions/setup-go@v5
     with:
       go-version: '1.24'  # ✅ Правильная версия
   ```

2. Убедиться что используется правильный action:
   ```yaml
   - name: golangci-lint
     uses: golangci/golangci-lint-action@v4  # ✅ v4, не v3
   ```

### Проблема 4: Coverage check падает (нет тестов)

**Ожидаемо на начальном этапе** - upstream не имеет тестов.

**Временное решение:**
```yaml
# .github/workflows/ci.yml
# Закомментировать coverage check до написания тестов

- name: Check coverage
  if: false  # ⚠️ Временно отключено - нет тестов
  run: |
    coverage=$(go tool cover -func=coverage.out | grep total | awk '{print $3}' | sed 's/%//')
    # ...
```

**Постоянное решение:**
- Написать unit tests (см. `docs/CONTRIBUTING.md`)
- Достичь coverage > 70%
- Включить coverage check обратно

### Проблема 5: Не могу push в fork

**Симптомы:**
```
remote: Permission to command-center-1c/ras-grpc-gw.git denied to YOUR-USERNAME.
fatal: unable to access 'https://github.com/command-center-1c/ras-grpc-gw.git/': The requested URL returned error: 403
```

**Решение:**

**Вариант A: HTTPS authentication**
```bash
# Использовать GitHub token вместо пароля
gh auth login

# Или настроить credential helper
git config --global credential.helper cache
```

**Вариант B: Переключиться на SSH**
```bash
# Изменить remote на SSH
git remote set-url origin git@github.com:command-center-1c/ras-grpc-gw.git

# Проверить
git remote -v
```

---

## Summary

После выполнения всех шагов у вас должен быть:

```
✅ Fork создан: https://github.com/command-center-1c/ras-grpc-gw
✅ Локальная копия: ~/projects/ras-grpc-gw
✅ Upstream настроен: git remote upstream
✅ Документация добавлена: docs/*.md (5 файлов)
✅ CI/CD настроен: .github/workflows/*.yml (2 файла)
✅ Sync log обновлён: docs/UPSTREAM_SYNC.md
✅ Готов к разработке: можно создавать feature branches
```

**Следующий шаг:** Начать рефакторинг по плану из `docs/FORK_CHANGELOG.md`

**Вопросы?** См. `docs/CONTRIBUTING.md` → Questions section

---

## Appendix: Useful Commands

### Git Commands

```bash
# Синхронизация с upstream
git fetch upstream
git merge upstream/master

# Создание feature branch
git checkout -b feature/my-feature

# Обновление fork
git pull origin master
git push origin master

# Просмотр истории
git log --oneline --graph --all -n 20

# Сравнение с upstream
git diff upstream/master..HEAD
```

### GitHub CLI Commands

```bash
# Просмотр fork
gh repo view command-center-1c/ras-grpc-gw

# Открыть в браузере
gh repo view command-center-1c/ras-grpc-gw --web

# Создать PR
gh pr create --title "feat: my feature" --body "Description"

# Просмотр Actions runs
gh run list

# Просмотр конкретного run
gh run view <run-id>
```

### Makefile Commands (после настройки)

```bash
# Development
make build              # Собрать binary
make run                # Запустить локально
make test               # Запустить тесты
make lint               # Проверить code style

# CI/CD simulation
make ci                 # Запустить все CI проверки локально

# Documentation
make docs               # Сгенерировать godoc
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Next Review:** После первого использования (соберите feedback!)
**Maintainer:** CommandCenter1C Team
