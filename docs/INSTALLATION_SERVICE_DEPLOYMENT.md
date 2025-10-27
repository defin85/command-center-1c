# Installation Service - Deployment Guide

**Проект:** CommandCenter1C
**Версия:** 1.0
**Дата:** 2025-10-27

---

## Обзор

Полное руководство по deployment Installation Service в production окружение для автоматизации установки OData расширений на 700 баз 1С:Бухгалтерия 3.0.

---

## Предварительные требования

### Infrastructure

**Windows Server для Installation Service:**
- Windows Server 2022 (рекомендуется) или Windows Server 2019
- Платформа 1С 8.3.x установлена (8.3.23.1912 или новее)
- .NET Framework 4.7.2+ (для NSSM)
- Минимум 4 CPU cores
- Минимум 8 GB RAM
- SSD диск для логов

**Linux Server для Orchestrator и Frontend:**
- Ubuntu 20.04 LTS / CentOS 8 / Debian 11
- Docker 20.10+ (для Redis, PostgreSQL)
- Python 3.11+ для Django
- Node.js 18+ для Frontend
- Минимум 4 CPU cores
- Минимум 16 GB RAM

**Network Requirements:**
- Windows Server → Redis (порт 6379)
- Windows Server → 1C Server (порт 1541)
- Windows Server → Django API (порт 8000)
- Frontend Server → Django API (порт 8000)
- Все серверы в одной локальной сети (низкая latency)

### Software Dependencies

**Windows Server:**
- Go 1.21+ (для сборки, опционально)
- Git (для версионирования)
- NSSM (для Windows Service)

**Linux Server:**
- Docker + Docker Compose
- PostgreSQL 15 client tools
- Redis 7 client tools
- Nginx (для Frontend)

---

## Deployment Architecture

```
┌─────────────────── LINUX INFRASTRUCTURE ───────────────────┐
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Frontend │    │ Django   │    │  Redis   │             │
│  │  (Nginx) │◄───┤Orchestrator├──►│  Queue   │             │
│  │  :80     │    │  :8000   │    │  :6379   │             │
│  └──────────┘    └──────────┘    └─────┬────┘             │
│                                         │                   │
└─────────────────────────────────────────┼──────────────────┘
                                          │ Redis Protocol
┌─────────────────────────────────────────▼──────────────────┐
│                   WINDOWS SERVER 2022                       │
│                                                              │
│  ┌────────────────────────────────────────────────┐        │
│  │    Installation Service (Windows Service)      │        │
│  │             Port :5555 (Health Check)           │        │
│  └────────────────────────┬───────────────────────┘        │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────┐        │
│  │            1C Server (SQL Bases)                │        │
│  │        700 Bases: Base001 - Base700             │        │
│  └────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Steps

### 1. PostgreSQL и Redis Deployment

**На Linux Server:**

```bash
# 1. Создать директории
sudo mkdir -p /opt/commandcenter/{postgres,redis}
sudo mkdir -p /var/log/commandcenter

# 2. Создать docker-compose.yml
cat > /opt/commandcenter/docker-compose.yml <<'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: cc_postgres
    environment:
      POSTGRES_DB: commandcenter
      POSTGRES_USER: cc_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - /opt/commandcenter/postgres:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cc_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    container_name: cc_redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - /opt/commandcenter/redis:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
EOF

# 3. Создать .env файл
cat > /opt/commandcenter/.env <<'EOF'
POSTGRES_PASSWORD=your_secure_postgres_password
REDIS_PASSWORD=your_secure_redis_password
EOF

# 4. Запустить контейнеры
cd /opt/commandcenter
docker-compose up -d

# 5. Проверить статус
docker-compose ps
docker-compose logs -f
```

**Проверка:**
```bash
# PostgreSQL
psql -h localhost -U cc_user -d commandcenter -c "SELECT 1"

# Redis
redis-cli -h localhost -a your_secure_redis_password PING
```

---

### 2. Django Orchestrator Deployment

#### 2.1. Подготовка кода

```bash
# На development машине
cd command-center-1c/orchestrator

# Создать requirements-prod.txt (без dev зависимостей)
cat > requirements-prod.txt <<'EOF'
Django==4.2.8
djangorestframework==3.14.0
celery==5.3.4
redis==5.0.1
psycopg2-binary==2.9.9
gunicorn==21.2.0
python-dotenv==1.0.0
cryptography==41.0.7
EOF

# Собрать статические файлы
python manage.py collectstatic --noinput
```

#### 2.2. Деплой на сервер

```bash
# На Linux Server
sudo mkdir -p /opt/commandcenter/orchestrator
sudo chown $USER:$USER /opt/commandcenter/orchestrator

# Копировать код на сервер (через git или rsync)
# Вариант 1: Git
cd /opt/commandcenter
git clone https://github.com/your-org/command-center-1c.git
cd command-center-1c/orchestrator

# Вариант 2: rsync (с development машины)
rsync -avz --exclude='*.pyc' --exclude='__pycache__' \
  orchestrator/ user@linux-server:/opt/commandcenter/orchestrator/

# Создать виртуальное окружение
cd /opt/commandcenter/orchestrator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-prod.txt

# Создать .env файл
cat > .env <<'EOF'
DJANGO_SECRET_KEY=your_very_long_random_secret_key_here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=orchestrator.local,10.0.1.51
DATABASE_URL=postgresql://cc_user:your_secure_postgres_password@localhost:5432/commandcenter
REDIS_URL=redis://:your_secure_redis_password@localhost:6379/0
CELERY_BROKER_URL=redis://:your_secure_redis_password@localhost:6379/0
INSTALLATION_SERVICE_TOKEN=your_installation_service_token_here
EOF

# Применить миграции
python manage.py migrate

# Создать superuser
python manage.py createsuperuser

# Собрать статику
python manage.py collectstatic --noinput
```

#### 2.3. Настройка systemd для Django

```bash
# Создать systemd unit для Gunicorn
sudo cat > /etc/systemd/system/orchestrator.service <<'EOF'
[Unit]
Description=CommandCenter Django Orchestrator
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=commandcenter
Group=commandcenter
WorkingDirectory=/opt/commandcenter/orchestrator
Environment="PATH=/opt/commandcenter/orchestrator/venv/bin"
ExecStart=/opt/commandcenter/orchestrator/venv/bin/gunicorn \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/commandcenter/gunicorn-access.log \
  --error-logfile /var/log/commandcenter/gunicorn-error.log \
  orchestrator.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Создать пользователя
sudo useradd -r -s /bin/false commandcenter
sudo chown -R commandcenter:commandcenter /opt/commandcenter/orchestrator

# Запустить сервис
sudo systemctl daemon-reload
sudo systemctl enable orchestrator.service
sudo systemctl start orchestrator.service

# Проверить статус
sudo systemctl status orchestrator.service
```

#### 2.4. Настройка Celery Worker

```bash
# Создать systemd unit для Celery Worker
sudo cat > /etc/systemd/system/celery-worker.service <<'EOF'
[Unit]
Description=CommandCenter Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=commandcenter
Group=commandcenter
WorkingDirectory=/opt/commandcenter/orchestrator
Environment="PATH=/opt/commandcenter/orchestrator/venv/bin"
ExecStart=/opt/commandcenter/orchestrator/venv/bin/celery -A orchestrator worker \
  --loglevel=info \
  --concurrency=4 \
  --logfile=/var/log/commandcenter/celery-worker.log \
  --pidfile=/var/run/celery/worker.pid
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Создать директорию для PID
sudo mkdir -p /var/run/celery
sudo chown commandcenter:commandcenter /var/run/celery

# Запустить Celery Worker
sudo systemctl daemon-reload
sudo systemctl enable celery-worker.service
sudo systemctl start celery-worker.service

# Проверить статус
sudo systemctl status celery-worker.service
```

**Проверка:**
```bash
# Проверить health endpoint
curl http://localhost:8000/health
# Ожидается: {"status": "ok", "database": "ok", "redis": "ok"}

# Проверить API
curl http://localhost:8000/api/v1/databases/ \
  -H "Authorization: Token YOUR_API_TOKEN"
```

---

### 3. Go Installation Service Deployment (Windows)

#### 3.1. Сборка бинарника

**На development машине (может быть Linux):**

```bash
cd installation-service

# Cross-compile для Windows
GOOS=windows GOARCH=amd64 go build -o bin/installation-service.exe cmd/main.go

# Или использовать Makefile
make build-windows

# Результат: bin/installation-service.exe (~11 MB)
```

#### 3.2. Копирование на Windows Server

**PowerShell на Windows Server:**

```powershell
# Создать директории
New-Item -Path "C:\Services\installation-service" -ItemType Directory -Force
New-Item -Path "C:\Extensions" -ItemType Directory -Force
New-Item -Path "C:\Logs" -ItemType Directory -Force

# Копировать файлы (через WinSCP, RDP shared folder, или network share)
# - installation-service.exe → C:\Services\installation-service\
# - config.example.yaml → C:\Services\installation-service\config.yaml

# Или через SMB share (с development машины)
scp installation-service.exe user@windows-server:C:\Services\installation-service\
scp config.example.yaml user@windows-server:C:\Services\installation-service\config.yaml
```

#### 3.3. Настройка конфигурации

**Редактировать `C:\Services\installation-service\config.yaml`:**

```yaml
redis:
  host: "10.0.1.51"  # Production Redis IP (Linux Server)
  port: 6379
  password: "your_secure_redis_password"
  queue: "installation_tasks"
  progress_channel: "installation_progress"
  db: 0
  max_retries: 3
  retry_delay_seconds: 5

onec:
  platform_path: "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  timeout_seconds: 300
  server_name: "prod-1c-server"  # Имя production 1C Server
  kill_timeout_seconds: 30

executor:
  max_parallel: 10  # Начать с 10, потом можно увеличить до 20-50
  retry_attempts: 3
  retry_delay_seconds: 30
  retry_backoff_multiplier: 2
  task_timeout_seconds: 600

orchestrator:
  api_url: "http://10.0.1.51:8000"  # Production Django API
  api_token: "your_installation_service_token_here"
  timeout_seconds: 30

server:
  health_check_port: 5555
  shutdown_timeout_seconds: 300

logging:
  level: "info"
  file: "C:\\Logs\\installation-service.log"
  max_size_mb: 100
  max_backups: 5
  max_age_days: 30
  compress: true
```

**Проверка конфигурации:**

```powershell
# Проверить доступность Redis с Windows Server
Test-NetConnection -ComputerName 10.0.1.51 -Port 6379

# Проверить доступность 1C Server
Test-NetConnection -ComputerName prod-1c-server -Port 1541

# Проверить доступность Django API
Invoke-WebRequest -Uri "http://10.0.1.51:8000/health"

# Проверить путь к 1cv8.exe
Test-Path "C:\Program Files\1cv8\8.3.23.1912\bin\1cv8.exe"
```

#### 3.4. Установка как Windows Service (NSSM)

**PowerShell (Administrator):**

```powershell
# 1. Скачать NSSM
# https://nssm.cc/download
# Распаковать в C:\Tools\nssm\

# 2. Создать Windows Service
C:\Tools\nssm\nssm.exe install InstallationService "C:\Services\installation-service\installation-service.exe"

# 3. Настроить сервис
C:\Tools\nssm\nssm.exe set InstallationService AppDirectory "C:\Services\installation-service"
C:\Tools\nssm\nssm.exe set InstallationService DisplayName "1C Installation Service"
C:\Tools\nssm\nssm.exe set InstallationService Description "Automated 1C OData extension installation service for CommandCenter"
C:\Tools\nssm\nssm.exe set InstallationService Start SERVICE_AUTO_START

# 4. Настроить логирование (stdout/stderr в отдельные файлы)
C:\Tools\nssm\nssm.exe set InstallationService AppStdout "C:\Logs\installation-service-stdout.log"
C:\Tools\nssm\nssm.exe set InstallationService AppStderr "C:\Logs\installation-service-stderr.log"

# 5. Настроить recovery (автоматический перезапуск при падении)
C:\Tools\nssm\nssm.exe set InstallationService AppExit Default Restart
C:\Tools\nssm\nssm.exe set InstallationService AppRestartDelay 5000  # 5 секунд

# 6. Настроить environment variables (если нужно)
C:\Tools\nssm\nssm.exe set InstallationService AppEnvironmentExtra REDIS_PASSWORD=your_password

# 7. Запустить сервис
C:\Tools\nssm\nssm.exe start InstallationService

# 8. Проверить статус
C:\Tools\nssm\nssm.exe status InstallationService
# Ожидается: SERVICE_RUNNING

# 9. Проверить Windows Services
Get-Service -Name "InstallationService"
# Status должен быть Running

# 10. Проверить логи
Get-Content C:\Logs\installation-service.log -Tail 50 -Wait
```

#### 3.5. Настройка Windows Firewall

```powershell
# Открыть порт 5555 для health check
New-NetFirewallRule -DisplayName "Installation Service Health Check" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 5555 `
  -Action Allow

# Проверить правило
Get-NetFirewallRule -DisplayName "Installation Service Health Check"
```

#### 3.6. Проверка deployment

```powershell
# Health check endpoint
Invoke-WebRequest -Uri "http://localhost:5555/health"

# Ожидаемый ответ:
# {
#   "status": "healthy",
#   "redis_connected": true,
#   "timestamp": "2025-10-27T12:00:00Z"
# }

# Проверить подключение к Redis
# (из логов должно быть "Connected to Redis")
Get-Content C:\Logs\installation-service.log -Tail 20

# Отправить тестовую задачу (с Linux Server)
redis-cli -h 10.0.1.51 -a your_redis_password LPUSH installation_tasks '{
  "task_id": "deployment-test-1",
  "database_id": 1,
  "database_name": "TestDB",
  "connection_string": "/S\"prod-1c-server\\TestDB\"",
  "username": "ODataUser",
  "password": "password",
  "extension_path": "C:\\Extensions\\Test.cfe",
  "extension_name": "TestExtension"
}'

# Проверить что задача обработана
Get-Content C:\Logs\installation-service.log -Tail 50
# Должны быть записи:
# - "Task received: deployment-test-1"
# - "Task started: deployment-test-1"
# - "Task completed: deployment-test-1" (или "Task failed")
```

---

### 4. Frontend Deployment

#### 4.1. Build Frontend

**На development машине:**

```bash
cd frontend

# Установить зависимости
npm install

# Создать production build
npm run build

# Результат: build/ директория с статическими файлами
```

#### 4.2. Копирование на Linux Server

```bash
# Создать директорию
sudo mkdir -p /var/www/commandcenter
sudo chown $USER:$USER /var/www/commandcenter

# Копировать build (с development машины)
rsync -avz build/ user@linux-server:/var/www/commandcenter/

# Или через git
cd /var/www/commandcenter
git clone https://github.com/your-org/command-center-1c.git
cd command-center-1c/frontend
npm install
npm run build
cp -r build/* /var/www/commandcenter/
```

#### 4.3. Настройка Nginx

```bash
# Установить Nginx (если не установлен)
sudo apt-get update
sudo apt-get install nginx

# Создать конфигурацию
sudo cat > /etc/nginx/sites-available/commandcenter <<'EOF'
server {
    listen 80;
    server_name commandcenter.local 10.0.1.51;

    root /var/www/commandcenter;
    index index.html;

    # Frontend static files
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Proxy to Django API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # WebSocket для real-time updates
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;
}
EOF

# Включить site
sudo ln -s /etc/nginx/sites-available/commandcenter /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезапустить Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx

# Проверить статус
sudo systemctl status nginx
```

**Проверка:**

```bash
# Health check
curl http://localhost/

# API через Nginx
curl http://localhost/api/v1/databases/ \
  -H "Authorization: Token YOUR_API_TOKEN"

# Открыть в браузере
# http://commandcenter.local
```

---

## Post-Deployment Verification

### 1. Health Checks

```bash
# PostgreSQL
psql -h 10.0.1.51 -U cc_user -d commandcenter -c "SELECT COUNT(*) FROM databases_database"

# Redis
redis-cli -h 10.0.1.51 -a your_redis_password PING

# Django Orchestrator
curl http://10.0.1.51:8000/health

# Installation Service (Windows)
curl http://windows-server:5555/health

# Frontend
curl http://10.0.1.51/
```

### 2. Functional Check (End-to-End)

```bash
# 1. Отправить тестовую задачу через API
curl -X POST http://10.0.1.51:8000/api/v1/databases/batch-install-extension/ \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_ids": [1],
    "extension_config": {
      "name": "DeploymentTest",
      "path": "C:\\Extensions\\DeploymentTest.cfe"
    }
  }'

# Получить task_id из ответа

# 2. Проверить прогресс
curl http://10.0.1.51:8000/api/v1/databases/installation-progress/TASK_ID/

# 3. Проверить логи Installation Service
# PowerShell на Windows:
Get-Content C:\Logs\installation-service.log -Tail 50

# 4. Проверить Redis events
redis-cli -h 10.0.1.51 -a your_redis_password SUBSCRIBE installation_progress

# 5. Проверить статус в БД
psql -h 10.0.1.51 -U cc_user -d commandcenter \
  -c "SELECT * FROM databases_extension_installation WHERE id='TASK_ID'"
```

### 3. Мониторинг логов

```bash
# Linux Server

# Django Orchestrator
tail -f /var/log/commandcenter/gunicorn-access.log
tail -f /var/log/commandcenter/gunicorn-error.log

# Celery Worker
tail -f /var/log/commandcenter/celery-worker.log

# Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Windows Server (PowerShell)

# Installation Service
Get-Content C:\Logs\installation-service.log -Tail 50 -Wait

# Windows Event Log
Get-EventLog -LogName Application -Source "InstallationService" -Newest 50
```

---

## Monitoring Setup

### Prometheus (опционально, для Phase 3)

**На Linux Server:**

```bash
# docker-compose.yml - добавить Prometheus
cat >> /opt/commandcenter/docker-compose.yml <<'EOF'
  prometheus:
    image: prom/prometheus:latest
    container_name: cc_prometheus
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    restart: unless-stopped
EOF

# Создать конфигурацию Prometheus
mkdir -p /opt/commandcenter/prometheus
cat > /opt/commandcenter/prometheus/prometheus.yml <<'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'installation-service'
    static_configs:
      - targets: ['windows-server:9100']  # Node exporter на Windows

  - job_name: 'django'
    static_configs:
      - targets: ['localhost:8000']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:6379']
EOF

# Запустить Prometheus
docker-compose up -d prometheus
```

---

## Rollback Procedure

Если deployment неудачен:

### 1. Остановить Installation Service

```powershell
# Windows Server
C:\Tools\nssm\nssm.exe stop InstallationService
```

### 2. Восстановить предыдущую версию

```powershell
# Windows Server
Copy-Item C:\Services\installation-service\installation-service.exe.backup `
  C:\Services\installation-service\installation-service.exe -Force
```

### 3. Откатить Django миграции (если применялись)

```bash
# Linux Server
cd /opt/commandcenter/orchestrator
source venv/bin/activate
python manage.py migrate databases PREVIOUS_MIGRATION_NAME
```

### 4. Восстановить конфигурацию

```bash
# Восстановить backup конфигурации
cp /opt/commandcenter/orchestrator/.env.backup \
   /opt/commandcenter/orchestrator/.env

# Перезапустить сервисы
sudo systemctl restart orchestrator celery-worker
```

### 5. Запустить Installation Service с предыдущей версией

```powershell
# Windows Server
C:\Tools\nssm\nssm.exe start InstallationService
```

---

## Troubleshooting

### Проблема: Installation Service не стартует

**Решение:**

```powershell
# Проверить логи Windows Service
C:\Tools\nssm\nssm.exe status InstallationService

# Проверить stderr
Get-Content C:\Logs\installation-service-stderr.log

# Попробовать запустить вручную
cd C:\Services\installation-service
.\installation-service.exe

# Проверить config
notepad config.yaml
```

### Проблема: Не подключается к Redis

**Решение:**

```powershell
# Проверить connectivity
Test-NetConnection -ComputerName 10.0.1.51 -Port 6379

# Проверить firewall на Linux Server
# (на Linux)
sudo ufw status
sudo ufw allow 6379/tcp

# Проверить Redis password
redis-cli -h 10.0.1.51 -a your_redis_password PING
```

### Проблема: Celery worker не обрабатывает задачи

**Решение:**

```bash
# Проверить подключение к Redis
redis-cli -h localhost -a your_redis_password PING

# Проверить очередь
redis-cli -h localhost -a your_redis_password LLEN installation_tasks

# Проверить логи Celery
tail -f /var/log/commandcenter/celery-worker.log

# Перезапустить worker
sudo systemctl restart celery-worker
```

### Проблема: Frontend не загружается

**Решение:**

```bash
# Проверить Nginx
sudo systemctl status nginx
sudo nginx -t

# Проверить логи
tail -f /var/log/nginx/error.log

# Проверить права на файлы
ls -la /var/www/commandcenter/
sudo chown -R www-data:www-data /var/www/commandcenter/

# Перезапустить Nginx
sudo systemctl restart nginx
```

---

## Backup Strategy

### Базы данных

```bash
# PostgreSQL backup (ежедневный cron)
cat > /opt/commandcenter/backup-postgres.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/commandcenter/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -h localhost -U cc_user commandcenter | gzip > $BACKUP_DIR/commandcenter_$DATE.sql.gz
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/commandcenter/backup-postgres.sh

# Добавить в cron
crontab -e
# 0 2 * * * /opt/commandcenter/backup-postgres.sh
```

### Конфигурация

```bash
# Backup конфигурации перед deployment
cp /opt/commandcenter/orchestrator/.env \
   /opt/commandcenter/orchestrator/.env.backup.$(date +%Y%m%d)

# Windows Server (PowerShell)
Copy-Item C:\Services\installation-service\config.yaml `
  "C:\Services\installation-service\config.yaml.backup.$(Get-Date -Format 'yyyyMMdd')"
```

---

## Security Hardening

### 1. Firewall Rules

```bash
# Linux Server
sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (Frontend)
sudo ufw allow 8000/tcp # Django API (internal network only)
sudo ufw allow 6379/tcp # Redis (internal network only)

# Windows Server
# В Windows Firewall настроить правила для:
# - Port 5555 (health check) - только internal network
# - Port 1541 (1C Server) - только localhost
```

### 2. Credentials Management

```bash
# Использовать environment variables вместо plain text в config
# Пример для Linux:
export REDIS_PASSWORD=$(cat /opt/commandcenter/secrets/redis_password)
export POSTGRES_PASSWORD=$(cat /opt/commandcenter/secrets/postgres_password)

# Windows: использовать DPAPI или Credential Manager
```

### 3. API Token Rotation

```python
# Django shell - ротация токена для Installation Service
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

user = User.objects.get(username='installation_service')
Token.objects.filter(user=user).delete()
new_token = Token.objects.create(user=user)
print(f"New token: {new_token.key}")

# Обновить config.yaml на Windows Server с новым токеном
```

---

## Maintenance

### Updates

```bash
# Django Orchestrator
cd /opt/commandcenter/orchestrator
git pull origin master
source venv/bin/activate
pip install -r requirements-prod.txt --upgrade
python manage.py migrate
sudo systemctl restart orchestrator celery-worker

# Installation Service
# Собрать новую версию на dev машине
# Копировать на Windows Server
# Остановить сервис
C:\Tools\nssm\nssm.exe stop InstallationService
# Заменить exe
# Запустить сервис
C:\Tools\nssm\nssm.exe start InstallationService
```

### Log Rotation

```bash
# Linux - logrotate
sudo cat > /etc/logrotate.d/commandcenter <<'EOF'
/var/log/commandcenter/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 commandcenter commandcenter
    sharedscripts
    postrotate
        systemctl reload orchestrator celery-worker
    endscript
}
EOF

# Windows - конфигурация в config.yaml уже настроена:
# max_size_mb: 100
# max_backups: 5
# max_age_days: 30
```

---

## Следующие шаги после deployment

1. ✅ Pilot на 50 базах (см. `INSTALLATION_SERVICE_TESTING.md`)
2. ✅ Анализ метрик и оптимизация
3. ✅ Production на 700 базах
4. ✅ Настройка мониторинга (Phase 3)
5. ✅ Настройка алертов (Phase 3)

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-27
