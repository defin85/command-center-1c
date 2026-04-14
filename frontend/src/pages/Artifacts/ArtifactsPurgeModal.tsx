import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App, Collapse, Descriptions, Form, Input, Progress, Space, Spin, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'

import type { Artifact, ArtifactPurgeBlocker, ArtifactPurgeJob, ArtifactPurgePlan } from '../../api/artifacts'
import { purgeArtifact as purgeArtifactApi } from '../../api/artifacts'
import { useArtifactPurgeJob, usePurgeArtifact } from '../../api/queries'
import { ModalSurfaceShell } from '../../components/platform'
import { useArtifactsTranslation } from '../../i18n'
import { queryKeys } from '../../api/queries'
import { formatBytes } from './artifactsUtils'

const { Text } = Typography

export type ArtifactsPurgeModalProps = {
  open: boolean
  target: Artifact | null
  onClose: () => void
  onDeleted: (artifactId: string) => void
}

export function ArtifactsPurgeModal({ open, target, onClose, onDeleted }: ArtifactsPurgeModalProps) {
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const purgeArtifactMutation = usePurgeArtifact()
  const { t } = useArtifactsTranslation()

  const [purgePlan, setPurgePlan] = useState<ArtifactPurgePlan | null>(null)
  const [purgeBlockers, setPurgeBlockers] = useState<ArtifactPurgeBlocker[]>([])
  const [purgePreflightLoading, setPurgePreflightLoading] = useState(false)
  const [purgePreflightError, setPurgePreflightError] = useState<string | null>(null)
  const [purgeReason, setPurgeReason] = useState('')
  const [purgeConfirmName, setPurgeConfirmName] = useState('')
  const [purgeJobId, setPurgeJobId] = useState<string | null>(null)
  const [purgeJobError, setPurgeJobError] = useState<string | null>(null)

  const purgeJobQuery = useArtifactPurgeJob(purgeJobId ?? undefined, {
    enabled: Boolean(purgeJobId),
    refetchInterval: purgeJobId ? 1000 : undefined,
  })

  const reset = useCallback(() => {
    setPurgePlan(null)
    setPurgeBlockers([])
    setPurgePreflightLoading(false)
    setPurgePreflightError(null)
    setPurgeReason('')
    setPurgeConfirmName('')
    setPurgeJobId(null)
    setPurgeJobError(null)
  }, [])

  useEffect(() => {
    if (!open) {
      reset()
      return
    }
    reset()
  }, [open, reset, target?.id])

  useEffect(() => {
    if (!open || !target) return
    let cancelled = false
    setPurgePreflightLoading(true)
    setPurgePreflightError(null)
    purgeArtifactApi(target.id, { dry_run: true })
      .then((response) => {
        if (cancelled) return
        setPurgePlan(response.plan)
        setPurgeBlockers(response.blockers)
      })
      .catch((error) => {
        if (cancelled) return
        const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
        const backendMessage = typeof err?.response?.data?.error === 'string'
          ? err.response?.data?.error
          : err?.response?.data?.error?.message
        setPurgePreflightError(backendMessage || t(($) => $.purge.buildPlanFailed))
      })
      .finally(() => {
        if (cancelled) return
        setPurgePreflightLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, target])

  useEffect(() => {
    if (!purgeJobId) return
    const job = purgeJobQuery.data as ArtifactPurgeJob | undefined
    if (!job) return

    if (job.status === 'success') {
      message.success(t(($) => $.purge.deleteSuccess))
      const id = target?.id
      onClose()
      reset()
      queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
      if (id) {
        onDeleted(id)
      }
      return
    }

    if (job.status === 'failed') {
      setPurgeJobError(job.error_message || job.error_code || t(($) => $.purge.deleteFailed))
    }
  }, [message, onClose, onDeleted, purgeJobId, purgeJobQuery.data, queryClient, reset, t, target?.id])

  const handleStartPurge = useCallback(async () => {
    if (!target) return
    setPurgeJobError(null)
    try {
      const response = await purgeArtifactMutation.mutateAsync({
        artifactId: target.id,
        payload: { reason: purgeReason, dry_run: false },
      })
      if (!response.job_id) {
        throw new Error(t(($) => $.purge.missingJobId))
      }
      setPurgeJobId(response.job_id)
      setPurgePlan(response.plan)
      setPurgeBlockers(response.blockers)
      message.success(t(($) => $.purge.started))
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      message.error(backendMessage || t(($) => $.purge.startFailed))
    }
  }, [message, purgeArtifactMutation, purgeReason, t, target])

  const okDisabled = useMemo(() => (
    Boolean(purgeJobId)
    || !target
    || purgePreflightLoading
    || Boolean(purgePreflightError)
    || purgeBlockers.length > 0
    || purgeReason.trim().length === 0
    || purgeConfirmName.trim() !== target?.name
  ), [purgeBlockers.length, purgeConfirmName, purgeJobId, purgePreflightError, purgePreflightLoading, purgeReason, target])

  return (
    <ModalSurfaceShell
      open={open}
      onClose={onClose}
      onSubmit={() => { void handleStartPurge() }}
      title={purgeJobId
        ? t(($) => $.purge.titleInProgress)
        : t(($) => $.purge.titleConfirm, { name: target?.name ?? '' })}
      submitText={purgeJobId ? t(($) => $.purge.submitInProgress) : t(($) => $.purge.submitDelete)}
      cancelText={purgeJobId ? t(($) => $.purge.cancelInProgress) : t(($) => $.purge.cancel)}
      okButtonProps={{
        danger: true,
        disabled: okDisabled,
      }}
      confirmLoading={purgeArtifactMutation.isPending}
      width={720}
      forceRender
    >
      {!target ? (
        <Text type="secondary">{t(($) => $.purge.empty)}</Text>
      ) : (
        <Spin spinning={purgePreflightLoading} tip={t(($) => $.purge.buildingPlan)}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {purgePreflightError && (
              <Alert type="error" message={purgePreflightError} showIcon />
            )}

            {purgePlan && (
              <Descriptions size="small" column={2} bordered>
                <Descriptions.Item label={t(($) => $.purge.plan.versions)}>{purgePlan.versions_count}</Descriptions.Item>
                <Descriptions.Item label={t(($) => $.purge.plan.aliases)}>{purgePlan.aliases_count}</Descriptions.Item>
                <Descriptions.Item label={t(($) => $.purge.plan.objects)}>{purgePlan.storage_keys_total}</Descriptions.Item>
                <Descriptions.Item label={t(($) => $.purge.plan.totalSize)}>{formatBytes(purgePlan.total_bytes)}</Descriptions.Item>
              </Descriptions>
            )}

            {purgeBlockers.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message={t(($) => $.purge.blockedTitle)}
                description={
                  <Collapse
                    items={[
                      {
                        key: 'blockers',
                        label: t(($) => $.purge.blockedUsage, { count: purgeBlockers.length }),
                        children: (
                          <Space direction="vertical" size="small" style={{ width: '100%' }}>
                            {purgeBlockers.map((blocker) => (
                              <Text key={`${blocker.type}:${blocker.id}`}>
                                {blocker.type} {blocker.id} ({blocker.status}) {blocker.name ?? ''}
                              </Text>
                            ))}
                          </Space>
                        ),
                      },
                    ]}
                  />
                }
              />
            )}

            {purgeJobError && (
              <Alert type="error" showIcon message={purgeJobError} />
            )}

            {purgeJobId && purgeJobQuery.data && (
              <>
                <Progress
                  percent={purgeJobQuery.data.total_objects > 0
                    ? Math.min(100, Math.round((purgeJobQuery.data.deleted_objects / purgeJobQuery.data.total_objects) * 100))
                    : 0}
                  status={purgeJobQuery.data.status === 'failed' ? 'exception' : undefined}
                />
                <Text type="secondary">
                  {t(($) => $.purge.progress, {
                    status: purgeJobQuery.data.status,
                    deleted: String(purgeJobQuery.data.deleted_objects),
                    total: String(purgeJobQuery.data.total_objects),
                  })}
                </Text>
              </>
            )}

            {!purgeJobId && (
              <>
                <Form layout="vertical">
                  <Form.Item label={t(($) => $.purge.reason)} required>
                    <Input.TextArea
                      value={purgeReason}
                      onChange={(event) => setPurgeReason(event.target.value)}
                      rows={3}
                      placeholder={t(($) => $.purge.reasonPlaceholder)}
                    />
                  </Form.Item>
                  <Form.Item label={t(($) => $.purge.confirmName, { name: target.name })} required>
                    <Input
                      value={purgeConfirmName}
                      onChange={(event) => setPurgeConfirmName(event.target.value)}
                      placeholder={target.name}
                      autoComplete="off"
                    />
                  </Form.Item>
                </Form>
                <Alert
                  type="warning"
                  showIcon
                  message={t(($) => $.purge.irreversibleTitle)}
                  description={t(($) => $.purge.irreversibleDescription)}
                />
              </>
            )}
          </Space>
        </Spin>
      )}
    </ModalSurfaceShell>
  )
}
