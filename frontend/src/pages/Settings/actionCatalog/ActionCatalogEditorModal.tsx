import type { ActionFormValues } from '../actionCatalogTypes'
import type { FormInstance } from 'antd'

import { OperationExposureEditorModal } from './OperationExposureEditorModal'

export type ActionCatalogEditorModalProps = {
  open: boolean
  title: string
  form: FormInstance<ActionFormValues>
  initialValues: ActionFormValues | null
  onCancel: () => void
  onApply: () => void
}

export function ActionCatalogEditorModal(props: ActionCatalogEditorModalProps) {
  return (
    <OperationExposureEditorModal
      {...props}
      surface="action_catalog"
    />
  )
}
