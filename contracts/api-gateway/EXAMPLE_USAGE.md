# TypeScript API Client - Примеры использования

> Практические примеры использования автогенерированного TypeScript клиента в React приложении

---

## Установка и настройка

### 1. Генерация клиента

```bash
# Автоматически при старте
./scripts/dev/start-all.sh

# Или вручную
./contracts/scripts/generate-all.sh --force
```

### 2. Импорт в проект

```typescript
// frontend/src/api/client.ts
import { DefaultApi, Configuration } from '@/api/generated';

// Создать конфигурацию
const config = new Configuration({
  basePath: process.env.REACT_APP_API_URL || 'http://localhost:8080',
  accessToken: () => localStorage.getItem('jwt_token') || ''
});

// Экспортировать API instance
export const api = new DefaultApi(config);
```

---

## Базовые примеры

### Пример 1: Получить список операций

```typescript
import { api } from '@/api/client';
import { OperationList } from '@/api/generated';

async function fetchOperations() {
  try {
    const response = await api.listOperations();
    const operations: OperationList = response.data;

    console.log(`Total operations: ${operations.total}`);
    operations.operations?.forEach(op => {
      console.log(`${op.id}: ${op.status} (${op.progress}%)`);
    });

    return operations;
  } catch (error) {
    console.error('Failed to fetch operations:', error);
    throw error;
  }
}
```

### Пример 2: Получить детали операции

```typescript
import { api } from '@/api/client';
import { Operation } from '@/api/generated';

async function getOperationDetails(operationId: string) {
  const response = await api.getOperation(operationId);
  const operation: Operation = response.data;

  return operation;
}

// Использование
const operation = await getOperationDetails('550e8400-e29b-41d4-a716-446655440000');
console.log(`Status: ${operation.status}, Progress: ${operation.progress}%`);
```

### Пример 3: Отменить операцию

```typescript
import { api } from '@/api/client';

async function cancelOperation(operationId: string) {
  const response = await api.cancelOperation(operationId);

  if (response.data.success) {
    console.log('Operation cancelled successfully');
  }

  return response.data;
}
```

---

## React Hooks

### useOperations - список операций с фильтрацией

```typescript
// frontend/src/hooks/useOperations.ts
import { useState, useEffect } from 'react';
import { api } from '@/api/client';
import { OperationList, Operation } from '@/api/generated';

interface UseOperationsOptions {
  status?: 'pending' | 'running' | 'completed' | 'failed';
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useOperations(options: UseOperationsOptions = {}) {
  const [data, setData] = useState<OperationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchOperations = async () => {
    try {
      setLoading(true);
      const response = await api.listOperations(
        options.status,
        100,  // limit
        0     // offset
      );
      setData(response.data);
      setError(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperations();

    // Auto-refresh
    if (options.autoRefresh) {
      const interval = setInterval(
        fetchOperations,
        options.refreshInterval || 5000
      );
      return () => clearInterval(interval);
    }
  }, [options.status, options.autoRefresh]);

  return { data, loading, error, refetch: fetchOperations };
}
```

**Использование в компоненте:**

```typescript
// frontend/src/components/OperationsList.tsx
import React from 'react';
import { useOperations } from '@/hooks/useOperations';

export function OperationsList() {
  const { data, loading, error } = useOperations({
    status: 'running',
    autoRefresh: true,
    refreshInterval: 3000  // 3 секунды
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h2>Running Operations ({data?.total})</h2>
      {data?.operations?.map(op => (
        <div key={op.id}>
          {op.operation_type}: {op.progress}%
        </div>
      ))}
    </div>
  );
}
```

### useDatabase - детали базы данных

```typescript
// frontend/src/hooks/useDatabase.ts
import { useState, useEffect } from 'react';
import { api } from '@/api/client';
import { Database } from '@/api/generated';

export function useDatabase(databaseId: string | null) {
  const [data, setData] = useState<Database | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!databaseId) {
      setLoading(false);
      return;
    }

    const fetchDatabase = async () => {
      try {
        setLoading(true);
        const response = await api.getDatabase(databaseId);
        setData(response.data);
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    };

    fetchDatabase();
  }, [databaseId]);

  return { data, loading, error };
}
```

---

## Обработка ошибок

### Глобальный Axios Interceptor

```typescript
// frontend/src/api/client.ts
import axios from 'axios';
import { DefaultApi, Configuration } from '@/api/generated';

// Создать Axios instance с interceptors
const axiosInstance = axios.create();

// Request interceptor - добавить токен
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - обработка ошибок
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - redirect to login
      localStorage.removeItem('jwt_token');
      window.location.href = '/login';
    } else if (error.response?.status === 429) {
      // Rate limit exceeded
      alert('Слишком много запросов. Подождите минуту.');
    } else if (error.response?.status >= 500) {
      // Server error
      console.error('Server error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

// Создать API client с custom axios instance
const config = new Configuration({
  basePath: process.env.REACT_APP_API_URL || 'http://localhost:8080',
  baseOptions: { axios: axiosInstance }
});

export const api = new DefaultApi(config, '', axiosInstance);
```

### Локальная обработка ошибок

```typescript
import { AxiosError } from 'axios';
import { api } from '@/api/client';
import { ErrorResponse } from '@/api/generated';

async function safeFetchOperation(operationId: string) {
  try {
    const response = await api.getOperation(operationId);
    return { success: true, data: response.data };
  } catch (error) {
    const axiosError = error as AxiosError<ErrorResponse>;

    if (axiosError.response) {
      // Сервер вернул ошибку
      return {
        success: false,
        error: axiosError.response.data.error,
        code: axiosError.response.data.code
      };
    } else if (axiosError.request) {
      // Запрос отправлен, но ответа нет
      return {
        success: false,
        error: 'No response from server',
        code: 'NETWORK_ERROR'
      };
    } else {
      // Ошибка настройки запроса
      return {
        success: false,
        error: axiosError.message,
        code: 'CLIENT_ERROR'
      };
    }
  }
}
```

---

## Продвинутые примеры

### Пример 4: Пагинация

```typescript
import { useState } from 'react';
import { api } from '@/api/client';
import { OperationList } from '@/api/generated';

function usePaginatedOperations() {
  const [page, setPage] = useState(0);
  const [pageSize] = useState(20);
  const [data, setData] = useState<OperationList | null>(null);

  const fetchPage = async (pageNum: number) => {
    const offset = pageNum * pageSize;
    const response = await api.listOperations(
      undefined,  // status filter
      pageSize,   // limit
      offset      // offset
    );
    setData(response.data);
    setPage(pageNum);
  };

  const nextPage = () => {
    if (data && (page + 1) * pageSize < data.total) {
      fetchPage(page + 1);
    }
  };

  const prevPage = () => {
    if (page > 0) {
      fetchPage(page - 1);
    }
  };

  return {
    data,
    page,
    pageSize,
    totalPages: data ? Math.ceil(data.total / pageSize) : 0,
    nextPage,
    prevPage,
    fetchPage
  };
}
```

### Пример 5: Создание кластера

```typescript
import { api } from '@/api/client';
import { ClusterCreate, Cluster } from '@/api/generated';

async function createCluster(data: ClusterCreate): Promise<Cluster> {
  const response = await api.createCluster(data);
  return response.data;
}

// Использование
const newCluster = await createCluster({
  name: 'Production Cluster',
  ras_server: 'localhost:1545',
  cluster_service_url: 'http://localhost:8088',
  cluster_user: 'admin',
  cluster_pwd: 'secure_password'
});

console.log(`Created cluster: ${newCluster.id}`);
```

### Пример 6: Синхронизация кластера

```typescript
import { api } from '@/api/client';

async function syncCluster(clusterId: string) {
  const response = await api.syncCluster(clusterId);
  const result = response.data;

  console.log(`Sync completed in ${result.duration_ms}ms:`);
  console.log(`  Created: ${result.created} databases`);
  console.log(`  Updated: ${result.updated} databases`);
  console.log(`  Errors: ${result.errors}`);

  return result;
}
```

---

## TypeScript типы

### Все типы автогенерируются

```typescript
// Импортировать типы
import {
  Operation,
  OperationList,
  Database,
  DatabaseList,
  Cluster,
  ClusterList,
  HealthResponse,
  StatusResponse,
  ErrorResponse,
  // ... и другие
} from '@/api/generated';

// Type-safe функции
function processOperation(op: Operation) {
  // IDE автодополнение для всех полей
  if (op.status === 'running') {
    console.log(`Progress: ${op.progress}%`);
  }
}

// Union types для enum
type OperationStatus = 'pending' | 'running' | 'completed' | 'failed';
const status: OperationStatus = 'running';  // Type-safe
```

### Generic обертки

```typescript
// Типизированная обработка результата
type ApiResult<T> = {
  success: true;
  data: T;
} | {
  success: false;
  error: string;
  code: string;
};

async function apiCall<T>(
  fn: () => Promise<{ data: T }>
): Promise<ApiResult<T>> {
  try {
    const response = await fn();
    return { success: true, data: response.data };
  } catch (error) {
    const axiosError = error as AxiosError<ErrorResponse>;
    return {
      success: false,
      error: axiosError.response?.data.error || 'Unknown error',
      code: axiosError.response?.data.code || 'UNKNOWN'
    };
  }
}

// Использование
const result = await apiCall(() => api.getOperation(id));
if (result.success) {
  console.log(result.data.status);  // Type-safe
} else {
  console.error(result.error);
}
```

---

## Тестирование

### Mock API для тестов

```typescript
// frontend/src/__mocks__/api.ts
import { OperationList, Operation } from '@/api/generated';

export const mockOperationList: OperationList = {
  operations: [
    {
      id: '123',
      operation_type: 'install_extension',
      status: 'running',
      progress: 50,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      completed_at: null
    }
  ],
  total: 1,
  limit: 100,
  offset: 0
};

export const mockApi = {
  listOperations: jest.fn().mockResolvedValue({ data: mockOperationList }),
  getOperation: jest.fn().mockResolvedValue({ data: mockOperationList.operations[0] }),
  cancelOperation: jest.fn().mockResolvedValue({ data: { success: true, message: 'OK' } })
};
```

---

## Миграция со старого кода

### Было (без типизации):

```typescript
// Старый код
const response = await fetch('/api/v1/operations');
const data = await response.json();
// Нет типов, нет автодополнения
data.operations.forEach(op => {
  console.log(op.status);  // Может быть undefined
});
```

### Стало (с автогенерацией):

```typescript
// Новый код
const response = await api.listOperations();
const data: OperationList = response.data;
// Полная типизация
data.operations?.forEach(op => {
  console.log(op.status);  // Type-safe, гарантирован
});
```

---

## См. также

- [README.md](./README.md) - документация API Gateway
- [openapi.yaml](./openapi.yaml) - полная спецификация API
- [TypeScript Axios Generator](https://openapi-generator.tech/docs/generators/typescript-axios/)

---

**Дата создания:** 2025-11-24
**Обновлено:** 2025-11-24
