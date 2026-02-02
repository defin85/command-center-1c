# CommandCenter1C - Setup Scripts

Полная автоматическая установка dev-окружения от нуля до работающей системы.

## Быстрый старт

```bash
# Клонировать репозиторий
git clone https://github.com/org/command-center-1c.git
cd command-center-1c

# Полная установка одной командой
./scripts/setup/bootstrap.sh

# Перезапустить терминал
source ~/.bashrc

# Запустить все сервисы
./scripts/dev/start-all.sh
```

## Что устанавливается

### Полная установка (`bootstrap.sh --full`)

| Компонент | Описание |
|-----------|----------|
| **Системные пакеты** | git, curl, wget, jq, ripgrep, fd, htop, build-essential |
| **PostgreSQL 15** | База данных + пользователь `commandcenter` + база `commandcenter` |
| **Redis 7** | Кеш и очередь задач |
| **MinIO** | S3-совместимое хранилище артефактов |
| **pgAdmin 4** | Web-интерфейс для управления PostgreSQL |
| **mise** | Менеджер версий для Go/Python/Node.js |
| **Go 1.24** | Backend сервисы |
| **Python 3.11** | Django Orchestrator |
| **Node.js 20** | Frontend (React) |
| **Prometheus** | Сбор метрик (опционально) |
| **Grafana** | Визуализация метрик (опционально) |
| **Exporters** | postgres_exporter, redis_exporter (опционально) |
| **Blackbox Exporter** | TCP/HTTP probes (RAS port monitoring) |

### Минимальная установка (`bootstrap.sh --minimal`)

Всё кроме мониторинга (Prometheus, Grafana, Exporters).

## Скрипты

### bootstrap.sh — Единая точка входа

```bash
./scripts/setup/bootstrap.sh [OPTIONS]

Режимы:
  --full              Полная установка (по умолчанию)
  --minimal           Без мониторинга

Фильтры:
  --system-only       Только системные пакеты
  --infra-only        Только PostgreSQL/Redis/MinIO
  --project-only      Только mise + зависимости
  --monitoring-only   Только мониторинг

Skip флаги:
  --skip-system       Пропустить системные пакеты
  --skip-infra        Пропустить PostgreSQL/Redis/MinIO
  --skip-project      Пропустить mise/deps
  --skip-monitoring   Пропустить мониторинг

Другие:
  --non-interactive   Без подтверждений (для CI/CD)
  --dry-run           Показать план без выполнения
  -v, --verbose       Подробный вывод
  -h, --help          Справка
```

### install-system.sh — Системные пакеты

```bash
./scripts/setup/install-system.sh [OPTIONS]

Options:
  --dry-run           Показать план без установки
  --skip-update       Не обновлять индекс пакетов
  -v, --verbose       Подробный вывод
```

Устанавливает: git, curl, wget, jq, ripgrep, fd, htop, tree, unzip, zip, openssh, base-devel

### install-infra.sh — PostgreSQL + Redis + MinIO + pgAdmin

```bash
./scripts/setup/install-infra.sh [OPTIONS]

Options:
  --only-postgres     Только PostgreSQL
  --only-redis        Только Redis
  --only-minio        Только MinIO
  --only-pgadmin      Только pgAdmin
  --skip-postgres     Пропустить PostgreSQL
  --skip-redis        Пропустить Redis
  --skip-minio        Пропустить MinIO
  --skip-pgadmin      Пропустить pgAdmin
  --dry-run           Показать план
```

PostgreSQL:
- Установка пакета
- Инициализация кластера (initdb)
- Настройка pg_hba.conf
- Создание пользователя и базы данных
- Автозапуск через systemd

pgAdmin 4:
- Установка пакета pgadmin4
- Web UI: http://127.0.0.1:5050
- Запуск: `pgadmin4`

### install-monitoring.sh — Мониторинг

```bash
./scripts/setup/install-monitoring.sh [OPTIONS]

Options:
  --only-prometheus   Только Prometheus
  --only-grafana      Только Grafana
  --only-exporters    Только exporters
  --skip-prometheus   Пропустить Prometheus
  --skip-grafana      Пропустить Grafana
  --skip-exporters    Пропустить exporters
  --skip-config       Не копировать конфиги
```

Компоненты:
- Prometheus (порт 9090)
- Grafana (порт 3000)
- node_exporter (порт 9100)
- blackbox_exporter (порт 9115)
- postgres_exporter (порт 9187)
- redis_exporter (порт 9121)

### install.sh — mise + зависимости проекта

```bash
./scripts/setup/install.sh [OPTIONS]

Options:
  --only-mise         Только mise + runtime'ы
  --only-docker       Только Docker
  --only-deps         Только pip/npm/go mod
  --skip-mise         Пропустить mise
  --skip-docker       Пропустить Docker
  --skip-deps         Пропустить зависимости
```

### verify.sh — Проверка установки

```bash
./scripts/setup/verify.sh [OPTIONS]

Options:
  --quick             Только критичные проверки
  --json              Вывод в JSON
  --fix               Попытаться исправить проблемы
```

Exit codes:
- 0 — все проверки прошли
- 1 — критичные ошибки (инфраструктура)
- 2 — некритичные ошибки (мониторинг)

## Поддерживаемые платформы

| Платформа | Пакетный менеджер | Статус |
|-----------|-------------------|--------|
| **Arch Linux** | pacman + yay (AUR) | ✅ Полная поддержка |
| **Ubuntu/Debian** | apt | ✅ Полная поддержка |
| **Fedora** | dnf | ⚠️ Базовая поддержка |
| **WSL** | зависит от дистрибутива | ✅ Полная поддержка |

## Структура файлов

```
scripts/setup/
├── bootstrap.sh          # Единая точка входа
├── install.sh            # mise + Go/Python/Node.js + deps
├── install-system.sh     # Системные пакеты
├── install-infra.sh      # PostgreSQL + Redis + MinIO + pgAdmin
├── install-monitoring.sh # Prometheus, Grafana, Exporters
├── install-exporters.sh  # Legacy (используется install-monitoring.sh)
├── verify.sh             # Проверка установки
├── uninstall.sh          # Удаление компонентов
├── README.md             # Эта документация
└── lib/
    ├── docker.sh         # Docker установка
    ├── offline.sh        # Офлайн режим
    └── postgres.sh       # PostgreSQL helpers
```

## Переменные окружения

Скрипты читают переменные из `.env.local`:

```bash
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_USER=commandcenter
DB_PASSWORD=commandcenter
DB_NAME=commandcenter

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=cc1c-artifacts
MINIO_SECURE=false
MINIO_DATA_DIR=/var/lib/minio
```

## Примеры использования

### Новый разработчик (с нуля)

```bash
./scripts/setup/bootstrap.sh
source ~/.bashrc
./scripts/dev/start-all.sh
```

### Только инфраструктура (PostgreSQL + Redis + MinIO)

```bash
./scripts/setup/bootstrap.sh --infra-only
```

### Добавить мониторинг позже

```bash
./scripts/setup/bootstrap.sh --monitoring-only
```

### CI/CD (без подтверждений)

```bash
./scripts/setup/bootstrap.sh --non-interactive --minimal
```

### Проверить что всё работает

```bash
./scripts/setup/verify.sh
```

### Исправить проблемы автоматически

```bash
./scripts/setup/verify.sh --fix
```

## Troubleshooting

### AUR helper не найден (Arch Linux)

```bash
# Установить yay
git clone https://aur.archlinux.org/yay.git
cd yay && makepkg -si
cd .. && rm -rf yay
```

### PostgreSQL: initdb не выполнен

```bash
# Arch Linux
sudo -u postgres initdb -D /var/lib/postgres/data
sudo systemctl start postgresql
```

### mise не активирован

```bash
source ~/.bashrc
# или
eval "$(mise activate bash)"
```

### Порт уже занят

```bash
# Проверить что использует порт
lsof -i :5432
lsof -i :6379

# Остановить конфликтующий процесс
sudo systemctl stop postgresql
sudo systemctl stop redis
```

## После установки

```bash
# 1. Перезапустите терминал
source ~/.bashrc

# 2. Проверьте версии
mise current

# 3. Запустите все сервисы
./scripts/dev/start-all.sh

# 4. Проверьте статус
./scripts/dev/health-check.sh

# 5. Откройте в браузере
# Frontend: http://localhost:15173
# Admin: http://localhost:8200/admin (admin / p-123456)
# pgAdmin: http://localhost:5050 (запустите: pgadmin4)
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin / admin)
```

## Ссылки

- [mise документация](https://mise.jdx.dev)
- [PostgreSQL](https://www.postgresql.org/docs/)
- [pgAdmin](https://www.pgadmin.org/docs/)
- [Redis](https://redis.io/docs/)
- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)

---

**Версия:** 2.0.0
**Обновлено:** 2025-12-02
MinIO:
- Установка пакета (AUR: minio)
- Настройка systemd unit + env
- Каталог данных: `/var/lib/minio`
- Health: http://localhost:9000/minio/health/ready
- Автосоздание бакета `cc1c-artifacts` (через `mc`, если доступен)
