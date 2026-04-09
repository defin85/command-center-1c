import { ModalFormShell } from '../../components/platform'
import {
  type OperationExposureEditorModalProps,
  useOperationExposureEditorSurface,
} from '../Settings/actionCatalog/OperationExposureEditorModal'

export function TemplateOperationExposureEditorModal(props: OperationExposureEditorModalProps) {
  const surface = useOperationExposureEditorSurface(props)

  return (
    <ModalFormShell
      open={props.open}
      title={props.title}
      onClose={props.onCancel}
      onSubmit={surface.handleSubmit}
      footerStart={surface.footerStart}
      submitButtonTestId="action-catalog-editor-apply"
      submitDisabled={surface.submitDisabled}
      destroyOnHidden={false}
      forceRender
      bodyStyle={{ maxHeight: '70vh', overflowY: 'auto' }}
    >
      {surface.content}
    </ModalFormShell>
  )
}
