import { useMemo } from 'react'
import { Button, Space, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { EyeOutlined } from '@ant-design/icons'

import type { Artifact, ArtifactKind } from '../../api/artifacts'
import { useArtifactsTranslation, useCommonTranslation, useLocaleFormatters } from '../../i18n'
import { getArtifactKindLabel, renderAutoPurge, type ArtifactKindLabels } from './artifactsUtils'

const { Text } = Typography

export type UseArtifactsColumnsParams = {
  catalogTab: 'active' | 'deleted'
  isStaff: boolean
  onOpenDetails: (artifact: Artifact) => void
  onDeleteArtifact: (artifact: Artifact) => void
  onRestoreArtifact: (artifact: Artifact) => void
  onOpenPurgeModal: (artifact: Artifact) => void
}

export const useArtifactsColumns = ({
  catalogTab,
  isStaff,
  onOpenDetails,
  onDeleteArtifact,
  onRestoreArtifact,
  onOpenPurgeModal,
}: UseArtifactsColumnsParams) => {
  const { t } = useArtifactsTranslation()
  const { t: tCommon } = useCommonTranslation()
  const formatters = useLocaleFormatters()
  const unavailableShort = tCommon(($) => $.values.unavailableShort)
  const kindLabels = useMemo<ArtifactKindLabels>(() => ({
    extension: t(($) => $.kinds.extension),
    config_cf: t(($) => $.kinds.configCf),
    config_xml: t(($) => $.kinds.configXml),
    dt_backup: t(($) => $.kinds.dtBackup),
    epf: t(($) => $.kinds.epf),
    erf: t(($) => $.kinds.erf),
    ibcmd_package: t(($) => $.kinds.ibcmdPackage),
    ras_script: t(($) => $.kinds.rasScript),
    other: t(($) => $.kinds.other),
  }), [t])

  return useMemo<ColumnsType<Artifact>>(() => {
    const base: ColumnsType<Artifact> = [
      {
        title: t(($) => $.table.name),
        dataIndex: 'name',
        key: 'name',
        width: 260,
        render: (value: string, record) => (
          <Button type="link" onClick={() => onOpenDetails(record)}>
            {value}
          </Button>
        ),
      },
      {
        title: t(($) => $.table.kind),
        dataIndex: 'kind',
        key: 'kind',
        width: 160,
        render: (value: ArtifactKind) => getArtifactKindLabel(value, kindLabels),
      },
      {
        title: t(($) => $.table.tags),
        dataIndex: 'tags',
        key: 'tags',
        width: 240,
        render: (tags: string[]) => (
          <Space wrap size={4}>
            {(tags ?? []).length === 0
              ? <Text type="secondary">—</Text>
              : tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
          </Space>
        ),
      },
      ...(catalogTab === 'deleted' ? ([
        {
          title: t(($) => $.table.autoPurge),
          dataIndex: 'purge_after',
          key: 'purge_after',
          width: 220,
          render: (_: unknown, record) => renderAutoPurge(record, formatters.dateTime, {
            unavailable: unavailableShort,
            blocked: t(($) => $.helpers.blocked),
            blockersCount: (count) => t(($) => $.helpers.blockersCount, { count }),
            retryAfter: (value) => t(($) => $.helpers.retryAfter, { value }),
            operation: t(($) => $.helpers.operation),
            workflow: t(($) => $.helpers.workflow),
            more: (count) => t(($) => $.helpers.more, { count }),
            inDays: (count) => t(($) => $.helpers.inDays, { count }),
            overdue: t(($) => $.helpers.overdue),
          }),
        },
      ] as ColumnsType<Artifact>) : []),
      {
        title: t(($) => $.table.created),
        dataIndex: 'created_at',
        key: 'created_at',
        width: 200,
        render: (value: string) => formatters.dateTime(value, { fallback: unavailableShort }),
      },
      {
        title: t(($) => $.table.actions),
        key: 'actions',
        width: catalogTab === 'deleted' ? 260 : 140,
        render: (_value, record) => (
          <Space>
            <Button icon={<EyeOutlined />} onClick={() => onOpenDetails(record)}>
              {t(($) => $.table.details)}
            </Button>
            {catalogTab === 'deleted' ? (
              <>
                <Button disabled={!isStaff} onClick={() => onRestoreArtifact(record)}>
                  {t(($) => $.table.restore)}
                </Button>
                <Button danger disabled={!isStaff} onClick={() => onOpenPurgeModal(record)}>
                  {t(($) => $.table.deletePermanently)}
                </Button>
              </>
            ) : (
              <Button danger disabled={!isStaff} onClick={() => onDeleteArtifact(record)}>
                {t(($) => $.table.delete)}
              </Button>
            )}
          </Space>
        ),
      },
    ]

    return base
  }, [
    catalogTab,
    formatters,
    isStaff,
    kindLabels,
    onDeleteArtifact,
    onOpenDetails,
    onOpenPurgeModal,
    onRestoreArtifact,
    t,
    unavailableShort,
  ])
}
