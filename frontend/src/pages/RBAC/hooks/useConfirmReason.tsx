import { Input } from 'antd'
import { useCallback } from 'react'

type ModalRef = {
  update: (config: any) => void
  destroy: () => void
}

type ModalApi = {
  confirm: (config: any) => ModalRef
}

type MessageApi = {
  error: (content: string) => void
}

export type ConfirmReasonLabels = {
  placeholder?: string
  okText?: string
  cancelText?: string
  requiredMessage?: string
}

export function useConfirmReason(modal: ModalApi, message: MessageApi, labels?: ConfirmReasonLabels) {
  const placeholder = labels?.placeholder ?? 'Reason (required)'
  const okText = labels?.okText ?? 'Confirm'
  const cancelText = labels?.cancelText ?? 'Cancel'
  const requiredMessage = labels?.requiredMessage ?? 'Reason is required'

  return useCallback((title: string, onConfirm: (reason: string) => Promise<void>) => {
    let value = ''
    let modalRef: ModalRef | null = null

    const syncOkDisabled = () => {
      const disabled = !value.trim()
      modalRef?.update({ okButtonProps: { disabled } })
    }

    modalRef = modal.confirm({
      title,
      content: (
        <Input.TextArea
          placeholder={placeholder}
          autoSize={{ minRows: 2, maxRows: 6 }}
          onChange={(event) => {
            value = event.target.value
            syncOkDisabled()
          }}
        />
      ),
      okText,
      cancelText,
      okButtonProps: { disabled: true },
      onOk: async () => {
        const reason = value.trim()
        if (!reason) {
          message.error(requiredMessage)
          return Promise.reject(new Error(requiredMessage))
        }
        await onConfirm(reason)
      },
    })

    syncOkDisabled()
  }, [modal, message, placeholder, okText, cancelText, requiredMessage])
}
