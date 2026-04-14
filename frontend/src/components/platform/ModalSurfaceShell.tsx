import { Grid, Modal, Space, Typography } from 'antd'
import type { ButtonProps } from 'antd'
import type { ReactNode } from 'react'
import { usePlatformTranslation } from '@/i18n'
import { trackUiAction } from '../../observability/uiActionJournal'
import { firstSemanticActionLabel } from '../../observability/semanticActionLabel'

const { useBreakpoint } = Grid
const { Text } = Typography
const DESKTOP_BREAKPOINT_PX = 992

type ModalSurfaceShellProps = {
  open: boolean
  onClose: () => void
  onSubmit?: () => void | Promise<void>
  title?: ReactNode
  subtitle?: ReactNode
  submitText?: ReactNode
  confirmLoading?: boolean
  width?: number
  forceRender?: boolean
  okButtonProps?: ButtonProps
  cancelText?: ReactNode
  children: ReactNode
}

export function ModalSurfaceShell({
  open,
  onClose,
  onSubmit,
  title,
  subtitle,
  submitText,
  confirmLoading = false,
  width = 880,
  forceRender = false,
  okButtonProps,
  cancelText,
  children,
}: ModalSurfaceShellProps) {
  const { t } = usePlatformTranslation()
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

  const resolvedSubmitText = submitText ?? t(($) => $.actions.confirm)
  const resolvedCancelText = cancelText ?? t(($) => $.actions.cancel)
  const actionName = firstSemanticActionLabel(
    resolvedSubmitText,
    title,
    subtitle,
  ) ?? 'Modal confirm'

  return (
    <Modal
      open={open}
      title={modalTitle}
      onCancel={onClose}
      onOk={onSubmit ? () => trackUiAction({
        actionKind: 'modal.confirm',
        actionName,
      }, () => onSubmit()) : undefined}
      okText={resolvedSubmitText}
      cancelText={resolvedCancelText}
      confirmLoading={confirmLoading}
      forceRender={forceRender}
      destroyOnHidden
      okButtonProps={okButtonProps}
      width={isNarrow ? 'calc(100vw - 24px)' : width}
      style={isNarrow ? { top: 12, paddingBottom: 12 } : undefined}
    >
      {children}
    </Modal>
  )
}
