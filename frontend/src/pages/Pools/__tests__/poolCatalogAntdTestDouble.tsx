import { useId, useState, type ChangeEvent, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

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

type AlertProps = {
  action?: ReactNode
  description?: ReactNode
  message?: ReactNode
  style?: CSSProperties
  type?: 'success' | 'info' | 'warning' | 'error'
  'data-testid'?: string
}

type CollapseItem = {
  key: string
  label?: ReactNode
  children?: ReactNode
}

type CollapseProps = {
  items?: CollapseItem[]
  style?: CSSProperties
  'data-testid'?: string
}

type InputNumberProps = {
  defaultValue?: number | null
  disabled?: boolean
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
  'data-testid'?: string
  [key: string]: unknown
}

type SwitchProps = {
  checked?: boolean
  className?: string
  defaultChecked?: boolean
  disabled?: boolean
  onChange?: (checked: boolean, event?: MouseEvent<HTMLButtonElement>) => void
  style?: CSSProperties
  'data-testid'?: string
}

type SpaceProps = {
  children?: ReactNode
  className?: string
  style?: CSSProperties
  'data-testid'?: string
}

type TabsItem = {
  children?: ReactNode
  disabled?: boolean
  key: string
  label?: ReactNode
}

type TabsProps = {
  activeKey?: string
  className?: string
  defaultActiveKey?: string
  items?: TabsItem[]
  onChange?: (key: string) => void
  style?: CSSProperties
  'data-testid'?: string
}

type TextProps = {
  children?: ReactNode
  code?: boolean
  strong?: boolean
  style?: CSSProperties
  type?: 'secondary' | 'success' | 'warning' | 'danger'
  'data-testid'?: string
}

type TitleProps = {
  children?: ReactNode
  level?: 1 | 2 | 3 | 4 | 5
  style?: CSSProperties
  'data-testid'?: string
}

type ParagraphProps = {
  children?: ReactNode
  style?: CSSProperties
  'data-testid'?: string
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
  const MockAlert = ({
    action,
    description,
    message,
    style,
    type,
    'data-testid': dataTestId,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type} style={style} data-testid={dataTestId}>
      {message ? <div>{message}</div> : null}
      {description ? <div>{description}</div> : null}
      {action}
    </section>
  )

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

  const MockCollapse = ({
    items = [],
    style,
    'data-testid': dataTestId,
  }: CollapseProps) => {
    const [openKeys, setOpenKeys] = useState<Set<string>>(() => new Set())

    return (
      <div style={style} data-testid={dataTestId}>
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

  const MockRow = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => <div style={style} data-testid={dataTestId}>{children}</div>

  const MockCol = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => <div style={style} data-testid={dataTestId}>{children}</div>

  const MockSpace = ({
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: SpaceProps) => (
    <div className={className} style={style} data-testid={dataTestId}>
      {children}
    </div>
  )

  const MockSwitch = (props: SwitchProps) => {
    const {
      checked,
      className,
      defaultChecked = false,
      disabled,
      onChange,
      style,
      'data-testid': dataTestId,
    } = props
    const [internalChecked, setInternalChecked] = useState(defaultChecked)
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'checked')
    const currentChecked = isControlled ? Boolean(checked) : internalChecked

    return (
      <button
        type="button"
        role="switch"
        className={className}
        aria-checked={currentChecked}
        disabled={disabled}
        style={style}
        data-testid={dataTestId}
        onClick={(event) => {
          const nextChecked = !currentChecked
          if (!isControlled) {
            setInternalChecked(nextChecked)
          }
          onChange?.(nextChecked, event)
        }}
      />
    )
  }

  const MockInputNumber = (props: InputNumberProps) => {
    const {
      defaultValue,
      disabled,
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

  const MockTabs = (props: TabsProps) => {
    const {
      activeKey,
      className,
      defaultActiveKey,
      items = [],
      onChange,
      style,
      'data-testid': dataTestId,
    } = props
    const [internalActiveKey, setInternalActiveKey] = useState<string | undefined>(
      defaultActiveKey ?? items[0]?.key
    )
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'activeKey')
    const currentActiveKey = (isControlled ? activeKey : internalActiveKey) ?? items[0]?.key
    const activeItem = items.find((item) => item.key === currentActiveKey) ?? items[0] ?? null
    const tabsId = useId()

    return (
      <div className={className} style={style} data-testid={dataTestId}>
        <div role="tablist">
          {items.map((item) => {
            const selected = item.key === activeItem?.key
            const tabId = `${tabsId}-tab-${item.key}`
            const panelId = `${tabsId}-panel-${item.key}`
            return (
              <button
                key={item.key}
                id={tabId}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={panelId}
                disabled={item.disabled}
                onClick={() => {
                  if (item.disabled) {
                    return
                  }
                  if (!isControlled) {
                    setInternalActiveKey(item.key)
                  }
                  onChange?.(item.key)
                }}
              >
                {item.label}
              </button>
            )
          })}
        </div>
        {activeItem ? (
          <div
            id={`${tabsId}-panel-${activeItem.key}`}
            role="tabpanel"
            aria-labelledby={`${tabsId}-tab-${activeItem.key}`}
          >
            {activeItem.children}
          </div>
        ) : null}
      </div>
    )
  }

  const MockText = ({
    children,
    code,
    strong,
    style,
    type,
    'data-testid': dataTestId,
  }: TextProps) => {
    if (code) {
      return <code style={style} data-text-type={type} data-testid={dataTestId}>{children}</code>
    }
    if (strong) {
      return <strong style={style} data-text-type={type} data-testid={dataTestId}>{children}</strong>
    }
    return <span style={style} data-text-type={type} data-testid={dataTestId}>{children}</span>
  }

  const MockTitle = ({
    children,
    level = 4,
    style,
    'data-testid': dataTestId,
  }: TitleProps) => {
    const titleByLevel = {
      1: <h1 style={style} data-testid={dataTestId}>{children}</h1>,
      2: <h2 style={style} data-testid={dataTestId}>{children}</h2>,
      3: <h3 style={style} data-testid={dataTestId}>{children}</h3>,
      4: <h4 style={style} data-testid={dataTestId}>{children}</h4>,
      5: <h5 style={style} data-testid={dataTestId}>{children}</h5>,
    } as const
    return titleByLevel[level]
  }

  const MockParagraph = ({
    children,
    style,
    'data-testid': dataTestId,
  }: ParagraphProps) => <p style={style} data-testid={dataTestId}>{children}</p>

  const MockTypography = Object.assign(
    ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    {
      Paragraph: MockParagraph,
      Text: MockText,
      Title: MockTitle,
    }
  )

  return {
    ...actual,
    Alert: MockAlert as unknown as AntdModule['Alert'],
    Card: MockCard as unknown as AntdModule['Card'],
    Col: MockCol as unknown as AntdModule['Col'],
    Collapse: MockCollapse as unknown as AntdModule['Collapse'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Drawer: MockDrawer as unknown as AntdModule['Drawer'],
    InputNumber: MockInputNumber as unknown as AntdModule['InputNumber'],
    Modal: MockModal as unknown as AntdModule['Modal'],
    Row: MockRow as unknown as AntdModule['Row'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Switch: MockSwitch as unknown as AntdModule['Switch'],
    Table: MockTable as unknown as AntdModule['Table'],
    Tag: MockTag as unknown as AntdModule['Tag'],
    Tabs: MockTabs as unknown as AntdModule['Tabs'],
    Typography: MockTypography as unknown as AntdModule['Typography'],
  }
}
