import type { ChangeEvent, MouseEvent, ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AppProps = {
  children?: ReactNode
}

type AlertProps = {
  children?: ReactNode
  message?: ReactNode
  type?: 'success' | 'info' | 'warning' | 'error'
}

type ButtonProps = {
  'aria-label'?: string
  'aria-pressed'?: boolean
  block?: boolean
  children?: ReactNode
  disabled?: boolean
  icon?: ReactNode
  loading?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type InputProps = {
  'aria-label'?: string
  allowClear?: boolean
  children?: ReactNode
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  value?: string
}

type PaginationProps = {
  children?: ReactNode
}

type SpaceProps = {
  children?: ReactNode
}

type TagProps = {
  children?: ReactNode
  closable?: boolean
  color?: string
  onClose?: () => void
}

type TextProps = {
  children?: ReactNode
  code?: boolean
  strong?: boolean
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

const noop = () => undefined

export function createOperationsAntdTestDouble(actual: AntdModule): AntdModule {
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

  const MockAlert = ({
    children,
    message,
    type,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type}>
      {message ? <div>{message}</div> : null}
      {children}
    </section>
  )

  const MockButton = ({
    'aria-label': ariaLabel,
    'aria-pressed': ariaPressed,
    block,
    children,
    disabled,
    icon,
    loading,
    onClick,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      data-button-block={block ? 'true' : undefined}
      data-button-type={type}
      disabled={Boolean(disabled) || Boolean(loading)}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  )

  const MockInput = ({
    'aria-label': ariaLabel,
    onChange,
    placeholder,
    value,
  }: InputProps) => (
    <input
      aria-label={ariaLabel}
      onChange={onChange}
      placeholder={placeholder}
      value={value ?? ''}
    />
  )

  const MockInputRoot = Object.assign(MockInput, {
    Search: MockInput,
  })

  const MockPagination = ({ children }: PaginationProps) => <div>{children}</div>

  const MockSpace = ({ children }: SpaceProps) => <div>{children}</div>

  const MockTag = ({
    children,
    closable,
    color,
    onClose,
  }: TagProps) => (
    <span data-tag-closable={closable ? 'true' : undefined} data-tag-color={color}>
      {children}
      {closable ? (
        <button type="button" onClick={onClose}>
          Close tag
        </button>
      ) : null}
    </span>
  )

  const MockText = ({
    children,
    code,
    strong,
    type,
  }: TextProps) => {
    let content = children
    if (code) {
      content = <code>{content}</code>
    }
    if (strong) {
      content = <strong>{content}</strong>
    }
    return <span data-text-type={type}>{content}</span>
  }

  const MockTypography = Object.assign(({ children }: { children?: ReactNode }) => <div>{children}</div>, {
    Text: MockText,
  })

  return {
    ...actual,
    Alert: MockAlert,
    App: MockApp,
    Button: MockButton,
    Input: MockInputRoot,
    Pagination: MockPagination,
    Space: MockSpace,
    Tag: MockTag,
    Typography: MockTypography,
  }
}
