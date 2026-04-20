import { useEffect, useId, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  action?: ReactNode
  children?: ReactNode
  description?: ReactNode
  message?: ReactNode
  title?: ReactNode
  style?: CSSProperties
  'data-testid'?: string
}

type CardProps = {
  children?: ReactNode
  className?: string
  extra?: ReactNode
  loading?: boolean
  style?: CSSProperties
  title?: ReactNode
  'data-testid'?: string
}

type DescriptionsItemProps = {
  children?: ReactNode
  label?: ReactNode
}

type EmptyProps = {
  children?: ReactNode
  description?: ReactNode
  style?: CSSProperties
  'data-testid'?: string
}

type ModalProps = {
  cancelText?: ReactNode
  children?: ReactNode
  className?: string
  confirmLoading?: boolean
  extra?: ReactNode
  footer?: ReactNode
  okText?: ReactNode
  onCancel?: () => void
  onOk?: () => void
  open?: boolean
  style?: CSSProperties
  title?: ReactNode
  'data-testid'?: string
}

type ProgressProps = {
  format?: (percent?: number) => ReactNode
  percent?: number
  showInfo?: boolean
  status?: string
  style?: CSSProperties
  success?: { percent?: number }
  type?: 'line' | 'circle' | 'dashboard'
  'data-testid'?: string
}

type SegmentedOption<T> =
  | T
  | {
      disabled?: boolean
      label?: ReactNode
      value: T
    }

type SegmentedProps<T = string> = {
  defaultValue?: T
  onChange?: (value: T) => void
  options?: Array<SegmentedOption<T>>
  style?: CSSProperties
  value?: T
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
  labelInValue?: boolean
  loading?: boolean
  mode?: 'multiple' | 'tags'
  notFoundContent?: ReactNode
  onChange?: (value: unknown, option?: SelectOption | SelectOption[]) => void
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
  className?: string
  style?: CSSProperties
  'data-testid'?: string
}

type StepItem = {
  description?: ReactNode
  key?: string
  status?: string
  subTitle?: ReactNode
  title?: ReactNode
}

type StepsProps = {
  current?: number
  items?: StepItem[]
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
  loading?: boolean
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

function normalizeMultipleValues(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value
  }
  if (value === undefined || value === null || value === '') {
    return []
  }
  return [value]
}

function normalizeSegmentedOption<T>(option: SegmentedOption<T>) {
  if (option && typeof option === 'object' && 'value' in option) {
    return {
      disabled: Boolean(option.disabled),
      label: option.label ?? String(option.value),
      value: option.value,
    }
  }
  return {
    disabled: false,
    label: String(option),
    value: option,
  }
}

export function createPoolMasterDataAntdTestDouble(actual: AntdModule): AntdModule {
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
    className,
    extra,
    loading,
    style,
    title,
    'data-testid': dataTestId,
  }: CardProps) => (
    <section
      className={['ant-card', className].filter(Boolean).join(' ')}
      style={style}
      data-testid={dataTestId}
    >
      {title || extra ? (
        <header>
          {title ? <h3>{title}</h3> : null}
          {extra}
        </header>
      ) : null}
      <div className="ant-card-body">
        {loading ? <div>Loading</div> : children}
      </div>
    </section>
  )

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
    locale,
    onRow,
    rowClassName,
    rowKey,
    style,
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

  const MockTag = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => <span style={style} data-testid={dataTestId}>{children}</span>

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

  const MockEmpty = ({
    children,
    description,
    style,
    'data-testid': dataTestId,
  }: EmptyProps) => (
    <div style={style} data-testid={dataTestId}>
      {description ?? children}
    </div>
  )

  const MockModal = ({
    cancelText,
    children,
    className,
    confirmLoading,
    extra,
    footer,
    okText,
    onCancel,
    onOk,
    open,
    style,
    title,
    'data-testid': dataTestId,
  }: ModalProps) => {
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

  const MockSelect = (props: SelectProps) => {
    const {
      allowClear,
      className,
      defaultValue,
      disabled,
      labelInValue,
      loading,
      mode,
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
    const isMultiple = mode === 'multiple' || mode === 'tags'
    const [open, setOpen] = useState(false)
    const [internalValue, setInternalValue] = useState<unknown>(
      defaultValue ?? (isMultiple ? [] : undefined)
    )
    const rootRef = useRef<HTMLDivElement | null>(null)
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = isControlled ? value : internalValue
    const rawSelectedValues = isMultiple ? normalizeMultipleValues(currentValue) : [currentValue]
    const selectedValues = rawSelectedValues
      .map((item) => resolveSelectedValue(item, labelInValue))
      .filter((item) => item !== undefined && item !== null && item !== '')
    const selectedLabels = rawSelectedValues
      .map((item) => resolveSelectedLabel(item, options, labelInValue))
      .filter((label) => label !== null && label !== undefined && label !== '')
    const listboxId = useId()

    const closeDropdown = () => {
      setOpen(false)
      onOpenChange?.(false)
    }

    useEffect(() => {
      if (!open) {
        return undefined
      }

      const handlePointerDown = (event: globalThis.MouseEvent) => {
        if (rootRef.current?.contains(event.target as Node)) {
          return
        }
        setOpen(false)
        onOpenChange?.(false)
      }

      document.addEventListener('mousedown', handlePointerDown)
      return () => {
        document.removeEventListener('mousedown', handlePointerDown)
      }
    }, [onOpenChange, open])

    const handleSelect = (option: SelectOption) => {
      if (isMultiple) {
        const hasAlreadySelected = selectedValues.some((selected) => Object.is(selected, option.value))
        const nextRawValues = hasAlreadySelected
          ? rawSelectedValues.filter((item) => !Object.is(resolveSelectedValue(item, labelInValue), option.value))
          : [
              ...rawSelectedValues,
              labelInValue
                ? { value: option.value, label: option.label }
                : option.value,
            ]
        const nextSelectedOptions = options.filter((candidate) => (
          nextRawValues.some((item) => Object.is(resolveSelectedValue(item, labelInValue), candidate.value))
        ))
        if (!isControlled) {
          setInternalValue(nextRawValues)
        }
        onChange?.(nextRawValues, nextSelectedOptions)
        closeDropdown()
        return
      }

      const nextValue = labelInValue
        ? { value: option.value, label: option.label }
        : option.value
      if (!isControlled) {
        setInternalValue(nextValue)
      }
      onChange?.(nextValue, option)
      closeDropdown()
    }

    const handleClear = (event: MouseEvent<HTMLButtonElement>) => {
      event.preventDefault()
      event.stopPropagation()
      const clearedValue = isMultiple ? [] : undefined
      if (!isControlled) {
        setInternalValue(clearedValue)
      }
      onChange?.(clearedValue, isMultiple ? [] : undefined)
      closeDropdown()
    }

    const hasSelection = isMultiple
      ? selectedValues.length > 0
      : selectedValues[0] !== undefined && selectedValues[0] !== null && selectedValues[0] !== ''
    const displayContent: ReactNode = isMultiple
      ? (
          selectedLabels.length > 0
            ? selectedLabels.map((label, index) => (
                <span key={`selection-${index}`}>
                  {index > 0 ? ', ' : null}
                  {label}
                </span>
              ))
            : (loading ? 'Loading...' : placeholder)
        )
      : (selectedLabels[0] ?? (loading ? 'Loading...' : placeholder))

    return (
      <div
        ref={rootRef}
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
                    aria-selected={selectedValues.some((selected) => Object.is(selected, option.value))}
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

  const MockText = ({
    children,
    code,
    strong,
    style,
    'data-testid': dataTestId,
  }: TextProps) => {
    let content: ReactNode = children
    if (code) {
      content = <code>{content}</code>
    }
    if (strong) {
      content = <strong>{content}</strong>
    }
    return <span style={style} data-testid={dataTestId}>{content}</span>
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

  const MockProgress = ({
    format,
    percent,
    showInfo = true,
    style,
    success,
    'data-testid': dataTestId,
  }: ProgressProps) => {
    const resolvedPercent = percent ?? success?.percent ?? 0
    const formatted = format ? format(percent) : `${resolvedPercent}%`
    return (
      <div
        role="progressbar"
        aria-valuenow={resolvedPercent}
        style={style}
        data-testid={dataTestId}
      >
        {showInfo ? formatted : null}
      </div>
    )
  }

  const MockSegmented = <T,>(props: SegmentedProps<T>) => {
    const {
      defaultValue,
      onChange,
      options = [],
      style,
      value,
      'data-testid': dataTestId,
    } = props
    const normalizedOptions = options.map(normalizeSegmentedOption)
    const [internalValue, setInternalValue] = useState<T | undefined>(
      defaultValue ?? normalizedOptions[0]?.value
    )
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = isControlled ? value : internalValue

    return (
      <div role="tablist" style={style} data-testid={dataTestId}>
        {normalizedOptions.map((option, index) => {
          const selected = Object.is(option.value, currentValue)
          return (
            <button
              key={index}
              type="button"
              role="tab"
              aria-selected={selected}
              disabled={option.disabled}
              onClick={() => {
                if (option.disabled) {
                  return
                }
                if (!isControlled) {
                  setInternalValue(option.value)
                }
                onChange?.(option.value)
              }}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    )
  }

  const MockSteps = ({
    current = 0,
    items = [],
    style,
    'data-testid': dataTestId,
  }: StepsProps) => (
    <ol style={style} data-testid={dataTestId}>
      {items.map((item, index) => (
        <li key={item.key ?? index} data-current={index === current ? 'true' : 'false'}>
          {item.title}
          {item.subTitle ? <div>{item.subTitle}</div> : null}
          {item.description ? <div>{item.description}</div> : null}
          {item.status ? <div>{item.status}</div> : null}
        </li>
      ))}
    </ol>
  )

  return {
    ...actual,
    Alert: MockAlert as unknown as AntdModule['Alert'],
    Card: MockCard as unknown as AntdModule['Card'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Empty: MockEmpty as unknown as AntdModule['Empty'],
    Modal: MockModal as unknown as AntdModule['Modal'],
    Progress: MockProgress as unknown as AntdModule['Progress'],
    Segmented: MockSegmented as unknown as AntdModule['Segmented'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Steps: MockSteps as unknown as AntdModule['Steps'],
    Table: MockTable as unknown as AntdModule['Table'],
    Tag: MockTag as unknown as AntdModule['Tag'],
    Typography: MockTypography as unknown as AntdModule['Typography'],
  }
}
