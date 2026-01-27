import { DatePicker, Input, InputNumber, Select, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { memo } from 'react'

import type { TableFilterConfig, TableFilters } from '../types'

const { Text } = Typography

export interface DefaultsTabProps {
  filters: TableFilterConfig[]
  values: TableFilters
  onChange: (key: string, value: TableFilters[string]) => void
  idPrefix: string
}

export const DefaultsTab = memo(({
  filters,
  values,
  onChange,
  idPrefix,
}: DefaultsTabProps) => (
  <Space direction="vertical" style={{ width: '100%' }}>
    {filters.map((filter) => {
      if (filter.type === 'select') {
        const value = values[filter.key]
        const selectValue = filter.multiple
          ? (Array.isArray(value) ? value : [])
          : (value as string | null) ?? undefined
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <Select
              id={`${idPrefix}-default-${filter.key}`}
              allowClear
              placeholder="Any"
              mode={filter.multiple ? 'multiple' : undefined}
              value={selectValue}
              onChange={(value) => {
                if (filter.multiple) {
                  const list = Array.isArray(value) ? value : []
                  onChange(filter.key, list.length > 0 ? list : null)
                  return
                }
                onChange(filter.key, value ?? null)
              }}
              options={filter.options || []}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      if (filter.type === 'boolean') {
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <Select
              id={`${idPrefix}-default-${filter.key}`}
              allowClear
              placeholder="Any"
              value={
                typeof values[filter.key] === 'boolean'
                  ? String(values[filter.key])
                  : undefined
              }
              onChange={(value) => {
                if (value === undefined) {
                  onChange(filter.key, null)
                  return
                }
                onChange(filter.key, value === 'true')
              }}
              options={[
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
              ]}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      if (filter.type === 'number') {
        const numericValue = typeof values[filter.key] === 'number'
          ? (values[filter.key] as number)
          : typeof values[filter.key] === 'string'
              ? Number.parseFloat(values[filter.key] as string)
              : null
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <InputNumber
              id={`${idPrefix}-default-${filter.key}`}
              value={Number.isFinite(numericValue) ? numericValue : undefined}
              onChange={(value) => onChange(filter.key, value ?? null)}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      if (filter.type === 'date') {
        const dateValue = typeof values[filter.key] === 'string' && values[filter.key]
          ? dayjs(values[filter.key] as string)
          : null
        return (
          <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
            <Text>{filter.label}</Text>
            <DatePicker
              id={`${idPrefix}-default-${filter.key}`}
              allowClear
              showTime
              value={dateValue && dateValue.isValid() ? dateValue : null}
              onChange={(value) => onChange(filter.key, value ? value.toISOString() : null)}
              style={{ width: 180 }}
            />
          </Space>
        )
      }
      return (
        <Space key={filter.key} style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text>{filter.label}</Text>
          <Input
            id={`${idPrefix}-default-${filter.key}`}
            value={(values[filter.key] as string | null) ?? ''}
            onChange={(event) => onChange(filter.key, event.target.value || null)}
            style={{ width: 220 }}
          />
        </Space>
      )
    })}
  </Space>
))

