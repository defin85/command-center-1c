import { App, Button, Card, Form, Input, Select, Space, Tabs, Typography } from 'antd'

import { parseIdListFromText } from '../utils/parseIdListFromText'

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
type RoleOption = { label: string; value: number }
type BulkGrantResult = { created: number; updated: number; skipped: number }
type BulkRevokeResult = { deleted: number; skipped: number }

type BulkRolePermissionsI18n = {
  title?: string
  tabGrant?: string
  tabRevoke?: string
  confirmGrantTitle?: string
  confirmRevokeTitle?: string
  applyText?: string
  cancelText?: string
  roleLabel?: string
  levelLabel?: string
  notesLabel?: string
  countLabel?: string
  exampleLabel?: string
  rolePlaceholder?: string
  notesPlaceholder?: string
  reasonPlaceholder?: string
  idsPlaceholder?: string
  grantButton?: string
  revokeButton?: string
  idsRequiredMessage?: string
  roleRequiredMessage?: string
  reasonRequiredMessage?: string
  grantSuccessMessage?: (result: BulkGrantResult) => string
  revokeSuccessMessage?: (result: BulkRevokeResult) => string
  grantFailedMessage?: string
  revokeFailedMessage?: string
}

export function RbacBulkDatabaseRolePermissions(props: {
  roleOptions: RoleOption[]
  roleNameById: Map<number, string>
  levelOptions: Array<{ label: PermissionLevelCode; value: PermissionLevelCode }>
  bulkGrant: {
    mutateAsync: (payload: {
      group_id: number
      database_ids: string[]
      level: PermissionLevelCode
      notes?: string
      reason: string
    }) => Promise<BulkGrantResult>
    isPending: boolean
  }
  bulkRevoke: {
    mutateAsync: (payload: {
      group_id: number
      database_ids: string[]
      reason: string
    }) => Promise<BulkRevokeResult>
    isPending: boolean
  }
  i18n?: BulkRolePermissionsI18n
}) {
  const { modal, message } = App.useApp()
  const { Text } = Typography
  const i18n = props.i18n ?? {}

  const [grantForm] = Form.useForm<{
    group_id: number
    level: PermissionLevelCode
    notes?: string
    reason: string
    database_ids: string
  }>()

  const [revokeForm] = Form.useForm<{
    group_id: number
    reason: string
    database_ids: string
  }>()

  return (
    <Card title={i18n.title ?? 'Bulk Database Role Permissions'} size="small">
      <Tabs
        items={[
          {
            key: 'grant',
            label: i18n.tabGrant ?? 'Bulk Grant',
            children: (
              <Form
                form={grantForm}
                layout="vertical"
                initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                onFinish={(values) => {
                  const databaseIds = parseIdListFromText(values.database_ids)
                  if (databaseIds.length === 0) {
                    message.error(i18n.idsRequiredMessage ?? 'database_ids required')
                    return
                  }

                  const roleName = props.roleNameById.get(values.group_id) ?? String(values.group_id)
                  modal.confirm({
                    title: i18n.confirmGrantTitle ?? 'Confirm bulk grant (Databases)',
                    okText: i18n.applyText ?? 'Apply',
                    cancelText: i18n.cancelText ?? 'Cancel',
                    content: (
                      <Space direction="vertical" size={4}>
                        <Text><Text strong>{i18n.roleLabel ?? 'Role'}:</Text> {roleName} #{values.group_id}</Text>
                        <Text><Text strong>{i18n.levelLabel ?? 'Level'}:</Text> {values.level}</Text>
                        {values.notes ? <Text><Text strong>{i18n.notesLabel ?? 'Notes'}:</Text> {values.notes}</Text> : null}
                        <Text><Text strong>{i18n.countLabel ?? 'Count'}:</Text> {databaseIds.length}</Text>
                        <Text type="secondary">
                          {i18n.exampleLabel ?? 'Example'}: {databaseIds.slice(0, 5).join(', ')}{databaseIds.length > 5 ? ', ...' : ''}
                        </Text>
                      </Space>
                    ),
                    onOk: async () => {
                      try {
                        const result = await props.bulkGrant.mutateAsync({
                          group_id: values.group_id,
                          database_ids: databaseIds,
                          level: values.level,
                          notes: values.notes,
                          reason: values.reason,
                        })
                        message.success((i18n.grantSuccessMessage ?? ((r) => `Bulk grant: created=${r.created}, updated=${r.updated}, skipped=${r.skipped}`))(result))
                        grantForm.resetFields()
                      } catch (error) {
                        message.error(i18n.grantFailedMessage ?? 'Bulk grant failed')
                        throw error
                      }
                    },
                  })
                }}
              >
                <Space wrap>
                  <Form.Item name="group_id" rules={[{ required: true, message: i18n.roleRequiredMessage ?? 'role required' }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder={i18n.rolePlaceholder ?? 'Role'}
                      options={props.roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                  </Form.Item>
                  <Form.Item name="level" rules={[{ required: true }]}>
                    <Select style={{ width: 140 }} options={props.levelOptions} />
                  </Form.Item>
                  <Form.Item name="notes">
                    <Input placeholder={i18n.notesPlaceholder ?? 'Notes (optional)'} style={{ width: 260 }} />
                  </Form.Item>
                  <Form.Item name="reason" rules={[{ required: true, message: i18n.reasonRequiredMessage ?? 'reason required' }]}>
                    <Input placeholder={i18n.reasonPlaceholder ?? 'Reason'} style={{ width: 320 }} />
                  </Form.Item>
                </Space>
                <Form.Item name="database_ids" rules={[{ required: true, message: i18n.idsRequiredMessage ?? 'database_ids required' }]}>
                  <Input.TextArea
                    placeholder={i18n.idsPlaceholder ?? 'Database IDs (one per line)'}
                    autoSize={{ minRows: 3, maxRows: 6 }}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={props.bulkGrant.isPending}>
                  {i18n.grantButton ?? 'Bulk Grant'}
                </Button>
              </Form>
            ),
          },
          {
            key: 'revoke',
            label: i18n.tabRevoke ?? 'Bulk Revoke',
            children: (
              <Form
                form={revokeForm}
                layout="vertical"
                onFinish={(values) => {
                  const databaseIds = parseIdListFromText(values.database_ids)
                  if (databaseIds.length === 0) {
                    message.error(i18n.idsRequiredMessage ?? 'database_ids required')
                    return
                  }

                  const roleName = props.roleNameById.get(values.group_id) ?? String(values.group_id)
                  modal.confirm({
                    title: i18n.confirmRevokeTitle ?? 'Confirm bulk revoke (Databases)',
                    okText: i18n.applyText ?? 'Apply',
                    cancelText: i18n.cancelText ?? 'Cancel',
                    content: (
                      <Space direction="vertical" size={4}>
                        <Text><Text strong>{i18n.roleLabel ?? 'Role'}:</Text> {roleName} #{values.group_id}</Text>
                        <Text><Text strong>{i18n.countLabel ?? 'Count'}:</Text> {databaseIds.length}</Text>
                        <Text type="secondary">
                          {i18n.exampleLabel ?? 'Example'}: {databaseIds.slice(0, 5).join(', ')}{databaseIds.length > 5 ? ', ...' : ''}
                        </Text>
                      </Space>
                    ),
                    onOk: async () => {
                      try {
                        const result = await props.bulkRevoke.mutateAsync({
                          group_id: values.group_id,
                          database_ids: databaseIds,
                          reason: values.reason,
                        })
                        message.success((i18n.revokeSuccessMessage ?? ((r) => `Bulk revoke: deleted=${r.deleted}, skipped=${r.skipped}`))(result))
                        revokeForm.resetFields()
                      } catch (error) {
                        message.error(i18n.revokeFailedMessage ?? 'Bulk revoke failed')
                        throw error
                      }
                    },
                  })
                }}
              >
                <Space wrap>
                  <Form.Item name="group_id" rules={[{ required: true, message: i18n.roleRequiredMessage ?? 'role required' }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder={i18n.rolePlaceholder ?? 'Role'}
                      options={props.roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                  </Form.Item>
                  <Form.Item name="reason" rules={[{ required: true, message: i18n.reasonRequiredMessage ?? 'reason required' }]}>
                    <Input placeholder={i18n.reasonPlaceholder ?? 'Reason'} style={{ width: 320 }} />
                  </Form.Item>
                </Space>
                <Form.Item name="database_ids" rules={[{ required: true, message: i18n.idsRequiredMessage ?? 'database_ids required' }]}>
                  <Input.TextArea
                    placeholder={i18n.idsPlaceholder ?? 'Database IDs (one per line)'}
                    autoSize={{ minRows: 3, maxRows: 8 }}
                  />
                </Form.Item>
                <Button type="primary" danger htmlType="submit" loading={props.bulkRevoke.isPending}>
                  {i18n.revokeButton ?? 'Bulk Revoke'}
                </Button>
              </Form>
            ),
          },
        ]}
      />
    </Card>
  )
}
