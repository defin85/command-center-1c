import { App, Button, Card, Form, Input, Select, Space, Tabs, Typography } from 'antd'

import { parseIdListFromText } from '../utils/parseIdListFromText'

type PermissionLevelCode = 'VIEW' | 'OPERATE' | 'MANAGE' | 'ADMIN'
type RoleOption = { label: string; value: number }
type BulkGrantResult = { created: number; updated: number; skipped: number }
type BulkRevokeResult = { deleted: number; skipped: number }

export function RbacBulkClusterRolePermissions(props: {
  roleOptions: RoleOption[]
  roleNameById: Map<number, string>
  levelOptions: Array<{ label: PermissionLevelCode; value: PermissionLevelCode }>
  bulkGrant: {
    mutateAsync: (payload: {
      group_id: number
      cluster_ids: string[]
      level: PermissionLevelCode
      notes?: string
      reason: string
    }) => Promise<BulkGrantResult>
    isPending: boolean
  }
  bulkRevoke: {
    mutateAsync: (payload: {
      group_id: number
      cluster_ids: string[]
      reason: string
    }) => Promise<BulkRevokeResult>
    isPending: boolean
  }
}) {
  const { modal, message } = App.useApp()
  const { Text } = Typography

  const [grantForm] = Form.useForm<{
    group_id: number
    level: PermissionLevelCode
    notes?: string
    reason: string
    cluster_ids: string
  }>()

  const [revokeForm] = Form.useForm<{
    group_id: number
    reason: string
    cluster_ids: string
  }>()

  return (
    <Card title="Bulk Cluster Role Permissions" size="small">
      <Tabs
        items={[
          {
            key: 'grant',
            label: 'Bulk Grant',
            children: (
              <Form
                form={grantForm}
                layout="vertical"
                initialValues={{ level: 'VIEW' satisfies PermissionLevelCode }}
                onFinish={(values) => {
                  const clusterIds = parseIdListFromText(values.cluster_ids)
                  if (clusterIds.length === 0) {
                    message.error('cluster_ids required')
                    return
                  }

                  const roleName = props.roleNameById.get(values.group_id) ?? String(values.group_id)
                  modal.confirm({
                    title: 'Confirm bulk grant (Clusters)',
                    okText: 'Apply',
                    cancelText: 'Cancel',
                    content: (
                      <Space direction="vertical" size={4}>
                        <Text><Text strong>Role:</Text> {roleName} #{values.group_id}</Text>
                        <Text><Text strong>Level:</Text> {values.level}</Text>
                        {values.notes ? <Text><Text strong>Notes:</Text> {values.notes}</Text> : null}
                        <Text><Text strong>Count:</Text> {clusterIds.length}</Text>
                        <Text type="secondary">
                          Example: {clusterIds.slice(0, 5).join(', ')}{clusterIds.length > 5 ? ', ...' : ''}
                        </Text>
                      </Space>
                    ),
                    onOk: async () => {
                      try {
                        const result = await props.bulkGrant.mutateAsync({
                          group_id: values.group_id,
                          cluster_ids: clusterIds,
                          level: values.level,
                          notes: values.notes,
                          reason: values.reason,
                        })
                        message.success(`Bulk grant: created=${result.created}, updated=${result.updated}, skipped=${result.skipped}`)
                        grantForm.resetFields()
                      } catch (error) {
                        message.error('Bulk grant failed')
                        throw error
                      }
                    },
                  })
                }}
              >
                <Space wrap>
                  <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="Role"
                      options={props.roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                  </Form.Item>
                  <Form.Item name="level" rules={[{ required: true }]}>
                    <Select style={{ width: 140 }} options={props.levelOptions} />
                  </Form.Item>
                  <Form.Item name="notes">
                    <Input placeholder="Notes (optional)" style={{ width: 260 }} />
                  </Form.Item>
                  <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                    <Input placeholder="Reason" style={{ width: 320 }} />
                  </Form.Item>
                </Space>
                <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                  <Input.TextArea
                    placeholder="Cluster UUIDs (one per line)"
                    autoSize={{ minRows: 3, maxRows: 6 }}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={props.bulkGrant.isPending}>
                  Bulk Grant
                </Button>
              </Form>
            ),
          },
          {
            key: 'revoke',
            label: 'Bulk Revoke',
            children: (
              <Form
                form={revokeForm}
                layout="vertical"
                onFinish={(values) => {
                  const clusterIds = parseIdListFromText(values.cluster_ids)
                  if (clusterIds.length === 0) {
                    message.error('cluster_ids required')
                    return
                  }

                  const roleName = props.roleNameById.get(values.group_id) ?? String(values.group_id)
                  modal.confirm({
                    title: 'Confirm bulk revoke (Clusters)',
                    okText: 'Apply',
                    cancelText: 'Cancel',
                    content: (
                      <Space direction="vertical" size={4}>
                        <Text><Text strong>Role:</Text> {roleName} #{values.group_id}</Text>
                        <Text><Text strong>Count:</Text> {clusterIds.length}</Text>
                        <Text type="secondary">
                          Example: {clusterIds.slice(0, 5).join(', ')}{clusterIds.length > 5 ? ', ...' : ''}
                        </Text>
                      </Space>
                    ),
                    onOk: async () => {
                      try {
                        const result = await props.bulkRevoke.mutateAsync({
                          group_id: values.group_id,
                          cluster_ids: clusterIds,
                          reason: values.reason,
                        })
                        message.success(`Bulk revoke: deleted=${result.deleted}, skipped=${result.skipped}`)
                        revokeForm.resetFields()
                      } catch (error) {
                        message.error('Bulk revoke failed')
                        throw error
                      }
                    },
                  })
                }}
              >
                <Space wrap>
                  <Form.Item name="group_id" rules={[{ required: true, message: 'role required' }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="Role"
                      options={props.roleOptions}
                      showSearch
                      optionFilterProp="label"
                    />
                  </Form.Item>
                  <Form.Item name="reason" rules={[{ required: true, message: 'reason required' }]}>
                    <Input placeholder="Reason" style={{ width: 320 }} />
                  </Form.Item>
                </Space>
                <Form.Item name="cluster_ids" rules={[{ required: true, message: 'cluster_ids required' }]}>
                  <Input.TextArea
                    placeholder="Cluster UUIDs (one per line)"
                    autoSize={{ minRows: 3, maxRows: 8 }}
                  />
                </Form.Item>
                <Button type="primary" danger htmlType="submit" loading={props.bulkRevoke.isPending}>
                  Bulk Revoke
                </Button>
              </Form>
            ),
          },
        ]}
      />
    </Card>
  )
}
