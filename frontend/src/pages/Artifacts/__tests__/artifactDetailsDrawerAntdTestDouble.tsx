/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import {
  cloneElement,
  isValidElement,
  useState,
  type ChangeEvent,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from 'react'

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
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  type?: 'default' | 'primary' | 'dashed' | 'link' | 'text'
}

type DescriptionsProps = {
  children?: ReactNode
}

type DescriptionsItemProps = {
  children?: ReactNode
  label?: ReactNode
}

type DropdownItem = {
  key: string
  label?: ReactNode
}

type DropdownProps = {
  children?: ReactNode
  disabled?: boolean
  menu?: {
    items?: DropdownItem[]
    onClick?: (info: { key: string }) => void
  }
}

type InputProps = {
  disabled?: boolean
  onChange?: (event: ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  value?: string
}

type SpaceProps = {
  children?: ReactNode
}

type SpinProps = {
  tip?: ReactNode
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
  type?: 'secondary' | 'success' | 'warning' | 'danger'
}

const noop = () => {}

const mockAppApi = {
  message: {
    error: noop,
    success: noop,
    warning: noop,
  },
  modal: {},
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

export function createArtifactDetailsDrawerAntdTestDouble(actual: AntdModule): AntdModule {
  const MockAppRoot = ({ children }: AppProps) => <>{children}</>

  const MockApp = Object.assign(MockAppRoot, {
    useApp: () => mockAppApi,
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
    onClick,
    type,
  }: ButtonProps) => (
    <button
      type="button"
      data-button-danger={danger ? 'true' : undefined}
      data-button-type={type}
      disabled={disabled}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  )

  const MockDescriptionsRoot = ({ children }: DescriptionsProps) => <dl>{children}</dl>

  const MockDescriptionsItem = ({
    children,
    label,
  }: DescriptionsItemProps) => (
    <>
      {label ? <dt>{label}</dt> : null}
      <dd>{children}</dd>
    </>
  )

  const MockDescriptions = Object.assign(MockDescriptionsRoot, {
    Item: MockDescriptionsItem,
  })

  const MockDropdown = ({
    children,
    disabled,
    menu,
  }: DropdownProps) => {
    const [open, setOpen] = useState(false)
    const items = menu?.items ?? []

    const trigger = isValidElement(children)
      ? cloneElement(children as ReactElement<{ onClick?: (event: MouseEvent<HTMLButtonElement>) => void }>, {
          onClick: (event) => {
            children.props.onClick?.(event)
            if (!disabled) {
              setOpen((current) => !current)
            }
          },
        })
      : (
        <button type="button" disabled={disabled} onClick={() => setOpen((current) => !current)}>
          Open menu
        </button>
      )

    return (
      <div>
        {trigger}
        {open ? (
          <div role="menu">
            {items.map((item) => (
              <button
                key={item.key}
                type="button"
                role="menuitem"
                onClick={() => {
                  menu?.onClick?.({ key: item.key })
                  setOpen(false)
                }}
              >
                {item.label ?? item.key}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const MockInput = ({
    disabled,
    onChange,
    placeholder,
    value,
  }: InputProps) => (
    <input
      disabled={disabled}
      placeholder={placeholder}
      value={value ?? ''}
      onChange={onChange}
    />
  )

  const MockSpace = ({ children }: SpaceProps) => <div>{children}</div>

  const MockSpin = ({ tip }: SpinProps) => (
    <div role="status">{tip ?? 'Loading'}</div>
  )

  const MockTable = ({
    columns = [],
    dataSource = [],
    locale,
    onRow,
    rowClassName,
    rowKey,
  }: TableProps) => {
    if (!dataSource.length) {
      return (
        <table>
          <tbody>
            <tr>
              <td>{locale?.emptyText ?? null}</td>
            </tr>
          </tbody>
        </table>
      )
    }

    return (
      <table>
        <thead>
          <tr>
            {columns.map((column, columnIndex) => (
              <th key={String(column.key ?? column.dataIndex ?? columnIndex)}>
                {column.title}
              </th>
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
    type,
  }: TextProps) => (
    <span data-text-type={type}>
      {code ? <code>{children}</code> : children}
    </span>
  )

  const MockTag = ({ children }: { children?: ReactNode }) => <span>{children}</span>

  return {
    ...actual,
    Alert: MockAlert,
    App: MockApp as unknown as AntdModule['App'],
    Button: MockButton,
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Dropdown: MockDropdown,
    Input: Object.assign(MockInput, {
      TextArea: actual.Input.TextArea,
      Password: actual.Input.Password,
      Search: actual.Input.Search,
      OTP: actual.Input.OTP,
      Group: actual.Input.Group,
    }) as unknown as AntdModule['Input'],
    Space: MockSpace,
    Spin: MockSpin,
    Table: MockTable as unknown as AntdModule['Table'],
    Tabs: MockTabs,
    Tag: MockTag,
    Typography: {
      ...actual.Typography,
      Text: MockText,
    },
  }
}
