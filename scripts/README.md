# CommandCenter1C Scripts

Утилиты и скрипты для разработки, деплоя и администрирования.

## Структура

```
scripts/
├── lib/           # Bash библиотеки (core, platform, prompts, files, services, build)
├── dev/           # Скрипты локальной разработки (start, stop, restart, logs)
├── setup/         # Установка и настройка окружения (install.sh, uninstall.sh)
├── django/        # Django-специфичные скрипты (migrations)
├── utils/         # Утилиты общего назначения
├── rollout/       # Скрипты деплоя (phases, rollback)
├── config/        # Генераторы конфигураций
└── build.sh       # Сборка проекта
```

## Быстрый старт

```bash
# Запуск всех сервисов
./scripts/dev/start-all.sh

# Проверка health
./scripts/dev/health-check.sh

# Просмотр логов
./scripts/dev/logs.sh <service>

# Остановка
./scripts/dev/stop-all.sh
```

## Библиотеки (lib/)

Унифицированные Bash библиотеки для всех скриптов:

```bash
# Подключение всех библиотек
source scripts/lib/init.sh

# Использование
log_info "Starting service..."
check_port 8180
```

Подробности: [lib/README.md](lib/README.md)

## Разработка (dev/)

| Скрипт | Назначение |
|--------|------------|
| `start-all.sh` | Запуск всех сервисов с автопересборкой |
| `stop-all.sh` | Остановка всех сервисов |
| `restart-all.sh` | Перезапуск всех сервисов |
| `restart.sh <svc>` | Перезапуск одного сервиса |
| `health-check.sh` | Проверка состояния сервисов |
| `logs.sh <svc>` | Просмотр логов сервиса |
| `debug-service.sh` | Запуск сервиса в debug режиме |

Подробности: [dev/README.md](dev/README.md)

## Django (django/)

| Скрипт | Назначение |
|--------|------------|
| `create_migrations.sh` | Создание миграций для apps |

## Utils (utils/)

| Скрипт | Назначение |
|--------|------------|
| `rollback-event-driven.sh` | Откат Event-Driven архитектуры |
| `generate_encryption_key.py` | Генерация ключа шифрования |

## Установка (setup/)

| Скрипт | Назначение |
|--------|------------|
| `install.sh` | Установка всех зависимостей |
| `uninstall.sh` | Удаление компонентов |
| `bootstrap.sh` | Первоначальная настройка |

Подробности: [setup/README.md](setup/README.md)

## Требования

- Bash 4.0+
- Linux / macOS / WSL
