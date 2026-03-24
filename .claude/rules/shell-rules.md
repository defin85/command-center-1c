# Shell Rules for AI Agents

> Статус: legacy/non-authoritative Claude rule.
> Для текущего agent-facing onboarding используйте [../../docs/agent/INDEX.md](../../docs/agent/INDEX.md).

> Правила работы с shell в WSL + Arch Linux.

## Environment

**OS:** WSL + Arch Linux (minimal installation)

## NOT Available by Default

- `jq` — use Python for JSON parsing
- `yq` — use Python for YAML
- `bat`, `fd`, `exa` — use basic `cat`, `find`, `ls`

## Best Practices

### 1. Check HTTP Responses Before Parsing

```python
# BAD - crashes if not JSON
r.json()

# GOOD
if r.status_code == 200:
    data = r.json()
else:
    print(f"Error: {r.status_code} - {r.text[:200]}")
```

### 2. Use Python Instead of jq/curl Pipelines

```python
# BAD - jq not installed
curl ... | jq '.field'

# GOOD
import requests
r = requests.get(url)
print(r.json().get('field'))
```

### 3. Django Operations via manage.py shell

```bash
cd orchestrator && source venv/bin/activate
python manage.py shell -c "from apps.databases.models import Database; print(Database.objects.count())"
```

### 4. Check Utility Availability

```bash
command -v jq &>/dev/null && jq ... || python -c "..."
```

### 5. Redis Checks

```bash
redis-cli XINFO GROUPS events:worker:cluster-synced
# Or via Python redis library
```

## Common Patterns

### Reading JSON from API

```python
import requests

def get_json(url):
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    print(f"Error {r.status_code}: {r.text[:200]}")
    return None
```

### Working with Django Data

```bash
cd orchestrator && source venv/bin/activate
python manage.py shell << 'EOF'
from apps.databases.models import Database
from apps.operations.models import BatchOperation

print(f"Databases: {Database.objects.count()}")
print(f"Operations: {BatchOperation.objects.count()}")
EOF
```
