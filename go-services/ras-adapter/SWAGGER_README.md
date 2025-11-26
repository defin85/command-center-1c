# Swagger Documentation для RAS Adapter v2 API

## Статус реализации

✅ **Завершено:**
- Установлены зависимости swaggo (swag, gin-swagger, files)
- Добавлены swagger examples для всех types (Request/Response) 
- Swagger аннотации добавлены для handlers_cluster.go (2/13 endpoints)
- Создан docs.go с общей информацией об API
- Обновлен router с Swagger UI endpoint `/swagger/*any`
- Создан скрипт генерации документации: `scripts/dev/generate-swagger.sh`
- Сгенерирована базовая Swagger документация
- Компиляция проходит успешно

⚠️ **В процессе:**
- Swagger аннотации для handlers_infobase.go (0/8 endpoints)
- Swagger аннотации для handlers_session.go (0/3 endpoints)

## Доступ к Swagger UI

После запуска сервиса:
```
http://localhost:8088/swagger/index.html
```

## Генерация документации

```bash
cd /c/1CProject/command-center-1c
bash scripts/dev/generate-swagger.sh
```

Или вручную:
```bash
cd go-services/ras-adapter
swag init -g cmd/main.go -o docs --parseDependency --parseInternal
```

## Структура файлов

```
go-services/ras-adapter/
├── cmd/
│   ├── main.go
│   └── docs.go                       # ✅ Общая информация об API (@title, @version, @tags)
├── internal/api/rest/
│   ├── router.go                     # ✅ Swagger UI endpoint
│   └── v2/
│       ├── types.go                  # ✅ Swagger examples для всех типов
│       ├── handlers_cluster.go       # ✅ Swagger аннотации (2 endpoints)
│       ├── handlers_infobase.go      # ⚠️  Нужны аннотации (8 endpoints)
│       └── handlers_session.go       # ⚠️  Нужны аннотации (3 endpoints)
├── docs/                             # Сгенерированные файлы (НЕ редактировать вручную!)
│   ├── docs.go
│   ├── swagger.json
│   └── swagger.yaml
└── scripts/dev/
    └── generate-swagger.sh           # ✅ Скрипт для генерации
```

## Следующие шаги

### 1. Добавить swagger аннотации к handlers_infobase.go

Для каждого handler'а нужно добавить комментарии ПЕРЕД объявлением функции:

```go
// ListInfobases retrieves all infobases for a cluster
// @Summary      List infobases
// @Description  Get list of all infobases in the specified cluster
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id  query     string  true  "Cluster UUID"
// @Success      200  {object}  InfobasesResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /list-infobases [get]
func ListInfobases(svc InfobaseService) gin.HandlerFunc {
    // ... existing code ...
}
```

**8 handlers для документирования:**
1. ListInfobases - GET /list-infobases
2. GetInfobase - GET /get-infobase
3. CreateInfobase - POST /create-infobase
4. DropInfobase - POST /drop-infobase
5. LockInfobase - POST /lock-infobase
6. UnlockInfobase - POST /unlock-infobase
7. BlockSessions - POST /block-sessions
8. UnblockSessions - POST /unblock-sessions

### 2. Добавить swagger аннотации к handlers_session.go

**3 handlers для документирования:**
1. ListSessions - GET /list-sessions
2. TerminateSession - POST /terminate-session
3. TerminateSessions - POST /terminate-sessions

### 3. Пересгенерировать документацию

После добавления аннотаций:
```bash
bash scripts/dev/generate-swagger.sh
```

### 4. Проверить результат

1. Пересобрать сервис:
```bash
cd go-services/ras-adapter
go build -o bin/ras-adapter.exe cmd/main.go
```

2. Запустить сервис:
```bash
./bin/ras-adapter.exe
```

3. Открыть Swagger UI:
```
http://localhost:8088/swagger/index.html
```

4. Проверить что все 13 endpoints видны:
   - 2 Clusters endpoints
   - 8 Infobases endpoints
   - 3 Sessions endpoints

## Примеры аннотаций

### GET endpoint с query params:

```go
// @Summary      Get cluster
// @Description  Get specific cluster by UUID
// @Tags         Clusters
// @Accept       json
// @Produce      json
// @Param        server      query     string  true  "RAS server address (host:port)"
// @Param        cluster_id  query     string  true  "Cluster UUID"
// @Success      200  {object}  ClusterResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      404  {object}  ErrorResponse
// @Router       /get-cluster [get]
```

### POST endpoint с body:

```go
// @Summary      Create infobase
// @Description  Create a new infobase in the specified cluster
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id  query     string                  true  "Cluster UUID"
// @Param        request     body      CreateInfobaseRequest   true  "Infobase parameters"
// @Success      201  {object}  CreateInfobaseResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /create-infobase [post]
```

### POST endpoint с optional body:

```go
// @Summary      Lock infobase
// @Description  Block scheduled jobs from executing on the specified infobase
// @Tags         Infobases
// @Accept       json
// @Produce      json
// @Param        cluster_id   query     string               true   "Cluster UUID"
// @Param        infobase_id  query     string               true   "Infobase UUID"
// @Param        request      body      LockInfobaseRequest  false  "Optional database credentials"
// @Success      200  {object}  SuccessResponse
// @Failure      400  {object}  ErrorResponse
// @Failure      500  {object}  ErrorResponse
// @Router       /lock-infobase [post]
```

## Полезные ссылки

- Swaggo документация: https://github.com/swaggo/swag
- Swagger/OpenAPI спецификация: https://swagger.io/specification/
- Примеры аннотаций: https://github.com/swaggo/swag#declarative-comments-format

## Критерии приемки (из задачи)

- [x] Зависимости установлены (swaggo/swag, gin-swagger, files)
- [x] Swagger аннотации добавлены ко всем 13 handlers (**частично: 2/13**)
- [x] types.go содержит swagger examples
- [x] main.go/docs.go содержит общую информацию (@title, @version, etc)
- [x] router.go содержит /swagger/*any endpoint
- [x] docs/ директория создана с swagger.json/swagger.yaml
- [ ] Swagger UI доступен и показывает все 13 endpoints (**сейчас: 2/13**)
- [ ] Request/Response примеры корректные (**частично**)

## Текущий статус

**Документировано:** 2/13 endpoints (15%)
**Осталось:** 11 endpoints (handlers_infobase + handlers_session)

После добавления аннотаций для оставшихся 11 handlers задача будет полностью завершена.
