import { DatePicker, Input, InputNumber, Select, Space } from 'antd'
import dayjs from 'dayjs'
import type { TableFilterConfig, TableFilters, TableFilterValue } from './types'

interface TableFiltersRowProps<TFilters extends TableFilters> {
  columns: Array<{ key: string; width?: number }>
  configs: TableFilterConfig[]
  values: TFilters
  visibility: Record<string, boolean>
  onChange: (key: keyof TFilters, value: TableFilterValue) => void
}

export const TableFiltersRow = <TFilters extends TableFilters>({
  columns,
  configs,
  values,
  visibility,
  onChange,
}: TableFiltersRowProps<TFilters>) => {
  const configByKey = new Map(configs.map((config) => [config.key, config]))
  const widths = columns.map((col) => col.width ?? 160)
  const minWidth = widths.reduce((sum, value) => sum + value, 0)
  const gridTemplateColumns = widths.map((value) => `${value}px`).join(' ')

  return (
    <div style={{ overflowX: 'auto' }}>
      <div
        style={{
          display: 'grid',
          gap: 8,
          gridTemplateColumns,
          minWidth,
          padding: '8px 0',
          alignItems: 'center',
        }}
      >
        {columns.map((column) => {
          const config = configByKey.get(column.key)
          if (!config) {
            return <div key={column.key} />
          }
          const value = values[config.key]
          const isVisible = visibility[config.key] !== false

          if (!isVisible) {
            return <div key={column.key} />
          }

          const control = (() => {
            if (config.type === 'text') {
              return (
                <Input
                  allowClear
                  size="small"
                  placeholder={config.placeholder || config.label}
                  value={(value as string | null) ?? ''}
                  onChange={(event) => onChange(config.key as keyof TFilters, event.target.value || null)}
                />
              )
            }
            if (config.type === 'number') {
              const numericValue = typeof value === 'number'
                ? value
                : typeof value === 'string'
                  ? Number.parseFloat(value)
                  : null
              return (
                <InputNumber
                  size="small"
                  placeholder={config.placeholder || config.label}
                  value={Number.isFinite(numericValue) ? numericValue : undefined}
                  onChange={(next) => {
                    if (next === null || next === undefined) {
                      onChange(config.key as keyof TFilters, null)
                      return
                    }
                    onChange(config.key as keyof TFilters, next)
                  }}
                  style={{ width: '100%' }}
                />
              )
            }
            if (config.type === 'date') {
              const dateValue = typeof value === 'string' && value
                ? dayjs(value)
                : null
              return (
                <DatePicker
                  allowClear
                  showTime
                  size="small"
                  placeholder={config.placeholder || config.label}
                  value={dateValue && dateValue.isValid() ? dateValue : null}
                  onChange={(next) => {
                    if (!next) {
                      onChange(config.key as keyof TFilters, null)
                      return
                    }
                    onChange(config.key as keyof TFilters, next.toISOString())
                  }}
                  style={{ width: '100%' }}
                />
              )
            }
            if (config.type === 'boolean') {
              const options = [
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
              ]
              return (
                <Select
                  allowClear
                  size="small"
                  placeholder={config.placeholder || config.label}
                  value={
                    typeof value === 'boolean'
                      ? String(value)
                      : (value as string | null) ?? undefined
                  }
                  onChange={(next) => {
                    if (next === undefined) {
                      onChange(config.key as keyof TFilters, null)
                      return
                    }
                    onChange(config.key as keyof TFilters, next === 'true')
                  }}
                  options={options}
                />
              )
            }
            const selectMode = config.multiple ? 'multiple' : undefined
            const selectValue = config.multiple
              ? (Array.isArray(value) ? value : [])
              : (value as string | null) ?? undefined
            return (
              <Select
                allowClear
                size="small"
                mode={selectMode}
                placeholder={config.placeholder || config.label}
                value={selectValue}
                onChange={(next) => {
                  if (config.multiple) {
                    const list = Array.isArray(next) ? next : []
                    onChange(config.key as keyof TFilters, list.length > 0 ? list : null)
                    return
                  }
                  onChange(config.key as keyof TFilters, (next ?? null) as string | null)
                }}
                options={config.options || []}
              />
            )
          })()

          return (
            <div key={column.key}>
              <Space size={4} align="start">
                {control}
              </Space>
            </div>
          )
        })}
      </div>
    </div>
  )
}
