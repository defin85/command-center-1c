# Development Environment Setup

Автоматическая установка dev-окружения для CommandCenter1C с использованием **mise**.

## Быстрый старт

```bash
./scripts/setup/install.sh
```

Это установит:
- **mise** — универсальный менеджер версий runtime'ов
- **Go, Python, Node.js** — версии из `.tool-versions`
- **Docker** — платформо-зависимо
- **Зависимости проекта** — pip, npm, go mod

## Что такое mise?

[mise](https://mise.jdx.dev) (произносится "meez") — современный менеджер версий для dev-инструментов:

- Управляет Go, Python, Node.js и 100+ других инструментов
- Совместим с `.tool-versions` (asdf) и `.nvmrc`
- Автоматически переключает версии при входе в директорию
- Быстрее asdf в 10-100x (написан на Rust)

## Опции

```bash
./scripts/setup/install.sh [OPTIONS]

Options:
  --dry-run           Показать план без изменений
  --only-mise         Установить только mise + runtime'ы
  --only-docker       Установить только Docker
  --only-deps         Установить только зависимости проекта
  --skip-mise         Пропустить mise и runtime'ы
  --skip-docker       Пропустить Docker
  --skip-deps         Пропустить зависимости проекта
  --verbose, -v       Подробный вывод
  --help, -h          Показать справку
```

## Примеры

```bash
# Показать план установки
./scripts/setup/install.sh --dry-run

# Установить только mise и runtime'ы
./scripts/setup/install.sh --only-mise

# Всё кроме Docker (если уже установлен)
./scripts/setup/install.sh --skip-docker

# Только зависимости проекта (pip, npm, go mod)
./scripts/setup/install.sh --only-deps
```

## Поддерживаемые платформы

| Платформа | mise | Docker |
|-----------|------|--------|
| **Arch Linux** | pacman | pacman |
| **Ubuntu/Debian** | apt (официальный репо) | apt (официальный репо) |
| **Fedora** | dnf | dnf |
| **macOS** | Homebrew | Docker Desktop |
| **WSL** | зависит от дистрибутива | Docker Desktop (Windows) |

## Управление версиями

### .tool-versions

Файл `.tool-versions` в корне проекта — единый источник версий:

```
go 1.24.0
python 3.11
nodejs 20
```

После установки mise автоматически использует эти версии при входе в директорию проекта.

### Ручное управление через mise

```bash
# Показать текущие версии
mise current

# Установить инструменты из .tool-versions
mise install

# Установить конкретную версию
mise install go@1.24.0

# Глобально использовать версию
mise use -g go@1.24.0

# Обновить mise
mise self-update
```

## Структура файлов

```
scripts/setup/
├── install.sh          # Основной скрипт (~350 строк)
├── install.ps1         # Windows PowerShell (legacy)
├── README.md           # Эта документация
└── lib/
    └── docker.sh       # Docker установка (~250 строк)
```

## Troubleshooting

### mise не найден после установки

Перезапустите терминал или:

```bash
source ~/.bashrc  # или ~/.zshrc
```

### WSL: Docker не работает

Docker в WSL использует Docker Desktop из Windows:

1. Установите [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)
2. В настройках включите **WSL Integration** для вашего дистрибутива
3. Перезапустите WSL: `wsl --shutdown` (в PowerShell)

### Arch Linux: mise не в репозиториях

mise доступен в официальных репозиториях Arch Linux:

```bash
sudo pacman -S mise
```

Если пакет не найден, обновите базу данных:

```bash
sudo pacman -Sy
```

### Permission denied

```bash
chmod +x ./scripts/setup/install.sh
```

### Python venv не создаётся

В Arch Linux venv включен в пакет python. Если проблема сохраняется:

```bash
# Arch
sudo pacman -S python

# Ubuntu/Debian
sudo apt install python3-venv
```

## После установки

```bash
# 1. Перезапустите терминал
source ~/.bashrc

# 2. Проверьте версии
mise current

# 3. Запустите инфраструктуру
docker compose up -d postgres redis

# 4. Примените миграции
./scripts/dev/run-migrations.sh

# 5. Запустите все сервисы
./scripts/dev/start-all.sh

# 6. Проверьте статус
./scripts/dev/health-check.sh
```

## Миграция с предыдущей версии

Если вы использовали старый install.sh (без mise):

1. Удалите старые установки Go/Python/Node.js (опционально)
2. Запустите новый `./scripts/setup/install.sh`
3. mise автоматически установит правильные версии

Старые установки не конфликтуют — mise использует изолированные директории в `~/.local/share/mise/`.

## Ссылки

- [mise документация](https://mise.jdx.dev)
- [mise GitHub](https://github.com/jdx/mise)
- [Docker установка](https://docs.docker.com/engine/install/)
