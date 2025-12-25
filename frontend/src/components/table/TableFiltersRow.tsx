import { Input, Select, Space } from 'antd'
import type { TableFilterConfig, TableFilters } from './types'

interface TableFiltersRowProps<TFilters extends TableFilters> {
  columns: Array<{ key: string; width?: number }>
  configs: TableFilterConfig[]
  values: TFilters
  visibility: Record<string, boolean>
  onChange: (key: keyof TFilters, value: string | boolean | null) => void
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
            return (
              <Select
                allowClear
                size="small"
                placeholder={config.placeholder || config.label}
                value={(value as string | null) ?? undefined}
                onChange={(next) => onChange(config.key as keyof TFilters, (next ?? null) as string | null)}
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
