import { useId, useState, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type TableColumn = {
  key?: string
  title?: ReactNode
  dataIndex?: string | number | Array<string | number>
  render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
}

type TableProps = {
  columns?: TableColumn[]
  dataSource?: Array<Record<string, unknown>>
  rowKey?: string | ((record: Record<string, unknown>) => string)
  onRow?: (record: Record<string, unknown>, index?: number) => Record<string, unknown>
  rowClassName?: string | ((record: Record<string, unknown>, index: number) => string)
  locale?: { emptyText?: ReactNode }
  style?: CSSProperties
  'data-testid'?: string
}

type OverlayProps = {
  open?: boolean
  title?: ReactNode
  extra?: ReactNode
  footer?: ReactNode
  onOk?: () => void
  onCancel?: () => void
  okText?: ReactNode
  cancelText?: ReactNode
  confirmLoading?: boolean
  children?: ReactNode
  className?: string
  style?: CSSProperties
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
  'data-testid'?: string
  [key: string]: unknown
}

const resolveDataIndex = (
  record: Record<string, unknown>,
  dataIndex: TableColumn['dataIndex'],
) => {
  if (Array.isArray(dataIndex)) {
    return dataIndex.reduce<unknown>((value, key) => {
      if (value && typeof value === 'object') {
        return (value as Record<string | number, unknown>)[key]
      }
      return undefined
    }, record)
  }
  if (typeof dataIndex === 'string' || typeof dataIndex === 'number') {
    return record[dataIndex]
  }
  return undefined
}

const resolveAccessibleLabel = (title: ReactNode) => (
  typeof title === 'string' || typeof title === 'number' ? String(title) : undefined
)

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

export function createPoolCatalogAntdTestDouble(actual: AntdModule): AntdModule {
  const MockCard = ({
    title,
    extra,
    className,
    children,
    style,
    'data-testid': dataTestId,
  }: {
    title?: ReactNode
    extra?: ReactNode
    className?: string
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <section
      className={['ant-card', className].filter(Boolean).join(' ')}
      style={style}
      data-testid={dataTestId}
    >
      {title || extra ? (
        <header>
          {title}
          {extra}
        </header>
      ) : null}
      {children}
    </section>
  )

  const MockDescriptionsRoot = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <dl style={style} data-testid={dataTestId}>
      {children}
    </dl>
  )

  const MockDescriptionsItem = ({
    label,
    children,
  }: {
    label?: ReactNode
    children?: ReactNode
  }) => (
    <>
      {label ? <dt>{label}</dt> : null}
      <dd>{children}</dd>
    </>
  )

  const MockDescriptions = Object.assign(MockDescriptionsRoot, {
    Item: MockDescriptionsItem,
  })

  const MockTag = ({
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    className?: string
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <span className={className} style={style} data-testid={dataTestId}>
      {children}
    </span>
  )

  const MockDrawer = ({
    open,
    title,
    extra,
    footer,
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: OverlayProps) => {
    if (!open) {
      return null
    }

    return (
      <section
        role="dialog"
        aria-label={resolveAccessibleLabel(title)}
        className={className}
        style={style}
        data-testid={dataTestId}
      >
        {title || extra ? (
          <header>
            {title ? <h2>{title}</h2> : null}
            {extra}
          </header>
        ) : null}
        {children}
        {footer}
      </section>
    )
  }

  const MockModal = ({
    open,
    title,
    extra,
    footer,
    onOk,
    onCancel,
    okText,
    cancelText,
    confirmLoading,
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: OverlayProps) => {
    if (!open) {
      return null
    }

    const resolvedFooter = footer !== undefined ? footer : (
      <footer>
        {onCancel ? (
          <button type="button" onClick={onCancel}>
            {cancelText ?? 'Cancel'}
          </button>
        ) : null}
        {onOk ? (
          <button type="button" onClick={onOk} disabled={confirmLoading}>
            {okText ?? 'OK'}
          </button>
        ) : null}
      </footer>
    )

    return (
      <section
        role="dialog"
        aria-label={resolveAccessibleLabel(title)}
        className={className}
        style={style}
        data-testid={dataTestId}
      >
        {title || extra ? (
          <header>
            {title ? <h2>{title}</h2> : null}
            {extra}
          </header>
        ) : null}
        {children}
        {resolvedFooter}
      </section>
    )
  }

  const MockTable = ({
    columns = [],
    dataSource = [],
    rowKey,
    onRow,
    rowClassName,
    locale,
    style,
    'data-testid': dataTestId,
  }: TableProps) => {
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
          {dataSource.map((record, rowIndex) => {
            const resolvedKey = typeof rowKey === 'function'
              ? rowKey(record)
              : typeof rowKey === 'string'
                ? String(record[rowKey] ?? rowIndex)
                : String(rowIndex)
            const rowProps = onRow?.(record, rowIndex) ?? {}
            const resolvedClassName = typeof rowClassName === 'function'
              ? rowClassName(record, rowIndex)
              : rowClassName

            return (
              <tr key={resolvedKey} className={resolvedClassName} {...rowProps}>
                {columns.map((column, columnIndex) => {
                  const value = resolveDataIndex(record, column.dataIndex)
                  const content = column.render ? column.render(value, record, rowIndex) : value
                  return (
                    <td key={String(column.key ?? column.dataIndex ?? columnIndex)}>
                      {content as ReactNode}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
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
      'data-testid': dataTestId,
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
        data-testid={dataTestId}
      >
        <div
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-controls={open ? listboxId : undefined}
          className="ant-select-selector"
          onMouseDown={(event) => {
            event.preventDefault()
            if (!disabled) {
              setOpen((previous) => {
                const nextOpen = !previous
                onOpenChange?.(nextOpen)
                return nextOpen
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
                options.map((option, index) => {
                  const optionLabel = option.label ?? String(option.value ?? '')
                  return (
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
                      <div className="ant-select-item-option-content">{optionLabel}</div>
                    </div>
                  )
                })
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
    Card: MockCard as unknown as AntdModule['Card'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Drawer: MockDrawer as unknown as AntdModule['Drawer'],
    Modal: MockModal as unknown as AntdModule['Modal'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Table: MockTable as unknown as AntdModule['Table'],
    Tag: MockTag as unknown as AntdModule['Tag'],
  }
}
