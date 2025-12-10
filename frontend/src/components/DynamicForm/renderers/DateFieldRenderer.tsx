/**
 * DateFieldRenderer Component
 *
 * Renders date and datetime fields using Ant Design DatePicker.
 * Note: Locale is managed by ConfigProvider at the application level.
 */

import { DatePicker } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { FieldRendererProps } from '../types'

/**
 * Renderer for date and datetime fields.
 * Supports: date, datetime
 */
export function DateFieldRenderer({
  name,
  schema,
  value,
  onChange,
  disabled,
}: FieldRendererProps) {
  const placeholder = schema['x-placeholder'] || schema.title
  const fieldType = schema['x-field-type']
  const format = schema.format

  // Determine if we need time picker
  const showTime = fieldType === 'datetime' || format === 'date-time'

  // Convert value to dayjs
  const dayjsValue = value ? dayjs(value as string) : null

  // Handle change
  const handleChange = (date: Dayjs | null) => {
    if (date) {
      // Format based on type
      if (showTime) {
        onChange(date.toISOString())
      } else {
        onChange(date.format('YYYY-MM-DD'))
      }
    } else {
      onChange(null)
    }
  }

  // Display format
  const displayFormat = showTime ? 'DD.MM.YYYY HH:mm' : 'DD.MM.YYYY'

  return (
    <DatePicker
      id={name}
      value={dayjsValue}
      placeholder={placeholder}
      disabled={disabled}
      showTime={showTime ? { format: 'HH:mm' } : false}
      format={displayFormat}
      style={{ width: '100%' }}
      onChange={handleChange}
    />
  )
}

export default DateFieldRenderer
