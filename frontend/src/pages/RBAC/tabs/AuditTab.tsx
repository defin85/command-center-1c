import { Space } from 'antd'

import { RbacAuditPanel } from '../components/RbacAuditPanel'

type UndoCommand = { code: string; meta?: Record<string, unknown> }

function formatUndoTitle(cmd: UndoCommand): string {
  const meta = cmd.meta ?? {}
  const id = (key: string) => {
    const value = meta[key]
    return value === undefined || value === null ? '?' : String(value)
  }

  switch (cmd.code) {
    case 'delete_role':
      return `Откат: удалить роль #${id('groupId')}`
    case 'rename_role':
      return `Откат: вернуть имя роли #${id('groupId')}`
    case 'restore_user_roles':
      return `Откат: восстановить роли пользователя #${id('userId')}`
    case 'restore_role_capabilities':
      return `Откат: восстановить права роли #${id('groupId')}`

    case 'revoke_cluster_permission':
      return `Откат: отозвать доступ пользователя #${id('userId')} к кластеру ${id('clusterId')}`
    case 'restore_cluster_permission_level':
      return `Откат: восстановить уровень доступа пользователя #${id('userId')} к кластеру ${id('clusterId')}`
    case 'restore_cluster_permission':
      return `Откат: восстановить доступ пользователя #${id('userId')} к кластеру ${id('clusterId')}`

    case 'revoke_database_permission':
      return `Откат: отозвать доступ пользователя #${id('userId')} к базе ${id('databaseId')}`
    case 'restore_database_permission_level':
      return `Откат: восстановить уровень доступа пользователя #${id('userId')} к базе ${id('databaseId')}`
    case 'restore_database_permission':
      return `Откат: восстановить доступ пользователя #${id('userId')} к базе ${id('databaseId')}`

    case 'revoke_cluster_group_permission':
      return `Откат: отозвать доступ группы #${id('groupId')} к кластеру ${id('clusterId')}`
    case 'restore_cluster_group_permission_level':
      return `Откат: восстановить уровень доступа группы #${id('groupId')} к кластеру ${id('clusterId')}`
    case 'restore_cluster_group_permission':
      return `Откат: восстановить доступ группы #${id('groupId')} к кластеру ${id('clusterId')}`

    case 'revoke_database_group_permission':
      return `Откат: отозвать доступ группы #${id('groupId')} к базе ${id('databaseId')}`
    case 'restore_database_group_permission_level':
      return `Откат: восстановить уровень доступа группы #${id('groupId')} к базе ${id('databaseId')}`
    case 'restore_database_group_permission':
      return `Откат: восстановить доступ группы #${id('groupId')} к базе ${id('databaseId')}`

    case 'revoke_operation_template_permission':
      return `Откат: отозвать доступ пользователя #${id('userId')} к шаблону операции ${id('templateId')}`
    case 'restore_operation_template_permission_level':
      return `Откат: восстановить уровень доступа пользователя #${id('userId')} к шаблону операции ${id('templateId')}`
    case 'restore_operation_template_permission':
      return `Откат: восстановить доступ пользователя #${id('userId')} к шаблону операции ${id('templateId')}`

    case 'revoke_operation_template_group_permission':
      return `Откат: отозвать доступ группы #${id('groupId')} к шаблону операции ${id('templateId')}`
    case 'restore_operation_template_group_permission_level':
      return `Откат: восстановить уровень доступа группы #${id('groupId')} к шаблону операции ${id('templateId')}`
    case 'restore_operation_template_group_permission':
      return `Откат: восстановить доступ группы #${id('groupId')} к шаблону операции ${id('templateId')}`

    case 'revoke_workflow_template_permission':
      return `Откат: отозвать доступ пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`
    case 'restore_workflow_template_permission_level':
      return `Откат: восстановить уровень доступа пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`
    case 'restore_workflow_template_permission':
      return `Откат: восстановить доступ пользователя #${id('userId')} к шаблону рабочего процесса ${id('templateId')}`

    case 'revoke_workflow_template_group_permission':
      return `Откат: отозвать доступ группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`
    case 'restore_workflow_template_group_permission_level':
      return `Откат: восстановить уровень доступа группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`
    case 'restore_workflow_template_group_permission':
      return `Откат: восстановить доступ группы #${id('groupId')} к шаблону рабочего процесса ${id('templateId')}`

    case 'revoke_artifact_permission':
      return `Откат: отозвать доступ пользователя #${id('userId')} к артефакту ${id('artifactId')}`
    case 'restore_artifact_permission_level':
      return `Откат: восстановить уровень доступа пользователя #${id('userId')} к артефакту ${id('artifactId')}`
    case 'restore_artifact_permission':
      return `Откат: восстановить доступ пользователя #${id('userId')} к артефакту ${id('artifactId')}`

    case 'revoke_artifact_group_permission':
      return `Откат: отозвать доступ группы #${id('groupId')} к артефакту ${id('artifactId')}`
    case 'restore_artifact_group_permission_level':
      return `Откат: восстановить уровень доступа группы #${id('groupId')} к артефакту ${id('artifactId')}`
    case 'restore_artifact_group_permission':
      return `Откат: восстановить доступ группы #${id('groupId')} к артефакту ${id('artifactId')}`
  }

  return `Откат: ${cmd.code}`
}

export function AuditTab(props: { canManageRbac: boolean }) {
  const { canManageRbac } = props

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div data-testid="rbac-audit-panel">
        <RbacAuditPanel
          enabled={canManageRbac}
          title="Аудит"
          errorMessage="Не удалось загрузить журнал аудита"
          undoLabel="Отменить"
          undoModalTitle="Отменить изменение"
          undoOkText="Отменить"
          undoCancelText="Закрыть"
          undoReasonPlaceholder="Причина (обязательно)"
          undoReasonRequiredMessage="Укажите причину"
          undoSuccessMessage="Изменение отменено"
          undoFailedMessage="Не удалось отменить изменение"
          undoNotSupportedMessage="Для этой записи откат не поддерживается"
          i18n={{
            searchPlaceholder: 'Поиск',
            refreshText: 'Обновить',
            viewText: 'Открыть',
            detailsModalTitle: (id) => `Аудит #${id}`,
            columnCreatedAt: 'Время',
            columnActor: 'Оператор',
            columnAction: 'Действие',
            columnOutcome: 'Результат',
            columnTarget: 'Цель',
            columnReason: 'Причина',
            columnDetails: 'Детали',
            detailsAuditIdLabel: 'ID аудита:',
            detailsActionLabel: 'Действие:',
            detailsTargetLabel: 'Цель:',
            formatUndoTitle,
          }}
        />
      </div>
    </Space>
  )
}

