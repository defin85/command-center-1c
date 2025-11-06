// Example: React Testing Library component test
// frontend/src/components/OperationForm.test.tsx

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OperationForm from './OperationForm';

describe('OperationForm', () => {
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
  });

  it('renders all form fields', () => {
    render(<OperationForm onSubmit={mockOnSubmit} />);

    expect(screen.getByLabelText('Название')).toBeInTheDocument();
    expect(screen.getByLabelText('Тип операции')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Создать' })).toBeInTheDocument();
  });

  it('validates required fields', async () => {
    render(<OperationForm onSubmit={mockOnSubmit} />);

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Пожалуйста введите название')).toBeInTheDocument();
    });

    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    render(<OperationForm onSubmit={mockOnSubmit} />);

    const nameInput = screen.getByLabelText('Название');
    const typeSelect = screen.getByLabelText('Тип операции');

    fireEvent.change(nameInput, { target: { value: 'Test Operation' } });
    fireEvent.change(typeSelect, { target: { value: 'create_users' } });

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith({
        name: 'Test Operation',
        operation_type: 'create_users'
      });
    });
  });

  it('disables submit button while submitting', async () => {
    const slowSubmit = jest.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    render(<OperationForm onSubmit={slowSubmit} />);

    const nameInput = screen.getByLabelText('Название');
    fireEvent.change(nameInput, { target: { value: 'Test' } });

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    expect(submitButton).toBeDisabled();

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it('shows error message on submit failure', async () => {
    const failingSubmit = jest.fn(() => Promise.reject(new Error('API Error')));
    render(<OperationForm onSubmit={failingSubmit} />);

    const nameInput = screen.getByLabelText('Название');
    fireEvent.change(nameInput, { target: { value: 'Test' } });

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Ошибка при создании операции')).toBeInTheDocument();
    });
  });
});
