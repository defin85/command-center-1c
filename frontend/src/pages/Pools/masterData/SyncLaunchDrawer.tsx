import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Form, Select, Space, Typography } from 'antd'

import {
  type CreatePoolMasterDataSyncLaunchPayload,
  type PoolMasterDataRegistryEntry,
  type PoolMasterDataSyncLaunchMode,
  type SimpleClusterRef,
  type SimpleDatabaseRef,
} from '../../../api/intercompanyPools'
import { DrawerFormShell } from '../../../components/platform'
import { usePoolsTranslation } from '../../../i18n'
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
  onOpenEligibilityContext?: (context: { clusterId: string; databaseId?: string }) => void
  onSubmit: (payload: CreatePoolMasterDataSyncLaunchPayload) => Promise<void>
}

type ClusterEligibilitySummary = {
  eligibleCount: number
  excluded: SimpleDatabaseRef[]
  unconfigured: SimpleDatabaseRef[]
}

export function SyncLaunchDrawer({
  open,
  clusters,
  databases,
  clusterNameById,
  registryEntries,
  loadingTargets,
  onClose,
  onOpenEligibilityContext,
  onSubmit,
}: SyncLaunchDrawerProps) {
  const { t } = usePoolsTranslation()
  const [form] = Form.useForm<SyncLauncherFormValues>()
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const setFieldErrorsFromProblem = (fieldErrors: Record<string, string[]>) => {
    if (Object.keys(fieldErrors).length === 0) {
      return
    }
    form.setFields(
      Object.entries(fieldErrors).map(([name, errors]) => ({ name, errors })) as never
    )
  }

  const launchMode = Form.useWatch('mode', form) as PoolMasterDataSyncLaunchMode | undefined
  const launchTargetMode = Form.useWatch('target_mode', form) as 'cluster_all' | 'database_set' | undefined
  const watchedClusterId = Form.useWatch('cluster_id', form) as string | undefined

  const launchEntityTypeOptions = useMemo(
    () => getSyncEntityOptions(registryEntries, launchMode ?? 'inbound'),
    [launchMode, registryEntries]
  )
  const launchModeOptions = useMemo<Array<{ value: PoolMasterDataSyncLaunchMode; label: string }>>(
    () => [
      { value: 'inbound', label: t('masterData.syncLaunchDrawer.mode.inbound') },
      { value: 'outbound', label: t('masterData.syncLaunchDrawer.mode.outbound') },
      { value: 'reconcile', label: t('masterData.syncLaunchDrawer.mode.reconcile') },
    ],
    [t]
  )
  const launchTargetModeOptions = useMemo<Array<{ value: 'cluster_all' | 'database_set'; label: string }>>(
    () => [
      { value: 'cluster_all', label: t('masterData.syncLaunchDrawer.targetMode.clusterAll') },
      { value: 'database_set', label: t('masterData.syncLaunchDrawer.targetMode.databaseSet') },
    ],
    [t]
  )

  const selectedClusterDatabases = useMemo(
    () => databases.filter((database) => database.cluster_id === watchedClusterId),
    [databases, watchedClusterId],
  )

  const clusterEligibilitySummary = useMemo<ClusterEligibilitySummary | null>(() => {
    if (launchTargetMode !== 'cluster_all' || !watchedClusterId) {
      return null
    }
    return {
      eligibleCount: selectedClusterDatabases.filter(
        (database) => database.cluster_all_eligibility_state === 'eligible'
      ).length,
      excluded: selectedClusterDatabases.filter(
        (database) => database.cluster_all_eligibility_state === 'excluded'
      ),
      unconfigured: selectedClusterDatabases.filter(
        (database) => database.cluster_all_eligibility_state === 'unconfigured'
      ),
    }
  }, [launchTargetMode, selectedClusterDatabases, watchedClusterId])

  const clusterAllBlocked = Boolean(
    clusterEligibilitySummary && clusterEligibilitySummary.unconfigured.length > 0
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
      if (clusterAllBlocked) {
        setSubmitError(t('masterData.syncLaunchDrawer.messages.resolveEligibilityBeforeLaunch'))
        return
      }
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
      const resolved = resolveApiError(error, t('masterData.syncLaunchDrawer.messages.failedToCreate'))
      setFieldErrorsFromProblem(resolved.fieldErrors)
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
      title={t('masterData.syncLaunchDrawer.title')}
      subtitle={t('masterData.syncLaunchDrawer.subtitle')}
      submitText={t('masterData.syncLaunchDrawer.submit')}
      confirmLoading={submitting}
      submitDisabled={submitting || clusterAllBlocked}
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
          label={t('masterData.syncLaunchDrawer.fields.mode')}
          name="mode"
          rules={[{ required: true, message: t('masterData.syncLaunchDrawer.validation.selectSyncMode') }]}
        >
          <Select
            data-testid="sync-launch-mode"
            options={launchModeOptions}
          />
        </Form.Item>

        <Form.Item
          label={t('masterData.syncLaunchDrawer.fields.targetMode')}
          name="target_mode"
          rules={[{ required: true, message: t('masterData.syncLaunchDrawer.validation.selectTargetMode') }]}
        >
          <Select
            data-testid="sync-launch-target-mode"
            options={launchTargetModeOptions}
          />
        </Form.Item>

        {launchTargetMode === 'cluster_all' ? (
          <>
            <Form.Item
              label={t('masterData.syncLaunchDrawer.fields.cluster')}
              name="cluster_id"
              rules={[{ required: true, message: t('masterData.syncLaunchDrawer.validation.selectCluster') }]}
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

            {clusterEligibilitySummary && watchedClusterId ? (
              <Alert
                type={clusterAllBlocked ? 'error' : 'info'}
                showIcon
                data-testid="sync-launch-cluster-all-summary"
                message={t('masterData.syncLaunchDrawer.clusterAll.summary', {
                  eligibleCount: clusterEligibilitySummary.eligibleCount,
                  excludedCount: clusterEligibilitySummary.excluded.length,
                  unconfiguredCount: clusterEligibilitySummary.unconfigured.length,
                })}
                description={(
                  <Space direction="vertical" size={4}>
                    <Typography.Text>
                      {t('masterData.syncLaunchDrawer.clusterAll.eligibleIncluded')}
                    </Typography.Text>
                    {clusterEligibilitySummary.excluded.length > 0 ? (
                      <Typography.Text>
                        {t('masterData.syncLaunchDrawer.clusterAll.excluded', {
                          databases: clusterEligibilitySummary.excluded.map((database) => database.name).join(', '),
                        })}
                      </Typography.Text>
                    ) : null}
                    {clusterEligibilitySummary.unconfigured.length > 0 ? (
                      <Typography.Text>
                        {t('masterData.syncLaunchDrawer.clusterAll.resolveEligibility', {
                          databases: clusterEligibilitySummary.unconfigured.map((database) => database.name).join(', '),
                        })}
                      </Typography.Text>
                    ) : null}
                    {clusterEligibilitySummary.excluded.length > 0 ? (
                      <Typography.Text>
                        {t('masterData.syncLaunchDrawer.clusterAll.useDatabaseSet')}
                      </Typography.Text>
                    ) : null}
                  </Space>
                )}
                action={clusterAllBlocked && onOpenEligibilityContext ? (
                  <Button
                    size="small"
                    onClick={() => {
                      onOpenEligibilityContext({
                        clusterId: watchedClusterId,
                        databaseId: clusterEligibilitySummary.unconfigured[0]?.id,
                      })
                    }}
                    data-testid="sync-launch-open-eligibility-handoff"
                  >
                    {t('masterData.syncLaunchDrawer.clusterAll.openDatabases')}
                  </Button>
                ) : undefined}
              />
            ) : null}
          </>
        ) : null}

        {launchTargetMode === 'database_set' ? (
          <Form.Item
            label={t('masterData.syncLaunchDrawer.fields.databases')}
            name="database_ids"
            rules={[{ required: true, message: t('masterData.syncLaunchDrawer.validation.selectAtLeastOneDatabase') }]}
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
          label={t('masterData.syncLaunchDrawer.fields.entityScope')}
          name="entity_scope"
          rules={[{ required: true, message: t('masterData.syncLaunchDrawer.validation.selectAtLeastOneEntityType') }]}
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
