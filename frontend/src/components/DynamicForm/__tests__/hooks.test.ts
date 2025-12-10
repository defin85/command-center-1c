/**
 * Tests for DynamicForm Hooks
 *
 * Covers useSchemaValidation, useConditionalFields, and useFieldOrder hooks.
 */

import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useSchemaValidation } from '../hooks/useSchemaValidation'
import { useConditionalFields } from '../hooks/useConditionalFields'
import { useFieldOrder } from '../hooks/useFieldOrder'
import type { ExtendedSchemaProperty, FieldConfig } from '../types'

describe('useSchemaValidation', () => {
  it('validates required fields', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        email: { type: 'string', title: 'Email' },
      },
      required: ['name', 'email'],
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    // Valid data - should pass
    const validResult = result.current.validate({ name: 'John', email: 'john@example.com' })
    expect(validResult).toBe(true)

    // Missing required field - should fail
    const invalidResult = result.current.validate({ name: 'John' })
    expect(invalidResult).toBe(false)

    // After validation fails, errors should be populated
    await waitFor(() => {
      expect(result.current.errors.length).toBeGreaterThan(0)
    })
    expect(result.current.errors[0].code).toBe('required')
    expect(result.current.errors[0].field).toBe('email')
  })

  it('validates string minLength', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        username: {
          type: 'string',
          title: 'Username',
          minLength: 3,
        },
      },
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    // Too short - should fail
    const invalidResult = result.current.validate({ username: 'ab' })
    expect(invalidResult).toBe(false)
    await waitFor(() => {
      expect(result.current.errors[0].code).toBe('minLength')
    })

    // Valid length - should pass
    const validResult = result.current.validate({ username: 'abc' })
    expect(validResult).toBe(true)
  })

  it('validates number minimum and maximum', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        age: {
          type: 'number',
          title: 'Age',
          minimum: 18,
          maximum: 100,
        },
      },
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    // Below minimum - should fail
    const belowMin = result.current.validate({ age: 17 })
    expect(belowMin).toBe(false)
    await waitFor(() => {
      expect(result.current.errors[0].code).toBe('minimum')
    })

    // Above maximum - should fail
    const aboveMax = result.current.validate({ age: 101 })
    expect(aboveMax).toBe(false)
    await waitFor(() => {
      expect(result.current.errors[0].code).toBe('maximum')
    })

    // Within range - should pass
    const validResult = result.current.validate({ age: 25 })
    expect(validResult).toBe(true)
  })

  it('validates email format', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        email: {
          type: 'string',
          title: 'Email',
          format: 'email',
        },
      },
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    // Invalid email - should fail
    const invalidResult = result.current.validate({ email: 'invalid-email' })
    expect(invalidResult).toBe(false)
    await waitFor(() => {
      expect(result.current.errors[0].code).toBe('format')
    })

    // Valid email - should pass
    const validResult = result.current.validate({ email: 'test@example.com' })
    expect(validResult).toBe(true)
  })

  it('returns empty errors for valid data', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        age: { type: 'number', title: 'Age', minimum: 0 },
      },
      required: ['name'],
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    expect(result.current.validate({ name: 'John', age: 30 })).toBe(true)
    expect(result.current.errors).toHaveLength(0)
    expect(result.current.errorMap).toEqual({})
  })

  it('provides getFieldError helper', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name', minLength: 3 },
      },
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    const invalidResult = result.current.validate({ name: 'ab' })
    expect(invalidResult).toBe(false)

    await waitFor(() => {
      expect(result.current.getFieldError('name')).toBeTruthy()
    })
    expect(result.current.getFieldError('nonexistent')).toBeUndefined()
  })

  it('clears errors when clearErrors is called', async () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    }

    const { result } = renderHook(() => useSchemaValidation(schema))

    // Create validation error
    const invalidResult = result.current.validate({})
    expect(invalidResult).toBe(false)
    await waitFor(() => {
      expect(result.current.errors.length).toBeGreaterThan(0)
    })

    // Clear errors
    result.current.clearErrors()
    await waitFor(() => {
      expect(result.current.errors).toHaveLength(0)
    })
  })
})

describe('useConditionalFields', () => {
  const createFieldConfig = (
    name: string,
    conditional?: FieldConfig['conditional']
  ): FieldConfig => ({
    name,
    type: 'text',
    schema: { type: 'string', title: name },
    order: 0,
    required: false,
    label: name,
    conditional,
  })

  it('shows field when condition is met with eq operator', () => {
    const values = { userType: 'admin' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('department', {
      field: 'userType',
      value: 'admin',
      operator: 'eq',
    })

    expect(result.current.isFieldVisible(field)).toBe(true)
  })

  it('hides field when condition is not met', () => {
    const values = { userType: 'user' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('department', {
      field: 'userType',
      value: 'admin',
      operator: 'eq',
    })

    expect(result.current.isFieldVisible(field)).toBe(false)
  })

  it('shows field with neq operator when values differ', () => {
    const values = { userType: 'user' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('publicProfile', {
      field: 'userType',
      value: 'admin',
      operator: 'neq',
    })

    expect(result.current.isFieldVisible(field)).toBe(true)
  })

  it('shows field with in operator when value is in array', () => {
    const values = { userType: 'moderator' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('moderationTools', {
      field: 'userType',
      value: ['admin', 'moderator'],
      operator: 'in',
    })

    expect(result.current.isFieldVisible(field)).toBe(true)
  })

  it('hides field with in operator when value is not in array', () => {
    const values = { userType: 'user' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('moderationTools', {
      field: 'userType',
      value: ['admin', 'moderator'],
      operator: 'in',
    })

    expect(result.current.isFieldVisible(field)).toBe(false)
  })

  it('shows field without conditional always', () => {
    const values = { userType: 'user' }
    const { result } = renderHook(() => useConditionalFields(values))

    const field = createFieldConfig('name')

    expect(result.current.isFieldVisible(field)).toBe(true)
  })

  it('filters visible fields correctly', () => {
    const values = { userType: 'admin' }
    const { result } = renderHook(() => useConditionalFields(values))

    const fields: FieldConfig[] = [
      createFieldConfig('name'),
      createFieldConfig('email'),
      createFieldConfig('department', {
        field: 'userType',
        value: 'admin',
      }),
      createFieldConfig('publicBio', {
        field: 'userType',
        value: 'user',
      }),
    ]

    const visible = result.current.getVisibleFields(fields)

    expect(visible).toHaveLength(3)
    expect(visible.map((f) => f.name)).toEqual(['name', 'email', 'department'])
  })
})

describe('useFieldOrder', () => {
  it('sorts fields by x-order', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        email: { type: 'string', title: 'Email', 'x-order': 3 },
        name: { type: 'string', title: 'Name', 'x-order': 1 },
        age: { type: 'number', title: 'Age', 'x-order': 2 },
      },
    }

    const { result } = renderHook(() => useFieldOrder(schema))

    expect(result.current.fields.map((f) => f.name)).toEqual(['name', 'age', 'email'])
  })

  it('places fields without order at the end', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name', 'x-order': 1 },
        email: { type: 'string', title: 'Email' }, // no order
        age: { type: 'number', title: 'Age', 'x-order': 2 },
        phone: { type: 'string', title: 'Phone' }, // no order
      },
    }

    const { result } = renderHook(() => useFieldOrder(schema))

    const fieldNames = result.current.fields.map((f) => f.name)
    expect(fieldNames.slice(0, 2)).toEqual(['name', 'age'])
    expect(fieldNames.slice(2)).toContain('email')
    expect(fieldNames.slice(2)).toContain('phone')
  })

  it('returns field count', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        email: { type: 'string', title: 'Email' },
        age: { type: 'number', title: 'Age' },
      },
    }

    const { result } = renderHook(() => useFieldOrder(schema))

    expect(result.current.fieldCount).toBe(3)
  })

  it('provides getField helper', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        email: { type: 'string', title: 'Email' },
      },
    }

    const { result } = renderHook(() => useFieldOrder(schema))

    const nameField = result.current.getField('name')
    expect(nameField).toBeDefined()
    expect(nameField?.name).toBe('name')

    const nonexistent = result.current.getField('nonexistent')
    expect(nonexistent).toBeUndefined()
  })

  it('skips readOnly fields', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        id: { type: 'string', title: 'ID', readOnly: true },
        email: { type: 'string', title: 'Email' },
      },
    }

    const { result } = renderHook(() => useFieldOrder(schema))

    expect(result.current.fieldCount).toBe(2)
    expect(result.current.fields.map((f) => f.name)).toEqual(['name', 'email'])
  })
})
