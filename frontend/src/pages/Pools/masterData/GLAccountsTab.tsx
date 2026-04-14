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
import { usePoolsTranslation } from '../../../i18n'
import { resolveApiError } from './errorUtils'
import { formatDateTime } from './formatters'
import { findRegistryEntryByEntityType, getRegistryEntityLabel } from './registry'

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
  const { t } = usePoolsTranslation()
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
      const resolved = resolveApiError(error, t('masterData.glAccountsTab.messages.failedToLoadList'))
      message.error(resolved.message)
    } finally {
      setLoadingRows(false)
    }
  }, [chartIdentityFilter, codeFilter, message, query, t])

  const loadSelectedAccount = useCallback(async (glAccountId: string) => {
    setLoadingDetail(true)
    try {
      const response = await getMasterDataGlAccount(glAccountId)
      setSelectedAccount(response.gl_account)
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountsTab.messages.failedToLoadDetail'))
      setSelectedAccount(null)
      message.error(resolved.message)
    } finally {
      setLoadingDetail(false)
    }
  }, [message, t])

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
      message.success(
        editingAccount
          ? t('masterData.glAccountsTab.messages.accountUpdated')
          : t('masterData.glAccountsTab.messages.accountCreated')
      )
      await loadRows()
    } catch (error) {
      const resolved = resolveApiError(error, t('masterData.glAccountsTab.messages.failedToSave'))
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

  const columns: ColumnsType<PoolMasterGLAccount> = useMemo(() => [
    {
      title: t('masterData.glAccountsTab.columns.canonicalId'),
      dataIndex: 'canonical_id',
      key: 'canonical_id',
      width: 180,
    },
    { title: t('masterData.glAccountsTab.columns.code'), dataIndex: 'code', key: 'code', width: 120 },
    { title: t('masterData.glAccountsTab.columns.name'), dataIndex: 'name', key: 'name', width: 220 },
    {
      title: t('masterData.glAccountsTab.columns.chartIdentity'),
      dataIndex: 'chart_identity',
      key: 'chart_identity',
      width: 220,
    },
    {
      title: t('masterData.glAccountsTab.columns.compatibilityClass'),
      key: 'compatibility',
      width: 260,
      render: (_, row) => (
        <Space direction="vertical" size={2}>
          <StatusBadge status="compatible" label={t('masterData.glAccountsTab.columns.compatibleClass')} />
          <Text type="secondary">{`${row.config_name} · ${row.config_version}`}</Text>
        </Space>
      ),
    },
    {
      title: t('masterData.glAccountsTab.columns.actions'),
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
          {t('common.edit')}
        </Button>
      ),
    },
  ], [openEditModal, t])

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message={t('masterData.glAccountsTab.alerts.capabilityState', {
          label: getRegistryEntityLabel(registryEntries, 'gl_account') || 'GL Account',
        })}
        description={(
          <Space direction="vertical" size={4}>
            <Text>{t('masterData.glAccountsTab.alerts.capabilityDescription')}</Text>
            <Space wrap>
              <StatusBadge
                status={registryEntry?.capabilities.bootstrap_import ? 'compatible' : 'warning'}
                label={registryEntry?.capabilities.bootstrap_import
                  ? t('masterData.glAccountsTab.alerts.bootstrapCapable')
                  : t('masterData.glAccountsTab.alerts.bootstrapDisabled')}
              />
              <StatusBadge
                status={registryEntry?.capabilities.token_exposure ? 'compatible' : 'warning'}
                label={registryEntry?.capabilities.token_exposure
                  ? t('masterData.glAccountsTab.alerts.tokenExposed')
                  : t('masterData.glAccountsTab.alerts.tokenDisabled')}
              />
            </Space>
          </Space>
        )}
      />

      <EntityTable
        title={t('masterData.glAccountsTab.table.title')}
        dataSource={rows}
        columns={columns}
        rowKey="id"
        loading={loadingRows}
        emptyDescription={t('masterData.glAccountsTab.table.emptyDescription')}
        toolbar={(
          <Space wrap>
            <Input
              allowClear
              placeholder={t('masterData.glAccountsTab.table.searchPlaceholder')}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onPressEnter={() => void loadRows()}
              style={{ width: 280 }}
            />
            <Input
              allowClear
              placeholder={t('masterData.glAccountsTab.table.codeFilter')}
              value={codeFilter}
              onChange={(event) => setCodeFilter(event.target.value)}
              style={{ width: 180 }}
            />
            <Input
              allowClear
              placeholder={t('masterData.glAccountsTab.table.chartIdentityFilter')}
              value={chartIdentityFilter}
              onChange={(event) => setChartIdentityFilter(event.target.value)}
              style={{ width: 220 }}
            />
            <Button onClick={() => void loadRows()} loading={loadingRows}>{t('catalog.actions.refresh')}</Button>
            <Button type="primary" onClick={openCreateModal}>{t('masterData.glAccountsTab.modal.create')}</Button>
          </Space>
        )}
        onRow={(row) => ({
          onClick: () => setSelectedAccountId(row.id),
        })}
        rowClassName={(row) => (row.id === selectedAccountId ? 'ant-table-row-selected' : '')}
      />

      <EntityDetails
        title={selectedAccount ? selectedAccount.name : t('masterData.glAccountsTab.details.title')}
        empty={!selectedAccount}
        emptyDescription={t('masterData.glAccountsTab.details.emptyDescription')}
        loading={loadingDetail}
        extra={selectedAccount ? (
          <Space wrap>
            <StatusBadge status="compatible" label={t('masterData.glAccountsTab.details.compatibilityClass')} />
            <Button onClick={() => openEditModal(selectedAccount)}>{t('masterData.glAccountsTab.details.edit')}</Button>
          </Space>
        ) : undefined}
      >
        {selectedAccount ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label={t('masterData.glAccountsTab.columns.canonicalId')}>{selectedAccount.canonical_id}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.columns.code')}>{selectedAccount.code}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.columns.name')}>{selectedAccount.name}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.columns.chartIdentity')}>{selectedAccount.chart_identity}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.details.configName')}>{selectedAccount.config_name}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.details.configVersion')}>{selectedAccount.config_version}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.columns.compatibilityClass')} span={2}>
                <Space wrap>
                  <StatusBadge status="compatible" label={t('masterData.glAccountsTab.columns.compatibleClass')} />
                  <Text>{buildCompatibilityClass(selectedAccount)}</Text>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.details.updated')}>{formatDateTime(selectedAccount.updated_at)}</Descriptions.Item>
              <Descriptions.Item label={t('masterData.glAccountsTab.details.selectedId')}>
                <Text code data-testid="pool-master-data-gl-account-selected-id">{selectedAccount.id}</Text>
              </Descriptions.Item>
            </Descriptions>
            <JsonBlock title={t('masterData.glAccountsTab.details.metadata')} value={selectedAccount.metadata ?? {}} />
          </Space>
        ) : null}
      </EntityDetails>

      <ModalFormShell
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={() => void handleSubmit()}
        title={editingAccount ? t('masterData.glAccountsTab.modal.editTitle') : t('masterData.glAccountsTab.modal.createTitle')}
        subtitle={t('masterData.glAccountsTab.modal.subtitle')}
        submitText={editingAccount ? t('masterData.glAccountsTab.modal.save') : t('masterData.glAccountsTab.modal.create')}
        confirmLoading={isSaving}
        width={760}
        forceRender
      >
        <Form form={form} layout="vertical">
          <Form.Item name="canonical_id" label={t('masterData.glAccountsTab.modal.fields.canonicalId')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label={t('masterData.glAccountsTab.modal.fields.code')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label={t('masterData.glAccountsTab.modal.fields.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="chart_identity" label={t('masterData.glAccountsTab.modal.fields.chartIdentity')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_name" label={t('masterData.glAccountsTab.modal.fields.configName')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="config_version" label={t('masterData.glAccountsTab.modal.fields.configVersion')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </ModalFormShell>
    </Space>
  )
}
