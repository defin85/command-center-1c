# OpenAPI TypeScript Code Generation Roadmap

**Version:** 1.0
**Date:** 2025-12-04
**Status:** Draft - Pending Approval
**Total Duration:** 1-2 weeks
**Related:** [contracts/](../../contracts/), [frontend/src/api/](../../frontend/src/api/)

---

## Table of Contents

- [Overview](#overview)
- [Tool Comparison](#tool-comparison)
- [Recommendation](#recommendation)
- [Architecture](#architecture)
- [Implementation Plan](#implementation-plan)
- [Configuration Examples](#configuration-examples)
- [CI Integration](#ci-integration)
- [Migration Strategy](#migration-strategy)
- [Success Metrics](#success-metrics)
- [References](#references)

---

## Overview

### Problem Statement

Frontend TypeScript типы написаны вручную в `frontend/src/types/` и расходятся с реальным API:
- API возвращает `{ workflow: {...} }`, а frontend ожидает объект напрямую
- Ошибки обнаруживаются только в runtime
- Дублирование типов между backend и frontend
- Ручное обновление типов при изменении API

### Goal

Автоматическая генерация TypeScript типов и API клиента из OpenAPI спецификации для:
- Type-safety на этапе компиляции
- Единый источник правды (contracts/)
- Автоматическое обнаружение breaking changes

### Current State

```
contracts/
├── ras-adapter/openapi.yaml      # Существует
├── api-gateway/openapi.yaml      # Планируется
└── orchestrator/openapi.yaml     # Нужно создать из drf-spectacular

frontend/src/
├── types/workflow.ts             # Ручные типы (DEPRECATED after migration)
├── types/database.ts
└── api/endpoints/                # Ручные API функции (DEPRECATED)
```

---

## Tool Comparison

### Comparison Table

| Критерий | **Orval** | openapi-typescript | @hey-api/openapi-ts | openapi-generator |
|----------|-----------|-------------------|---------------------|-------------------|
| **GitHub Stars** | ~5,000 | ~7,600 | ~2,500 | ~21,000 |
| **Weekly Downloads** | ~466K | ~1.7M | ~150K | ~1.2M |
| **Генерирует** | Типы + клиент + hooks | Только типы | Типы + клиент | Полный SDK |
| **Runtime overhead** | ~5-15 KB | **0 KB** | ~6 KB | ~20-50 KB |
| **Tree-shaking** | Хороший | N/A | Хороший | Проблематичный |
| **Axios support** | **Нативный** | Нет (fetch) | **Нативный** | Да |
| **React Query hooks** | **Да** | Нет | Нет | Нет |
| **Mock generation** | **MSW + Faker** | Нет | Нет | Нет |
| **Кастомизация** | Высокая | Низкая | Средняя | Mustache |
| **OpenAPI 3.1** | Да | Да | Да | Частично |

### Detailed Analysis

#### Orval

**Концепция:** Полный генератор клиента с поддержкой React Query, MSW, мокинга.

**Плюсы:**
- Нативная поддержка Axios (используется в проекте)
- Генерирует React Query hooks из коробки
- Поддержка MSW для моков
- Гибкая кастомизация через mutators
- Custom Axios instance с interceptors

**Минусы:**
- Больший размер bundle
- Может генерировать избыточный код

#### openapi-typescript

**Концепция:** Генерирует только TypeScript типы, никакого runtime кода.

**Плюсы:**
- Zero runtime cost
- Быстрая генерация
- Companion library `openapi-fetch`

**Минусы:**
- Требует написания API клиента вручную
- `openapi-fetch` не поддерживает Axios

#### @hey-api/openapi-ts

**Концепция:** Форк `openapi-typescript-codegen` с активной поддержкой.

**Плюсы:**
- Нативная поддержка Axios
- Bundled клиенты
- Активная разработка

**Минусы:**
- Менее зрелый чем Orval
- Нет React Query поддержки

---

## Recommendation

### Primary: **Orval**

**Обоснование:**

1. **Совместимость с проектом:**
   - Нативная поддержка Axios (уже используется в `frontend/src/api/client.ts`)
   - Поддержка custom Axios instance с interceptors (token refresh)

2. **Полнота решения:**
   - Генерирует и типы, и API функции
   - Mode `tags-split` разделяет код по тегам API

3. **Дополнительные возможности:**
   - MSW мокинг для тестов
   - React Query hooks (опционально)

4. **Production-ready:**
   - Используется в продакшене (Ackee Agency, Prototyp Digital)

### Alternative: openapi-typescript + manual client

Если приоритет — минимальный bundle size:
- Генерировать только типы
- Использовать типы в существующих endpoint функциях
- Zero runtime overhead

---

## Architecture

### Source of Truth Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Source of Truth                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Django Orchestrator                    contracts/                  │
│   (drf-spectacular)        ───export──►  orchestrator/               │
│        │                                 openapi.yaml                │
│        │                                     │                       │
│        ▼                                     │                       │
│   GET /api/docs/?format=yaml                 │                       │
│   (runtime schema)                           │                       │
│                                              │                       │
├──────────────────────────────────────────────┼───────────────────────┤
│                         Generation                                   │
├──────────────────────────────────────────────┼───────────────────────┤
│                                              │                       │
│   ┌──────────────────┐                       │                       │
│   │  npm run         │◄──────────────────────┘                       │
│   │  generate:api    │                                               │
│   └────────┬─────────┘                                               │
│            │                                                         │
│            ▼                                                         │
│   ┌──────────────────┐                                               │
│   │  npx orval       │                                               │
│   │  --config        │                                               │
│   │  orval.config.ts │                                               │
│   └────────┬─────────┘                                               │
│            │                                                         │
├────────────┼─────────────────────────────────────────────────────────┤
│            │              Generated Output                           │
├────────────┼─────────────────────────────────────────────────────────┤
│            ▼                                                         │
│   frontend/src/api/generated/                                        │
│   ├── index.ts            # Re-exports                               │
│   ├── workflows.ts        # Workflow API functions                   │
│   ├── databases.ts        # Database API functions                   │
│   ├── operations.ts       # Operations API functions                 │
│   ├── clusters.ts         # Cluster API functions                    │
│   └── model/              # TypeScript interfaces                    │
│       ├── workflowTemplate.ts                                        │
│       ├── workflowExecution.ts                                       │
│       ├── databaseInfo.ts                                            │
│       └── ...                                                        │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                         Integration                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   frontend/src/api/                                                  │
│   ├── client.ts           # Existing axios instance (KEEP)           │
│   ├── generated/          # Auto-generated (committed to git)        │
│   └── endpoints/          # DEPRECATED after migration               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Workflow Integration

| Источник | Когда использовать | Плюсы | Минусы |
|----------|-------------------|-------|--------|
| **contracts/*.yaml** | Production, CI/CD | Версионируется | Может отстать |
| **drf-spectacular** | Development | Всегда актуальный | Требует server |

**Рекомендуемый workflow:**
1. Contract-first: изменения API → обновление contracts/
2. Генерация из статической схемы
3. Периодическая синхронизация с drf-spectacular

---

## Implementation Plan

### Phase 1: Setup (2-4 hours)

**Tasks:**
1. Install Orval: `npm install -D orval`
2. Create `frontend/orval.config.ts`
3. Export OpenAPI from Django: `contracts/orchestrator/openapi.yaml`
4. Update `package.json` scripts

**Deliverables:**
- [ ] Orval installed
- [ ] Configuration file created
- [ ] OpenAPI schema exported
- [ ] `npm run generate:api` working

### Phase 2: Initial Generation (1-2 hours)

**Tasks:**
1. Run initial generation
2. Review generated code structure
3. Verify types match API responses
4. Fix any schema issues

**Deliverables:**
- [ ] `frontend/src/api/generated/` populated
- [ ] Types validated against actual API

### Phase 3: Migration (3-5 days)

**Tasks:**
1. Migrate workflow endpoints
2. Migrate database endpoints
3. Migrate operations endpoints
4. Migrate cluster endpoints
5. Update component imports
6. Remove deprecated manual types

**Deliverables:**
- [ ] All endpoints migrated
- [ ] `frontend/src/types/` deprecated
- [ ] `frontend/src/api/endpoints/` deprecated
- [ ] All components using generated types

### Phase 4: CI Integration (4-8 hours)

**Tasks:**
1. Create GitHub workflow for type generation
2. Add pre-commit validation
3. Setup breaking change detection
4. Documentation update

**Deliverables:**
- [ ] CI workflow created
- [ ] Pre-commit hooks configured
- [ ] Documentation updated

---

## Configuration Examples

### frontend/orval.config.ts

```typescript
import { defineConfig } from 'orval'

export default defineConfig({
  commandcenter: {
    input: {
      target: '../contracts/orchestrator/openapi.yaml',
    },
    output: {
      mode: 'tags-split',
      target: './src/api/generated',
      schemas: './src/api/generated/model',
      client: 'axios',
      override: {
        mutator: {
          path: './src/api/client.ts',
          name: 'apiClient',
        },
        // Transform response wrapper
        transformer: './src/api/transformer.ts',
      },
    },
    hooks: {
      afterAllFilesWrite: 'prettier --write',
    },
  },
})
```

### package.json scripts

```json
{
  "scripts": {
    "generate:api": "orval",
    "generate:api:watch": "orval --watch",
    "predev": "npm run generate:api",
    "prebuild": "npm run generate:api",
    "dev": "vite",
    "build": "tsc && vite build",
    "validate:api": "orval --config orval.config.ts --dry-run"
  }
}
```

### Custom Axios Mutator

```typescript
// frontend/src/api/mutator.ts
import { apiClient } from './client'
import type { AxiosRequestConfig } from 'axios'

export const customInstance = <T>(config: AxiosRequestConfig): Promise<T> => {
  const source = axios.CancelToken.source()
  const promise = apiClient({
    ...config,
    cancelToken: source.token,
  }).then(({ data }) => data)

  // @ts-ignore
  promise.cancel = () => source.cancel('Query was cancelled')

  return promise
}

export default customInstance
```

---

## CI Integration

### .github/workflows/api-types.yml

```yaml
name: API Types Validation

on:
  push:
    paths:
      - 'contracts/**'
      - 'frontend/orval.config.ts'
  pull_request:
    paths:
      - 'contracts/**'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Generate API types
        run: cd frontend && npm run generate:api

      - name: Check for uncommitted changes
        run: |
          if [[ -n $(git status --porcelain frontend/src/api/generated) ]]; then
            echo "::error::Generated types are out of sync!"
            echo "Run 'npm run generate:api' and commit the changes"
            git diff frontend/src/api/generated
            exit 1
          fi

      - name: TypeScript check
        run: cd frontend && npx tsc --noEmit
```

### Pre-commit Hook

```bash
#!/bin/bash
# .githooks/pre-commit

# Check if contracts changed
if git diff --cached --name-only | grep -q "contracts/"; then
  echo "Contracts changed, regenerating API types..."
  cd frontend && npm run generate:api

  # Add generated files to commit
  git add frontend/src/api/generated/
fi
```

---

## Migration Strategy

### Step-by-step Migration

```typescript
// Step 1: Keep old import, add new
import { listWorkflowTemplates } from '@/api/endpoints/workflows'  // OLD
import { listWorkflows } from '@/api/generated'  // NEW

// Step 2: Compare responses in development
const oldData = await listWorkflowTemplates()
const newData = await listWorkflows()
console.assert(JSON.stringify(oldData) === JSON.stringify(newData))

// Step 3: Switch to new import
import { listWorkflows, WorkflowTemplate } from '@/api/generated'

// Step 4: Remove old import after verification
```

### Deprecated Files (to remove after migration)

```
frontend/src/
├── types/
│   ├── workflow.ts      → api/generated/model/
│   ├── database.ts      → api/generated/model/
│   └── operation.ts     → api/generated/model/
└── api/endpoints/
    ├── workflows.ts     → api/generated/workflows.ts
    ├── databases.ts     → api/generated/databases.ts
    └── operations.ts    → api/generated/operations.ts
```

---

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Runtime type errors | ~5/week | 0 | 0 |
| API sync issues | Manual detection | CI detection | 100% automated |
| Type coverage | ~60% | ~95% | >90% |
| Manual type maintenance | ~2h/week | 0 | 0 |

---

## References

- [Orval Documentation](https://orval.dev/)
- [Orval Custom Axios Instance](https://orval.dev/guides/custom-axios)
- [openapi-typescript](https://openapi-ts.dev/)
- [@hey-api/openapi-ts](https://github.com/hey-api/openapi-ts)
- [drf-spectacular Client Generation](https://drf-spectacular.readthedocs.io/en/latest/client_generation.html)
- [React & REST APIs: End-To-End TypeScript](https://profy.dev/article/react-openapi-typescript)
- [Ackee Agency - Orval in Production](https://www.ackee.agency/blog/orval-generating-typescript-from-OpenAPI)

---

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-04 | AI Architect | Initial draft |
