import { Button, Drawer, Grid, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { trackUiAction } from '../../observability/uiActionJournal'
import { firstSemanticActionLabel } from '../../observability/semanticActionLabel'

const { useBreakpoint } = Grid
const { Text } = Typography
const DESKTOP_BREAKPOINT_PX = 992

type DrawerFormShellProps = {
  open: boolean
  onClose: () => void
  onSubmit?: () => void | Promise<void>
  title?: ReactNode
  subtitle?: ReactNode
  submitText?: ReactNode
  confirmLoading?: boolean
  extra?: ReactNode
  width?: number
  submitButtonTestId?: string
  drawerTestId?: string
  children: ReactNode
}

export function DrawerFormShell({
  open,
  onClose,
  onSubmit,
  title,
  subtitle,
  submitText = 'Save',
  confirmLoading = false,
  extra,
  width = 880,
  submitButtonTestId,
  drawerTestId,
  children,
}: DrawerFormShellProps) {
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

  const actionName = firstSemanticActionLabel(
    submitText,
    title,
    subtitle,
  ) ?? 'Drawer submit'

  const submitButton = onSubmit
    ? (
      <Button
        type="primary"
        loading={confirmLoading}
        onClick={() => {
          void trackUiAction({
            actionKind: 'drawer.submit',
            actionName,
          }, onSubmit)
        }}
        data-testid={submitButtonTestId}
      >
        {submitText}
      </Button>
    )
    : null

  const drawerExtra = extra || submitButton
    ? (
      <Space size="small" wrap>
        {extra}
        {submitButton}
      </Space>
    )
    : undefined

  return (
    <Drawer
      data-testid={drawerTestId}
      open={open}
      onClose={onClose}
      title={drawerTitle}
      extra={drawerExtra}
      width={isNarrow ? '100%' : width}
      forceRender
      destroyOnClose
    >
      {children}
    </Drawer>
  )
}
