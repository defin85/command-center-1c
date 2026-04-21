/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import {
  useState,
  type ChangeEvent,
  type MouseEvent,
  type ReactNode,
} from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  children?: ReactNode
  description?: ReactNode
  message?: ReactNode
  type?: 'success' | 'info' | 'warning' | 'error'
}

type AppProps = {
  children?: ReactNode
}

type ButtonProps = {
  'aria-label'?: string
  'aria-pressed'?: boolean
  'data-testid'?: string
  block?: boolean
  children?: ReactNode
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  style?: React.CSSProperties
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type SearchInputProps = {
  'aria-label'?: string
  allowClear?: boolean
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  style?: React.CSSProperties
  value?: string
}

type DescriptionsProps = {
  bordered?: boolean
  children?: ReactNode
  column?: number
  size?: 'default' | 'middle' | 'small'
}

type DescriptionsItemProps = {
  children?: ReactNode
  label?: ReactNode
}

type PaginationProps = {
  current?: number
  pageSize?: number
  total?: number
}

type PopconfirmProps = {
  children?: ReactNode
}

type SpaceProps = {
  children?: ReactNode
  size?: number | string | [number | string, number | string]
  style?: React.CSSProperties
  wrap?: boolean
}

type TagProps = {
  children?: ReactNode
  color?: string
}

type TextProps = {
  children?: ReactNode
  code?: boolean
  strong?: boolean
  type?: 'secondary' | 'success' | 'warning' | 'danger'
  ['data-testid']?: string
}

const noop = () => undefined

export function createWorkflowListAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: noop,
        info: noop,
        success: noop,
        warning: noop,
      },
      modal: {},
    }),
  })

  const MockAlert = ({
    children,
    description,
    message,
    type,
  }: AlertProps) => (
    <section role="alert" data-alert-type={type}>
      {message ? <div>{message}</div> : null}
      {description ? <div>{description}</div> : null}
      {children}
    </section>
  )

  const MockButton = ({
    'aria-label': ariaLabel,
    'aria-pressed': ariaPressed,
    'data-testid': dataTestId,
    block,
    children,
    danger,
    disabled,
    icon,
    onClick,
    style,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      data-testid={dataTestId}
      data-block={block ? 'true' : undefined}
      data-button-danger={danger ? 'true' : undefined}
      data-button-type={type}
      disabled={disabled}
      onClick={onClick}
      style={style}
    >
      {icon}
      {children}
    </button>
  )

  const MockSearch = ({
    'aria-label': ariaLabel,
    onChange,
    placeholder,
    style,
    value,
  }: SearchInputProps) => {
    const [internalValue, setInternalValue] = useState(value ?? '')

    return (
      <input
        aria-label={ariaLabel}
        onChange={(event) => {
          setInternalValue(event.target.value)
          onChange?.(event)
        }}
        placeholder={placeholder}
        style={style}
        value={value ?? internalValue}
      />
    )
  }

  const MockInputRoot = Object.assign(() => null, {
    Search: MockSearch,
  })

  const MockDescriptionsRoot = ({ children }: DescriptionsProps) => <dl>{children}</dl>

  const MockDescriptionsItem = ({
    children,
    label,
  }: DescriptionsItemProps) => (
    <div>
      {label ? <dt>{label}</dt> : null}
      <dd>{children}</dd>
    </div>
  )

  const MockDescriptions = Object.assign(MockDescriptionsRoot, {
    Item: MockDescriptionsItem,
  })

  const MockPagination = ({
    current,
    pageSize,
    total,
  }: PaginationProps) => (
    <div data-testid="workflow-list-pagination">{`page:${current ?? 1};size:${pageSize ?? 0};total:${total ?? 0}`}</div>
  )

  const MockPopconfirm = ({ children }: PopconfirmProps) => <>{children}</>

  const MockSpace = ({
    children,
    style,
  }: SpaceProps) => <div style={style}>{children}</div>

  const MockTag = ({
    children,
    color,
  }: TagProps) => <span data-tag-color={color}>{children}</span>

  const MockText = ({
    children,
    code,
    strong,
    type,
    ['data-testid']: dataTestId,
  }: TextProps) => {
    if (code) {
      return <code data-testid={dataTestId} data-text-type={type}>{children}</code>
    }
    if (strong) {
      return <strong data-testid={dataTestId} data-text-type={type}>{children}</strong>
    }
    return <span data-testid={dataTestId} data-text-type={type}>{children}</span>
  }

  const MockTypography = {
    ...actual.Typography,
    Text: MockText,
  }

  return {
    ...actual,
    Alert: MockAlert,
    App: MockApp,
    Button: MockButton,
    Descriptions: MockDescriptions,
    Input: MockInputRoot as unknown as AntdModule['Input'],
    Pagination: MockPagination as unknown as AntdModule['Pagination'],
    Popconfirm: MockPopconfirm as unknown as AntdModule['Popconfirm'],
    Space: MockSpace as unknown as AntdModule['Space'],
    Tag: MockTag as unknown as AntdModule['Tag'],
    Typography: MockTypography,
  }
}
