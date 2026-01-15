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
| `restart-all.sh` | Перезапуск всех сервисов (есть `--makemigrations`) |
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

## Monitoring (Native mode)

Если вы работаете в native режиме (`USE_DOCKER=false`) и хотите, чтобы в UI (`/system-status`, `/service-mesh`)
корректно отображалась доступность внешних зависимостей (например, **RAS Server:1545**), используйте
**Prometheus + Blackbox Exporter** как единую точку ответственности.

Минимальный набор:
- Prometheus (9090)
- blackbox_exporter (9115)
- targets file: `/etc/prometheus/targets/blackbox_tcp.yml` (генерируется из `.env.local` → `RAS_SERVER_ADDR`)

Команды:
```bash
./scripts/dev/generate-blackbox-targets.sh
sudo mkdir -p /etc/prometheus/targets
sudo cp infrastructure/monitoring/prometheus/targets/blackbox_tcp.yml /etc/prometheus/targets/blackbox_tcp.yml
sudo systemctl restart prometheus
sudo systemctl restart blackbox-exporter
```

Автоматизация:
- `./scripts/dev/start-all.sh` (native mode) пытается синхронизировать `/etc/prometheus/*` и `/etc/blackbox_exporter/*`
  через `./scripts/dev/sync-native-monitoring.sh` (использует `sudo -n`, без запроса пароля).
- Если видите предупреждение про `sudo password required`, выполните `sudo -v` и повторите запуск,
  либо запустите `./scripts/dev/sync-native-monitoring.sh` вручную.

Установка/настройка мониторинга: `scripts/setup/install-monitoring.sh`, детали: `scripts/setup/README.md`.

Примечание (Arch Linux):
- бинарник обычно называется `prometheus-blackbox-exporter`
- unit файл проекта: `infrastructure/systemd/blackbox-exporter.service` запускает его через `blackbox-exporter.service`

## ITS (its.1c.ru) Scraper

Скрипт `scripts/dev/its-scrape.py` читает **отрендеренный** контент ITS из открытого Chromium (через CDP) и сохраняет
в JSON (для последующего парсинга/индексации).

Требования:
- Chromium в WSL с CDP: `chromium --remote-debugging-port=9222 --no-first-run "https://its.1c.ru/..." &`
- Ручной логин в браузере
- Python dependency: `pip install websockets`

Примеры:
```bash
# Сохранить текущую открытую страницу (имя файла автогенерируется из breadcrumbs + версии)
./scripts/dev/its-scrape.py --url-pattern "its.1c.ru/db/v8327doc"

# Сохранить с структурированными blocks (для более надежного парсинга)
./scripts/dev/its-scrape.py --with-blocks --no-raw-text

# Сохранить, используя полное breadcrumb-имя в filename
./scripts/dev/its-scrape.py --name-style full

# Пройти по оглавлению (TOC) и сохранить каждую посещенную страницу
./scripts/dev/its-scrape.py --crawl-toc --out-dir generated/its/crawl --no-raw-text --only-unique-docs
```

Импорт в UI:
- Откройте страницу `Settings → Driver Catalogs`.
- Вкладка `CLI` → `Import ITS JSON`.
- Загрузите JSON, сохраненный скриптом.
