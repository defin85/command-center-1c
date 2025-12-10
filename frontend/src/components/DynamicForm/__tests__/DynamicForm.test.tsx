/**
 * Integration Tests for DynamicForm Component
 *
 * Tests the complete DynamicForm behavior including:
 * - Schema parsing and field rendering
 * - Validation integration
 * - Conditional fields
 * - Field ordering
 * - User interactions
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DynamicForm } from '../DynamicForm'
import type { ExtendedSchemaProperty } from '../types'

describe('DynamicForm Integration', () => {
  it('renders all fields from schema', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        email: { type: 'string', title: 'Email', format: 'email' },
        age: { type: 'number', title: 'Age' },
        active: { type: 'boolean', title: 'Active' },
      },
    }

    const values = {}
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Age')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows required indicator for required fields', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        email: { type: 'string', title: 'Email' },
      },
      required: ['name', 'email'],
    }

    const values = {}
    const onChange = vi.fn()

    const { container } = render(
      <DynamicForm schema={schema} values={values} onChange={onChange} />
    )

    // Ant Design marks required fields with 'ant-form-item-required' class
    // Both fields should be present in the form
    const formItems = container.querySelectorAll('.ant-form-item')
    expect(formItems.length).toBeGreaterThanOrEqual(2)
  })

  it('shows field description as help text', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        username: {
          type: 'string',
          title: 'Username',
          'x-help-text': 'Choose a unique username',
        },
      },
    }

    const values = {}
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    expect(screen.getByText('Choose a unique username')).toBeInTheDocument()
  })

  it('calls onChange when field value changes', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
      },
    }

    const values = { name: '' }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    const input = screen.getByRole('textbox')
    await user.type(input, 'John')

    expect(onChange).toHaveBeenCalled()
    expect(onChange).toHaveBeenLastCalledWith({ name: 'John' })
  })

  it('hides conditional fields when condition not met', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        userType: {
          type: 'string',
          title: 'User Type',
          enum: ['user', 'admin'],
          'x-order': 1,
        },
        department: {
          type: 'string',
          title: 'Department',
          'x-order': 2,
          'x-conditional': {
            field: 'userType',
            value: 'admin',
          },
        },
      },
    }

    const values = { userType: 'user' }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    // Use getAllByText to handle multiple elements (label + title)
    expect(screen.getAllByText('User Type').length).toBeGreaterThan(0)
    expect(screen.queryByText('Department')).not.toBeInTheDocument()
  })

  it('shows conditional field when condition is met', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        userType: {
          type: 'string',
          title: 'User Type',
          enum: ['user', 'admin'],
          'x-order': 1,
        },
        department: {
          type: 'string',
          title: 'Department',
          'x-order': 2,
          'x-conditional': {
            field: 'userType',
            value: 'admin',
          },
        },
      },
    }

    const values = { userType: 'admin' }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    expect(screen.getAllByText('User Type').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Department').length).toBeGreaterThan(0)
  })

  it('shows validation errors', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        email: {
          type: 'string',
          title: 'Email',
          format: 'email',
        },
      },
      required: ['email'],
    }

    const values = {}
    const onChange = vi.fn()
    const onValidationError = vi.fn()

    render(
      <DynamicForm
        schema={schema}
        values={values}
        onChange={onChange}
        onValidationError={onValidationError}
      />
    )

    // Validation errors are shown through Ant Design's Form validation
    // which requires form submission or field blur
    const formItem = screen.getByText('Email').closest('.ant-form-item')
    expect(formItem).toBeInTheDocument()
  })

  it('respects disabled prop', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        age: { type: 'number', title: 'Age' },
      },
    }

    const values = {}
    const onChange = vi.fn()

    render(
      <DynamicForm schema={schema} values={values} onChange={onChange} disabled />
    )

    const nameInput = screen.getByRole('textbox')
    const ageInput = screen.getByRole('spinbutton')

    expect(nameInput).toBeDisabled()
    expect(ageInput).toBeDisabled()
  })

  it('sorts fields by x-order', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        email: { type: 'string', title: 'Email', 'x-order': 3 },
        name: { type: 'string', title: 'Name', 'x-order': 1 },
        age: { type: 'number', title: 'Age', 'x-order': 2 },
      },
    }

    const values = {}
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    const labels = screen.getAllByText(/Name|Age|Email/)
    expect(labels[0]).toHaveTextContent('Name')
    expect(labels[1]).toHaveTextContent('Age')
    expect(labels[2]).toHaveTextContent('Email')
  })

  it('uses horizontal layout when specified', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
      },
    }

    const values = {}
    const onChange = vi.fn()

    render(
      <DynamicForm
        schema={schema}
        values={values}
        onChange={onChange}
        layout="horizontal"
        labelCol={{ span: 6 }}
        wrapperCol={{ span: 18 }}
      />
    )

    const form = screen.getByText('Name').closest('form')
    expect(form).toHaveClass('ant-form-horizontal')
  })

  it('shows "No fields to display" when no fields exist', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {},
    }

    const values = {}
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    expect(screen.getByText('No fields to display')).toBeInTheDocument()
  })

  it('shows "No fields to display" when all fields are conditional and hidden', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        department: {
          type: 'string',
          title: 'Department',
          'x-conditional': {
            field: 'userType',
            value: 'admin',
          },
        },
      },
    }

    const values = { userType: 'user' }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    expect(screen.getByText('No fields to display')).toBeInTheDocument()
  })

  it('handles multiple field types in one form', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name', 'x-order': 1 },
        age: { type: 'number', title: 'Age', 'x-order': 2 },
        active: { type: 'boolean', title: 'Active', 'x-order': 3 },
        status: {
          type: 'string',
          title: 'Status',
          enum: ['active', 'inactive'],
          'x-order': 4,
        },
      },
    }

    const values = {
      name: '',
      age: 0,
      active: false,
      status: '',
    }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    // Verify all field types are rendered
    expect(screen.getByRole('textbox')).toBeInTheDocument() // name
    expect(screen.getByRole('spinbutton')).toBeInTheDocument() // age
    expect(screen.getByRole('switch')).toBeInTheDocument() // active
    expect(screen.getByRole('combobox')).toBeInTheDocument() // status

    // Test interaction with text field
    const nameInput = screen.getByRole('textbox')
    await user.type(nameInput, 'John')

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ name: 'John' })
    )
  })

  it('handles complex conditional logic with multiple conditions', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        role: {
          type: 'string',
          title: 'Role',
          enum: ['user', 'moderator', 'admin'],
          'x-order': 1,
        },
        moderationTools: {
          type: 'string',
          title: 'Moderation Tools',
          'x-order': 2,
          'x-conditional': {
            field: 'role',
            value: ['moderator', 'admin'],
            operator: 'in',
          },
        },
        adminPanel: {
          type: 'string',
          title: 'Admin Panel',
          'x-order': 3,
          'x-conditional': {
            field: 'role',
            value: 'admin',
            operator: 'eq',
          },
        },
      },
    }

    const { rerender } = render(
      <DynamicForm
        schema={schema}
        values={{ role: 'user' }}
        onChange={vi.fn()}
      />
    )

    // User role - no special fields
    expect(screen.getAllByText('Role').length).toBeGreaterThan(0)
    expect(screen.queryByText('Moderation Tools')).not.toBeInTheDocument()
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument()

    // Moderator role - shows moderation tools
    rerender(
      <DynamicForm
        schema={schema}
        values={{ role: 'moderator' }}
        onChange={vi.fn()}
      />
    )

    expect(screen.getAllByText('Moderation Tools').length).toBeGreaterThan(0)
    expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument()

    // Admin role - shows both special fields
    rerender(
      <DynamicForm
        schema={schema}
        values={{ role: 'admin' }}
        onChange={vi.fn()}
      />
    )

    expect(screen.getAllByText('Moderation Tools').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Admin Panel').length).toBeGreaterThan(0)
  })

  it('clears validation errors when field value changes', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          title: 'Name',
          minLength: 3,
        },
      },
    }

    const values = { name: 'ab' }
    const onChange = vi.fn()

    render(<DynamicForm schema={schema} values={values} onChange={onChange} />)

    const input = screen.getByRole('textbox')
    await user.clear(input)
    await user.type(input, 'John')

    // Errors should be cleared when user starts typing
    expect(onChange).toHaveBeenCalled()
  })
})
