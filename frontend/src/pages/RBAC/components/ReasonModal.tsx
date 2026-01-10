import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { App, Input, Modal, Space } from 'antd'
import type { ModalProps } from 'antd'

type OkButtonProps = NonNullable<ModalProps['okButtonProps']>

export function ReasonModal(props: {
  open: boolean
  title: ModalProps['title']
  okText?: string
  cancelText?: string
  okButtonProps?: OkButtonProps
  onCancel: () => void
  onOk: (reason: string) => Promise<void> | void
  children?: ReactNode
  reasonPlaceholder?: string
}) {
  const { message } = App.useApp()
  const [reason, setReason] = useState<string>('')

  useEffect(() => {
    if (props.open) {
      setReason('')
    }
  }, [props.open])

  const trimmedReason = reason.trim()
  const mergedOkButtonProps: OkButtonProps | undefined = useMemo(() => {
    if (!props.okButtonProps && trimmedReason) {
      return undefined
    }
    return {
      ...props.okButtonProps,
      disabled: Boolean(props.okButtonProps?.disabled) || !trimmedReason,
    }
  }, [props.okButtonProps, trimmedReason])

  return (
    <Modal
      title={props.title}
      open={props.open}
      okText={props.okText}
      cancelText={props.cancelText}
      onCancel={props.onCancel}
      okButtonProps={mergedOkButtonProps}
      onOk={async () => {
        if (!trimmedReason) {
          message.error('Reason is required')
          return
        }
        await props.onOk(trimmedReason)
      }}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {props.children}
        <Input.TextArea
          placeholder={props.reasonPlaceholder ?? 'Reason (required)'}
          value={reason}
          autoSize={{ minRows: 2, maxRows: 6 }}
          onChange={(event) => setReason(event.target.value)}
        />
      </Space>
    </Modal>
  )
}
