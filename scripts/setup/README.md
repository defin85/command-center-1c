# Development Environment Setup

Автоматическая установка зависимостей для разработки CommandCenter1C.

## Быстрый старт

### Linux / WSL

```bash
./scripts/setup/install.sh
```

### Windows (PowerShell)

```powershell
.\scripts\setup\install.ps1
```

## Возможности

- **Автоматическое определение версий** — читает требуемые версии из файлов проекта:
  - Go: из `go-services/*/go.mod`
  - Python: по версии Django в `orchestrator/requirements.txt`
  - Node.js: по версии Vite в `frontend/package.json`
  - Или из `.tool-versions` (приоритетный источник)

- **Кроссплатформенность:**
  - Linux (Ubuntu, Debian, Fedora, Arch)
  - WSL (Windows Subsystem for Linux)
  - Windows (через winget или chocolatey)

- **Идемпотентность** — безопасный повторный запуск

- **Модульность** — возможность установки отдельных компонентов

## Опции

### Linux / WSL

```bash
./scripts/setup/install.sh [OPTIONS]

Options:
  --dry-run           Показать что будет установлено без изменений
  --only-go           Установить только Go
  --only-python       Установить только Python + venv
  --only-nodejs       Установить только Node.js + npm
  --only-docker       Установить только Docker
  --only-deps         Установить только зависимости проекта
  --skip-docker       Пропустить установку Docker
  --skip-deps         Пропустить установку зависимостей проекта
  --force             Принудительная переустановка
  --verbose, -v       Подробный вывод
  --help, -h          Показать справку
```

### Windows (PowerShell)

```powershell
.\scripts\setup\install.ps1 [OPTIONS]

Options:
  -DryRun             Показать что будет установлено без изменений
  -OnlyGo             Установить только Go
  -OnlyPython         Установить только Python
  -OnlyNodeJS         Установить только Node.js
  -OnlyDocker         Установить только Docker Desktop
  -OnlyDeps           Установить только зависимости проекта
  -SkipDocker         Пропустить установку Docker
  -SkipDeps           Пропустить установку зависимостей проекта
  -Force              Принудительная переустановка
```

## Примеры использования

### Проверить что будет установлено

```bash
# Linux/WSL
./scripts/setup/install.sh --dry-run

# Windows
.\scripts\setup\install.ps1 -DryRun
```

### Установить только Go и Python

```bash
# Linux/WSL
./scripts/setup/install.sh --only-go --only-python

# Windows
.\scripts\setup\install.ps1 -OnlyGo -OnlyPython
```

### Полная установка без Docker

```bash
# Linux/WSL
./scripts/setup/install.sh --skip-docker

# Windows
.\scripts\setup\install.ps1 -SkipDocker
```

## Управление версиями

### .tool-versions

Файл `.tool-versions` в корне проекта — единый источник правды для версий:

```
go 1.24.0
python 3.11
nodejs 20
```

Этот файл совместим с [asdf](https://asdf-vm.com) и [mise](https://mise.jdx.dev).

### Автоматическое определение

Если `.tool-versions` отсутствует, скрипт определяет версии из:

| Инструмент | Источник | Логика |
|------------|----------|--------|
| Go | `go-services/*/go.mod` | Максимальная версия из всех go.mod |
| Python | `orchestrator/requirements.txt` | По версии Django (4.x → 3.11, 5.x → 3.12) |
| Node.js | `frontend/package.json` | По версии Vite (5.x → 20, 6.x → 22) |

## Что устанавливается

### Системные пакеты (Linux)

- `build-essential` / `gcc` — компиляция
- `git`, `curl`, `wget` — утилиты
- `jq` — парсинг JSON
- `libpq-dev` — PostgreSQL клиент

### Runtime'ы

| Компонент | Linux | Windows |
|-----------|-------|---------|
| Go | Официальный бинарник в `/usr/local/go` | winget / choco |
| Python | apt (deadsnakes PPA) / dnf | winget / choco |
| Node.js | NodeSource репозиторий | winget / choco |
| Docker | docker-ce официальный | Docker Desktop |

### Зависимости проекта

- **Python:** venv + `pip install -r requirements.txt`
- **Node.js:** `npm ci` (или `npm install`)
- **Go:** `go mod download` для всех сервисов

## Структура

```
scripts/setup/
├── install.sh          # Entry point для Linux/WSL
├── install.ps1         # Entry point для Windows
├── README.md           # Эта документация
└── lib/
    ├── common.sh       # Общие функции (logging, version compare)
    ├── version-parser.sh   # Парсинг версий из проекта
    └── installers/     # (будущее) Отдельные установщики
```

## Troubleshooting

### Linux: Permission denied

```bash
chmod +x ./scripts/setup/install.sh
```

### Windows: Execution Policy

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### WSL: Docker не найден

Docker в WSL работает через Docker Desktop для Windows:

1. Установите [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. В настройках включите **WSL 2 integration**
3. Перезапустите WSL

### Go/Python/Node не найден после установки

Перезапустите терминал или выполните:

```bash
# Linux/WSL
source ~/.bashrc

# Windows PowerShell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
```

## После установки

```bash
# 1. Запустить инфраструктуру
docker compose up -d postgres redis

# 2. Применить миграции
./scripts/dev/run-migrations.sh

# 3. Запустить все сервисы
./scripts/dev/start-all.sh

# 4. Проверить статус
./scripts/dev/health-check.sh
```
