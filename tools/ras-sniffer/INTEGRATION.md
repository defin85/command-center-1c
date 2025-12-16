# Интеграция RAS Sniffer в проект

## Добавить в docs/DEVELOPMENT_TOOLS.md

```markdown
### RAS Protocol Sniffer

**Назначение:** Reverse engineering RAS Binary Protocol

**Расположение:** `tools/ras-sniffer/`

**Быстрый старт:**
```bash
cd tools/ras-sniffer
./start.sh

# В другом терминале:
rac.exe cluster list localhost:1546
```

**Документация:** [tools/ras-sniffer/README.md](../tools/ras-sniffer/README.md)
```

## Добавить в CLAUDE.md (секция Tools)

```markdown
## Development Tools

### RAS Protocol Analyzer

**Location:** `tools/ras-sniffer/`

TCP proxy для перехвата и анализа RAS протокола. Используй для:
- Reverse engineering RAS binary protocol
- Debugging ras-grpc-gw интеграции
- Анализ message formats

**Quick usage:**
```bash
cd tools/ras-sniffer && ./start.sh
rac.exe cluster list localhost:1546  # В другом терминале
tail -f ras-protocol-capture.log     # Просмотр захваченного трафика
```
```

## Упоминания в других документах

### 1. docs/1C_ADMINISTRATION_GUIDE.md

Добавить в секцию "Troubleshooting RAS Connection":

```markdown
#### Debugging RAS Protocol

Для детального анализа RAS протокола используй **RAS Protocol Sniffer**:

```bash
cd tools/ras-sniffer
./start.sh

# В другом терминале - команда через proxy
rac.exe cluster list localhost:1546

# Analyze captured traffic
tail -f ras-protocol-capture.log
```

См. [tools/ras-sniffer/README.md](../tools/ras-sniffer/README.md) для деталей.
```

### 2. docs/DJANGO_CLUSTER_INTEGRATION.md

Добавить в секцию "Testing cluster-service integration":

```markdown
### Debug RAS Communication

Используй RAS Sniffer для debugging:

```bash
# Terminal 1: Start sniffer
cd tools/ras-sniffer && ./start.sh

# Terminal 2: Test cluster-service через proxy
curl "http://localhost:8088/api/v2/list-clusters?server=localhost:1546"

# Terminal 3: Analyze traffic
tail -f tools/ras-sniffer/ras-protocol-capture.log
```

**Примечание:** Измени `GRPC_GATEWAY_ADDR` в cluster-service на `:1546` для routing через sniffer.
```

### 3. go-services/cluster-service/README.md

Добавить в секцию "Development":

```markdown
### Debug RAS Protocol

Для debugging RAS communication используй RAS Protocol Sniffer:

```bash
# Start sniffer
cd ../../tools/ras-sniffer && ./start.sh

# Modify cluster-service to use proxy
export GRPC_GATEWAY_ADDR=localhost:1546

# Start cluster-service
go run cmd/main.go

# All RAS traffic will be captured to ras-protocol-capture.log
```
```

## Git commit message (пример)

```
feat(tools): add RAS Protocol Proxy Sniffer for reverse engineering

Создан TCP proxy для перехвата и анализа бинарного протокола RAS.

Features:
- Bi-directional traffic capture (rac.exe ↔ RAS Server)
- Hex dump с ASCII view для каждого пакета
- Автоматический анализ: UUID detection, string extraction, length encoding
- Real-time logging в файл + console
- Готовый бинарник (ras-sniffer.exe)

Usage:
  cd tools/ras-sniffer && ./start.sh
  rac.exe cluster list localhost:1546

Deliverables:
- tools/ras-sniffer/main.go (305 lines)
- tools/ras-sniffer/ras-sniffer.exe (3.3MB)
- tools/ras-sniffer/start.sh (convenience script)
- tools/ras-sniffer/README.md (detailed docs)
- tools/ras-sniffer/QUICKSTART.md (2-min start guide)
- tools/ras-sniffer/DEMO_OUTPUT.txt (example output)

Use case: Reverse engineering для улучшения ras-grpc-gw интеграции

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Следующие шаги

1. **Документация:**
   - Добавить упоминания в указанных документах
   - Обновить docs/START_HERE.md с ссылкой на tools

2. **Integration:**
   - Возможно создать wrapper для cluster-service testing
   - Добавить в CI/CD для automated protocol testing

3. **Enhancement:**
   - Добавить более детальный parser для известных message types
   - Создать Go библиотеку для encoding/decoding RAS messages
   - Интегрировать с ras-grpc-gw для валидации протокола
