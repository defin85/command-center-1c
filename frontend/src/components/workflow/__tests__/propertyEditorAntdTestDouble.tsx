import {
  useId,
  useState,
  type ChangeEvent,
  type MouseEvent,
  type ReactNode,
} from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  description?: ReactNode
  message?: ReactNode
  type?: 'success' | 'info' | 'warning' | 'error'
}

type AppProps = {
  children?: ReactNode
}

type ButtonProps = {
  children?: ReactNode
  className?: string
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type CardProps = {
  children?: ReactNode
  className?: string
  title?: ReactNode
}

type CollapseProps = {
  children?: ReactNode
}

type CollapsePanelProps = {
  children?: ReactNode
  header?: ReactNode
}

type DividerProps = {
  children?: ReactNode
}

type FormProps = {
  children?: ReactNode
}

type FormItemProps = {
  children?: ReactNode
  help?: ReactNode
  htmlFor?: string
  label?: ReactNode
  required?: boolean
}

type InputProps = {
  className?: string
  defaultValue?: string
  disabled?: boolean
  id?: string
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  role?: string
  value?: string
}

type TextAreaProps = {
  className?: string
  defaultValue?: string
  disabled?: boolean
  id?: string
  onChange?: (event: ChangeEvent<HTMLTextAreaElement>) => void
  placeholder?: string
  role?: string
  rows?: number
  value?: string
}

type InputNumberProps = {
  disabled?: boolean
  id?: string
  max?: number
  min?: number
  onChange?: (value: number | null) => void
  value?: number
}

type SelectOption = {
  disabled?: boolean
  label?: ReactNode
  value: unknown
}

type SelectProps = {
  allowClear?: boolean
  className?: string
  'data-testid'?: string
  defaultValue?: unknown
  disabled?: boolean
  loading?: boolean
  notFoundContent?: ReactNode
  onChange?: (value: unknown, option?: SelectOption) => void
  onOpenChange?: (open: boolean) => void
  options?: SelectOption[]
  placeholder?: ReactNode
  value?: unknown
}

type SpaceProps = {
  children?: ReactNode
}

type TextProps = {
  children?: ReactNode
  strong?: boolean
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

function resolveSelectedLabel(value: unknown, options: SelectOption[]) {
  const selected = options.find((option) => Object.is(option.value, value))
  if (selected) {
    return selected.label ?? String(selected.value ?? '')
  }
  if (value === undefined || value === null || value === '') {
    return null
  }
  return String(value)
}

export function createPropertyEditorAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: () => undefined,
        success: () => undefined,
        warning: () => undefined,
      },
      modal: {},
    }),
  })

  const MockAlert = ({
    description,
    message,
    type,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type}>
      {message ? <div>{message}</div> : null}
      {description ? <div>{description}</div> : null}
    </section>
  )

  const MockButton = ({
    children,
    className,
    danger,
    disabled,
    icon,
    onClick,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      className={className}
      data-button-danger={danger ? 'true' : undefined}
      data-button-type={type}
      disabled={disabled}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  )

  const MockCard = ({
    children,
    className,
    title,
  }: CardProps) => (
    <section className={className}>
      {title ? <header>{title}</header> : null}
      {children}
    </section>
  )

  const MockCollapseRoot = ({ children }: CollapseProps) => <div>{children}</div>

  const MockCollapsePanel = ({
    children,
    header,
  }: CollapsePanelProps) => (
    <section>
      {header ? <header>{header}</header> : null}
      <div>{children}</div>
    </section>
  )

  const MockCollapse = Object.assign(MockCollapseRoot, {
    Panel: MockCollapsePanel,
  })

  const MockDivider = ({ children }: DividerProps) => (
    <>
      <hr />
      {children}
    </>
  )

  const MockFormRoot = ({ children }: FormProps) => <form>{children}</form>

  const MockFormItem = ({
    children,
    help,
    htmlFor,
    label,
    required,
  }: FormItemProps) => (
    <div>
      {label ? (
        <label htmlFor={htmlFor}>
          {label}
          {required ? ' *' : null}
        </label>
      ) : null}
      {children}
      {help ? <div>{help}</div> : null}
    </div>
  )

  const MockForm = Object.assign(MockFormRoot, {
    Item: MockFormItem,
  })

  const MockInput = ({
    className,
    defaultValue,
    disabled,
    id,
    onChange,
    placeholder,
    role,
    value,
  }: InputProps) => (
    <input
      className={className}
      disabled={disabled}
      id={id}
      onChange={onChange}
      placeholder={placeholder}
      role={role}
      value={value ?? defaultValue ?? ''}
    />
  )

  const MockTextArea = ({
    className,
    defaultValue,
    disabled,
    id,
    onChange,
    placeholder,
    role,
    rows,
    value,
  }: TextAreaProps) => (
    <textarea
      className={className}
      disabled={disabled}
      id={id}
      onChange={onChange}
      placeholder={placeholder}
      role={role}
      rows={rows}
      value={value ?? defaultValue ?? ''}
    />
  )

  const MockInputRoot = Object.assign(MockInput, {
    TextArea: MockTextArea,
  })

  const MockInputNumber = ({
    disabled,
    id,
    max,
    min,
    onChange,
    value,
  }: InputNumberProps) => (
    <input
      type="number"
      disabled={disabled}
      id={id}
      max={max}
      min={min}
      value={value ?? ''}
      onChange={(event) => {
        const nextValue = event.target.value
        onChange?.(nextValue === '' ? null : Number(nextValue))
      }}
    />
  )

  const MockSelect = (props: SelectProps) => {
    const {
      allowClear,
      className,
      'data-testid': dataTestId,
      defaultValue,
      disabled,
      loading,
      notFoundContent,
      onChange,
      onOpenChange,
      options = [],
      placeholder,
      value,
    } = props
    const [open, setOpen] = useState(false)
    const [internalValue, setInternalValue] = useState(defaultValue)
    const isControlled = Object.prototype.hasOwnProperty.call(props, 'value')
    const currentValue = isControlled ? value : internalValue
    const selectedLabel = resolveSelectedLabel(currentValue, options)
    const hasSelection = currentValue !== undefined && currentValue !== null && currentValue !== ''
    const listboxId = useId()

    const handleSelect = (option: SelectOption) => {
      if (!isControlled) {
        setInternalValue(option.value)
      }
      onChange?.(option.value, option)
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

    return (
      <div className={className} data-testid={dataTestId}>
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
          <span>
            {selectedLabel ?? (loading ? 'Loading...' : placeholder) ?? null}
          </span>
          {allowClear && hasSelection ? (
            <button
              type="button"
              aria-label="Clear selection"
              onMouseDown={handleClear}
              onClick={handleClear}
            >
              ×
            </button>
          ) : null}
        </div>
        {open ? (
          <div role="listbox" id={listboxId}>
            {options.length > 0 ? (
              options.map((option, index) => (
                <div
                  key={String(option.value ?? index)}
                  role="option"
                  aria-selected={Object.is(option.value, currentValue)}
                  onClick={() => {
                    if (!option.disabled) {
                      handleSelect(option)
                    }
                  }}
                >
                  {option.label ?? String(option.value ?? '')}
                </div>
              ))
            ) : (
              <div>{notFoundContent ?? null}</div>
            )}
          </div>
        ) : null}
      </div>
    )
  }

  const MockSpace = ({ children }: SpaceProps) => <div>{children}</div>

  const MockText = ({
    children,
    strong,
    type,
  }: TextProps) => (
    <span data-text-type={type}>
      {strong ? <strong>{children}</strong> : children}
    </span>
  )

  const MockTypography = Object.assign(({ children }: { children?: ReactNode }) => <div>{children}</div>, {
    Text: MockText,
  })

  return {
    ...actual,
    Alert: MockAlert as unknown as AntdModule['Alert'],
    App: MockApp as unknown as AntdModule['App'],
    Button: MockButton as unknown as AntdModule['Button'],
    Card: MockCard as unknown as AntdModule['Card'],
    Collapse: MockCollapse as unknown as AntdModule['Collapse'],
    Divider: MockDivider as unknown as AntdModule['Divider'],
    Form: MockForm as unknown as AntdModule['Form'],
    Input: MockInputRoot as unknown as AntdModule['Input'],
    InputNumber: MockInputNumber as unknown as AntdModule['InputNumber'],
    Select: MockSelect as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Typography: MockTypography as unknown as AntdModule['Typography'],
  }
}
