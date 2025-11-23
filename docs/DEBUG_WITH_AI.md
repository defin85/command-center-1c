# AI-Powered Debugging with MCP DAP Server

> Автоматическая отладка Go сервисов с помощью AI через Model Context Protocol и Debug Adapter Protocol

---

## 🎯 Что это?

**MCP DAP Server** - это bridge между Claude Code и отладчиком Delve, позволяющий AI агенту:
- Автоматически находить и чинить баги
- Устанавливать breakpoints и инспектировать состояние
- Вычислять выражения в контексте отладки
- Управлять выполнением программы (step, continue, pause)

**Архитектура:**
```
Claude Code → MCP DAP Server → Delve → Go Service
            ↑ SSE (8090)      ↑ DAP  ↑ Debug
```

---

## 🚀 Quick Start

### 1. Проверка установки

Убедитесь что всё установлено:

```bash
# Delve debugger
dlv version
# Должно показать: Delve Debugger Version: 1.25.2+

# MCP DAP Server
ls /c/Users/Egor/Documents/GitHub/mcp-dap-server/bin/mcp-dap-server
# Должен существовать бинарник

# Claude Code подключение
claude mcp list
# Должен быть в списке: mcp-dap-server (SSE) ✓ Connected
```

### 2. Запуск MCP DAP Server

```bash
cd /c/1CProject/command-center-1c
./scripts/dev/start-mcp-dap-server.sh
```

**Проверка:**
```bash
curl http://localhost:8090/health
# Ожидается ответ от сервера
```

### 3. Запуск Go сервиса в debug режиме

**Вариант A: Автоматический запуск (рекомендуется)**

```bash
# API Gateway на порту 2345
./scripts/dev/debug-service.sh api-gateway

# Worker на порту 2346
./scripts/dev/debug-service.sh worker

# RAS Adapter на порту 2347
./scripts/dev/debug-service.sh ras-adapter

# Batch Service на порту 2348
./scripts/dev/debug-service.sh batch-service
```

**Вариант B: Ручной запуск**

```bash
cd go-services/api-gateway
dlv debug --headless --listen=:2345 --api-version=2 --accept-multiclient cmd/main.go
```

---

## 🛠️ Доступные MCP Tools

После подключения к MCP DAP Server, AI агент получает доступ к следующим инструментам:

### Session Management
- `start_debugger(port)` - подключиться к Delve на указанном порту
- `stop_debugger()` - остановить debug сессию
- `restart_debugger()` - перезапустить программу
- `terminate_debugger()` - полностью завершить

### Breakpoints
- `set_breakpoints(file, lines)` - установить breakpoints по строкам
- `set_function_breakpoints(functions)` - установить по именам функций

### Execution Control
- `continue(threadId?)` - продолжить выполнение
- `next(threadId)` - шаг через (step over)
- `step_in(threadId)` - шаг внутрь функции
- `step_out(threadId)` - выйти из функции
- `pause(threadId)` - пауза

### State Inspection
- `threads()` - список всех потоков
- `stack_trace(threadId, startFrame?, levels?)` - стек вызовов
- `scopes(frameId)` - области видимости (Locals, Arguments, Globals) + все переменные
- `variables(variablesReference)` - переменные в scope
- `evaluate(expression, frameId?, context?)` - вычислить выражение
- `set_variable(variablesReference, name, value)` - изменить значение переменной

### Advanced
- `attach_debugger(mode, processId?)` - присоединиться к running процессу
- `modules()` - загруженные модули
- `loaded_sources()` - загруженные исходники
- `disassemble(memoryReference, instructionCount)` - дизассемблировать код
- `exception_info(threadId)` - информация об исключениях

---

## 📝 Примеры использования

### Пример 1: Autonomous Bug Finding

**Сценарий:** API Gateway возвращает 500 Internal Server Error

```
👤 User: API Gateway падает с 500 ошибкой при запросе /api/v1/databases

🤖 Claude:
1. Запускаю API Gateway в debug режиме...
   start_debugger(port=2345)

2. Устанавливаю breakpoint в handler...
   set_breakpoints(file="go-services/api-gateway/handlers/database.go", lines=[42])

3. Продолжаю выполнение и делаю запрос...
   continue()

4. Breakpoint сработал! Инспектирую состояние...
   stack_trace(threadId=1)
   scopes(frameId=0)

5. Нашёл проблему: переменная 'db' равна nil!
   evaluate(expression="db == nil", frameId=0)
   # Результат: true

6. Причина: не инициализирован connection pool
   Исправление: добавить инициализацию в main.go:25
```

### Пример 2: Inspect Running Service

**Сценарий:** Worker тормозит, нужно понять почему

```
👤 User: Worker медленно обрабатывает задачи

🤖 Claude:
1. Присоединяюсь к running процессу...
   attach_debugger(mode="attach", processId=12345)

2. Получаю список потоков...
   threads()
   # Вижу 10 горутин, 3 из них в WAITING

3. Смотрю стек самой долгой горутины...
   stack_trace(threadId=5)
   # Горутина застряла в wait на Redis lock

4. Инспектирую переменные...
   scopes(frameId=0)
   # lockKey = "operation:123"
   # timeout = 30s (слишком долго!)

5. Рекомендация: уменьшить timeout до 5s в config
```

### Пример 3: Live Expression Evaluation

**Сценарий:** Проверить значение переменной в runtime

```
👤 User: Что находится в cache для ключа "db:prod:123"?

🤖 Claude:
1. Подключаюсь к RAS Adapter...
   start_debugger(port=2347)

2. Ставлю breakpoint в getCachedDatabase()...
   set_breakpoints(file="go-services/ras-adapter/cache.go", lines=[67])

3. Продолжаю и жду срабатывания...
   continue()

4. Вычисляю выражение...
   evaluate(expression='cache.Get("db:prod:123")', frameId=0)
   # Результат: {ID: "123", Name: "Prod", Connected: false}

5. Ага! Connected=false - это проблема!
```

---

## 🎬 Пошаговый workflow

### Типичный debugging сценарий

**1. Подготовка**
```bash
# Terminal 1: MCP DAP Server
./scripts/dev/start-mcp-dap-server.sh

# Terminal 2: Go Service в debug режиме
./scripts/dev/debug-service.sh api-gateway
```

**2. В Claude Code**
```
1. start_debugger(port=2345)
2. set_breakpoints(file="handlers/auth.go", lines=[45, 67])
3. continue()
4. [Делаем запрос, который должен сработать breakpoint]
5. threads()  # Проверяем какой поток остановился
6. stack_trace(threadId=1, levels=5)  # Смотрим стек
7. scopes(frameId=0)  # Инспектируем переменные
8. evaluate(expression="user.IsAdmin()")  # Проверяем условия
9. next(threadId=1)  # Шаг дальше
10. continue()  # Продолжить до следующего breakpoint
```

**3. После отладки**
```bash
# Остановить debug сессию (в Claude Code)
disconnect(terminateDebuggee=true)

# Остановить MCP DAP Server
./scripts/dev/stop-mcp-dap-server.sh
```

---

## ⚠️ Важные замечания

### Security

**🚨 КРИТИЧНО:**
- **НЕ используй в production!** Delve добавляет уязвимости
- Debug порты (2345-2348) должны быть **закрыты** для внешнего доступа
- Только в **trusted development** окружении
- DAP протокол **не шифрован** - не передавай чувствительные данные

### Performance

**Overhead от Delve:**
- ~20-30% slowdown в debug режиме
- Используй только для troubleshooting
- Для production - logging и tracing вместо debugging

### Limitations

**Что НЕ работает:**
- Debugging оптимизированных бинарников (`-ldflags="-s -w"`)
- Inline функции могут быть пропущены
- Некоторые compiler optimizations мешают точности

**Решение:**
```bash
# Собирать с debug символами
go build -gcflags="all=-N -l" -o bin/service cmd/main.go

# Или через Delve напрямую
dlv debug cmd/main.go  # Автоматически без оптимизаций
```

---

## 🔧 Troubleshooting

### MCP DAP Server не запускается

**Проблема:** `Cannot start server on :8090`

**Решение:**
```bash
# Проверить что порт свободен
netstat -ano | grep :8090

# Убить процесс если занят
taskkill /PID <pid> /F

# Перезапустить
./scripts/dev/start-mcp-dap-server.sh
```

### Delve не подключается

**Проблема:** `start_debugger(port=2345)` возвращает ошибку

**Решение:**
```bash
# Проверить что Delve запущен
netstat -ano | grep :2345

# Проверить логи Delve
# (они в терминале где запущен dlv debug)

# Перезапустить debug сессию
./scripts/dev/debug-service.sh api-gateway
```

### Breakpoints не срабатывают

**Причины:**
1. **Неправильный путь к файлу** - используй относительный путь от корня проекта
2. **Оптимизированный код** - пересобери с `-gcflags="all=-N -l"`
3. **Inline функция** - добавь `//go:noinline` перед функцией

**Решение:**
```bash
# Проверить что файл загружен
loaded_sources()

# Установить breakpoint по функции вместо строки
set_function_breakpoints(functions=["main.handleRequest"])
```

### Claude Code не видит MCP tools

**Проблема:** AI не может использовать debug команды

**Решение:**
```bash
# Проверить подключение
claude mcp list
# Должен быть: mcp-dap-server ✓ Connected

# Если нет - переподключить
claude mcp remove mcp-dap-server
claude mcp add --transport sse mcp-dap-server http://localhost:8090

# Перезапустить Claude Code
```

---

## 📊 Порты и сервисы

| Service | Debug Port | Production Port | Status |
|---------|-----------|----------------|---------|
| **api-gateway** | 2345 | 8080 | ✅ Ready |
| **worker** | 2346 | - | ✅ Ready |
| **ras-adapter** | 2347 | 8088 | ✅ Ready |
| **batch-service** | 2348 | 8087 | ⚠️ In Dev |

**MCP DAP Server:** http://localhost:8090 (SSE)

---

## 🎓 Best Practices

### DO ✅

1. **Используй для complex bugs** - когда logging недостаточно
2. **Инспектируй состояние** - смотри переменные перед изменением кода
3. **Тестируй гипотезы** - используй `evaluate()` для проверки условий
4. **Сохраняй breakpoints** - документируй найденные проблемные места
5. **Autonomous debugging** - доверяй AI находить баги самостоятельно

### DON'T ❌

1. **НЕ используй в production** - только dev/staging
2. **НЕ оставляй debug сессии надолго** - завершай после отладки
3. **НЕ debug оптимизированный код** - пересобирай с debug флагами
4. **НЕ expose debug порты** - только localhost
5. **НЕ игнорируй security** - debug режим открывает уязвимости

---

## 📚 Дополнительные ресурсы

### Документация

- [Delve Documentation](https://github.com/go-delve/delve/tree/master/Documentation)
- [DAP Specification](https://microsoft.github.io/debug-adapter-protocol/)
- [MCP DAP Server GitHub](https://github.com/go-delve/mcp-dap-server)

### Demo Videos

- [Basic demo with multiple prompts](https://youtu.be/q0pNfhxWAWk)
- [Autonomous agentic debugging pt.1](https://youtu.be/k5Z51et_rog)
- [Autonomous agentic debugging pt.2](https://youtu.be/8PcfLbU_EQM)

### Внутренние документы

- [LOCAL_DEVELOPMENT_GUIDE.md](LOCAL_DEVELOPMENT_GUIDE.md) - Local dev setup
- [CLAUDE.md](../CLAUDE.md) - AI Agent instructions
- [ROADMAP.md](ROADMAP.md) - Project roadmap

---

**Версия:** 1.0
**Последнее обновление:** 2025-11-20
**Авторы:** CommandCenter1C Team + AI Assistant
