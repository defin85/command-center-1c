/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import { useId, useState, type ChangeEvent, type CSSProperties, type MouseEvent, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AppProps = {
  children?: ReactNode
}

type AlertProps = {
  description?: ReactNode
  message?: ReactNode
  type?: 'success' | 'info' | 'warning' | 'error'
}

type ButtonProps = {
  children?: ReactNode
  danger?: boolean
  disabled?: boolean
  icon?: ReactNode
  loading?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type CheckboxProps = {
  checked?: boolean
  children?: ReactNode
  disabled?: boolean
  onChange?: (event: { target: { checked: boolean } }) => void
}

type CollapseItem = {
  key: string
  label?: ReactNode
  children?: ReactNode
}

type CollapseProps = {
  items?: CollapseItem[]
  style?: CSSProperties
}

type DividerProps = {
  style?: CSSProperties
}

type FormProps = {
  children?: ReactNode
}

type FormItemProps = {
  children?: ReactNode
  help?: ReactNode
  label?: ReactNode
  required?: boolean
  style?: CSSProperties
}

type InputProps = {
  'aria-label'?: string
  defaultValue?: string
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  value?: string
}

type TextAreaProps = {
  'aria-label'?: string
  defaultValue?: string
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLTextAreaElement>) => void
  rows?: number
  value?: string
}

type InputNumberProps = {
  disabled?: boolean
  max?: number
  min?: number
  onChange?: (value: number | null) => void
  value?: number
}

type ModalProps = {
  cancelText?: ReactNode
  children?: ReactNode
  okButtonProps?: { danger?: boolean }
  okText?: ReactNode
  onCancel?: () => void
  onOk?: () => void
  open?: boolean
  title?: ReactNode
}

type RadioGroupProps = {
  children?: ReactNode
  disabled?: boolean
  onChange?: (event: { target: { value: string } }) => void
  value?: string
}

type RadioButtonProps = {
  children?: ReactNode
  value?: string
}

type SelectOption = {
  disabled?: boolean
  label?: ReactNode
  value: unknown
}

type SelectProps = {
  allowClear?: boolean
  disabled?: boolean
  loading?: boolean
  notFoundContent?: ReactNode
  onChange?: (value: unknown) => void
  options?: SelectOption[]
  placeholder?: ReactNode
  value?: unknown
}

type SpaceProps = {
  children?: ReactNode
  style?: CSSProperties
}

type SpinProps = {
  size?: 'small' | 'default' | 'large'
  tip?: ReactNode
}

type TabsItem = {
  children?: ReactNode
  key: string
  label?: ReactNode
}

type TabsProps = {
  activeKey?: string
  defaultActiveKey?: string
  items?: TabsItem[]
  onChange?: (key: string) => void
}

type SwitchProps = {
  checked?: boolean
  disabled?: boolean
  onChange?: (checked: boolean) => void
}

type TextProps = {
  children?: ReactNode
  code?: boolean
  strong?: boolean
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

type TitleProps = {
  children?: ReactNode
  level?: 1 | 2 | 3 | 4 | 5
}

type ParagraphProps = {
  children?: ReactNode
}

const noop = () => undefined

export function createDriverCommandBuilderAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => ({
      message: {
        error: noop,
        info: noop,
        success: noop,
        warning: noop,
      },
      modal: {
        error: noop,
        info: noop,
        warning: noop,
      },
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
    danger,
    disabled,
    icon,
    loading,
    onClick,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      data-button-danger={danger ? 'true' : undefined}
      data-button-type={type}
      disabled={Boolean(disabled) || Boolean(loading)}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  )

  const MockCheckbox = ({
    checked,
    children,
    disabled,
    onChange,
  }: CheckboxProps) => (
    <label>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange?.({ target: { checked: event.target.checked } })}
      />
      {children}
    </label>
  )

  const MockCollapse = ({
    items = [],
    style,
  }: CollapseProps) => (
    <div style={style}>
      {items.map((item) => (
        <section key={item.key}>
          <header>{item.label}</header>
          <div>{item.children}</div>
        </section>
      ))}
    </div>
  )

  const MockDivider = ({ style }: DividerProps) => <hr style={style} />

  const MockFormRoot = ({ children }: FormProps) => <form>{children}</form>

  const MockFormItem = ({
    children,
    help,
    label,
    style,
  }: FormItemProps) => (
    <div className="ant-form-item" style={style}>
      {label ? <label>{label}</label> : null}
      {children}
      {help ? <div>{help}</div> : null}
    </div>
  )

  const MockForm = Object.assign(MockFormRoot, {
    Item: MockFormItem,
  })

  const MockInput = ({
    'aria-label': ariaLabel,
    defaultValue,
    disabled,
    onChange,
    placeholder,
    value,
  }: InputProps) => (
    <input
      aria-label={ariaLabel}
      disabled={disabled}
      onChange={onChange}
      placeholder={placeholder}
      value={value ?? defaultValue ?? ''}
    />
  )

  const MockTextArea = ({
    'aria-label': ariaLabel,
    defaultValue,
    disabled,
    onChange,
    rows,
    value,
  }: TextAreaProps) => (
    <textarea
      aria-label={ariaLabel}
      disabled={disabled}
      onChange={onChange}
      rows={rows}
      value={value ?? defaultValue ?? ''}
    />
  )

  const MockInputRoot = Object.assign(MockInput, {
    TextArea: MockTextArea,
  })

  const MockInputNumber = ({
    disabled,
    max,
    min,
    onChange,
    value,
  }: InputNumberProps) => (
    <input
      type="number"
      disabled={disabled}
      max={max}
      min={min}
      value={value ?? ''}
      onChange={(event) => {
        if (event.target.value === '') {
          onChange?.(null)
          return
        }
        onChange?.(Number(event.target.value))
      }}
    />
  )

  const MockModal = ({
    cancelText,
    children,
    okButtonProps,
    okText,
    onCancel,
    onOk,
    open,
    title,
  }: ModalProps) => {
    if (!open) {
      return null
    }

    return (
      <section role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined}>
        {title ? <h2>{title}</h2> : null}
        <div>{children}</div>
        <footer>
          <button type="button" onClick={onCancel}>
            {cancelText ?? 'Cancel'}
          </button>
          <button
            type="button"
            data-button-danger={okButtonProps?.danger ? 'true' : undefined}
            onClick={onOk}
          >
            {okText ?? 'OK'}
          </button>
        </footer>
      </section>
    )
  }

  const MockRadioButton = ({ children }: RadioButtonProps) => <>{children}</>

  const MockRadioGroup = ({
    children,
    disabled,
    onChange,
    value,
  }: RadioGroupProps) => {
    const currentValue = value ?? ''
    return (
      <div role="radiogroup" aria-disabled={disabled ? 'true' : undefined}>
        {Array.isArray(children)
          ? children.map((child, index) => {
            if (typeof child !== 'object' || child === null || !('props' in child)) {
              return child
            }
            const radioValue = (child as { props?: { value?: string; children?: ReactNode } }).props?.value ?? ''
            const label = (child as { props?: { children?: ReactNode } }).props?.children
            return (
              <label key={`${radioValue}-${index}`}>
                <input
                  type="radio"
                  checked={radioValue === currentValue}
                  disabled={disabled}
                  onChange={() => onChange?.({ target: { value: radioValue } })}
                />
                {label}
              </label>
            )
          })
          : children}
      </div>
    )
  }

  const MockRadio = {
    Group: MockRadioGroup,
    Button: MockRadioButton,
  }

  const MockSelect = ({
    allowClear,
    disabled,
    loading,
    notFoundContent,
    onChange,
    options = [],
    placeholder,
    value,
  }: SelectProps) => {
    const selectId = useId()
    return (
      <div>
        <select
          aria-label={typeof placeholder === 'string' ? placeholder : undefined}
          disabled={Boolean(disabled) || Boolean(loading)}
          id={selectId}
          onChange={(event) => onChange?.(event.target.value || undefined)}
          value={value == null ? '' : String(value)}
        >
          {allowClear || placeholder ? <option value="">{placeholder ?? ''}</option> : null}
          {options.map((option, index) => (
            <option
              key={`${String(option.value)}-${index}`}
              disabled={option.disabled}
              value={String(option.value ?? '')}
            >
              {typeof option.label === 'string' ? option.label : String(option.value ?? '')}
            </option>
          ))}
        </select>
        {options.length === 0 ? notFoundContent : null}
      </div>
    )
  }

  const MockSpace = ({
    children,
    style,
  }: SpaceProps) => (
    <div style={style}>
      {children}
    </div>
  )

  const MockSpin = ({
    size,
    tip,
  }: SpinProps) => (
    <div role="status" data-spin-size={size}>
      {tip ?? 'Loading'}
    </div>
  )

  const MockTabs = ({
    activeKey,
    defaultActiveKey,
    items = [],
    onChange,
  }: TabsProps) => {
    const [internalKey, setInternalKey] = useState(defaultActiveKey ?? items[0]?.key)
    const currentKey = activeKey ?? internalKey ?? items[0]?.key
    const currentItem = items.find((item) => item.key === currentKey) ?? items[0]

    return (
      <div>
        <div role="tablist">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={item.key === currentKey}
              onClick={() => {
                setInternalKey(item.key)
                onChange?.(item.key)
              }}
            >
              {item.label ?? item.key}
            </button>
          ))}
        </div>
        <div>{currentItem?.children}</div>
      </div>
    )
  }

  const MockSwitch = ({
    checked,
    disabled,
    onChange,
  }: SwitchProps) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked ? 'true' : 'false'}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
    >
      {checked ? 'On' : 'Off'}
    </button>
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

  const MockTitle = ({
    children,
    level = 2,
  }: TitleProps) => {
    switch (level) {
      case 1:
        return <h1>{children}</h1>
      case 3:
        return <h3>{children}</h3>
      case 4:
        return <h4>{children}</h4>
      case 5:
        return <h5>{children}</h5>
      default:
        return <h2>{children}</h2>
    }
  }

  const MockParagraph = ({ children }: ParagraphProps) => <p>{children}</p>

  return {
    ...actual,
    Alert: MockAlert,
    App: MockApp,
    Button: MockButton,
    Checkbox: MockCheckbox,
    Collapse: MockCollapse,
    Divider: MockDivider,
    Form: MockForm,
    Input: MockInputRoot,
    InputNumber: MockInputNumber,
    Modal: MockModal,
    Radio: MockRadio,
    Select: MockSelect,
    Space: MockSpace,
    Spin: MockSpin,
    Switch: MockSwitch,
    Tabs: MockTabs,
    Typography: {
      ...actual.Typography,
      Paragraph: MockParagraph,
      Text: MockText,
      Title: MockTitle,
    },
  }
}
