import { useMemo } from 'react'
import { Button, Space, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { EyeOutlined } from '@ant-design/icons'

import type { Artifact, ArtifactKind } from '../../api/artifacts'
import { KIND_LABELS, renderAutoPurge } from './artifactsUtils'

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
  return useMemo<ColumnsType<Artifact>>(() => {
    const base: ColumnsType<Artifact> = [
      {
        title: 'Name',
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
        title: 'Kind',
        dataIndex: 'kind',
        key: 'kind',
        width: 160,
        render: (value: ArtifactKind) => KIND_LABELS[value] ?? value,
      },
      {
        title: 'Tags',
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
          title: 'Auto purge',
          dataIndex: 'purge_after',
          key: 'purge_after',
          width: 220,
          render: (_: unknown, record) => renderAutoPurge(record),
        },
      ] as ColumnsType<Artifact>) : []),
      {
        title: 'Created',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 200,
        render: (value: string) => (value ? new Date(value).toLocaleString() : ''),
      },
      {
        title: 'Actions',
        key: 'actions',
        width: catalogTab === 'deleted' ? 260 : 140,
        render: (_value, record) => (
          <Space>
            <Button icon={<EyeOutlined />} onClick={() => onOpenDetails(record)}>
              Details
            </Button>
            {catalogTab === 'deleted' ? (
              <>
                <Button disabled={!isStaff} onClick={() => onRestoreArtifact(record)}>
                  Restore
                </Button>
                <Button danger disabled={!isStaff} onClick={() => onOpenPurgeModal(record)}>
                  Delete permanently
                </Button>
              </>
            ) : (
              <Button danger disabled={!isStaff} onClick={() => onDeleteArtifact(record)}>
                Delete
              </Button>
            )}
          </Space>
        ),
      },
    ]

    return base
  }, [catalogTab, isStaff, onDeleteArtifact, onOpenDetails, onOpenPurgeModal, onRestoreArtifact])
}
