import { useId, useState, type ChangeEvent, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  action?: ReactNode
  children?: ReactNode
  description?: ReactNode
  message?: ReactNode
  style?: CSSProperties
  type?: 'success' | 'info' | 'warning' | 'error'
  'data-testid'?: string
}

type ButtonProps = {
  'aria-label'?: string
  'aria-pressed'?: boolean
  block?: boolean
  children?: ReactNode
  className?: string
  danger?: boolean
  disabled?: boolean
  htmlType?: 'button' | 'submit' | 'reset'
  loading?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  style?: CSSProperties
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
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

type DescriptionsItemProps = {
  children?: ReactNode
  label?: ReactNode
}

type InputProps = {
  allowClear?: boolean
  'aria-label'?: string
  autoComplete?: string
  className?: string
  defaultValue?: string
  disabled?: boolean
  id?: string
  name?: string
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  style?: CSSProperties
  type?: string
  value?: string
  'data-testid'?: string
}

type TextAreaProps = {
  'aria-label'?: string
  autoSize?: unknown
  className?: string
  defaultValue?: string
  disabled?: boolean
  id?: string
  name?: string
  onChange?: (event: ChangeEvent<HTMLTextAreaElement>) => void
  placeholder?: string
  rows?: number
  style?: CSSProperties
  value?: string
  'data-testid'?: string
}

type SelectOption = {
  disabled?: boolean
  label?: ReactNode
  value: unknown
}

type SelectProps = {
  allowClear?: boolean
  className?: string
  defaultValue?: unknown
  disabled?: boolean
  loading?: boolean
  notFoundContent?: ReactNode
  onChange?: (value: unknown, option?: SelectOption) => void
  onOpenChange?: (open: boolean) => void
  options?: SelectOption[]
  placeholder?: ReactNode
  style?: CSSProperties
  value?: unknown
  'aria-label'?: string
  'data-testid'?: string
  [key: string]: unknown
}

type SpaceProps = {
  children?: ReactNode
  className?: string
  style?: CSSProperties
  'data-testid'?: string
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

type TableColumn = {
  dataIndex?: string | number | Array<string | number>
  key?: string
  render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
  title?: ReactNode
}

type TableProps = {
  columns?: TableColumn[]
  dataSource?: Array<Record<string, unknown>>
  locale?: { emptyText?: ReactNode }
  onRow?: (record: Record<string, unknown>, index?: number) => Record<string, unknown>
  rowClassName?: string | ((record: Record<string, unknown>, index: number) => string)
  rowKey?: string | ((record: Record<string, unknown>) => string)
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

function resolveDataIndex(
  record: Record<string, unknown>,
  dataIndex: TableColumn['dataIndex'],
) {
  if (Array.isArray(dataIndex)) {
    return dataIndex.reduce<unknown>((current, key) => {
      if (current && typeof current === 'object') {
        return (current as Record<string | number, unknown>)[key]
      }
      return undefined
    }, record)
  }
  if (typeof dataIndex === 'string' || typeof dataIndex === 'number') {
    return record[dataIndex]
  }
  return undefined
}

function resolveSelectedLabel(value: unknown, options: SelectOption[]) {
  const matchedOption = options.find((option) => Object.is(option.value, value))
  if (matchedOption) {
    return matchedOption.label ?? String(matchedOption.value ?? '')
  }
  if (value === undefined || value === null || value === '') {
    return null
  }
  return String(value)
}

function coerceTextValue(value: unknown) {
  if (value === undefined || value === null) {
    return undefined
  }
  return String(value)
}

export function createPoolReusableAuthoringAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAlert = ({
    action,
    children,
    description,
    message,
    style,
    type,
    'data-testid': dataTestId,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type} style={style} data-testid={dataTestId}>
      {message ? <div>{message}</div> : null}
      {description ? <div>{description}</div> : null}
      {children}
      {action}
    </section>
  )

  const MockButton = ({
    'aria-label': ariaLabel,
    'aria-pressed': ariaPressed,
    block,
    children,
    className,
    danger,
    disabled,
    htmlType,
    loading,
    onClick,
    style,
    type,
    'data-testid': dataTestId,
  }: ButtonProps) => (
    <button
      type={htmlType ?? 'button'}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      className={className}
      disabled={Boolean(disabled) || Boolean(loading)}
      data-button-type={type}
      data-button-danger={danger ? 'true' : undefined}
      data-button-block={block ? 'true' : undefined}
      style={style}
      onClick={onClick}
      data-testid={dataTestId}
    >
      {children}
    </button>
  )

  const MockCollapse = ({
    items = [],
    style,
    'data-testid': dataTestId,
  }: CollapseProps) => {
    const [openKey, setOpenKey] = useState<string | null>(null)

    return (
      <section style={style} data-testid={dataTestId}>
        {items.map((item) => {
          const isOpen = item.key === openKey
          return (
            <div key={item.key}>
              <button
                type="button"
                onClick={() => setOpenKey(isOpen ? null : item.key)}
              >
                {item.label}
              </button>
              {isOpen ? <div>{item.children}</div> : null}
            </div>
          )
        })}
      </section>
    )
  }

  const MockDescriptionsItem = ({
    children,
    label,
  }: DescriptionsItemProps) => (
    <div>
      {label ? <dt>{label}</dt> : null}
      <dd>{children}</dd>
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
    }) => <dl style={style} data-testid={dataTestId}>{children}</dl>,
    { Item: MockDescriptionsItem }
  )

  const MockInput = ({
    'aria-label': ariaLabel,
    autoComplete,
    className,
    defaultValue,
    disabled,
    id,
    name,
    onChange,
    placeholder,
    style,
    type,
    value,
    'data-testid': dataTestId,
  }: InputProps) => {
    const resolvedValue = value === undefined
      ? coerceTextValue(defaultValue) ?? ''
      : coerceTextValue(value) ?? ''

    return (
      <input
        id={id}
        aria-label={ariaLabel}
        autoComplete={autoComplete}
        className={className}
        disabled={disabled}
        name={name}
        onChange={onChange}
        placeholder={placeholder}
        style={style}
        type={type ?? 'text'}
        value={resolvedValue}
        data-testid={dataTestId}
      />
    )
  }

  const MockTextArea = ({
    'aria-label': ariaLabel,
    className,
    defaultValue,
    disabled,
    id,
    name,
    onChange,
    placeholder,
    rows,
    style,
    value,
    'data-testid': dataTestId,
  }: TextAreaProps) => {
    const resolvedValue = value === undefined
      ? coerceTextValue(defaultValue) ?? ''
      : coerceTextValue(value) ?? ''

    return (
      <textarea
        id={id}
        aria-label={ariaLabel}
        className={className}
        disabled={disabled}
        name={name}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        style={style}
        value={resolvedValue}
        data-testid={dataTestId}
      />
    )
  }

  const MockInputRoot = Object.assign(MockInput, {
    Search: MockInput,
    TextArea: MockTextArea,
  })

  const MockSelect = ({
    allowClear,
    className,
    defaultValue,
    disabled,
    loading,
    notFoundContent,
    onChange,
    onOpenChange,
    options = [],
    placeholder,
    style,
    value,
    'aria-label': ariaLabel,
    'data-testid': dataTestId,
  }: SelectProps) => {
    const [isOpen, setIsOpen] = useState(false)
    const [internalValue, setInternalValue] = useState(defaultValue)
    const listboxId = useId()
    const selectedValue = value === undefined ? internalValue : value
    const selectedLabel = resolveSelectedLabel(selectedValue, options)

    const handleOpenChange = (nextOpen: boolean) => {
      setIsOpen(nextOpen)
      onOpenChange?.(nextOpen)
    }

    const handleSelect = (option: SelectOption) => {
      if (value === undefined) {
        setInternalValue(option.value)
      }
      onChange?.(option.value, option)
      handleOpenChange(false)
    }

    const handleClear = (event: MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation()
      if (value === undefined) {
        setInternalValue(undefined)
      }
      onChange?.(undefined, undefined)
    }

    return (
      <div
        className={['ant-select', className].filter(Boolean).join(' ')}
        style={style}
        data-testid={dataTestId}
      >
        <div
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-label={ariaLabel}
          aria-expanded={isOpen}
          aria-controls={isOpen ? listboxId : undefined}
          aria-disabled={disabled ? 'true' : undefined}
          className="ant-select-selector"
          onMouseDown={() => {
            if (!disabled && !loading) {
              handleOpenChange(!isOpen)
            }
          }}
        >
          {selectedLabel ?? placeholder ?? null}
        </div>
        {allowClear && selectedValue !== undefined && selectedValue !== null && selectedValue !== '' ? (
          <button type="button" onClick={handleClear}>
            Clear
          </button>
        ) : null}
        {isOpen ? (
          options.length > 0 ? (
            <div role="listbox" id={listboxId}>
              {options.map((option, optionIndex) => (
                <button
                  key={`${String(option.value)}:${optionIndex}`}
                  type="button"
                  role="option"
                  disabled={option.disabled}
                  className="ant-select-item-option"
                  onClick={() => handleSelect(option)}
                >
                  {option.label ?? String(option.value ?? '')}
                </button>
              ))}
            </div>
          ) : (
            <div role="listbox" id={listboxId}>
              {notFoundContent ?? 'No options'}
            </div>
          )
        ) : null}
      </div>
    )
  }

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

  const MockSwitch = ({
    checked,
    className,
    defaultChecked,
    disabled,
    onChange,
    style,
    'data-testid': dataTestId,
  }: SwitchProps) => {
    const [internalChecked, setInternalChecked] = useState(Boolean(defaultChecked))
    const resolvedChecked = checked ?? internalChecked

    return (
      <button
        type="button"
        role="switch"
        aria-checked={resolvedChecked}
        className={className}
        disabled={disabled}
        style={style}
        onClick={(event) => {
          const nextChecked = !resolvedChecked
          if (checked === undefined) {
            setInternalChecked(nextChecked)
          }
          onChange?.(nextChecked, event)
        }}
        data-testid={dataTestId}
      >
        {resolvedChecked ? 'On' : 'Off'}
      </button>
    )
  }

  const MockTable = ({
    columns = [],
    dataSource = [],
    locale,
    onRow,
    rowClassName,
    rowKey,
    style,
    'data-testid': dataTestId,
  }: TableProps) => (
    <table style={style} data-testid={dataTestId}>
      <thead>
        <tr>
          {columns.map((column, columnIndex) => (
            <th key={column.key ?? `header-${columnIndex}`}>
              {column.title}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {dataSource.length > 0 ? dataSource.map((record, rowIndex) => {
          const resolvedKey = typeof rowKey === 'function'
            ? rowKey(record)
            : typeof rowKey === 'string'
              ? coerceTextValue(record[rowKey]) ?? `row-${rowIndex}`
              : coerceTextValue(record.id) ?? `row-${rowIndex}`
          const rowProps = onRow?.(record, rowIndex) ?? {}
          const resolvedClassName = typeof rowClassName === 'function'
            ? rowClassName(record, rowIndex)
            : rowClassName
          return (
            <tr
              key={resolvedKey}
              className={resolvedClassName}
              onClick={rowProps.onClick as ((event: MouseEvent<HTMLTableRowElement>) => void) | undefined}
            >
              {columns.map((column, columnIndex) => {
                const value = resolveDataIndex(record, column.dataIndex)
                const content = column.render
                  ? column.render(value, record, rowIndex)
                  : coerceTextValue(value) ?? ''
                return <td key={column.key ?? `${resolvedKey}-${columnIndex}`}>{content}</td>
              })}
            </tr>
          )
        }) : (
          <tr>
            <td colSpan={Math.max(columns.length, 1)}>
              {locale?.emptyText ?? null}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )

  const MockText = ({
    children,
    code,
    strong,
    style,
    type,
    'data-testid': dataTestId,
  }: TextProps) => {
    let content = children

    if (code) {
      content = <code>{content}</code>
    }
    if (strong) {
      content = <strong>{content}</strong>
    }

    return (
      <span style={style} data-text-type={type} data-testid={dataTestId}>
        {content}
      </span>
    )
  }

  const MockTitle = ({
    children,
    level = 1,
    style,
    'data-testid': dataTestId,
  }: TitleProps) => {
    const Tag = `h${level}` as const
    return <Tag style={style} data-testid={dataTestId}>{children}</Tag>
  }

  const MockParagraph = ({
    children,
    style,
    'data-testid': dataTestId,
  }: ParagraphProps) => <p style={style} data-testid={dataTestId}>{children}</p>

  const MockTypography = {
    ...actual.Typography,
    Text: MockText,
    Title: MockTitle,
    Paragraph: MockParagraph,
  }

  return {
    ...actual,
    Alert: MockAlert,
    Button: MockButton,
    Collapse: MockCollapse,
    Descriptions: MockDescriptions,
    Input: MockInputRoot,
    Select: MockSelect,
    Space: MockSpace,
    Switch: MockSwitch,
    Table: MockTable,
    Typography: MockTypography,
  }
}
