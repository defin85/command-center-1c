import { Space } from 'antd'

import { useRbacTranslation } from '../../../i18n'
import { RbacAuditPanel } from '../components/RbacAuditPanel'

type UndoCommand = { code: string; meta?: Record<string, unknown> }

export function AuditTab(props: { canManageRbac: boolean }) {
  const { canManageRbac } = props
  const { t } = useRbacTranslation()

  const formatUndoTitle = (cmd: UndoCommand): string => {
    const meta = cmd.meta ?? {}
    const id = (key: string) => {
      const value = meta[key]
      return value === undefined || value === null ? '?' : String(value)
    }
    const prefix = t(($) => $.audit.undo.prefix)

    switch (cmd.code) {
      case 'delete_role':
        return `${prefix}: ${t(($) => $.audit.undo.role.delete)} #${id('groupId')}`
      case 'rename_role':
        return `${prefix}: ${t(($) => $.audit.undo.role.rename)} #${id('groupId')}`
      case 'restore_user_roles':
        return `${prefix}: ${t(($) => $.audit.undo.role.restoreUserRoles)} #${id('userId')}`
      case 'restore_role_capabilities':
        return `${prefix}: ${t(($) => $.audit.undo.role.restoreCapabilities)} #${id('groupId')}`
    }

    const subjectKey = cmd.code.includes('_group_') ? 'group' : 'user'
    const subjectIdKey = subjectKey === 'group' ? 'groupId' : 'userId'
    const subject = t(($) => $.audit.undo.subjects[subjectKey])

    const resourceKey = (() => {
      if (cmd.code.includes('operation_template')) return 'operationTemplate'
      if (cmd.code.includes('workflow_template')) return 'workflowTemplate'
      if (cmd.code.includes('database')) return 'database'
      if (cmd.code.includes('artifact')) return 'artifact'
      if (cmd.code.includes('cluster')) return 'cluster'
      return null
    })()

    if (!resourceKey) {
      return `${prefix}: ${cmd.code}`
    }

    const resourceIdKey = resourceKey === 'database'
      ? 'databaseId'
      : resourceKey === 'cluster'
        ? 'clusterId'
        : resourceKey === 'artifact'
          ? 'artifactId'
          : 'templateId'
    const resource = t(($) => $.audit.undo.resources[resourceKey])

    const templateKey = cmd.code.startsWith('revoke_')
      ? 'revoke'
      : cmd.code.includes('_level')
        ? 'restoreLevel'
        : 'restore'

    return `${prefix}: ${t(($) => $.audit.undo.templates[templateKey], {
      subject,
      subjectId: id(subjectIdKey),
      resource,
      resourceId: id(resourceIdKey),
    })}`
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div data-testid="rbac-audit-panel">
        <RbacAuditPanel
          enabled={canManageRbac}
          title={t(($) => $.audit.title)}
          errorMessage={t(($) => $.audit.loadFailed)}
          undoLabel={t(($) => $.audit.undo.label)}
          undoModalTitle={t(($) => $.audit.undo.modalTitle)}
          undoOkText={t(($) => $.audit.undo.ok)}
          undoCancelText={t(($) => $.audit.undo.cancel)}
          undoReasonPlaceholder={t(($) => $.audit.undo.reasonPlaceholder)}
          undoReasonRequiredMessage={t(($) => $.audit.undo.reasonRequired)}
          undoSuccessMessage={t(($) => $.audit.undo.success)}
          undoFailedMessage={t(($) => $.audit.undo.failed)}
          undoNotSupportedMessage={t(($) => $.audit.undo.notSupported)}
          i18n={{
            searchPlaceholder: t(($) => $.audit.searchPlaceholder),
            refreshText: t(($) => $.audit.refresh),
            viewText: t(($) => $.audit.view),
            detailsModalTitle: (id) => t(($) => $.audit.detailsModalTitle, { id: String(id) }),
            columnCreatedAt: t(($) => $.audit.columns.createdAt),
            columnActor: t(($) => $.audit.columns.actor),
            columnAction: t(($) => $.audit.columns.action),
            columnOutcome: t(($) => $.audit.columns.outcome),
            columnTarget: t(($) => $.audit.columns.target),
            columnReason: t(($) => $.audit.columns.reason),
            columnDetails: t(($) => $.audit.columns.details),
            detailsAuditIdLabel: t(($) => $.audit.detailsLabels.auditId),
            detailsActionLabel: t(($) => $.audit.detailsLabels.action),
            detailsTargetLabel: t(($) => $.audit.detailsLabels.target),
            formatUndoTitle,
          }}
        />
      </div>
    </Space>
  )
}
