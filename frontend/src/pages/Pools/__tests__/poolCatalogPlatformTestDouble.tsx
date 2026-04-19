import type { CSSProperties, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

const formatStatus = (value: ReactNode) => {
  if (typeof value !== 'string') {
    return value
  }
  return value
    .split('_')
    .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : part))
    .join(' ')
}

export function WorkspacePage({
  header,
  children,
}: {
  header?: ReactNode
  children: ReactNode
}) {
  return (
    <div>
      {header}
      {children}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div>
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
    </div>
  )
}

export function RouteButton({
  to,
  children,
  disabled,
  style,
  className,
  block: _block,
  'data-testid': dataTestId,
}: {
  to: string
  children: ReactNode
  disabled?: boolean
  style?: CSSProperties
  className?: string
  block?: boolean
  'data-testid'?: string
}) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      className={className}
      data-testid={dataTestId}
      disabled={disabled}
      style={style}
      onClick={() => navigate(to)}
    >
      {children}
    </button>
  )
}

export function StatusBadge({
  status,
  label,
}: {
  status?: ReactNode
  label?: ReactNode
}) {
  return <span>{label ?? formatStatus(status ?? '')}</span>
}

export function DrawerFormShell({
  open,
  title,
  subtitle,
  onClose,
  drawerTestId,
  children,
}: {
  open: boolean
  title?: ReactNode
  subtitle?: ReactNode
  onClose?: () => void
  drawerTestId?: string
  children?: ReactNode
}) {
  return open ? (
    <section data-testid={drawerTestId}>
      {title ? <h2>{title}</h2> : null}
      {subtitle ? <p>{subtitle}</p> : null}
      {onClose ? (
        <button type="button" onClick={onClose}>
          Close
        </button>
      ) : null}
      {children}
    </section>
  ) : null
}
