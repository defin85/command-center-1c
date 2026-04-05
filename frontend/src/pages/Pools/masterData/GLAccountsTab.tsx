import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App as AntApp, Button, Descriptions, Form, Input, Space, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import {
  getMasterDataGlAccount,
  listMasterDataGlAccounts,
  type PoolMasterDataRegistryEntry,
  type PoolMasterGLAccount,
  upsertMasterDataGlAccount,
} from '../../../api/intercompanyPools'
import {
  EntityDetails,
  EntityTable,
  JsonBlock,
  ModalFormShell,
  StatusBadge,
} from '../../../components/platform'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getRegistryEntryLabel } from './registry'

const { Text } = Typography

type GLAccountFormValues = {
  canonical_id: string
  code: string
  name: string
  chart_identity: string
  config_name: string
  config_version: string
}

type GLAccountsTabProps = {
  registryEntries: PoolMasterDataRegistryEntry[]
}

const buildCompatibilityClass = (account: Pick<PoolMasterGLAccount, 'chart_identity' | 'config_name' | 'config_version'>) => (
  `${account.chart_identity} · ${account.config_name} · ${account.config_version}`
)

export function GLAccountsTab({ registryEntries }: GLAccountsTabProps) {
  const { message } = AntApp.useApp()
  const [rows, setRows] = useState<PoolMasterGLAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)
  const [selectedAccount, setSelectedAccount] = useState<PoolMasterGLAccount | null>(null)
  const [loadingRows, setLoadingRows] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [query, setQuery] = useState('')
  const [codeFilter, setCodeFilter] = useState('')
  const [chartIdentityFilter, setChartIdentityFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingAccount, setEditingAccount] = useState<PoolMasterGLAccount | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [form] = Form.useForm<GLAccountFormValues>()

  const registryEntry = useMemo(
    () => findRegistryEntryByEntityType(registryEntries, 'gl_account'),
    [registryEntries]
  )

  const loadRows = useCallback(async () => {
    setLoadingRows(true)
    try {
      const response = await listMasterDataGlAccounts({
        query: query.trim() || undefined,
        code: codeFilter.trim() || undefined,
        chart_identity: chartIdentityFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(response.gl_accounts)
      setSelectedAccountId((current) => {
        if (current && response.gl_accounts.some((item) => item.id === current)) {
          return current
        }
        return response.gl_accounts[0]?.id ?? null
      })
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить GL Accounts.')
      message.error(resolved.message)
    } finally {
      setLoadingRows(false)
    }
  }, [chartIdentityFilter, codeFilter, message, query])

  const loadSelectedAccount = useCallback(async (glAccountId: string) => {
    setLoadingDetail(true)
    try {
      const response = await getMasterDataGlAccount(glAccountId)
      setSelectedAccount(response.gl_account)
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось загрузить детали GL Account.')
      setSelectedAccount(null)
      message.error(resolved.message)
    } finally {
      setLoadingDetail(false)
    }
  }, [message])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  useEffect(() => {
    if (!selectedAccountId) {
      setSelectedAccount(null)
      return
    }
    void loadSelectedAccount(selectedAccountId)
  }, [loadSelectedAccount, selectedAccountId])

  const openCreateModal = () => {
    setEditingAccount(null)
    form.setFieldsValue({
      canonical_id: '',
      code: '',
      name: '',
      chart_identity: '',
      config_name: '',
      config_version: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (account: PoolMasterGLAccount) => {
    setEditingAccount(account)
    form.setFieldsValue({
      canonical_id: account.canonical_id,
      code: account.code,
      name: account.name,
      chart_identity: account.chart_identity,
      config_name: account.config_name,
      config_version: account.config_version,
    })
    setIsModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setIsSaving(true)
    try {
      const response = await upsertMasterDataGlAccount({
        gl_account_id: editingAccount?.id,
        canonical_id: values.canonical_id.trim(),
        code: values.code.trim(),
        name: values.name.trim(),
        chart_identity: values.chart_identity.trim(),
        config_name: values.config_name.trim(),
        config_version: values.config_version.trim(),
      })
      setIsModalOpen(false)
      setSelectedAccountId(response.gl_account.id)
      setSelectedAccount(response.gl_account)
      message.success(editingAccount ? 'GL Account обновлён.' : 'GL Account создан.')
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, 'Не удалось сохранить GL Account.')
      if (Object.keys(resolved.fieldErrors).length > 0) {
        form.setFields(
          Object.entries(resolved.fieldErrors).map(([name, errors]) => ({ name, errors })) as never
        )
      }
      message.error(resolved.message)
    } finally {
      setIsSaving(false)
    }
  }

  const columns: ColumnsType<PoolMasterGLAccount> = [
    { title: 'Canonical ID', dataIndex: 'canonical_id', key: 'canonical_id', width: 180 },
    { title: 'Code', dataIndex: 'code', key: 'code', width: 120 },
    { title: 'Name', dataIndex: 'name', key: 'name', width: 220 },
    { title: 'Chart Identity', dataIndex: 'chart_identity', key: 'chart_identity', width: 220 },
    {
      title: 'Compatibility Class',
      key: 'compatibility',
      width: 260,
      render: (_, row) => (
        <Space direction="vertical" size={2}>
          <StatusBadge status="compatible" label="Compatible class" />
          <Text type="secondary">{`${row.config_name} · ${row.config_version}`}</Text>
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, row) => (
        <Button
          size="small"
          onClick={(event) => {
            event.stopPropagation()
            openEditModal(row)
          }}
        >
          Edit
        </Button>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={`${getRegistryEntryLabel(registryEntry) || 'GL Account'} capability state`}
        description={(
          <Space direction="vertical" size={4}>
            <Text>
              Bootstrap import availability is governed by the reusable-data registry. Generic mutating sync
              controls stay outside this authoring surface.
            </Text>
            <Space wrap>
              <StatusBadge
                status={registryEntry?.capabilities.bootstrap_import ? 'compatible' : 'warning'}
                label={registryEntry?.capabilities.bootstrap_import ? 'Bootstrap-capable' : 'Bootstrap-disabled'}
              />
              <StatusBadge
                status={registryEntry?.capabilities.token_exposure ? 'compatible' : 'warning'}
                label={registryEntry?.capabilities.token_exposure ? 'Token-exposed' : 'Token-disabled'}
              />
            </Space>
          </Space>
        )}
      />

      <EntityTable
        title="GL Accounts"
        dataSource={rows}
        columns={columns}
        rowKey="id"
        loading={loadingRows}
        emptyDescription="GL Accounts are not configured yet."
        toolbar={(
          <Space wrap>
            <Input
              allowClear
              placeholder="Search canonical_id / code / name"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onPressEnter={() => void loadRows()}
              style={{ width: 280 }}
            />
            <Input
              allowClear
              placeholder="Code filter"
              value={codeFilter}
              onChange={(event) => setCodeFilter(event.target.value)}
              style={{ width: 180 }}
            />
            <Input
              allowClear
              placeholder="Chart identity"
              value={chartIdentityFilter}
              onChange={(event) => setChartIdentityFilter(event.target.value)}
              style={{ width: 220 }}
            />
            <Button onClick={() => void loadRows()} loading={loadingRows}>Refresh</Button>
            <Button type="primary" onClick={openCreateModal}>Add GL Account</Button>
          </Space>
        )}
        onRow={(row) => ({
          onClick: () => setSelectedAccountId(row.id),
        })}
        rowClassName={(row) => (row.id === selectedAccountId ? 'ant-table-row-selected' : '')}
      />

      <EntityDetails
        title={selectedAccount ? selectedAccount.name : 'GL Account details'}
        empty={!selectedAccount}
        emptyDescription="Select a GL Account to inspect its compatibility class and metadata."
        loading={loadingDetail}
        extra={selectedAccount ? (
          <Space wrap>
            <StatusBadge status="compatible" label="Compatibility class" />
            <Button onClick={() => openEditModal(selectedAccount)}>Edit GL Account</Button>
          </Space>
        ) : undefined}
      >
        {selectedAccount ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="Canonical ID">{selectedAccount.canonical_id}</Descriptions.Item>
              <Descriptions.Item label="Code">{selectedAccount.code}</Descriptions.Item>
              <Descriptions.Item label="Name">{selectedAccount.name}</Descriptions.Item>
              <Descriptions.Item label="Chart Identity">{selectedAccount.chart_identity}</Descriptions.Item>
              <Descriptions.Item label="Config Name">{selectedAccount.config_name}</Descriptions.Item>
              <Descriptions.Item label="Config Version">{selectedAccount.config_version}</Descriptions.Item>
              <Descriptions.Item label="Compatibility Class" span={2}>
                <Space wrap>
                  <StatusBadge status="compatible" label="Compatible class" />
                  <Text>{buildCompatibilityClass(selectedAccount)}</Text>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Updated">{formatDateTime(selectedAccount.updated_at)}</Descriptions.Item>
              <Descriptions.Item label="Selected ID">
                <Text code data-testid="pool-master-data-gl-account-selected-id">{selectedAccount.id}</Text>
              </Descriptions.Item>
            </Descriptions>
            <JsonBlock title="Metadata" value={selectedAccount.metadata ?? {}} />
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={() => void handleSubmit()}
        title={editingAccount ? 'Edit GL Account' : 'Create GL Account'}
        subtitle="Operator-facing compatibility class is explicit and separate from runtime provenance."
        submitText={editingAccount ? 'Save GL Account' : 'Create GL Account'}
        confirmLoading={isSaving}
        width={760}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label="Canonical ID" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="Code" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="chart_identity" label="Chart Identity" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_name" label="Config Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_version" label="Config Version" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </Space>
  )
}
