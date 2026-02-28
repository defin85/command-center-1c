# Debug Toolkit (autonomous-feedback-loop)

Этот файл описывает локальную debug-инфраструктуру для быстрого цикла:
`проверка -> гипотеза -> runtime-eval -> фикс -> повторная проверка`.

Все команды запускаются из корня репозитория.

## Быстрый старт

```bash
./scripts/dev/start-all.sh
./debug/probe.sh all
./debug/runtime-inventory.sh
```

Для Beads/Dolt server mode:

```bash
./debug/start-dolt.sh
systemctl --user status beads-dolt.service --no-pager
```

## Инвентарь команд

1. `./debug/runtime-inventory.sh`
Показывает карту рантаймов (entrypoint, health, eval, тест-команды).

2. `./debug/runtime-inventory.sh --json`
Тот же инвентарь в JSON для скриптов/агентов.

3. `./debug/probe.sh all`
Проверяет процесс (`pid`) и HTTP health для рантаймов.

4. `./debug/probe.sh <runtime>`
Точечная проверка одного рантайма:
`orchestrator | event-subscriber | api-gateway | worker | worker-workflows | frontend`.

5. `./debug/restart-runtime.sh <runtime>`
Перезапускает рантайм через `scripts/dev/restart.sh` и сразу делает `probe`.

6. `./debug/eval-django.sh "<python code>"`
Выполняет код в `orchestrator/manage.py shell -c ...` строго через `orchestrator/venv`.

Пример:

```bash
./debug/eval-django.sh "from apps.databases.models import Database; print(Database.objects.count())"
```

7. `./debug/start-chromium-cdp.sh [port] [target_url] [profile_dir] [log_file]`
Поднимает Chromium с CDP (по умолчанию `127.0.0.1:9222`) и гарантирует наличие target-страницы.

8. `./debug/eval-frontend.sh "<js expression>" [url_pattern]`
Автоматически поднимает CDP (если не запущен), затем выполняет JS через `scripts/dev/chrome-debug.py`.

Пример:

```bash
./debug/eval-frontend.sh "document.title"
./debug/eval-frontend.sh "window.location.href" "localhost:15173"
```

9. `./debug/receiver.py --port 3333`
Локальный HTTP receiver для sandbox-интеграций (эндпоинты: `GET /health`, `POST /log`).

10. `./debug/start-dolt.sh`
Переводит текущий Beads-репозиторий в shared Dolt server storage, запускает `systemd --user` сервис `beads-dolt.service` и валидирует доступ через `bd doctor --server`.

Сервис общий для всех Beads-репозиториев и использует каталог:
`~/.local/share/beads/dolt-server`

Инварианты:
- база проекта живёт как реальный каталог `~/.local/share/beads/dolt-server/<database>`;
- `metadata.json` должен содержать `dolt_mode: "server"`;
- при первой миграции legacy `.beads/dolt` архивируется в `~/.local/share/beads/dolt-backups/`;
- пароль не хранится в репозитории, используется `BEADS_DOLT_PASSWORD`.

## Важные замечания

1. Для `eval-django.sh` обязателен `orchestrator/venv` с установленным Django.
2. Для `eval-frontend.sh` нужен Python-пакет `websockets` (используется `scripts/dev/chrome-debug.py`).
3. `chrome-debug.py` и интерактивный MCP chrome-devtools не стоит использовать одновременно на одной вкладке/CDP-сессии.
4. Для Beads/Dolt server mode ожидается доступный `systemd --user`; состояние сервиса проверяется через `systemctl --user status beads-dolt.service`.
