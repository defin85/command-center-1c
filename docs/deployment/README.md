# Deployment Guide

Актуальный путь деплоя для этого репозитория: **native deploy без Docker** через **GitHub Actions**.

## Что уже считается базовым контуром

На сервере должны быть подготовлены:

- `postgresql`
- `redis-server`
- `nginx`
- `clickhouse-server` (опционально для аналитики)
- systemd unit-файлы `cc1c-*`
- файл окружения `/etc/command-center-1c/env.production`
- deploy helper `/usr/local/bin/cc1c-deploy`

Подробности по workflow: [native-github-actions.md](./native-github-actions.md)

Отдельные frontend runbooks:

- [frontend-ui-platform-validation-runbook.md](./frontend-ui-platform-validation-runbook.md)
- [frontend-query-stream-runtime-runbook.md](./frontend-query-stream-runtime-runbook.md)

## 1) Одноразовая подготовка деплой-хелпера

Из корня репозитория:

```bash
./scripts/deploy/install-server-deployer.sh --host <SERVER_IP> --port <SSH_PORT> --user <SSH_USER> --ssh-pass '<SSH_PASSWORD>'
```

Скрипт установит:

- `/usr/local/bin/cc1c-deploy`
- `/etc/sudoers.d/cc1c-deploy` (возможность вызывать `cc1c-deploy` без пароля для deploy user)

## 2) Настроить SSH-ключ для GitHub Actions

Создать отдельный ключ локально:

```bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/cc1c_gha_deploy -C 'gha-command-center-1c'
```

Добавить публичный ключ на сервер:

```bash
ssh-copy-id -i ~/.ssh/cc1c_gha_deploy.pub -p <SSH_PORT> <SSH_USER>@<SERVER_IP>
```

## 3) Добавить GitHub Secrets

В репозитории (`Settings -> Secrets and variables -> Actions`) создать:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY` (содержимое `~/.ssh/cc1c_gha_deploy`)

## 4) Запуск деплоя

Workflow: [deploy-native.yml](../../.github/workflows/deploy-native.yml)

Триггеры:

- `workflow_dispatch`
- `push` в `main` или `master`

Что делает workflow:

1. Собирает frontend
2. Собирает Go-бинарники (`cc1c-api-gateway`, `cc1c-worker`)
3. Пакует релизный архив
4. Загружает архив на сервер
5. Вызывает `sudo /usr/local/bin/cc1c-deploy <archive> <sha>`

## 5) Проверка после деплоя

На сервере:

```bash
sudo systemctl status cc1c-orchestrator cc1c-api-gateway cc1c-worker-ops cc1c-worker-workflows --no-pager
curl -I http://127.0.0.1/
```

## 6) Rollback (ручной)

```bash
sudo ln -sfn /opt/command-center-1c/releases/<PREVIOUS_RELEASE_ID> /opt/command-center-1c/current
sudo systemctl restart cc1c-orchestrator cc1c-api-gateway cc1c-worker-ops cc1c-worker-workflows
sudo systemctl reload nginx
```

## 7) Переход к домену и TLS (позже)

При появлении домена:

1. Обновить `server_name` в `/etc/nginx/sites-available/command-center-1c.conf`
2. Обновить `/etc/command-center-1c/env.production`:
   - `DJANGO_SETTINGS_MODULE=config.settings.production`
   - `ALLOWED_HOSTS=<your-domain>`
   - `CREDENTIALS_TRANSPORT_KEY=<64+ hex chars>` (генерируется один раз, не менять после запуска системы)
3. Выпустить сертификат:

```bash
sudo certbot --nginx -d <your-domain>
```
