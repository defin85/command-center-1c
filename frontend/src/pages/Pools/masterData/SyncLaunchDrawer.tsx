import { useEffect, useMemo, useState } from 'react'
import { Alert, Form, Select } from 'antd'

import {
  type CreatePoolMasterDataSyncLaunchPayload,
  type PoolMasterDataRegistryEntry,
  type PoolMasterDataSyncLaunchMode,
  type SimpleClusterRef,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { DrawerFormShell } from '../../../components/platform'
import { resolveApiError } from './errorUtils'
import { getSyncEntityOptions } from './registry'

type SyncLauncherFormValues = {
  mode: PoolMasterDataSyncLaunchMode
  target_mode: 'cluster_all' | 'database_set'
  cluster_id?: string
  database_ids?: string[]
  entity_scope: string[]
}

type SyncLaunchDrawerProps = {
  open: boolean
  clusters: SimpleClusterRef[]
  databases: SimpleDatabaseRef[]
  clusterNameById: ReadonlyMap<string, string>
  registryEntries: PoolMasterDataRegistryEntry[]
  loadingTargets: boolean
  onClose: () => void
  onSubmit: (payload: CreatePoolMasterDataSyncLaunchPayload) => Promise<void>
}

const LAUNCH_MODE_OPTIONS: Array<{ value: PoolMasterDataSyncLaunchMode; label: string }> = [
  { value: 'inbound', label: 'Inbound' },
  { value: 'outbound', label: 'Outbound' },
  { value: 'reconcile', label: 'Reconcile' },
]

const LAUNCH_TARGET_MODE_OPTIONS: Array<{ value: 'cluster_all' | 'database_set'; label: string }> = [
  { value: 'cluster_all', label: 'Cluster All' },
  { value: 'database_set', label: 'Database Set' },
]

export function SyncLaunchDrawer({
  open,
  clusters,
  databases,
  clusterNameById,
  registryEntries,
  loadingTargets,
  onClose,
  onSubmit,
}: SyncLaunchDrawerProps) {
  const [form] = Form.useForm<SyncLauncherFormValues>()
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const launchMode = Form.useWatch('mode', form) as PoolMasterDataSyncLaunchMode | undefined
  const launchTargetMode = Form.useWatch('target_mode', form) as 'cluster_all' | 'database_set' | undefined
  const watchedClusterId = Form.useWatch('cluster_id', form) as string | undefined

  const launchEntityTypeOptions = useMemo(
    () => getSyncEntityOptions(registryEntries, launchMode ?? 'inbound'),
    [launchMode, registryEntries]
  )

  const filteredLauncherDatabases = useMemo(() => {
    if (launchTargetMode !== 'database_set' || !watchedClusterId) {
      return databases
    }
    return databases.filter((database) => database.cluster_id === watchedClusterId)
  }, [databases, launchTargetMode, watchedClusterId])

  useEffect(() => {
    if (!open) {
      setSubmitError('')
      return
    }
    const currentMode = form.getFieldValue('mode') as PoolMasterDataSyncLaunchMode | undefined
    const currentTargetMode = form.getFieldValue('target_mode') as 'cluster_all' | 'database_set' | undefined
    const currentScope = (form.getFieldValue('entity_scope') as string[] | undefined) ?? []
    form.setFieldsValue({
      mode: currentMode || 'inbound',
      target_mode: currentTargetMode || 'database_set',
      entity_scope: currentScope.length > 0
        ? currentScope
        : launchEntityTypeOptions.slice(0, 2).map((option) => option.value),
    })
  }, [form, launchEntityTypeOptions, open])

  useEffect(() => {
    const currentScope = (form.getFieldValue('entity_scope') as string[] | undefined) ?? []
    const allowedValues = new Set(launchEntityTypeOptions.map((option) => option.value))
    const nextScope = currentScope.filter((value) => allowedValues.has(value))
    if (nextScope.length === currentScope.length) {
      return
    }
    form.setFieldsValue({
      entity_scope: nextScope.length > 0
        ? nextScope
        : launchEntityTypeOptions.slice(0, 2).map((option) => option.value),
    })
  }, [form, launchEntityTypeOptions])

  useEffect(() => {
    if (launchTargetMode !== 'database_set') {
      return
    }
    const selectedDatabaseIds = (form.getFieldValue('database_ids') as string[] | undefined) ?? []
    const allowedDatabaseIds = new Set(filteredLauncherDatabases.map((database) => database.id))
    const nextDatabaseIds = selectedDatabaseIds.filter((value) => allowedDatabaseIds.has(value))
    if (nextDatabaseIds.length === selectedDatabaseIds.length) {
      return
    }
    form.setFieldsValue({ database_ids: nextDatabaseIds })
  }, [filteredLauncherDatabases, form, launchTargetMode])

  const handleSubmit = async () => {
    try {
      setSubmitError('')
      const values = await form.validateFields()
      setSubmitting(true)
      await onSubmit({
        mode: values.mode,
        target_mode: values.target_mode,
        cluster_id: values.target_mode === 'cluster_all' ? values.cluster_id : undefined,
        database_ids: values.target_mode === 'database_set' ? (values.database_ids ?? []) : undefined,
        entity_scope: values.entity_scope ?? [],
      })
    } catch (error) {
      if (typeof error === 'object' && error !== null && 'errorFields' in error) {
        return
      }
      const resolved = resolveApiError(error, 'Не удалось создать manual sync launch.')
      setSubmitError(resolved.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <DrawerFormShell
      open={open}
      onClose={onClose}
      onSubmit={handleSubmit}
      title="Launch Sync"
      subtitle="Create a cluster-wide or database-scoped manual sync launch request."
      submitText="Launch"
      confirmLoading={submitting}
      drawerTestId="sync-launch-drawer"
      submitButtonTestId="sync-launch-submit"
    >
      <Form<SyncLauncherFormValues>
        layout="vertical"
        form={form}
        initialValues={{
          mode: 'inbound',
          target_mode: 'database_set',
          entity_scope: launchEntityTypeOptions.slice(0, 2).map((option) => option.value),
        }}
      >
        <Form.Item
          label="Mode"
          name="mode"
          rules={[{ required: true, message: 'Select sync mode.' }]}
        >
          <Select
            data-testid="sync-launch-mode"
            options={LAUNCH_MODE_OPTIONS}
          />
        </Form.Item>

        <Form.Item
          label="Target Mode"
          name="target_mode"
          rules={[{ required: true, message: 'Select target mode.' }]}
        >
          <Select
            data-testid="sync-launch-target-mode"
            options={LAUNCH_TARGET_MODE_OPTIONS}
          />
        </Form.Item>

        {launchTargetMode === 'cluster_all' ? (
          <Form.Item
            label="Cluster"
            name="cluster_id"
            rules={[{ required: true, message: 'Select cluster.' }]}
          >
            <Select
              data-testid="sync-launch-cluster"
              loading={loadingTargets}
              options={clusters.map((cluster) => ({
                value: cluster.id,
                label: cluster.name,
              }))}
            />
          </Form.Item>
        ) : null}

        {launchTargetMode === 'database_set' ? (
          <Form.Item
            label="Databases"
            name="database_ids"
            rules={[{ required: true, message: 'Select at least one database.' }]}
          >
            <Select
              data-testid="sync-launch-database-set"
              mode="multiple"
              loading={loadingTargets}
              options={filteredLauncherDatabases.map((database) => ({
                value: database.id,
                label: database.cluster_id
                  ? `${database.name} · ${clusterNameById.get(database.cluster_id) || database.cluster_id}`
                  : database.name,
              }))}
            />
          </Form.Item>
        ) : null}

        <Form.Item
          label="Entity Scope"
          name="entity_scope"
          rules={[{ required: true, message: 'Select at least one entity type.' }]}
        >
          <Select
            data-testid="sync-launch-entity-scope"
            mode="multiple"
            options={launchEntityTypeOptions}
          />
        </Form.Item>

        {submitError ? (
          <Alert
            type="error"
            showIcon
            message={submitError}
          />
        ) : null}
      </Form>
    </DrawerFormShell>
  )
}
