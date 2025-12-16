# Extension Storage API - Testing Guide

## Запуск batch-service

```bash
cd go-services/batch-service
go run cmd/main.go
```

## Переменные окружения (опционально)

```bash
export EXTENSION_STORAGE_PATH="./storage/extensions"  # Путь к хранилищу
export RETENTION_VERSIONS=3                            # Количество версий для хранения
export SERVER_PORT=8087                                # Порт сервера
export LOG_LEVEL=info                                  # Уровень логирования
```

## API Endpoints

### 1. Health Check

```bash
curl http://localhost:8087/health
```

**Ожидаемый ответ:**
```json
{
  "service": "batch-service",
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. Upload Extension (POST /storage/upload)

```bash
# Создать тестовый .cfe файл
echo "Test CFE content v1.0.5" > ODataAutoConfig_v1.0.5.cfe

# Загрузить файл
curl -X POST http://localhost:8087/storage/upload \
  -F "file=@ODataAutoConfig_v1.0.5.cfe" \
  -F "author=Developer Name"
```

**Ожидаемый ответ:**
```json
{
  "success": true,
  "file_name": "ODataAutoConfig_v1.0.5.cfe",
  "path": "storage/extensions/ODataAutoConfig/ODataAutoConfig_v1.0.5.cfe",
  "size_bytes": 24,
  "checksum_md5": "4872de119d7a55014402b629fcf88762",
  "uploaded_at": "2025-11-09T12:00:00Z"
}
```

### 3. List Extensions (GET /storage/list)

```bash
# Получить список всех расширений
curl http://localhost:8087/storage/list

# Фильтр по имени расширения
curl "http://localhost:8087/storage/list?extension_name=ODataAutoConfig"
```

**Ожидаемый ответ:**
```json
{
  "extensions": [
    {
      "file_name": "ODataAutoConfig_v1.0.5.cfe",
      "extension_name": "ODataAutoConfig",
      "version": "1.0.5",
      "author": "Developer Name",
      "size_bytes": 24,
      "checksum_md5": "4872de119d7a55014402b629fcf88762",
      "uploaded_at": "2025-11-09T12:00:00Z",
      "file_path": "storage/extensions/ODataAutoConfig/ODataAutoConfig_v1.0.5.cfe"
    }
  ],
  "total_count": 1
}
```

### 4. Get Extension Metadata (GET /storage/:name/metadata)

```bash
curl "http://localhost:8087/storage/ODataAutoConfig_v1.0.5.cfe/metadata"
```

**Ожидаемый ответ:**
```json
{
  "file_name": "ODataAutoConfig_v1.0.5.cfe",
  "extension_name": "ODataAutoConfig",
  "version": "1.0.5",
  "author": "Developer Name",
  "size_bytes": 24,
  "checksum_md5": "4872de119d7a55014402b629fcf88762",
  "uploaded_at": "2025-11-09T12:00:00Z",
  "file_path": "storage/extensions/ODataAutoConfig/ODataAutoConfig_v1.0.5.cfe"
}
```

### 5. Delete Extension (DELETE /storage/:name)

```bash
curl -X DELETE "http://localhost:8087/storage/ODataAutoConfig_v1.0.5.cfe"
```

**Ожидаемый ответ:**
```json
{
  "success": true,
  "message": "Extension file deleted successfully",
  "deleted_file": "ODataAutoConfig_v1.0.5.cfe"
}
```

## Тестирование Retention Policy

Retention policy автоматически удаляет старые версии, оставляя только последние 3 (по умолчанию).

```bash
# Создать 5 версий
echo "v1.0.3" > OData_v1.0.3.cfe
echo "v1.0.4" > OData_v1.0.4.cfe
echo "v1.0.5" > OData_v1.0.5.cfe
echo "v1.0.6" > OData_v1.0.6.cfe
echo "v1.0.7" > OData_v1.0.7.cfe

# Загрузить все версии
curl -s -X POST http://localhost:8087/storage/upload -F "file=@OData_v1.0.3.cfe"
curl -s -X POST http://localhost:8087/storage/upload -F "file=@OData_v1.0.4.cfe"
curl -s -X POST http://localhost:8087/storage/upload -F "file=@OData_v1.0.5.cfe"
curl -s -X POST http://localhost:8087/storage/upload -F "file=@OData_v1.0.6.cfe"
curl -s -X POST http://localhost:8087/storage/upload -F "file=@OData_v1.0.7.cfe"

# Проверить что остались только последние 3 версии (1.0.5, 1.0.6, 1.0.7)
python - <<'PY'
import json, urllib.request
data = json.loads(urllib.request.urlopen("http://localhost:8087/storage/list").read().decode("utf-8"))
versions = sorted([e.get("version") for e in data.get("extensions", []) if e.get("version")])
print(versions)
PY
```

**Ожидаемый результат:**
```json
[
  "1.0.5",
  "1.0.6",
  "1.0.7"
]
```

Версии 1.0.3 и 1.0.4 были автоматически удалены.

## Структура Storage

После загрузки файлов storage имеет следующую структуру:

```
storage/extensions/
├── ODataAutoConfig/
│   ├── ODataAutoConfig_v1.0.5.cfe
│   ├── ODataAutoConfig_v1.0.6.cfe
│   ├── ODataAutoConfig_v1.0.7.cfe
│   └── metadata.json
└── MobileApp/
    ├── MobileApp_v2.1.3.cfe
    └── metadata.json
```

**Пример metadata.json:**
```json
{
  "extension_name": "ODataAutoConfig",
  "versions": [
    {
      "file_name": "ODataAutoConfig_v1.0.7.cfe",
      "extension_name": "ODataAutoConfig",
      "version": "1.0.7",
      "size_bytes": 1024000,
      "checksum_md5": "abc123...",
      "uploaded_at": "2025-11-09T12:00:00Z",
      "file_path": "storage/extensions/ODataAutoConfig/ODataAutoConfig_v1.0.7.cfe"
    }
  ]
}
```

## Валидация

API выполняет следующие проверки:

1. **Формат имени файла:** `{Name}_v{Version}.cfe` (например, `ODataAutoConfig_v1.0.5.cfe`)
2. **Расширение файла:** Должно быть `.cfe`
3. **Semantic versioning:** Версия должна соответствовать формату `major.minor.patch`
4. **Размер файла:** Минимум 1 byte, максимум 100 MB
5. **Path traversal protection:** Имена с `..`, `/`, `\` отклоняются
6. **MD5 checksum:** Вычисляется автоматически для каждого файла

## Обработка ошибок

### Неправильный формат имени файла
```bash
curl -X POST http://localhost:8087/storage/upload \
  -F "file=@invalid_name.cfe"
```
**Ответ:**
```json
{
  "error": "invalid file name",
  "details": "invalid file name format, expected: {Name}_v{Version}.cfe"
}
```

### Файл не найден
```bash
curl "http://localhost:8087/storage/NonExistent_v1.0.0.cfe/metadata"
```
**Ответ:**
```json
{
  "error": "extension not found",
  "details": "extension not found: NonExistent_v1.0.0.cfe"
}
```

### Файл слишком большой
```bash
# Создать файл > 100MB
dd if=/dev/zero of=Large_v1.0.0.cfe bs=1M count=101

curl -X POST http://localhost:8087/storage/upload \
  -F "file=@Large_v1.0.0.cfe"
```
**Ответ:**
```json
{
  "error": "file size too large",
  "details": "maximum size: 100 MB"
}
```

## Troubleshooting

### Сервис не запускается
```bash
# Проверить логи
tail -f batch-service.log

# Проверить что порт свободен
netstat -ano | grep :8087
```

### Проблемы с путями Windows
Если видите `\` вместо `/` в путях - это нормально для Windows. API работает корректно с обоими форматами.

### Permission denied при создании storage
```bash
# Убедитесь что директория существует и доступна для записи
mkdir -p ./storage/extensions
chmod 755 ./storage/extensions
```
