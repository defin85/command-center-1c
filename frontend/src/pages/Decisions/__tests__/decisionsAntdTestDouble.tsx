import {
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ChangeEvent,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from 'react'

type AntdModule = typeof import('antd')

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
  style?: Record<string, unknown>
  value?: unknown
  'aria-label'?: string
  'data-testid'?: string
}

type AutoCompleteProps = {
  children?: ReactNode
  className?: string
  defaultValue?: string
  disabled?: boolean
  filterOption?: boolean | ((inputValue: string, option?: SelectOption) => boolean)
  onChange?: (value: string) => void
  options?: SelectOption[]
  style?: Record<string, unknown>
  value?: string
}

type AlertProps = {
  action?: ReactNode
  closable?: boolean
  description?: ReactNode
  message?: ReactNode
  onClose?: () => void
  type?: 'success' | 'info' | 'warning' | 'error'
}

type CardProps = {
  children?: ReactNode
  extra?: ReactNode
  title?: ReactNode
}

type ButtonProps = {
  'aria-label'?: string
  children?: ReactNode
  className?: string
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
  loading?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  role?: string
  style?: Record<string, unknown>
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
  [key: string]: unknown
}

type CollapseItem = {
  key: string
  label?: ReactNode
  children?: ReactNode
}

type CollapseProps = {
  items?: CollapseItem[]
}

type DescriptionsItem = {
  key?: string
  label?: ReactNode
  children?: ReactNode
}

type DescriptionsProps = {
  items?: DescriptionsItem[]
}

type SpaceProps = {
  children?: ReactNode
}

type InputProps = {
  'aria-controls'?: string
  'aria-expanded'?: boolean
  'aria-label'?: string
  className?: string
  defaultValue?: string
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  role?: string
  style?: Record<string, unknown>
  value?: string
  [key: string]: unknown
}

type TextAreaProps = {
  'aria-label'?: string
  className?: string
  defaultValue?: string
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLTextAreaElement>) => void
  placeholder?: string
  role?: string
  rows?: number
  style?: Record<string, unknown>
  value?: string
  [key: string]: unknown
}

type SpinProps = {
  className?: string
  size?: 'small' | 'default' | 'large'
  style?: Record<string, unknown>
}

type TextProps = {
  children?: ReactNode
  code?: boolean
  strong?: boolean
}

type TitleProps = {
  children?: ReactNode
  level?: 1 | 2 | 3 | 4 | 5
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

function renderOptionLabel(option: SelectOption) {
  return option.label ?? String(option.value ?? '')
}

function renderOptionSearchText(option: SelectOption) {
  const label = option.label
  const labelText = typeof label === 'string' || typeof label === 'number' ? String(label) : ''
  return `${String(option.value ?? '')} ${labelText}`.trim()
}

export function createDecisionsAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAlert = ({
    action,
    closable,
    description,
    message,
    onClose,
    type,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type}>
      <div>{message}</div>
      {description ? <div>{description}</div> : null}
      {action}
      {closable ? (
        <button type="button" onClick={onClose}>
          Close
        </button>
      ) : null}
    </section>
  )

  const MockCard = ({
    children,
    extra,
    title,
  }: CardProps) => (
    <section>
      {title || extra ? (
        <header>
          {title}
          {extra}
        </header>
      ) : null}
      {children}
    </section>
  )

  const MockButton = ({
    'aria-label': ariaLabel,
    children,
    className,
    danger,
    disabled,
    icon,
    loading,
    onClick,
    role,
    style,
    type,
    ...rest
  }: ButtonProps) => (
    <button
      type="button"
      aria-label={ariaLabel}
      className={className}
      disabled={Boolean(disabled) || Boolean(loading)}
      data-button-type={type}
      data-button-danger={danger ? 'true' : undefined}
      role={role}
      style={style}
      onClick={onClick}
      {...rest}
    >
      {icon}
      {children}
    </button>
  )

  const MockCollapse = ({ items = [] }: CollapseProps) => {
    const [openKeys, setOpenKeys] = useState<string[]>([])

    return (
      <div>
        {items.map((item) => {
          const key = String(item.key)
          const isOpen = openKeys.includes(key)
          return (
            <section key={key}>
              <button
                type="button"
                onClick={() => {
                  setOpenKeys((previous) => (
                    previous.includes(key)
                      ? previous.filter((value) => value !== key)
                      : [...previous, key]
                  ))
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

  const MockDescriptions = ({ items = [] }: DescriptionsProps) => (
    <dl>
      {items.map((item, index) => (
        <div key={String(item.key ?? index)}>
          <dt>{item.label}</dt>
          <dd>{item.children}</dd>
        </div>
      ))}
    </dl>
  )

  const MockDivider = () => <hr />

  const MockInput = ({
    'aria-controls': ariaControls,
    'aria-expanded': ariaExpanded,
    'aria-label': ariaLabel,
    className,
    defaultValue,
    disabled,
    onChange,
    placeholder,
    role,
    style,
    value,
    ...rest
  }: InputProps) => (
    <input
      aria-controls={ariaControls}
      aria-expanded={ariaExpanded}
      aria-label={ariaLabel}
      className={className}
      disabled={disabled}
      onChange={onChange}
      placeholder={placeholder}
      role={role}
      style={style}
      value={value ?? defaultValue ?? ''}
      {...rest}
    />
  )

  const MockTextArea = ({
    'aria-label': ariaLabel,
    className,
    defaultValue,
    disabled,
    onChange,
    placeholder,
    role,
    rows,
    style,
    value,
    ...rest
  }: TextAreaProps) => (
    <textarea
      aria-label={ariaLabel}
      className={className}
      disabled={disabled}
      onChange={onChange}
      placeholder={placeholder}
      role={role}
      rows={rows}
      style={style}
      value={value ?? defaultValue ?? ''}
      {...rest}
    />
  )

  const MockInputRoot = Object.assign(MockInput, {
    TextArea: MockTextArea,
  })

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
      'aria-label': ariaLabel,
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
          aria-label={ariaLabel}
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
                    <div className="ant-select-item-option-content">{renderOptionLabel(option)}</div>
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

  const MockAutoComplete = (props: AutoCompleteProps) => {
    const {
      children,
      className,
      defaultValue,
      disabled,
      filterOption = true,
      onChange,
      options = [],
      style,
      value,
    } = props
    const [open, setOpen] = useState(false)
    const [internalValue, setInternalValue] = useState(defaultValue ?? '')
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = String(isControlled ? (value ?? '') : internalValue)
    const listboxId = useId()

    const visibleOptions = options.filter((option) => {
      if (!currentValue.trim()) {
        return false
      }
      if (typeof filterOption === 'function') {
        return filterOption(currentValue, option)
      }
      if (filterOption === false) {
        return true
      }
      return renderOptionSearchText(option).toLowerCase().includes(currentValue.trim().toLowerCase())
    })

    const isOpen = open && visibleOptions.length > 0

    const handleInputChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const nextValue = event.target.value
      if (!isControlled) {
        setInternalValue(nextValue)
      }
      onChange?.(nextValue)
      setOpen(true)
    }

    const inputChild = isValidElement(children)
      ? cloneElement(children as ReactElement<Record<string, unknown>>, {
          value: currentValue,
          disabled,
          role: 'combobox',
          'aria-expanded': isOpen,
          'aria-controls': isOpen ? listboxId : undefined,
          onChange: handleInputChange,
        })
      : (
        <input
          value={currentValue}
          disabled={disabled}
          role="combobox"
          aria-expanded={isOpen}
          aria-controls={isOpen ? listboxId : undefined}
          onChange={handleInputChange}
        />
      )

    return (
      <div className={className} style={style}>
        {inputChild}
        {isOpen ? (
          <div role="listbox" id={listboxId}>
            {visibleOptions.map((option, index) => (
              <div
                key={String(option.value ?? index)}
                role="option"
                onClick={() => {
                  const nextValue = String(option.value ?? '')
                  if (!isControlled) {
                    setInternalValue(nextValue)
                  }
                  onChange?.(nextValue)
                  setOpen(false)
                }}
              >
                {renderOptionLabel(option)}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const MockSpace = ({ children }: SpaceProps) => <div>{children}</div>

  const MockSpin = ({ className, size, style }: SpinProps) => (
    <span role="status" aria-label="loading" className={className} data-spin-size={size} style={style}>
      Loading
    </span>
  )

  const MockText = ({ children, code, strong }: TextProps) => {
    let content = <span>{children}</span>
    if (code) {
      content = <code>{children}</code>
    }
    if (strong) {
      content = <strong>{content}</strong>
    }
    return content
  }

  const MockTitle = ({ children, level = 4 }: TitleProps) => {
    const tagName = `h${level}` as keyof JSX.IntrinsicElements
    const TitleTag = tagName
    return <TitleTag>{children}</TitleTag>
  }

  const MockTypographyRoot = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  const MockTypography = Object.assign(MockTypographyRoot, {
    Text: MockText,
    Title: MockTitle,
  })

  return {
    ...actual,
    Alert: MockAlert as unknown as AntdModule['Alert'],
    AutoComplete: MockAutoComplete as unknown as AntdModule['AutoComplete'],
    Button: MockButton as unknown as AntdModule['Button'],
    Card: MockCard as unknown as AntdModule['Card'],
    Collapse: MockCollapse as unknown as AntdModule['Collapse'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Divider: MockDivider as unknown as AntdModule['Divider'],
    Input: MockInputRoot as unknown as AntdModule['Input'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Spin: MockSpin as unknown as AntdModule['Spin'],
    Typography: MockTypography as unknown as AntdModule['Typography'],
  }
}
