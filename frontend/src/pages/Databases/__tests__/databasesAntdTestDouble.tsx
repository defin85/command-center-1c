import { useRef, type ChangeEvent, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AppProps = {
  children?: ReactNode
}

type ButtonProps = {
  'aria-label'?: string
  'aria-pressed'?: boolean
  block?: boolean
  children?: ReactNode
  className?: string
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
  loading?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  style?: React.CSSProperties
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type CheckboxProps = {
  'aria-label'?: string
  checked?: boolean
  disabled?: boolean
  onChange?: (event: { target: { checked: boolean } }) => void
  onClick?: (event: MouseEvent<HTMLInputElement>) => void
  style?: React.CSSProperties
}

type DropdownProps = {
  children?: ReactNode
}

type FormApi = {
  resetFields: () => void
  setFieldsValue: (_values: Record<string, unknown>) => void
  validateFields: () => Promise<Record<string, unknown>>
}

type FormProps = {
  children?: ReactNode
}

type InputProps = {
  'aria-label'?: string
  className?: string
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  style?: React.CSSProperties
  value?: string
}

type PaginationProps = {
  children?: ReactNode
}

type SelectProps = {
  'aria-label'?: string
  allowClear?: boolean
  children?: ReactNode
  disabled?: boolean
  loading?: boolean
  onChange?: (value: string | undefined) => void
  placeholder?: ReactNode
  style?: React.CSSProperties
  value?: string
}

type SelectOptionProps = {
  children?: ReactNode
  value?: string
}

type SpaceProps = {
  children?: ReactNode
}

type TagProps = {
  children?: ReactNode
  color?: string
}

type TextProps = {
  children?: ReactNode
  className?: string
  strong?: boolean
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

const noop = () => undefined

const createMockForm = (): FormApi => ({
  resetFields: noop,
  setFieldsValue: noop,
  validateFields: async () => ({}),
})

export function createDatabasesAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: noop,
        success: noop,
        warning: noop,
      },
      modal: {},
    }),
  })

  const MockButton = ({
    'aria-label': ariaLabel,
    'aria-pressed': ariaPressed,
    block,
    children,
    className,
    danger,
    disabled,
    icon,
    loading,
    onClick,
    style,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      className={className}
      data-block={block ? 'true' : undefined}
      data-button-danger={danger ? 'true' : undefined}
      data-button-type={type}
      disabled={Boolean(disabled) || Boolean(loading)}
      onClick={onClick}
      style={style}
    >
      {icon}
      {children}
    </button>
  )

  const MockCheckbox = ({
    'aria-label': ariaLabel,
    checked,
    disabled,
    onChange,
    onClick,
    style,
  }: CheckboxProps) => (
    <input
      type="checkbox"
      aria-label={ariaLabel}
      checked={checked}
      disabled={disabled}
      onChange={(event) => onChange?.({ target: { checked: event.target.checked } })}
      onClick={onClick}
      style={style}
    />
  )

  const MockDropdown = ({ children }: DropdownProps) => <div>{children}</div>

  const MockFormRoot = ({ children }: FormProps) => <form>{children}</form>

  const MockForm = Object.assign(MockFormRoot, {
    useForm: () => {
      const formRef = useRef<FormApi>()
      if (!formRef.current) {
        formRef.current = createMockForm()
      }
      return [formRef.current] as const
    },
  })

  const MockInput = ({
    'aria-label': ariaLabel,
    className,
    disabled,
    onChange,
    placeholder,
    style,
    value,
  }: InputProps) => (
    <input
      aria-label={ariaLabel}
      className={className}
      disabled={disabled}
      onChange={onChange}
      placeholder={placeholder}
      style={style}
      value={value ?? ''}
    />
  )

  const MockSelectOption = ({
    children,
    value,
  }: SelectOptionProps) => <option value={value}>{children}</option>

  const MockSelect = ({
    'aria-label': ariaLabel,
    allowClear,
    children,
    disabled,
    loading,
    onChange,
    placeholder,
    style,
    value,
  }: SelectProps) => (
    <select
      aria-label={ariaLabel}
      disabled={Boolean(disabled) || Boolean(loading)}
      onChange={(event) => onChange?.(event.target.value || undefined)}
      style={style}
      value={value ?? ''}
    >
      {allowClear ? <option value="">{placeholder ?? ''}</option> : null}
      {children}
    </select>
  )

  const MockInputRoot = Object.assign(MockInput, {
    Search: MockInput,
  })

  const MockPagination = ({ children }: PaginationProps) => (
    <div data-testid="databases-pagination">
      {children}
    </div>
  )

  const MockSpace = ({ children }: SpaceProps) => <div>{children}</div>

  const MockTag = ({
    children,
    color,
  }: TagProps) => <span data-tag-color={color}>{children}</span>

  const MockText = ({
    children,
    className,
    strong,
    type,
  }: TextProps) => (
    <span className={className} data-text-type={type}>
      {strong ? <strong>{children}</strong> : children}
    </span>
  )

  const MockTypography = Object.assign(({ children }: { children?: ReactNode }) => <div>{children}</div>, {
    Text: MockText,
  })

  const MockSelectRoot = Object.assign(MockSelect, {
    Option: MockSelectOption,
  })

  return {
    ...actual,
    App: MockApp as unknown as AntdModule['App'],
    Button: MockButton as unknown as AntdModule['Button'],
    Checkbox: MockCheckbox as unknown as AntdModule['Checkbox'],
    Dropdown: MockDropdown as unknown as AntdModule['Dropdown'],
    Form: MockForm as unknown as AntdModule['Form'],
    Input: MockInputRoot as unknown as AntdModule['Input'],
    Pagination: MockPagination as unknown as AntdModule['Pagination'],
    Select: MockSelectRoot as unknown as AntdModule['Select'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Tag: MockTag as unknown as AntdModule['Tag'],
    Typography: MockTypography as unknown as AntdModule['Typography'],
  }
}
