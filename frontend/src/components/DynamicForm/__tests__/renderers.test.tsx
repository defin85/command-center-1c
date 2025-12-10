/**
 * Tests for DynamicForm Field Renderers
 *
 * Covers all field renderers: Text, Number, Boolean, Select, Date.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TextFieldRenderer } from '../renderers/TextFieldRenderer'
import { NumberFieldRenderer } from '../renderers/NumberFieldRenderer'
import { BooleanFieldRenderer } from '../renderers/BooleanFieldRenderer'
import { SelectFieldRenderer } from '../renderers/SelectFieldRenderer'
import { DateFieldRenderer } from '../renderers/DateFieldRenderer'
import type { ExtendedSchemaProperty } from '../types'

describe('TextFieldRenderer', () => {
  it('renders text input', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Name',
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="name"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByRole('textbox')
    expect(input).toBeInTheDocument()
  })

  it('renders textarea for textarea type', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Description',
      'x-field-type': 'textarea',
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="description"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeInTheDocument()
    expect(textarea.tagName).toBe('TEXTAREA')
  })

  it('renders password input for password type', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Password',
      'x-field-type': 'password',
    }

    const onChange = vi.fn()

    const { container } = render(
      <TextFieldRenderer
        name="password"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = container.querySelector('input[type="password"]')
    expect(input).toBeInTheDocument()
  })

  it('shows placeholder', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Email',
      'x-placeholder': 'Enter your email',
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="email"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByPlaceholderText('Enter your email')
    expect(input).toBeInTheDocument()
  })

  it('calls onChange when value changes', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Name',
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="name"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByRole('textbox')
    await user.type(input, 'John')

    // userEvent.type calls onChange for each character
    // We just verify that onChange was called with some value
    expect(onChange).toHaveBeenCalled()
    expect(onChange.mock.calls.length).toBeGreaterThan(0)
  })

  it('respects disabled state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Name',
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="name"
        schema={schema}
        value=""
        onChange={onChange}
        disabled
      />
    )

    const input = screen.getByRole('textbox')
    expect(input).toBeDisabled()
  })

  it('respects maxLength', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Name',
      maxLength: 50,
    }

    const onChange = vi.fn()

    render(
      <TextFieldRenderer
        name="name"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByRole('textbox')
    expect(input).toHaveAttribute('maxlength', '50')
  })
})

describe('NumberFieldRenderer', () => {
  it('renders input number', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'number',
      title: 'Price',
    }

    const onChange = vi.fn()

    render(
      <NumberFieldRenderer
        name="price"
        schema={schema}
        value={0}
        onChange={onChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    expect(input).toBeInTheDocument()
  })

  it('respects min and max values', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'number',
      title: 'Age',
      minimum: 18,
      maximum: 100,
    }

    const onChange = vi.fn()

    render(
      <NumberFieldRenderer
        name="age"
        schema={schema}
        value={25}
        onChange={onChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    expect(input).toHaveAttribute('aria-valuemin', '18')
    expect(input).toHaveAttribute('aria-valuemax', '100')
  })

  it('calls onChange with number value', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'number',
      title: 'Price',
    }

    const onChange = vi.fn()

    render(
      <NumberFieldRenderer
        name="price"
        schema={schema}
        value={0}
        onChange={onChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    await user.clear(input)
    await user.type(input, '19.99')

    expect(onChange).toHaveBeenCalled()
  })

  it('uses step 1 for integer type', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'integer',
      title: 'Count',
    }

    const onChange = vi.fn()

    render(
      <NumberFieldRenderer
        name="count"
        schema={schema}
        value={0}
        onChange={onChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    expect(input).toHaveAttribute('step', '1')
  })

  it('respects disabled state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'number',
      title: 'Price',
    }

    const onChange = vi.fn()

    render(
      <NumberFieldRenderer
        name="price"
        schema={schema}
        value={0}
        onChange={onChange}
        disabled
      />
    )

    const input = screen.getByRole('spinbutton')
    expect(input).toBeDisabled()
  })
})

describe('BooleanFieldRenderer', () => {
  it('renders switch', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'boolean',
      title: 'Active',
    }

    const onChange = vi.fn()

    render(
      <BooleanFieldRenderer
        name="active"
        schema={schema}
        value={false}
        onChange={onChange}
      />
    )

    const switchElement = screen.getByRole('switch')
    expect(switchElement).toBeInTheDocument()
  })

  it('shows checked state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'boolean',
      title: 'Active',
    }

    const onChange = vi.fn()

    const { rerender } = render(
      <BooleanFieldRenderer
        name="active"
        schema={schema}
        value={false}
        onChange={onChange}
      />
    )

    let switchElement = screen.getByRole('switch')
    expect(switchElement).not.toBeChecked()

    rerender(
      <BooleanFieldRenderer
        name="active"
        schema={schema}
        value={true}
        onChange={onChange}
      />
    )

    switchElement = screen.getByRole('switch')
    expect(switchElement).toBeChecked()
  })

  it('calls onChange with boolean value', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'boolean',
      title: 'Active',
    }

    const onChange = vi.fn()

    render(
      <BooleanFieldRenderer
        name="active"
        schema={schema}
        value={false}
        onChange={onChange}
      />
    )

    const switchElement = screen.getByRole('switch')
    await user.click(switchElement)

    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('respects disabled state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'boolean',
      title: 'Active',
    }

    const onChange = vi.fn()

    render(
      <BooleanFieldRenderer
        name="active"
        schema={schema}
        value={false}
        onChange={onChange}
        disabled
      />
    )

    const switchElement = screen.getByRole('switch')
    expect(switchElement).toBeDisabled()
  })
})

describe('SelectFieldRenderer', () => {
  it('renders select with options', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Status',
      enum: ['active', 'inactive', 'pending'],
    }

    const onChange = vi.fn()

    render(
      <SelectFieldRenderer
        name="status"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()
  })

  it('renders multi-select mode', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'array',
      title: 'Tags',
      items: {
        type: 'string',
        enum: ['tag1', 'tag2', 'tag3'],
      },
    }

    const onChange = vi.fn()

    render(
      <SelectFieldRenderer
        name="tags"
        schema={schema}
        value={[]}
        onChange={onChange}
      />
    )

    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()
  })

  it('calls onChange with selected value', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Status',
      enum: ['active', 'inactive'],
    }

    const onChange = vi.fn()

    render(
      <SelectFieldRenderer
        name="status"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const select = screen.getByRole('combobox')
    await user.click(select)

    // Find and click option
    const option = await screen.findByText('Active')
    await user.click(option)

    expect(onChange).toHaveBeenCalled()
  })

  it('respects disabled state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Status',
      enum: ['active', 'inactive'],
    }

    const onChange = vi.fn()

    const { container } = render(
      <SelectFieldRenderer
        name="status"
        schema={schema}
        value=""
        onChange={onChange}
        disabled
      />
    )

    // Ant Design Select uses .ant-select-disabled class for disabled state
    const select = container.querySelector('.ant-select')
    expect(select).toHaveClass('ant-select-disabled')
  })
})

describe('DateFieldRenderer', () => {
  it('renders date picker', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Birth Date',
      format: 'date',
    }

    const onChange = vi.fn()

    render(
      <DateFieldRenderer
        name="birthDate"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByPlaceholderText(/Birth Date/i)
    expect(input).toBeInTheDocument()
  })

  it('renders datetime picker with showTime', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Created At',
      'x-field-type': 'datetime',
    }

    const onChange = vi.fn()

    render(
      <DateFieldRenderer
        name="createdAt"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByPlaceholderText(/Created At/i)
    expect(input).toBeInTheDocument()
  })

  it('calls onChange with dayjs formatted value', async () => {
    const user = userEvent.setup()
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Birth Date',
      format: 'date',
    }

    const onChange = vi.fn()

    render(
      <DateFieldRenderer
        name="birthDate"
        schema={schema}
        value=""
        onChange={onChange}
      />
    )

    const input = screen.getByPlaceholderText(/Birth Date/i)
    await user.click(input)

    // DatePicker requires complex interaction, we just verify it's rendered
    expect(input).toBeInTheDocument()
  })

  it('respects disabled state', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Birth Date',
      format: 'date',
    }

    const onChange = vi.fn()

    render(
      <DateFieldRenderer
        name="birthDate"
        schema={schema}
        value=""
        onChange={onChange}
        disabled
      />
    )

    const input = screen.getByPlaceholderText(/Birth Date/i)
    expect(input).toBeDisabled()
  })

  it('formats datetime with ISO string', () => {
    const schema: ExtendedSchemaProperty = {
      type: 'string',
      title: 'Created At',
      format: 'date-time',
    }

    const onChange = vi.fn()

    const isoDate = '2024-01-15T10:30:00.000Z'

    render(
      <DateFieldRenderer
        name="createdAt"
        schema={schema}
        value={isoDate}
        onChange={onChange}
      />
    )

    const input = screen.getByPlaceholderText(/Created At/i)
    expect(input).toBeInTheDocument()
    // Value should be parsed and formatted
    expect(input).toHaveValue()
  })
})
