import { Button, Grid, Modal, Space, Typography, type ButtonProps } from 'antd'
import type { CSSProperties, ReactNode } from 'react'
import { trackUiAction } from '../../observability/uiActionJournal'
import { firstSemanticActionLabel } from '../../observability/semanticActionLabel'

const { useBreakpoint } = Grid
const { Text } = Typography
const DESKTOP_BREAKPOINT_PX = 992

type ModalFormShellProps = {
  open: boolean
  onClose: () => void
  onSubmit?: () => void | Promise<void>
  title?: ReactNode
  subtitle?: ReactNode
  submitText?: ReactNode
  cancelText?: ReactNode
  confirmLoading?: boolean
  width?: number
  submitButtonTestId?: string
  forceRender?: boolean
  destroyOnHidden?: boolean
  submitDisabled?: boolean
  footerStart?: ReactNode
  bodyStyle?: CSSProperties
  children: ReactNode
}

export function ModalFormShell({
  open,
  onClose,
  onSubmit,
  title,
  subtitle,
  submitText = 'Save',
  cancelText = 'Cancel',
  confirmLoading = false,
  width = 880,
  submitButtonTestId,
  forceRender = false,
  destroyOnHidden = true,
  submitDisabled = false,
  footerStart,
  bodyStyle,
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

  const actionName = firstSemanticActionLabel(
    submitText,
    title,
    subtitle,
  ) ?? 'Modal submit'
  const handleSubmit = onSubmit
    ? () => trackUiAction({
      actionKind: 'modal.submit',
      actionName,
    }, () => onSubmit())
    : undefined
  const okButtonProps: ButtonProps | undefined = submitButtonTestId || submitDisabled
    ? {
      ...(submitButtonTestId ? { 'data-testid': submitButtonTestId } : {}),
      disabled: submitDisabled,
    }
    : undefined
  const customFooter = footerStart ? (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
      <Space size="small" wrap>{footerStart}</Space>
      <Space size="small" wrap>
        <Button onClick={onClose}>{cancelText}</Button>
        {onSubmit ? (
          <Button
            type="primary"
            loading={confirmLoading}
            disabled={submitDisabled}
            onClick={() => {
              void handleSubmit?.()
            }}
            data-testid={submitButtonTestId}
          >
            {submitText}
          </Button>
        ) : null}
      </Space>
    </div>
  ) : undefined

  return (
    <Modal
      open={open}
      title={modalTitle}
      onCancel={onClose}
      onOk={customFooter ? undefined : handleSubmit}
      okText={submitText}
      cancelText={cancelText}
      confirmLoading={confirmLoading}
      forceRender={forceRender}
      destroyOnHidden={destroyOnHidden}
      footer={customFooter}
      okButtonProps={okButtonProps}
      width={isNarrow ? 'calc(100vw - 24px)' : width}
      style={isNarrow ? { top: 12, paddingBottom: 12 } : undefined}
      styles={bodyStyle ? { body: bodyStyle } : undefined}
    >
      {children}
    </Modal>
  )
}
