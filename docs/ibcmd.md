"c:\Program Files\1cv8\8.3.27.1508\bin\ibcmd.exe" infobase config -c "dump-standalone.cfg" export --sync --force --data=d:\tmp\ibcmd-data\ "d:\Repos\BIT\src\cf" < logo-pass.txt

содержимое dump-standalone.cfg :
database:
    dbms: MSSQLServer
    server: sql-server
    name: dbName
    user: dbUser
    password: dbPass

А в файле "logo-pass.txt" - две строки - логин и пароль от базы 1с.
Раньше ibcmd не умела принимать логопасы базы и приходилось каждый раз вбивать их вручную. Выкрутился вот таким способом.
Возможно сейчас с этим уже всё нормально и можно логопас базы передавать параметрами командной строки или в конфиг-файлах. Не проверял

---

## IBCMD в CommandCenter1C (Phase 5)

### Operation types

- `ibcmd_backup` — бэкап инфобазы (`infobase dump`)
- `ibcmd_restore` — восстановление (`infobase restore`)
- `ibcmd_replicate` — репликация (`infobase replicate`)
- `ibcmd_create` — создание базы (`infobase create`)
- `ibcmd_load_cfg` — загрузка конфигурации/расширения из файла (`infobase config load-cfg`)
- `ibcmd_extension_update` — обновление свойств расширения (`infobase extension update`)

### Payload (пример)

```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "output_path": "db-123/backup_20250101.dt",
  "input_path": "db-123/backup_20250101.dt",
  "create_database": true,
  "force": true,
  "additional_args": ["--jobs-count=4"]
}
```

Пример `ibcmd_load_cfg` (загрузка расширения из артефакта MinIO):

```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "file": "artifact://artifacts/<artifact_id>/<version_id>/myext.cfe",
  "extension": "MyExtension"
}
```

Пример `ibcmd_extension_update` (включить safe-mode и защиту от опасных действий):

```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "name": "MyExtension",
  "safe_mode": true,
  "unsafe_action_protection": true
}
```

### Storage

- **local (default):** `IBCMD_STORAGE_PATH` (по умолчанию `storage/ibcmd`)
- **s3:** `IBCMD_STORAGE_BACKEND=s3` и `output_path`/`input_path` в виде `s3://bucket/key` или ключа внутри bucket.

Для `ibcmd_backup`:
- `output_path` необязателен, при отсутствии генерируется имя с префиксом `ibcmd_backup_<db>_<ts>.dt`.

Для `ibcmd_restore`:
- `input_path` обязателен (или `backup_path`).

### Env vars (Worker)

- `IBCMD_PATH` — путь к `ibcmd.exe` (обязательно)
- `IBCMD_TIMEOUT` — таймаут (например `10m`)
- `USE_DIRECT_IBCMD` — `false` отключает выполнение
- `IBCMD_STORAGE_BACKEND` — `local` или `s3`
- `IBCMD_STORAGE_PATH` — база для local

Общие настройки выполнения команд (лимиты вывода и защита от зависаний пайпов):
- `COMMANDRUNNER_STDOUT_MAX_BYTES` — максимум bytes для stdout (по умолчанию `1048576`, сохраняется tail)
- `COMMANDRUNNER_STDERR_MAX_BYTES` — максимум bytes для stderr (по умолчанию `1048576`, сохраняется tail)
- `COMMANDRUNNER_WAIT_DELAY` — `time.ParseDuration`, ожидание закрытия stdout/stderr после exit (по умолчанию `2s`)

Флаги попадают в `result.data`:
- `stdout_truncated`, `stderr_truncated`, `wait_delay_hit`

S3:
- `IBCMD_S3_ENDPOINT`
- `IBCMD_S3_BUCKET`
- `IBCMD_S3_ACCESS_KEY`
- `IBCMD_S3_SECRET_KEY`
- `IBCMD_S3_REGION` (опц.)
- `IBCMD_S3_PREFIX` (опц.)
- `IBCMD_S3_USE_SSL` (по умолчанию `true`)

ibserv (dev/test only):
- `IBSRV_ENABLED=true` + `APP_ENV != production`

AgentMode параметры (payload):
- `use_ibsrv`: `true` включает запуск `1cv8.exe DESIGNER /AgentMode` перед ibcmd
- `agent_port`: порт SSH агента (по умолчанию 1543)
- `agent_listen_address`: адрес прослушивания (по умолчанию 127.0.0.1)
- `agent_ssh_host_key`: путь к приватному ключу хоста
- `agent_ssh_host_key_auto`: авто‑ключ хоста (если `agent_ssh_host_key` не задан)
- `agent_base_dir`: рабочий каталог агента (SFTP + dump/load)
- `agent_visible`: показывать окно конфигуратора
- `agent_startup_timeout_seconds`: таймаут запуска агента
- `agent_shutdown_timeout_seconds`: таймаут остановки агента

### Templates

После добавления операций используйте `/api/v2/templates/sync-from-registry/`,
чтобы появились шаблоны `ibcmd_*` для использования в workflows.

---

## Примеры конфигураций

### 1) Local FS (по умолчанию)

env (Worker):
- `IBCMD_STORAGE_BACKEND=local`
- `IBCMD_STORAGE_PATH=/var/lib/cc1c/ibcmd`

payload:
```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "output_path": "db-123/backup_20250101.dt"
}
```

### 2) S3 (артефакты в объектном хранилище)

env (Worker):
- `IBCMD_STORAGE_BACKEND=s3`
- `IBCMD_S3_ENDPOINT=minio.local:9000`
- `IBCMD_S3_BUCKET=cc1c-ibcmd`
- `IBCMD_S3_ACCESS_KEY=...`
- `IBCMD_S3_SECRET_KEY=...`
- `IBCMD_S3_REGION=us-east-1`
- `IBCMD_S3_PREFIX=backups`
- `IBCMD_S3_USE_SSL=false`

payload (backup):
```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "output_path": "s3://cc1c-ibcmd/backups/db-123/backup_20250101.dt"
}
```

payload (restore):
```json
{
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "input_path": "s3://cc1c-ibcmd/backups/db-123/backup_20250101.dt",
  "create_database": true,
  "force": true
}
```

### 3) AgentMode + ibcmd (dev/test, по guard-ам)

env (Worker):
- `IBSRV_ENABLED=true`
- `APP_ENV=development`
- `PLATFORM_1C_BIN_PATH=/opt/1c/8.3.27/bin`

payload:
```json
{
  "use_ibsrv": true,
  "agent_port": 1543,
  "agent_ssh_host_key_auto": true,
  "agent_base_dir": "/var/lib/1c/agent",
  "dbms": "PostgreSQL",
  "db_server": "db-host:5432",
  "db_name": "mydb",
  "db_user": "dbuser",
  "db_password": "secret",
  "output_path": "db-123/backup_20250101.dt"
}
```
