import type { CSSProperties, ReactNode } from 'react'

type AntdModule = typeof import('antd')

type TableColumn = {
  key?: string
  title?: ReactNode
  dataIndex?: string | number | Array<string | number>
  render?: (value: unknown, record: Record<string, unknown>, index: number) => ReactNode
}

type TableProps = {
  columns?: TableColumn[]
  dataSource?: Array<Record<string, unknown>>
  rowKey?: string | ((record: Record<string, unknown>) => string)
  onRow?: (record: Record<string, unknown>, index?: number) => Record<string, unknown>
  rowClassName?: string | ((record: Record<string, unknown>, index: number) => string)
  locale?: { emptyText?: ReactNode }
  style?: CSSProperties
  'data-testid'?: string
}

type OverlayProps = {
  open?: boolean
  title?: ReactNode
  extra?: ReactNode
  footer?: ReactNode
  onOk?: () => void
  onCancel?: () => void
  okText?: ReactNode
  cancelText?: ReactNode
  confirmLoading?: boolean
  children?: ReactNode
  className?: string
  style?: CSSProperties
  'data-testid'?: string
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

const resolveAccessibleLabel = (title: ReactNode) => (
  typeof title === 'string' || typeof title === 'number' ? String(title) : undefined
)

export function createPoolCatalogAntdTestDouble(actual: AntdModule): AntdModule {
  const MockCard = ({
    title,
    extra,
    className,
    children,
    style,
    'data-testid': dataTestId,
  }: {
    title?: ReactNode
    extra?: ReactNode
    className?: string
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <section
      className={['ant-card', className].filter(Boolean).join(' ')}
      style={style}
      data-testid={dataTestId}
    >
      {title || extra ? (
        <header>
          {title}
          {extra}
        </header>
      ) : null}
      {children}
    </section>
  )

  const MockDescriptionsRoot = ({
    children,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <dl style={style} data-testid={dataTestId}>
      {children}
    </dl>
  )

  const MockDescriptionsItem = ({
    label,
    children,
  }: {
    label?: ReactNode
    children?: ReactNode
  }) => (
    <>
      {label ? <dt>{label}</dt> : null}
      <dd>{children}</dd>
    </>
  )

  const MockDescriptions = Object.assign(MockDescriptionsRoot, {
    Item: MockDescriptionsItem,
  })

  const MockTag = ({
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: {
    children?: ReactNode
    className?: string
    style?: CSSProperties
    'data-testid'?: string
  }) => (
    <span className={className} style={style} data-testid={dataTestId}>
      {children}
    </span>
  )

  const MockDrawer = ({
    open,
    title,
    extra,
    footer,
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: OverlayProps) => {
    if (!open) {
      return null
    }

    return (
      <section
        role="dialog"
        aria-label={resolveAccessibleLabel(title)}
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
        {footer}
      </section>
    )
  }

  const MockModal = ({
    open,
    title,
    extra,
    footer,
    onOk,
    onCancel,
    okText,
    cancelText,
    confirmLoading,
    children,
    className,
    style,
    'data-testid': dataTestId,
  }: OverlayProps) => {
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
        aria-label={resolveAccessibleLabel(title)}
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

  const MockTable = ({
    columns = [],
    dataSource = [],
    rowKey,
    onRow,
    rowClassName,
    locale,
    style,
    'data-testid': dataTestId,
  }: TableProps) => {
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

  return {
    ...actual,
    Card: MockCard as unknown as AntdModule['Card'],
    Descriptions: MockDescriptions as unknown as AntdModule['Descriptions'],
    Drawer: MockDrawer as unknown as AntdModule['Drawer'],
    Modal: MockModal as unknown as AntdModule['Modal'],
    Table: MockTable as unknown as AntdModule['Table'],
    Tag: MockTag as unknown as AntdModule['Tag'],
  }
}
