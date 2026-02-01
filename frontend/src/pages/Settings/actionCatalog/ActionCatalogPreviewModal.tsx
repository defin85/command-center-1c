import { Alert, Button, Modal, Spin } from 'antd'

import type { ActionCatalogPreviewState } from './useActionCatalogPreview'

export type ActionCatalogPreviewModalProps = {
  previewModal: ActionCatalogPreviewState
  onClose: () => void
}

export function ActionCatalogPreviewModal({ previewModal, onClose }: ActionCatalogPreviewModalProps) {
  return (
    <Modal
      title={previewModal.title}
      open={previewModal.open}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>Close</Button>,
      ]}
      width={900}
    >
      {previewModal.loading ? (
        <Spin />
      ) : previewModal.error ? (
        <Alert type="error" showIcon message="Preview failed" description={previewModal.error} />
      ) : (
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(previewModal.payload, null, 2)}
        </pre>
      )}
    </Modal>
  )
}
