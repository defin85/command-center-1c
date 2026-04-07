import { Drawer, Grid, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useEffect } from 'react'

const { useBreakpoint } = Grid
const { Text } = Typography
const DESKTOP_BREAKPOINT_PX = 992

type DrawerSurfaceShellProps = {
  open: boolean
  onClose: () => void
  title?: ReactNode
  subtitle?: ReactNode
  extra?: ReactNode
  width?: number
  drawerTestId?: string
  children: ReactNode
}

export function DrawerSurfaceShell({
  open,
  onClose,
  title,
  subtitle,
  extra,
  width = 880,
  drawerTestId,
  children,
}: DrawerSurfaceShellProps) {
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )

  useEffect(() => {
    if (!open || typeof document === 'undefined') {
      return
    }

    const root = document.documentElement
    const body = document.body
    const previousRootOverflowX = root.style.overflowX
    const previousBodyOverflowX = body.style.overflowX

    root.style.overflowX = 'hidden'
    body.style.overflowX = 'hidden'

    return () => {
      root.style.overflowX = previousRootOverflowX
      body.style.overflowX = previousBodyOverflowX
    }
  }, [open])

  const drawerTitle = title || subtitle
    ? (
      <Space direction="vertical" size={0}>
        {title}
        {subtitle ? <Text type="secondary">{subtitle}</Text> : null}
      </Space>
    )
    : undefined

  return (
    <Drawer
      data-testid={drawerTestId}
      open={open}
      onClose={onClose}
      title={drawerTitle}
      extra={extra}
      width={isNarrow ? '100%' : width}
      forceRender
      destroyOnClose
    >
      {children}
    </Drawer>
  )
}
