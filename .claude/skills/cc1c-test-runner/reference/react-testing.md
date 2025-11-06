# React Testing Reference

Детальное руководство по тестированию React компонентов в CommandCenter1C.

## Running React Tests

```bash
# All tests
cd frontend
npm test

# Watch mode (interactive)
npm test -- --watch

# Coverage
npm test -- --coverage

# Specific test file
npm test -- OperationForm.test.tsx

# Update snapshots
npm test -- -u

# Run once (CI mode)
npm test -- --watchAll=false
```

## Component Tests

```typescript
// frontend/src/components/OperationForm.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OperationForm from './OperationForm';

describe('OperationForm', () => {
  it('renders form fields', () => {
    render(<OperationForm onSubmit={jest.fn()} />);

    expect(screen.getByLabelText('Название')).toBeInTheDocument();
    expect(screen.getByLabelText('Тип операции')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Создать' })).toBeInTheDocument();
  });

  it('validates required fields', async () => {
    render(<OperationForm onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Пожалуйста введите название')).toBeInTheDocument();
    });
  });

  it('calls onSubmit with form data', async () => {
    const mockSubmit = jest.fn();
    render(<OperationForm onSubmit={mockSubmit} />);

    const nameInput = screen.getByLabelText('Название');
    const typeSelect = screen.getByLabelText('Тип операции');

    fireEvent.change(nameInput, { target: { value: 'Test Operation' } });
    fireEvent.change(typeSelect, { target: { value: 'create_users' } });

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        name: 'Test Operation',
        operation_type: 'create_users'
      });
    });
  });
});
```

## API Client Tests

```typescript
// frontend/src/api/endpoints/operations.test.ts
import { operationsApi } from './operations';
import { apiClient } from '../client';

jest.mock('../client');

describe('operationsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('fetches all operations', async () => {
    const mockData = [{ id: 1, name: 'Operation 1' }];
    (apiClient.get as jest.Mock).mockResolvedValue({ data: mockData });

    const result = await operationsApi.getAll();

    expect(apiClient.get).toHaveBeenCalledWith('/operations/');
    expect(result).toEqual(mockData);
  });

  it('creates new operation', async () => {
    const newOperation = { name: 'New Op', operation_type: 'create_users' };
    const mockResponse = { id: 1, ...newOperation };
    (apiClient.post as jest.Mock).mockResolvedValue({ data: mockResponse });

    const result = await operationsApi.create(newOperation);

    expect(apiClient.post).toHaveBeenCalledWith('/operations/', newOperation);
    expect(result).toEqual(mockResponse);
  });
});
```

## Store Tests (Zustand)

```typescript
// frontend/src/stores/useOperations.test.ts
import { renderHook, act } from '@testing-library/react-hooks';
import { useOperations } from './useOperations';
import { operationsApi } from '../api/endpoints/operations';

jest.mock('../api/endpoints/operations');

describe('useOperations', () => {
  it('fetches operations on fetchData call', async () => {
    const mockData = [{ id: 1, name: 'Op 1' }];
    (operationsApi.getAll as jest.Mock).mockResolvedValue(mockData);

    const { result } = renderHook(() => useOperations());

    await act(async () => {
      await result.current.fetchData();
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.loading).toBe(false);
  });

  it('handles errors during fetch', async () => {
    (operationsApi.getAll as jest.Mock).mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => useOperations());

    await act(async () => {
      await result.current.fetchData();
    });

    expect(result.current.error).toBe('API Error');
    expect(result.current.loading).toBe(false);
  });
});
```

## Coverage

```bash
# Coverage with thresholds
npm test -- --coverage --coverageThreshold='{"global":{"branches":60,"functions":60,"lines":60,"statements":60}}'

# View uncovered lines
npm test -- --coverage --verbose

# Coverage for specific files
npm test -- --coverage --collectCoverageFrom='src/components/**/*.tsx'
```
