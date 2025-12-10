/**
 * Tests for DynamicForm Utilities
 *
 * Covers schemaParser and defaults utilities.
 */

import { describe, it, expect } from 'vitest'
import {
  inferFieldType,
  parseSchemaProperties,
  formatFieldName,
  getSelectOptions,
  sortFieldsByOrder,
  getValidationRules,
} from '../utils/schemaParser'
import {
  extractDefaults,
  getDefaultValue,
  mergeWithDefaults,
  isEmptyValue,
  cleanValues,
  coerceValues,
} from '../utils/defaults'
import type { ExtendedSchemaProperty } from '../types'

describe('schemaParser', () => {
  describe('inferFieldType', () => {
    it('infers text type from string', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Name',
      }

      expect(inferFieldType(schema)).toBe('text')
    })

    it('infers textarea from string with long maxLength', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Description',
        maxLength: 500,
      }

      expect(inferFieldType(schema)).toBe('textarea')
    })

    it('infers number type from integer', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'integer',
        title: 'Age',
      }

      expect(inferFieldType(schema)).toBe('number')
    })

    it('infers number type from number', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'number',
        title: 'Price',
      }

      expect(inferFieldType(schema)).toBe('number')
    })

    it('infers select type from enum', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Status',
        enum: ['active', 'inactive', 'pending'],
      }

      expect(inferFieldType(schema)).toBe('select')
    })

    it('infers boolean type', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'boolean',
        title: 'Active',
      }

      expect(inferFieldType(schema)).toBe('boolean')
    })

    it('infers date type from format', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Birth Date',
        format: 'date',
      }

      expect(inferFieldType(schema)).toBe('date')
    })

    it('infers datetime type from format', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Created At',
        format: 'date-time',
      }

      expect(inferFieldType(schema)).toBe('datetime')
    })

    it('infers password type from format', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Password',
        format: 'password',
      }

      expect(inferFieldType(schema)).toBe('password')
    })

    it('uses explicit x-field-type', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        title: 'Custom',
        'x-field-type': 'textarea',
      }

      expect(inferFieldType(schema)).toBe('textarea')
    })

    it('infers multi-select from array with enum items', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'array',
        title: 'Tags',
        items: {
          type: 'string',
          enum: ['tag1', 'tag2', 'tag3'],
        },
      }

      expect(inferFieldType(schema)).toBe('multi-select')
    })
  })

  describe('parseSchemaProperties', () => {
    it('parses schema properties into field configs', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', title: 'Name', 'x-order': 1 },
          email: { type: 'string', title: 'Email', 'x-order': 2 },
        },
        required: ['name'],
      }

      const fields = parseSchemaProperties(schema)

      expect(fields).toHaveLength(2)
      expect(fields[0]).toMatchObject({
        name: 'name',
        type: 'text',
        label: 'Name',
        required: true,
        order: 1,
      })
      expect(fields[1]).toMatchObject({
        name: 'email',
        type: 'text',
        label: 'Email',
        required: false,
        order: 2,
      })
    })

    it('skips readOnly fields', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', title: 'Name' },
          id: { type: 'string', title: 'ID', readOnly: true },
        },
      }

      const fields = parseSchemaProperties(schema)

      expect(fields).toHaveLength(1)
      expect(fields[0].name).toBe('name')
    })

    it('assigns default order of 999 when not specified', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', title: 'Name' },
        },
      }

      const fields = parseSchemaProperties(schema)

      expect(fields[0].order).toBe(999)
    })

    it('extracts conditional config', () => {
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

      const fields = parseSchemaProperties(schema)

      expect(fields[0].conditional).toEqual({
        field: 'userType',
        value: 'admin',
      })
    })
  })

  describe('formatFieldName', () => {
    it('converts snake_case to Title Case', () => {
      expect(formatFieldName('first_name')).toBe('First Name')
      expect(formatFieldName('user_email_address')).toBe('User Email Address')
    })

    it('converts camelCase to Title Case', () => {
      expect(formatFieldName('firstName')).toBe('First Name')
      expect(formatFieldName('userEmailAddress')).toBe('User Email Address')
    })

    it('handles mixed formats', () => {
      expect(formatFieldName('user_firstName')).toBe('User First Name')
    })
  })

  describe('getSelectOptions', () => {
    it('extracts options from enum', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        enum: ['active', 'inactive', 'pending'],
      }

      const options = getSelectOptions(schema)

      expect(options).toHaveLength(3)
      expect(options[0]).toEqual({ label: 'Active', value: 'active' })
      expect(options[1]).toEqual({ label: 'Inactive', value: 'inactive' })
    })

    it('uses enumNames for labels', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        enum: ['A', 'B', 'C'],
        enumNames: ['Option A', 'Option B', 'Option C'],
      } as ExtendedSchemaProperty

      const options = getSelectOptions(schema)

      expect(options[0]).toEqual({ label: 'Option A', value: 'A' })
      expect(options[1]).toEqual({ label: 'Option B', value: 'B' })
    })

    it('extracts options from oneOf with const', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        oneOf: [
          { const: 'option1', title: 'First Option' },
          { const: 'option2', title: 'Second Option' },
        ],
      }

      const options = getSelectOptions(schema)

      expect(options).toHaveLength(2)
      expect(options[0]).toEqual({ label: 'First Option', value: 'option1' })
    })

    it('extracts options from array items enum', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'array',
        items: {
          type: 'string',
          enum: ['tag1', 'tag2', 'tag3'],
        },
      }

      const options = getSelectOptions(schema)

      expect(options).toHaveLength(3)
      expect(options[0]).toEqual({ label: 'Tag1', value: 'tag1' })
    })
  })

  describe('sortFieldsByOrder', () => {
    it('sorts fields by order property', () => {
      const fields = [
        { name: 'c', order: 3 } as any,
        { name: 'a', order: 1 } as any,
        { name: 'b', order: 2 } as any,
      ]

      const sorted = sortFieldsByOrder(fields)

      expect(sorted.map((f) => f.name)).toEqual(['a', 'b', 'c'])
    })

    it('does not mutate original array', () => {
      const fields = [
        { name: 'c', order: 3 } as any,
        { name: 'a', order: 1 } as any,
      ]

      const original = [...fields]
      sortFieldsByOrder(fields)

      expect(fields).toEqual(original)
    })
  })

  describe('getValidationRules', () => {
    it('creates required rule', () => {
      const fieldConfig = {
        name: 'name',
        required: true,
        label: 'Name',
        schema: { type: 'string' },
      } as any

      const rules = getValidationRules(fieldConfig)

      expect(rules).toContainEqual({
        required: true,
        message: 'Name is required',
      })
    })

    it('creates minLength rule', () => {
      const fieldConfig = {
        name: 'username',
        required: false,
        label: 'Username',
        schema: { type: 'string', minLength: 3 },
      } as any

      const rules = getValidationRules(fieldConfig)

      expect(rules).toContainEqual({
        min: 3,
        message: 'Username must be at least 3 characters',
      })
    })

    it('creates number range rules', () => {
      const fieldConfig = {
        name: 'age',
        required: false,
        label: 'Age',
        schema: { type: 'number', minimum: 18, maximum: 100 },
      } as any

      const rules = getValidationRules(fieldConfig)

      expect(rules).toContainEqual({
        type: 'number',
        min: 18,
        message: 'Age must be at least 18',
      })
      expect(rules).toContainEqual({
        type: 'number',
        max: 100,
        message: 'Age must be at most 100',
      })
    })

    it('creates email format rule', () => {
      const fieldConfig = {
        name: 'email',
        required: false,
        label: 'Email',
        schema: { type: 'string', format: 'email' },
      } as any

      const rules = getValidationRules(fieldConfig)

      expect(rules).toContainEqual({
        type: 'email',
        message: 'Email must be a valid email',
      })
    })
  })
})

describe('defaults utilities', () => {
  describe('extractDefaults', () => {
    it('extracts default values from schema', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', default: 'John' },
          age: { type: 'number', default: 25 },
          active: { type: 'boolean', default: true },
        },
      }

      const defaults = extractDefaults(schema)

      expect(defaults).toEqual({
        name: 'John',
        age: 25,
        active: true,
      })
    })

    it('returns empty object for schema without defaults', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          email: { type: 'string' },
        },
      }

      const defaults = extractDefaults(schema)

      expect(defaults).toEqual({})
    })

    it('handles nested object defaults', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          address: {
            type: 'object',
            properties: {
              city: { type: 'string', default: 'Moscow' },
              zip: { type: 'string', default: '101000' },
            },
          },
        },
      }

      const defaults = extractDefaults(schema)

      expect(defaults).toEqual({
        address: {
          city: 'Moscow',
          zip: '101000',
        },
      })
    })
  })

  describe('getDefaultValue', () => {
    it('returns explicit default value', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
        default: 'default value',
      }

      expect(getDefaultValue(schema)).toBe('default value')
    })

    it('returns undefined for schema without default', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'string',
      }

      expect(getDefaultValue(schema)).toBeUndefined()
    })

    it('returns nested defaults for object type', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', default: 'John' },
        },
      }

      expect(getDefaultValue(schema)).toEqual({ name: 'John' })
    })
  })

  describe('mergeWithDefaults', () => {
    it('merges values with defaults, values take precedence', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          name: { type: 'string', default: 'John' },
          age: { type: 'number', default: 25 },
          city: { type: 'string', default: 'Moscow' },
        },
      }

      const values = { name: 'Jane', age: 30 }

      const merged = mergeWithDefaults(schema, values)

      expect(merged).toEqual({
        name: 'Jane', // from values
        age: 30, // from values
        city: 'Moscow', // from defaults
      })
    })
  })

  describe('isEmptyValue', () => {
    it('returns true for null and undefined', () => {
      expect(isEmptyValue(null)).toBe(true)
      expect(isEmptyValue(undefined)).toBe(true)
    })

    it('returns true for empty string', () => {
      expect(isEmptyValue('')).toBe(true)
      expect(isEmptyValue('   ')).toBe(true)
    })

    it('returns true for empty array', () => {
      expect(isEmptyValue([])).toBe(true)
    })

    it('returns false for non-empty values', () => {
      expect(isEmptyValue('text')).toBe(false)
      expect(isEmptyValue(0)).toBe(false)
      expect(isEmptyValue(false)).toBe(false)
      expect(isEmptyValue(['item'])).toBe(false)
    })
  })

  describe('cleanValues', () => {
    it('removes empty values', () => {
      const values = {
        name: 'John',
        email: '',
        age: null,
        city: 'Moscow',
        tags: [],
      }

      const cleaned = cleanValues(values)

      expect(cleaned).toEqual({
        name: 'John',
        city: 'Moscow',
      })
    })

    it('recursively cleans nested objects', () => {
      const values = {
        user: {
          name: 'John',
          email: '',
          address: {
            city: 'Moscow',
            zip: null,
          },
        },
        extra: null,
      }

      const cleaned = cleanValues(values)

      expect(cleaned).toEqual({
        user: {
          name: 'John',
          address: {
            city: 'Moscow',
          },
        },
      })
    })
  })

  describe('coerceValues', () => {
    it('coerces string to integer', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          age: { type: 'integer' },
        },
      }

      const values = { age: '25' }

      const coerced = coerceValues(schema, values)

      expect(coerced).toEqual({ age: 25 })
    })

    it('coerces string to number', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          price: { type: 'number' },
        },
      }

      const values = { price: '19.99' }

      const coerced = coerceValues(schema, values)

      expect(coerced).toEqual({ price: 19.99 })
    })

    it('coerces string to boolean', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          active: { type: 'boolean' },
        },
      }

      const values = { active: 'true' }

      const coerced = coerceValues(schema, values)

      expect(coerced).toEqual({ active: true })
    })

    it('ensures arrays stay as arrays', () => {
      const schema: ExtendedSchemaProperty = {
        type: 'object',
        properties: {
          tags: { type: 'array' },
        },
      }

      const values = { tags: 'single-value' }

      const coerced = coerceValues(schema, values)

      expect(coerced).toEqual({ tags: ['single-value'] })
    })
  })
})
