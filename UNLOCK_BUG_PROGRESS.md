# Unlock Bug - Текущий прогресс (2025-11-22 20:41)

## Проблема
Unlock infobase падает с ошибкой PostgreSQL: "no password supplied"
Lock работает через rac, Unlock НЕ работает через RAS Adapter SDK.

## Root Cause (из RAS sniffer)
- **rac** отправляет `0x03 0xef 0xbf 0xbd` (UTF-8 replacement char U+FFFD) для пустого db_pwd
- **SDK** отправляет `0x00` (NULL) для пустого db_pwd
- RAS при получении NULL пытается валидировать с PostgreSQL → ошибка
- RAS при получении U+FFFD пропускает валидацию → успех

## Что сделано

### 1. Vendored khorevaa/ras-client SDK ✅
```
go-services/ras-adapter/ras-client/
├── protocol/codec/encoder.go  ← проблемный файл
├── ORIGIN.md                  ← ссылка на оригинал
└── ... (весь SDK)
```

**Импорты обновлены:**
- `github.com/khorevaa/ras-client` → `github.com/commandcenter1c/commandcenter/ras-adapter/ras-client`

**go.mod:**
```go
replace github.com/commandcenter1c/commandcenter/ras-adapter/ras-client => ./ras-client
```

### 2. Попытка фикса через encoder.go ❌ ОТКАЧЕНО
**Что пробовал:**
```go
func (e *encoder) String(val string, w io.Writer) {
    if len(val) == 0 {
        // Отправлять UTF-8 replacement char вместо NULL
        replacementChar := []byte{0xef, 0xbf, 0xbd}
        e.NullableSize(len(replacementChar), w)
        e.write(w, replacementChar)
        return
    }
    // ...
}
```

**Результат:**
- ✅ Должно было исправить Unlock
- ❌ Сломало ВСЮ аутентификацию (cluster credentials тоже стали replacement char)
- ❌ GET /infobases, Lock - всё падало с "Администратор кластера не аутентифицирован"

**Решение:** Откатил encoder.go к оригиналу

### 3. Текущее состояние ✅
- RAS перезапущен (PID из pids/ras.pid)
- ras-adapter пересобран и перезапущен
- Базовая функциональность РАБОТАЕТ:
  - GET /infobases ✅
  - rac infobase lock/unlock ✅

## Следующие шаги

### Правильный фикс
**НЕ изменять encoder.go глобально!**

Вместо этого:
1. Найти где создаётся `serialize.InfobaseInfo` для UpdateInfobase в `client.go`
2. Локально заменить пустой `DbPwd` на "\uFFFD" ТОЛЬКО для UpdateInfobase
3. Альтернатива: создать wrapper функцию `encodeDbPwd(pwd string) string`

**Файлы для изменения:**
- `go-services/ras-adapter/internal/ras/client.go` ← функции LockInfobase/UnlockInfobase
- Строки ~280-320 (RegInfoBase вызов)

### Тестирование
```bash
# 1. Lock через RAS Adapter
curl -X POST http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269/lock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "c3e50859-3d41-4383-b0d7-4ee20272b69d"}'

# 2. Unlock через RAS Adapter (сейчас ПАДАЕТ)
curl -X POST http://localhost:8088/api/v1/infobases/ae1e5ea8-96e9-45cb-8363-8e4473daa269/unlock \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "c3e50859-3d41-4383-b0d7-4ee20272b69d"}'

# 3. Проверить через rac
rac infobase info --infobase=ae1e5ea8-96e9-45cb-8363-8e4473daa269 \
  --cluster=c3e50859-3d41-4383-b0d7-4ee20272b69d localhost:1545 | grep scheduled-jobs-deny
```

## Тестовая база
```
UUID: ae1e5ea8-96e9-45cb-8363-8e4473daa269
Name: test_lock_unlock
Cluster: c3e50859-3d41-4383-b0d7-4ee20272b69d
DB: PostgreSQL localhost/test_lock_unlock (postgres/postgres)
```

## Команды для быстрого старта
```bash
cd /c/1CProject/command-center-1c

# Пересборка
./scripts/build.sh --service=ras-adapter
./scripts/dev/restart.sh ras-adapter

# Проверка логов
tail -f logs/ras-adapter.log

# Health check
curl http://localhost:8088/health
```

## Статус задач
- ✅ Task #1-5: Cluster/Infobase CRUD
- ⚠️ Task #6: Lock - работает через rac, через API нужно проверить
- 🔴 Task #7: **FIX UNLOCK BUG** ← ЗДЕСЬ СЕЙЧАС
- ⚠️ Task #8: Unlock - заблокировано Task #7
- ✅ Task #9: Drop infobase
- 📋 Task #10-16: Pending

