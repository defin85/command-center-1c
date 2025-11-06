# CommandCenter1C - Restart All Guide

> Детальное руководство по использованию скрипта `scripts/dev/restart-all.sh`

---

## Обзор

**restart-all.sh** - умный скрипт для перезапуска всех сервисов CommandCenter1C с автоматическим определением изменений в Go коде и выборочной пересборкой.

**Основные возможности:**
- ✅ Автоматическое определение изменений в Go исходниках
- ✅ Выборочная пересборка только измененных сервисов
- ✅ Поддержка shared/ модулей (пересборка всех зависимых сервисов)
- ✅ Принудительная пересборка всех сервисов
- ✅ Режим "только перезапуск" (без проверки изменений)
- ✅ Перезапуск одного сервиса
- ✅ Параллельная сборка (ускорение на multi-core CPU)
- ✅ Verbose режим для отладки

**Решаемая проблема:**
- Windows Firewall запрашивает разрешение при каждом `go run` → используются собранные бинарники
- Автоматическая пересборка только при изменении кода → экономия времени

---

## Быстрый старт

### Базовое использование

```bash
# Smart restart (автоопределение изменений)
./scripts/dev/restart-all.sh

# Принудительная пересборка всех Go сервисов
./scripts/dev/restart-all.sh --force-rebuild

# Только перезапуск, без пересборки
./scripts/dev/restart-all.sh --no-rebuild

# Перезапуск одного сервиса
./scripts/dev/restart-all.sh --service=api-gateway

# Dry-run режим (посмотреть что будет выполнено)
./scripts/dev/restart-all.sh --dry-run

# Verbose режим (детальный вывод)
./scripts/dev/restart-all.sh --verbose
```

---

## Алгоритм работы

### 1. Smart Restart (по умолчанию)

**Шаги:**

1. **Проверка изменений** для каждого Go сервиса:
   ```
   FOR каждый сервис in (api-gateway, worker, cluster-service, batch-service):
       IF бинарник НЕ существует:
           → REBUILD_NEEDED
       ELSE IF самый новый .go файл НОВЕЕ бинарника:
           → REBUILD_NEEDED
       ELSE IF shared/ модули НОВЕЕ бинарника:
           → REBUILD_NEEDED (ВСЕ СЕРВИСЫ!)
       ELSE:
           → UP_TO_DATE (пересборка не требуется)
   ```

2. **Пересборка** (если нужна):
   - Если изменился **только 1 сервис** → пересобрать только его (`build.sh --service=<name>`)
   - Если изменилось **несколько сервисов** → пересобрать все (`build.sh`)
   - Если изменился **shared/** → пересобрать ВСЕ сервисы

3. **Остановка** всех сервисов (`stop-all.sh`)

4. **Запуск** всех сервисов (`start-all.sh`)

5. **Итоговая сводка** - показать какие сервисы пересобраны

---

### 2. Force Rebuild

```bash
./scripts/dev/restart-all.sh --force-rebuild
```

**Алгоритм:**
1. Пропустить проверку изменений
2. Пересобрать **все** Go сервисы (`build.sh`)
3. Остановить все сервисы
4. Запустить все сервисы

**Use case:**
- После обновления Go версии
- После изменения build flags в `build.sh`
- После pull из git (много изменений)

---

### 3. No Rebuild

```bash
./scripts/dev/restart-all.sh --no-rebuild
```

**Алгоритм:**
1. Пропустить проверку изменений
2. Пропустить пересборку
3. Остановить все сервисы
4. Запустить все сервисы

**Use case:**
- Изменения только в Python/Django коде
- Изменения только в Frontend (React)
- Нужно просто перезапустить сервисы (например, после изменения .env)

---

### 4. Single Service Restart

```bash
./scripts/dev/restart-all.sh --service=api-gateway
```

**Алгоритм:**
1. Проверить изменения **только** для указанного сервиса
2. Пересобрать (если нужно)
3. Остановить **только** указанный сервис (`restart.sh <service>`)
4. Запустить **только** указанный сервис

**Доступные сервисы:**
- `orchestrator` (Django)
- `celery-worker` (Celery)
- `celery-beat` (Celery)
- `api-gateway` (Go)
- `worker` (Go)
- `cluster-service` (Go)
- `batch-service` (Go)
- `ras-grpc-gw` (Go, внешний)
- `frontend` (React)

**Use case:**
- Изменения только в одном сервисе
- Быстрый перезапуск для тестирования

---

## Режимы работы

### Parallel Build

```bash
./scripts/dev/restart-all.sh --parallel-build
```

**Описание:**
- Включает параллельную компиляцию Go сервисов
- Передает флаг `--parallel` в `build.sh`
- Ускоряет сборку на multi-core CPU (2-4x)

**Рекомендация:**
- Использовать при первой сборке проекта
- Использовать при `--force-rebuild` (пересборка всех сервисов)
- НЕ использовать при сборке одного сервиса (нет эффекта)

---

### Dry-Run Mode

```bash
./scripts/dev/restart-all.sh --dry-run
```

**Описание:**
- Показывает что будет выполнено, БЕЗ реального выполнения
- Полезно для проверки перед коммитом
- Комбинируется с `--verbose` для детального вывода

**Пример вывода:**
```
Проверка изменений в Go коде...

[1/4] Проверка api-gateway...
⚠️ Обнаружены изменения → требуется пересборка

[2/4] Проверка worker...
✓ Бинарник актуален → пересборка не требуется

...

[DRY-RUN] Пересборка пропущена (--dry-run)
  [DRY-RUN] Будет пересобран: api-gateway

[DRY-RUN] Перезапуск всех сервисов пропущен (--dry-run)
```

---

### Verbose Mode

```bash
./scripts/dev/restart-all.sh --verbose
```

**Описание:**
- Детальный вывод для отладки
- Показывает проверяемые пути, timestamps, решения

**Пример вывода:**
```
[VERBOSE] Параметры:
[VERBOSE]   FORCE_REBUILD: false
[VERBOSE]   NO_REBUILD: false
[VERBOSE]   SINGLE_SERVICE:
[VERBOSE]
[VERBOSE] Проверка изменений для сервиса: api-gateway
[VERBOSE]   Директория: /c/1CProject/command-center-1c/go-services/api-gateway
[VERBOSE]   Бинарник: /c/1CProject/command-center-1c/bin/cc1c-api-gateway.exe
[VERBOSE]   Самый новый .go файл: /c/.../cmd/main.go
[VERBOSE]   Исходники новее бинарника -> REBUILD_NEEDED
```

**Use case:**
- Отладка проблем с определением изменений
- Проверка что shared/ корректно обрабатывается
- Понимание почему сервис пересобирается/пропускается

---

## Примеры сценариев

### Сценарий 1: Ежедневная разработка

**Ситуация:** Изменил код в `go-services/api-gateway/internal/handlers/databases.go`

```bash
# 1. Smart restart (автоопределит изменения в api-gateway)
./scripts/dev/restart-all.sh

# Вывод:
# [1/4] Проверка api-gateway...
# ⚠️ Обнаружены изменения → требуется пересборка
# [2/4] Проверка worker...
# ✓ Бинарник актуален → пересборка не требуется
# ...
# Пересборка сервиса: api-gateway
# ...
# ✓ Все сервисы запущены
```

---

### Сценарий 2: Изменение shared/ модуля

**Ситуация:** Изменил код в `go-services/shared/auth/jwt.go`

```bash
# Smart restart автоопределит изменения в shared/
./scripts/dev/restart-all.sh

# Вывод:
# ...
# Проверка shared/ модулей...
# ⚠️ Обнаружены изменения в shared/ модулях
#    Все Go сервисы будут пересобраны
#
# Пересборка сервисов: api-gateway worker cluster-service batch-service
# ...
```

**Почему все сервисы?**
- Все Go сервисы зависят от `shared/` модулей
- Изменение в `shared/` требует пересборки всех зависимых

---

### Сценарий 3: Только Django изменения

**Ситуация:** Изменил код в `orchestrator/apps/databases/views.py`

```bash
# Пересборка Go не нужна - используем --no-rebuild
./scripts/dev/restart-all.sh --no-rebuild

# Или только перезапустить orchestrator
./scripts/dev/restart-all.sh --service=orchestrator --no-rebuild
```

---

### Сценарий 4: После git pull

**Ситуация:** `git pull` принес изменения в нескольких Go сервисах

```bash
# Принудительная пересборка всех (на всякий случай)
./scripts/dev/restart-all.sh --force-rebuild --parallel-build

# --parallel-build ускорит компиляцию
```

---

### Сценарий 5: Быстрое тестирование одного сервиса

**Ситуация:** Изменил код в `go-services/worker/internal/processor/odata.go`

```bash
# Перезапустить только worker
./scripts/dev/restart-all.sh --service=worker

# Вывод:
# Проверка изменений для worker...
# ⚠️ Обнаружены изменения → требуется пересборка
#
# Пересборка worker перед перезапуском...
# ...
# ✓ Сервис worker успешно перезапущен
```

---

## Логика определения изменений

### Алгоритм сравнения timestamps

**Для каждого Go сервиса:**

```bash
# 1. Проверить существование бинарника
IF bin/cc1c-<service>.exe НЕ существует:
    → REBUILD_NEEDED

# 2. Найти самый новый .go файл в директории сервиса
newest_source = find go-services/<service> -name "*.go" | самый новый

# 3. Сравнить timestamps (используется bash оператор -nt "newer than")
IF newest_source НОВЕЕ бинарника:
    → REBUILD_NEEDED

# 4. Проверить shared/ модули
newest_shared = find go-services/shared -name "*.go" | самый новый

IF newest_shared НОВЕЕ бинарника:
    → REBUILD_NEEDED

# 5. Всё актуально
→ UP_TO_DATE
```

**Используемые команды:**
- `find <dir> -name "*.go" -type f -printf '%T@ %p\n'` - найти файлы с timestamps
- `sort -rn | head -1` - выбрать самый новый
- `[ "$file1" -nt "$file2" ]` - сравнить timestamps (bash встроенный)

---

### Обработка shared/ модулей

**Проблема:**
- Все Go сервисы зависят от `go-services/shared/` модулей
- Изменение в `shared/` требует пересборки **всех** сервисов

**Решение:**

```bash
# После проверки всех сервисов:
IF есть изменения в shared/:
    # Найти ЛЮБОЙ существующий бинарник
    any_binary = first(bin/cc1c-*.exe)

    IF shared/ НОВЕЕ any_binary:
        # Пересобрать ВСЕ сервисы
        REBUILD_SERVICES = (api-gateway, worker, cluster-service, batch-service)
        SKIPPED_SERVICES = ()
```

**Обоснование:**
- Если `shared/` изменился ПОСЛЕ сборки любого бинарника, значит **все** бинарники устарели
- Не важно какой бинарник проверять - результат одинаковый

---

## Флаги и опции

### Полный список

| Флаг | Описание | Значение по умолчанию |
|------|----------|----------------------|
| `--help` | Показать справку | - |
| `--force-rebuild` | Принудительно пересобрать все Go сервисы | false |
| `--no-rebuild` | Только перезапуск, без проверки/пересборки | false |
| `--parallel-build` | Параллельная пересборка (через build.sh --parallel) | false |
| `--service=<name>` | Перезапустить только один сервис | "" (все сервисы) |
| `--verbose` | Детальный вывод для отладки | false |
| `--dry-run` | Показать что будет выполнено, без реального выполнения | false |

---

### Валидация флагов

**Конфликтующие флаги:**
- `--force-rebuild` и `--no-rebuild` **несовместимы**
  ```bash
  ./scripts/dev/restart-all.sh --force-rebuild --no-rebuild
  # Ошибка: Флаги --force-rebuild и --no-rebuild несовместимы
  ```

**Валидация сервисов:**
- `--service=<name>` проверяется на существование
  ```bash
  ./scripts/dev/restart-all.sh --service=nonexistent
  # Ошибка: Неизвестный сервис 'nonexistent'
  # Доступные сервисы: orchestrator celery-worker celery-beat api-gateway ...
  ```

---

## Troubleshooting

### Проблема 1: Сервис пересобирается постоянно

**Симптомы:**
```bash
./scripts/dev/restart-all.sh
# [1/4] Проверка api-gateway...
# ⚠️ Обнаружены изменения → требуется пересборка

./scripts/dev/restart-all.sh
# [1/4] Проверка api-gateway...
# ⚠️ Обнаружены изменения → требуется пересборка  <-- Опять!
```

**Причины:**
1. **Timestamps файлов изменяются при сборке** (редко, но бывает)
2. **Git меняет timestamps при checkout/pull**
3. **IDE меняет timestamps при автосохранении**

**Решение:**

```bash
# Проверить timestamps вручную (verbose режим)
./scripts/dev/restart-all.sh --verbose --dry-run

# Вывод покажет:
# [VERBOSE] Самый новый .go файл: /c/.../cmd/main.go
# [VERBOSE] Исходники новее бинарника -> REBUILD_NEEDED

# Проверить timestamps вручную
ls -la bin/cc1c-api-gateway.exe
ls -la go-services/api-gateway/cmd/main.go

# Если timestamps действительно отличаются - это нормально
# Если timestamps одинаковые - это баг, сообщить разработчикам
```

**Workaround:**
```bash
# Использовать --no-rebuild если точно знаете что пересборка не нужна
./scripts/dev/restart-all.sh --no-rebuild
```

---

### Проблема 2: Ошибка "Бинарник не найден, используется 'go run'"

**Симптомы:**
```bash
./scripts/dev/restart-all.sh
# ...
# [6/11] Запуск API Gateway (port 8080)...
#    Бинарник не найден, используется 'go run'
#    Совет: Запустите 'make build-go-all' или './scripts/build.sh'
```

**Причина:**
- Бинарник `bin/cc1c-api-gateway.exe` не был собран
- Скрипт пропустил пересборку (или она упала с ошибкой)

**Решение:**

```bash
# Принудительно пересобрать все
./scripts/dev/restart-all.sh --force-rebuild

# Или собрать вручную
./scripts/build.sh

# Проверить что бинарники появились
ls -la bin/
```

---

### Проблема 3: Ошибка "Ошибка при пересборке сервиса"

**Симптомы:**
```bash
./scripts/dev/restart-all.sh
# ...
# Пересборка сервиса: api-gateway
# ...
# ✗ Ошибка при пересборке сервиса api-gateway
```

**Причины:**
1. **Синтаксическая ошибка в Go коде**
2. **Отсутствуют зависимости** (не выполнен `go mod download`)
3. **Неправильная версия Go** (требуется 1.21+)

**Решение:**

```bash
# Проверить ошибки вручную
cd go-services/api-gateway
go build -o ../../bin/cc1c-api-gateway.exe ./cmd/main.go

# Исправить ошибки в коде
# Затем повторить restart-all.sh
```

---

### Проблема 4: shared/ изменился, но не все сервисы пересобрались

**Симптомы:**
```bash
# Изменил go-services/shared/auth/jwt.go
./scripts/dev/restart-all.sh

# Проверка shared/ модулей...
# ✓ shared/ модули актуальны  <-- Неправильно!
```

**Причина:**
- Баг в логике определения изменений shared/ (редко)
- Timestamps файлов некорректны

**Решение:**

```bash
# Использовать --force-rebuild
./scripts/dev/restart-all.sh --force-rebuild

# Или пересобрать вручную
./scripts/build.sh

# Сообщить разработчикам о баге (с выводом --verbose)
./scripts/dev/restart-all.sh --verbose --dry-run > debug.log
```

---

### Проблема 5: Скрипт падает с ошибкой "set -e"

**Симптомы:**
```bash
./scripts/dev/restart-all.sh
# ...
# (скрипт прерывается без понятной ошибки)
```

**Причина:**
- `set -e` прерывает выполнение при любой ошибке
- Ошибка может быть в зависимых скриптах (stop-all.sh, start-all.sh)

**Решение:**

```bash
# Запустить с verbose для отладки
./scripts/dev/restart-all.sh --verbose

# Проверить зависимые скрипты вручную
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh

# Проверить логи сервисов
./scripts/dev/logs.sh all
```

---

## Интеграция с другими скриптами

### Зависимости

**restart-all.sh зависит от:**

1. **build.sh** - сборка Go бинарников
   - Вызов: `bash $PROJECT_ROOT/scripts/build.sh [--service=<name>] [--parallel]`
   - Проверка существования: есть (строка 302)

2. **stop-all.sh** - остановка всех сервисов
   - Вызов: `bash $SCRIPTS_DIR/stop-all.sh`
   - Проверка существования: нужна (TODO)

3. **start-all.sh** - запуск всех сервисов
   - Вызов: `bash $SCRIPTS_DIR/start-all.sh`
   - Проверка существования: нужна (TODO)

4. **restart.sh** - перезапуск одного сервиса
   - Вызов: `bash $SCRIPTS_DIR/restart.sh <service>`
   - Проверка существования: нужна (TODO)

---

### Переиспользование

**restart-all.sh переиспользует:**
- Функции из build.sh (через вызов скрипта)
- Логику start-all.sh для запуска сервисов
- Логику stop-all.sh для остановки сервисов

**НЕ дублирует:**
- Команды запуска сервисов (используется start-all.sh)
- Команды остановки сервисов (используется stop-all.sh)
- Логику сборки (используется build.sh)

---

## Дополнительные материалы

**Связанная документация:**
- [LOCAL_DEVELOPMENT_GUIDE.md](LOCAL_DEVELOPMENT_GUIDE.md) - полное руководство по локальной разработке
- [BUILD_SYSTEM.md](BUILD_SYSTEM.md) - детали build системы (naming, версионирование)
- [CLAUDE.md](../CLAUDE.md) - инструкции для AI агентов (Quick Start секция)

**Связанные скрипты:**
- `scripts/build.sh` - централизованная сборка Go бинарников
- `scripts/dev/start-all.sh` - запуск всех сервисов
- `scripts/dev/stop-all.sh` - остановка всех сервисов
- `scripts/dev/restart.sh` - перезапуск одного сервиса
- `scripts/dev/health-check.sh` - проверка статуса сервисов

---

## FAQ

### Q: Когда использовать restart-all.sh vs restart.sh?

**A:**
- `restart-all.sh` - когда изменился **один или несколько** Go сервисов, или нужно перезапустить **все** сервисы
- `restart.sh <service>` - когда изменился **только один** конкретный сервис (Python/React/Go)

**Преимущества restart-all.sh:**
- Автоматическое определение изменений в Go коде
- Умная пересборка (только измененные сервисы)
- Обработка shared/ зависимостей
- Итоговая сводка (что пересобрано)

---

### Q: Почему при изменении shared/ пересобираются ВСЕ сервисы?

**A:** Все Go сервисы зависят от `go-services/shared/` модулей:
- `shared/auth` - JWT токены, middleware
- `shared/logger` - логирование
- `shared/config` - конфигурация
- `shared/models` - общие модели данных

Изменение в любом из этих модулей требует пересборки всех зависимых сервисов (api-gateway, worker, cluster-service, batch-service).

---

### Q: Можно ли пропустить пересборку если точно знаю что она не нужна?

**A:** Да, используйте `--no-rebuild`:
```bash
./scripts/dev/restart-all.sh --no-rebuild
```

**Use cases:**
- Изменения только в Python/Django коде
- Изменения только в React коде
- Изменения в .env файлах
- Нужно просто перезапустить сервисы

---

### Q: Как ускорить пересборку?

**A:** Используйте `--parallel-build`:
```bash
./scripts/dev/restart-all.sh --parallel-build
```

Это передаст флаг `--parallel` в `build.sh`, который соберет все Go сервисы параллельно (2-4x ускорение на multi-core CPU).

---

### Q: Как посмотреть что будет выполнено БЕЗ реального выполнения?

**A:** Используйте `--dry-run`:
```bash
./scripts/dev/restart-all.sh --dry-run
```

Это покажет:
- Какие сервисы будут пересобраны
- Какие сервисы будут пропущены
- НО не выполнит реальную пересборку и перезапуск

---

### Q: Почему бинарник считается устаревшим если я ничего не менял?

**A:** Возможные причины:
1. **Git изменил timestamps при checkout/pull**
2. **IDE автосохранил файлы** (изменил timestamps)
3. **Файлы были изменены другим процессом**

**Проверка:**
```bash
./scripts/dev/restart-all.sh --verbose --dry-run
```

Посмотрите в выводе timestamps файлов. Если действительно изменились - это нормально.

**Workaround:**
```bash
./scripts/dev/restart-all.sh --no-rebuild
```

---

## Версия

**Документ:** v1.0
**Дата:** 2025-11-06
**Автор:** CommandCenter1C Team
**Статус:** Production Ready (после применения патчей)

---

## Changelog

### v1.0 (2025-11-06)
- Первая версия документации
- Описание алгоритма Smart Restart
- Примеры использования всех флагов
- Troubleshooting секция
- FAQ секция
