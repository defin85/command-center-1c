import { Grid, Modal, Space, Typography } from 'antd'
import type { ReactNode } from 'react'

const { useBreakpoint } = Grid
const { Text } = Typography
const DESKTOP_BREAKPOINT_PX = 992

type ModalFormShellProps = {
  open: boolean
  onClose: () => void
  onSubmit?: () => void
  title?: ReactNode
  subtitle?: ReactNode
  submitText?: ReactNode
  confirmLoading?: boolean
  width?: number
  submitButtonTestId?: string
  forceRender?: boolean
  children: ReactNode
}

export function ModalFormShell({
  open,
  onClose,
  onSubmit,
  title,
  subtitle,
  submitText = 'Save',
  confirmLoading = false,
  width = 880,
  submitButtonTestId,
  forceRender = false,
  children,
}: ModalFormShellProps) {
  const screens = useBreakpoint()
  const hasMatchedBreakpoint = Object.values(screens).some(Boolean)
  const isNarrow = hasMatchedBreakpoint
    ? !screens.lg
    : (
      typeof window !== 'undefined'
        ? window.innerWidth < DESKTOP_BREAKPOINT_PX
        : false
    )

  const modalTitle = title || subtitle
    ? (
      <Space direction="vertical" size={0}>
        {title}
        {subtitle ? <Text type="secondary">{subtitle}</Text> : null}
      </Space>
    )
    : undefined

  return (
    <Modal
      open={open}
      title={modalTitle}
      onCancel={onClose}
      onOk={onSubmit}
      okText={submitText}
      confirmLoading={confirmLoading}
      forceRender={forceRender}
      destroyOnHidden
      okButtonProps={submitButtonTestId ? { 'data-testid': submitButtonTestId } : undefined}
      width={isNarrow ? 'calc(100vw - 24px)' : width}
      style={isNarrow ? { top: 12, paddingBottom: 12 } : undefined}
    >
      {children}
    </Modal>
  )
}
