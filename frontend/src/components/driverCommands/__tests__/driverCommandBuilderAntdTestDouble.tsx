import { useState, type CSSProperties, type ReactNode } from 'react'

type AntdModule = typeof import('antd')

type AlertProps = {
  description?: ReactNode
  message?: ReactNode
  type?: 'success' | 'info' | 'warning' | 'error'
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

export function createDriverCommandBuilderAntdTestDouble(actual: AntdModule): AntdModule {
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
    Collapse: MockCollapse,
    Modal: MockModal,
    Space: MockSpace,
    Spin: MockSpin,
    Tabs: MockTabs,
    Typography: {
      ...actual.Typography,
      Paragraph: MockParagraph,
      Text: MockText,
      Title: MockTitle,
    },
  }
}
