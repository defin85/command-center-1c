import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, App, Collapse, Descriptions, Form, Input, Progress, Space, Spin, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'

import type { Artifact, ArtifactPurgeBlocker, ArtifactPurgeJob, ArtifactPurgePlan } from '../../api/artifacts'
import { purgeArtifact as purgeArtifactApi } from '../../api/artifacts'
import { useArtifactPurgeJob, usePurgeArtifact } from '../../api/queries'
import { ModalSurfaceShell } from '../../components/platform'
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
        setPurgePreflightError(backendMessage || 'Failed to build purge plan')
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
      message.success('Artifact permanently deleted')
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
      setPurgeJobError(job.error_message || job.error_code || 'Purge failed')
    }
  }, [message, onClose, onDeleted, purgeJobId, purgeJobQuery.data, queryClient, reset, target?.id])

  const handleStartPurge = useCallback(async () => {
    if (!target) return
    setPurgeJobError(null)
    try {
      const response = await purgeArtifactMutation.mutateAsync({
        artifactId: target.id,
        payload: { reason: purgeReason, dry_run: false },
      })
      if (!response.job_id) {
        throw new Error('Missing job_id')
      }
      setPurgeJobId(response.job_id)
      setPurgePlan(response.plan)
      setPurgeBlockers(response.blockers)
      message.success('Purge started')
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      message.error(backendMessage || 'Failed to start purge')
    }
  }, [message, purgeArtifactMutation, purgeReason, target])

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
      title={purgeJobId ? 'Deleting permanently…' : `Delete permanently "${target?.name ?? ''}"?`}
      submitText={purgeJobId ? 'In progress' : 'Delete permanently'}
      cancelText={purgeJobId ? 'Close' : 'Cancel'}
      okButtonProps={{
        danger: true,
        disabled: okDisabled,
      }}
      confirmLoading={purgeArtifactMutation.isPending}
      width={720}
      forceRender
    >
      {!target ? (
        <Text type="secondary">Select an artifact.</Text>
      ) : (
        <Spin spinning={purgePreflightLoading} tip="Building purge plan…">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {purgePreflightError && (
              <Alert type="error" message={purgePreflightError} showIcon />
            )}

            {purgePlan && (
              <Descriptions size="small" column={2} bordered>
                <Descriptions.Item label="Versions">{purgePlan.versions_count}</Descriptions.Item>
                <Descriptions.Item label="Aliases">{purgePlan.aliases_count}</Descriptions.Item>
                <Descriptions.Item label="Objects">{purgePlan.storage_keys_total}</Descriptions.Item>
                <Descriptions.Item label="Total size">{formatBytes(purgePlan.total_bytes)}</Descriptions.Item>
              </Descriptions>
            )}

            {purgeBlockers.length > 0 && (
              <Alert
                type="warning"
                showIcon
                message="Purge is blocked"
                description={
                  <Collapse
                    items={[
                      {
                        key: 'blockers',
                        label: `Active usage (${purgeBlockers.length})`,
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
                  {purgeJobQuery.data.status}: {purgeJobQuery.data.deleted_objects}/{purgeJobQuery.data.total_objects} objects
                </Text>
              </>
            )}

            {!purgeJobId && (
              <>
                <Form layout="vertical">
                  <Form.Item label="Reason" required>
                    <Input.TextArea
                      value={purgeReason}
                      onChange={(event) => setPurgeReason(event.target.value)}
                      rows={3}
                      placeholder="Why are you deleting this artifact permanently?"
                    />
                  </Form.Item>
                  <Form.Item label={`Type "${target.name}" to confirm`} required>
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
                  message="This action cannot be undone"
                  description="All versions, aliases, and files in MinIO will be removed."
                />
              </>
            )}
          </Space>
        </Spin>
      )}
    </ModalSurfaceShell>
  )
}
