import { Input, Select, Space } from 'antd'
import type { TableFilterConfig, TableFilters } from './types'

interface TableFiltersProps<TFilters extends TableFilters> {
  configs: TableFilterConfig[]
  values: TFilters
  onChange: (key: keyof TFilters, value: string | boolean | null) => void
}

export const TableFiltersPanel = <TFilters extends TableFilters>({
  configs,
  values,
  onChange,
}: TableFiltersProps<TFilters>) => {
  return (
    <Space wrap>
      {configs.map((config) => {
        if (config.type === 'text') {
          return (
            <Input
              key={config.key}
              allowClear
              placeholder={config.placeholder || config.label}
              value={(values[config.key] as string | null) ?? ''}
              onChange={(event) => onChange(config.key as keyof TFilters, event.target.value || null)}
              style={{ width: 220 }}
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
              key={config.key}
              allowClear
              placeholder={config.placeholder || config.label}
              value={
                typeof values[config.key] === 'boolean'
                  ? String(values[config.key])
                  : (values[config.key] as string | null) ?? undefined
              }
              onChange={(value) => {
                if (value === undefined) {
                  onChange(config.key as keyof TFilters, null)
                  return
                }
                onChange(config.key as keyof TFilters, value === 'true')
              }}
              style={{ width: 180 }}
              options={options}
            />
          )
        }

        return (
          <Select
            key={config.key}
            allowClear
            placeholder={config.placeholder || config.label}
            value={(values[config.key] as string | null) ?? undefined}
            onChange={(value) => onChange(config.key as keyof TFilters, (value ?? null) as string | null)}
            style={{ width: 180 }}
            options={config.options || []}
          />
        )
      })}
    </Space>
  )
}
