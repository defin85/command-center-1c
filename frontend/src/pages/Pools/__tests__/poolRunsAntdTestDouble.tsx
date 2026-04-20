import { useId, useState, type ChangeEvent, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  action?: ReactNode
  children?: ReactNode
  description?: ReactNode
  loading?: boolean
  message?: ReactNode
  style?: CSSProperties
  title?: ReactNode
  'data-testid'?: string
}

type CardProps = {
  children?: ReactNode
  extra?: ReactNode
  loading?: boolean
  style?: CSSProperties
  title?: ReactNode
  'data-testid'?: string
}

type CollapseItem = {
  key: string
  label?: ReactNode
  children?: ReactNode
}

type CollapseProps = {
  items?: CollapseItem[]
}

type DescriptionsItemProps = {
  children?: ReactNode
  label?: ReactNode
}

type InputNumberProps = {
  defaultValue?: number | null
  disabled?: boolean
  id?: string
  min?: number
  onChange?: (value: number | null) => void
  placeholder?: string
  step?: number
  style?: CSSProperties
  value?: number | null
  'aria-label'?: string
  'data-testid'?: string
}

type SelectOption = {
  value: unknown
  label?: ReactNode
  disabled?: boolean
}

type SelectProps = {
  allowClear?: boolean
  className?: string
  defaultValue?: unknown
  disabled?: boolean
  labelInValue?: boolean
  loading?: boolean
  notFoundContent?: ReactNode
  onChange?: (value: unknown, option?: SelectOption) => void
  onOpenChange?: (open: boolean) => void
  options?: SelectOption[]
  placeholder?: ReactNode
  style?: CSSProperties
  value?: unknown
  'aria-disabled'?: boolean | 'false' | 'true'
  'aria-label'?: string
  'data-testid'?: string
  [key: string]: unknown
}

type SpaceProps = {
  children?: ReactNode
  style?: CSSProperties
  'data-testid'?: string
}

type TableColumn = {
  key?: string
  title?: ReactNode
  dataIndex?: unknown
  render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
}

type TableProps = {
  columns?: TableColumn[]
  dataSource?: Array<Record<string, unknown>>
  loading?: boolean
  onRow?: (record: Record<string, unknown>, index?: number) => Record<string, unknown>
  rowClassName?: string | ((record: Record<string, unknown>, index: number) => string)
  rowKey?: string | ((record: Record<string, unknown>) => string)
  style?: CSSProperties
  locale?: { emptyText?: ReactNode }
  'data-testid'?: string
}

function resolveDataIndex(
  record: Record<string, unknown>,
  dataIndex: TableColumn['dataIndex'],
) {
  if (Array.isArray(dataIndex)) {
    return dataIndex.reduce<unknown>((current, key) => (
      current && typeof current === 'object' ? (current as Record<string, unknown>)[String(key)] : undefined
    ), record)
  }
  if (typeof dataIndex === 'string') {
    return record[dataIndex]
  }
  return undefined
}

function isLabelValue(value: unknown): value is { value: unknown; label?: ReactNode } {
  return Boolean(value) && typeof value === 'object' && 'value' in (value as Record<string, unknown>)
}

function resolveSelectedValue(value: unknown, labelInValue?: boolean) {
  if (labelInValue && isLabelValue(value)) {
    return value.value
  }
  return value
}

function resolveSelectedLabel(
  value: unknown,
  options: SelectOption[],
  labelInValue?: boolean,
) {
  if (labelInValue && isLabelValue(value) && value.label !== undefined && value.label !== null && value.label !== '') {
    return value.label
  }

  const selectedValue = resolveSelectedValue(value, labelInValue)
  const matchedOption = options.find((option) => Object.is(option.value, selectedValue))
  if (matchedOption) {
    return matchedOption.label ?? String(matchedOption.value ?? '')
  }
  if (selectedValue === undefined || selectedValue === null || selectedValue === '') {
    return null
  }
  return String(selectedValue)
}

export function createPoolRunsAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAlert = ({
    action,
    children,
    description,
    message,
    style,
    title,
    'data-testid': dataTestId,
  }: AlertProps) => (
    <section role="alert" style={style} data-testid={dataTestId}>
      {title ?? message ? <div>{title ?? message}</div> : null}
      {description ? <div>{description}</div> : null}
      {children}
      {action}
    </section>
  )

  const MockCard = ({
    children,
    extra,
    loading,
    style,
    title,
    'data-testid': dataTestId,
  }: CardProps) => (
    <section style={style} data-testid={dataTestId}>
      {title || extra ? (
        <header>
          {title ? <h3>{title}</h3> : null}
          {extra}
        </header>
      ) : null}
      {loading ? <div>Loading</div> : children}
    </section>
  )

  const MockTag = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => <span style={style} data-testid={dataTestId}>{children}</span>

  const MockDescriptionsItem = ({
    children,
    label,
  }: DescriptionsItemProps) => (
    <div>
      {label ? <span>{label}</span> : null}
      {children}
    </div>
  )

  const MockDescriptions = Object.assign(
    ({
      children,
      style,
      'data-testid': dataTestId,
    }: {
      children?: ReactNode
      style?: CSSProperties
      'data-testid'?: string
    }) => <section style={style} data-testid={dataTestId}>{children}</section>,
    { Item: MockDescriptionsItem }
  )

  const MockTable = ({
    columns = [],
    dataSource = [],
    loading,
    onRow,
    rowClassName,
    rowKey,
    style,
    locale,
    'data-testid': dataTestId,
  }: TableProps) => {
    if (loading) {
      return <div>Loading</div>
    }

    if (!dataSource.length) {
      return (
        <table style={style} data-testid={dataTestId}>
          <tbody>
            <tr>
              <td>{locale?.emptyText ?? null}</td>
            </tr>
          </tbody>
        </table>
      )
    }

    return (
      <table style={style} data-testid={dataTestId}>
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th key={String(column.key ?? column.dataIndex ?? index)}>{column.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataSource.map((record, index) => {
            const resolvedRowKey = typeof rowKey === 'function'
              ? rowKey(record)
              : typeof rowKey === 'string'
                ? String(record[rowKey] ?? index)
                : String(record.id ?? index)
            const rowProps = onRow?.(record, index) ?? {}
            const resolvedClassName = typeof rowClassName === 'function'
              ? rowClassName(record, index)
              : rowClassName

            return (
              <tr key={resolvedRowKey} className={resolvedClassName} {...rowProps}>
                {columns.map((column, columnIndex) => {
                  const value = resolveDataIndex(record, column.dataIndex)
                  const content = column.render
                    ? column.render(value, record, index)
                    : (
                      value == null
                        ? ''
                        : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
                          ? String(value)
                          : JSON.stringify(value)
                    )
                  return <td key={String(column.key ?? `${resolvedRowKey}-${columnIndex}`)}>{content}</td>
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    )
  }

  const MockCollapse = ({ items = [] }: CollapseProps) => {
    const [openKeys, setOpenKeys] = useState<Set<string>>(() => new Set())

    return (
      <div>
        {items.map((item) => {
          const isOpen = openKeys.has(item.key)
          return (
            <section key={item.key}>
              <button
                type="button"
                onClick={() => {
                  setOpenKeys((current) => {
                    const next = new Set(current)
                    if (next.has(item.key)) {
                      next.delete(item.key)
                    } else {
                      next.add(item.key)
                    }
                    return next
                  })
                }}
              >
                {item.label}
              </button>
              {isOpen ? <div>{item.children}</div> : null}
            </section>
          )
        })}
      </div>
    )
  }

  const MockRow = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  const MockCol = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  const MockSpace = ({ children, style, 'data-testid': dataTestId }: SpaceProps) => (
    <div style={style} data-testid={dataTestId}>{children}</div>
  )

  const MockInputNumber = (props: InputNumberProps) => {
    const {
      defaultValue,
      disabled,
      id,
      min,
      onChange,
      placeholder,
      step,
      style,
      value,
      'aria-label': ariaLabel,
      'data-testid': dataTestId,
    } = props
    const [internalValue, setInternalValue] = useState<number | null>(defaultValue ?? null)
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = isControlled ? (value ?? null) : internalValue

    const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
      const rawValue = event.target.value
      const nextValue = rawValue === '' ? null : Number(rawValue)
      if (!isControlled) {
        setInternalValue(nextValue)
      }
      onChange?.(nextValue)
    }

    return (
      <input
        id={id}
        type="number"
        role="spinbutton"
        min={min}
        step={step}
        value={currentValue ?? ''}
        disabled={disabled}
        placeholder={placeholder}
        style={style}
        aria-label={ariaLabel}
        data-testid={dataTestId}
        onChange={handleChange}
      />
    )
  }

  const MockSelect = (props: SelectProps) => {
    const {
      allowClear,
      className,
      defaultValue,
      disabled,
      labelInValue,
      loading,
      notFoundContent,
      onChange,
      onOpenChange,
      options = [],
      placeholder,
      style,
      value,
      'aria-disabled': ariaDisabled,
      'aria-label': ariaLabel,
      'data-testid': dataTestId,
      ...restProps
    } = props
    const [open, setOpen] = useState(false)
    const [internalValue, setInternalValue] = useState(defaultValue)
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = isControlled ? value : internalValue
    const selectedValue = resolveSelectedValue(currentValue, labelInValue)
    const selectedLabel = resolveSelectedLabel(currentValue, options, labelInValue)
    const listboxId = useId()

    const handleSelect = (option: SelectOption) => {
      const nextValue = labelInValue
        ? { value: option.value, label: option.label }
        : option.value
      if (!isControlled) {
        setInternalValue(nextValue)
      }
      onChange?.(nextValue, option)
      setOpen(false)
      onOpenChange?.(false)
    }

    const handleClear = (event: MouseEvent<HTMLButtonElement>) => {
      event.preventDefault()
      event.stopPropagation()
      if (!isControlled) {
        setInternalValue(undefined)
      }
      onChange?.(undefined, undefined)
      setOpen(false)
      onOpenChange?.(false)
    }

    const hasSelection = selectedValue !== undefined && selectedValue !== null && selectedValue !== ''
    const displayContent = selectedLabel ?? (loading ? 'Loading...' : placeholder)

    return (
      <div
        className={['ant-select', disabled ? 'ant-select-disabled' : null, className].filter(Boolean).join(' ')}
        style={style}
        aria-disabled={ariaDisabled ?? (disabled ? 'true' : undefined)}
        data-testid={dataTestId}
        {...restProps}
      >
        <div
          role="combobox"
          aria-label={ariaLabel}
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-controls={open ? listboxId : undefined}
          className="ant-select-selector"
          onMouseDown={(event) => {
            event.preventDefault()
            if (!disabled) {
              setOpen((current) => {
                const next = !current
                onOpenChange?.(next)
                return next
              })
            }
          }}
        >
          <span className={hasSelection ? 'ant-select-selection-item' : 'ant-select-selection-placeholder'}>
            {displayContent ?? null}
          </span>
          {allowClear && hasSelection ? (
            <button
              type="button"
              className="ant-select-clear"
              aria-label="Clear selection"
              onMouseDown={handleClear}
              onClick={handleClear}
            >
              ×
            </button>
          ) : null}
        </div>
        {open ? (
          <div className="ant-select-dropdown">
            <div role="listbox" id={listboxId}>
              {options.length > 0 ? (
                options.map((option, index) => (
                  <div
                    key={String(option.value ?? index)}
                    role="option"
                    aria-selected={Object.is(option.value, selectedValue)}
                    className={[
                      'ant-select-item-option',
                      option.disabled ? 'ant-select-item-option-disabled' : null,
                    ].filter(Boolean).join(' ')}
                    onClick={() => {
                      if (!option.disabled) {
                        handleSelect(option)
                      }
                    }}
                  >
                    <div className="ant-select-item-option-content">
                      {option.label ?? String(option.value ?? '')}
                    </div>
                  </div>
                ))
              ) : (
                <div className="ant-select-item-empty">{notFoundContent ?? null}</div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  return {
    ...actual,
    Alert: MockAlert as unknown as AntdModule['Alert'],
    Card: MockCard as unknown as AntdModule['Card'],
    Col: MockCol as unknown as AntdModule['Col'],
    Collapse: MockCollapse as unknown as AntdModule['Collapse'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    InputNumber: MockInputNumber as unknown as AntdModule['InputNumber'],
    Row: MockRow as unknown as AntdModule['Row'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Table: MockTable as unknown as AntdModule['Table'],
    Tag: MockTag as unknown as AntdModule['Tag'],
  }
}
