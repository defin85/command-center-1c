import { Input } from 'antd'
import { useCallback } from 'react'

type ModalApi = {
  confirm: (config: any) => void
}

type MessageApi = {
  error: (content: string) => void
}

export function useConfirmReason(modal: ModalApi, message: MessageApi) {
  return useCallback((title: string, onConfirm: (reason: string) => Promise<void>) => {
    let value = ''
    modal.confirm({
      title,
      content: (
        <Input.TextArea
          placeholder="Reason (required)"
          autoSize={{ minRows: 2, maxRows: 6 }}
          onChange={(event) => {
            value = event.target.value
          }}
        />
      ),
      okText: 'Confirm',
      cancelText: 'Cancel',
      onOk: async () => {
        const reason = value.trim()
        if (!reason) {
          message.error('Reason is required')
          return Promise.reject(new Error('Reason is required'))
        }
        await onConfirm(reason)
      },
    })
  }, [modal, message])
}

