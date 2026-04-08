import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Dropdown,
  Input,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { CheckOutlined, DownloadOutlined } from '@ant-design/icons'

import type { Artifact, ArtifactAlias, ArtifactVersion } from '../../api/artifacts'
import { downloadArtifactVersion } from '../../api/artifacts'
import { useArtifactAliases, useArtifactVersions, useUpsertArtifactAlias } from '../../api/queries'
import { DrawerSurfaceShell } from '../../components/platform'
import { confirmWithTracking } from '../../observability/confirmWithTracking'
import { trackUiAction } from '../../observability/uiActionJournal'
import { aliasMenuItems, diffLines, formatBytes, KIND_LABELS, MAX_PREVIEW_BYTES, renderAutoPurge, renderPurgeBlockers } from './artifactsUtils'

const { Text } = Typography

export type ArtifactDetailsDrawerProps = {
  open: boolean
  artifact: Artifact | null
  loading?: boolean
  error?: string | null
  catalogTab: 'active' | 'deleted'
  isStaff: boolean
  onClose: () => void
  onDeleteArtifact: (artifact: Artifact) => void
  onRestoreArtifact: (artifact: Artifact) => void
  onOpenPurgeModal: (artifact: Artifact) => void
}

export function ArtifactDetailsDrawer({
  open,
  artifact,
  loading = false,
  error = null,
  catalogTab,
  isStaff,
  onClose,
  onDeleteArtifact,
  onRestoreArtifact,
  onOpenPurgeModal,
}: ArtifactDetailsDrawerProps) {
  const { message, modal } = App.useApp()

  const [activeTab, setActiveTab] = useState('versions')
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [customAlias, setCustomAlias] = useState('')
  const [compareBaseVersion, setCompareBaseVersion] = useState<string | null>(null)
  const [compareTargetVersion, setCompareTargetVersion] = useState<string | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [compareDiff, setCompareDiff] = useState<ReturnType<typeof diffLines>>([])
  const [versionTextCache, setVersionTextCache] = useState<Record<string, string>>({})

  const selectedArtifactId = artifact?.id
  const versionsQuery = useArtifactVersions(selectedArtifactId)
  const aliasesQuery = useArtifactAliases(selectedArtifactId)
  const aliasMutation = useUpsertArtifactAlias(selectedArtifactId)

  const versions = useMemo(() => (
    versionsQuery.data?.versions ?? []
  ), [versionsQuery.data?.versions])
  const aliases = useMemo(() => (
    aliasesQuery.data?.aliases ?? []
  ), [aliasesQuery.data?.aliases])

  const selectedVersion = versions.find((version) => version.id === selectedVersionId) ?? null
  const selectedVersionRowKey = selectedVersionId ?? undefined

  useEffect(() => {
    if (!open) return
    setActiveTab('versions')
    setPreviewContent('')
    setPreviewError(null)
    setSelectedVersionId(null)
    setCustomAlias('')
    setCompareBaseVersion(null)
    setCompareTargetVersion(null)
    setCompareDiff([])
    setCompareError(null)
    setVersionTextCache({})
  }, [open, selectedArtifactId])

  useEffect(() => {
    if (!selectedArtifactId) {
      setSelectedVersionId(null)
      return
    }
    if (versions.length > 0 && !selectedVersionId) {
      setSelectedVersionId(versions[0].id)
    }
  }, [selectedArtifactId, versions, selectedVersionId])

  useEffect(() => {
    if (!selectedArtifactId) return
    if (!compareBaseVersion && versions.length > 0) {
      setCompareBaseVersion(versions[0].version)
    }
    if (!compareTargetVersion && versions.length > 1) {
      setCompareTargetVersion(versions[1].version)
    }
  }, [compareBaseVersion, compareTargetVersion, selectedArtifactId, versions])

  useEffect(() => {
    let cancelled = false

    const loadPreview = async () => {
      if (activeTab !== 'preview' || !artifact || !selectedVersion) {
        return
      }
      const isXmlKind = artifact.kind === 'config_xml'
      const isXmlFile = selectedVersion.filename.toLowerCase().endsWith('.xml')
      if (!isXmlKind && !isXmlFile) {
        setPreviewContent('')
        setPreviewError('Preview available only for XML artifacts')
        return
      }

      setPreviewLoading(true)
      setPreviewError(null)
      try {
        const blob = await downloadArtifactVersion(artifact.id, selectedVersion.version)
        const slice = blob.size > MAX_PREVIEW_BYTES ? blob.slice(0, MAX_PREVIEW_BYTES) : blob
        const text = await slice.text()
        if (!cancelled) {
          setPreviewContent(text)
        }
      } catch (_error) {
        if (!cancelled) {
          setPreviewError('Failed to load preview')
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false)
        }
      }
    }

    void loadPreview()

    return () => {
      cancelled = true
    }
  }, [activeTab, artifact, selectedVersion])

  const loadVersionText = useCallback(async (version: ArtifactVersion) => {
    if (versionTextCache[version.version]) {
      return versionTextCache[version.version]
    }
    const blob = await downloadArtifactVersion(selectedArtifactId as string, version.version)
    const slice = blob.size > MAX_PREVIEW_BYTES ? blob.slice(0, MAX_PREVIEW_BYTES) : blob
    const text = await slice.text()
    setVersionTextCache((prev) => ({ ...prev, [version.version]: text }))
    return text
  }, [selectedArtifactId, versionTextCache])

  useEffect(() => {
    let cancelled = false

    const loadCompare = async () => {
      if (activeTab !== 'compare' || !selectedArtifactId) return
      if (!compareBaseVersion || !compareTargetVersion) return
      if (compareBaseVersion === compareTargetVersion) {
        setCompareDiff([])
        setCompareError('Select two different versions to compare')
        return
      }
      const base = versions.find((item) => item.version === compareBaseVersion)
      const target = versions.find((item) => item.version === compareTargetVersion)
      if (!base || !target) return

      const isXmlKind = artifact?.kind === 'config_xml'
      const isXmlFile = base.filename.toLowerCase().endsWith('.xml')
        || target.filename.toLowerCase().endsWith('.xml')
      if (!isXmlKind && !isXmlFile) {
        setCompareDiff([])
        setCompareError('Diff available only for XML artifacts')
        return
      }

      setCompareLoading(true)
      setCompareError(null)
      try {
        const [baseText, targetText] = await Promise.all([
          loadVersionText(base),
          loadVersionText(target),
        ])
        if (cancelled) return
        const diff = diffLines(baseText.split('\\n'), targetText.split('\\n'))
        setCompareDiff(diff)
      } catch (_error) {
        if (!cancelled) {
          setCompareError('Failed to load diff')
        }
      } finally {
        if (!cancelled) {
          setCompareLoading(false)
        }
      }
    }

    void loadCompare()

    return () => {
      cancelled = true
    }
  }, [
    activeTab,
    artifact?.kind,
    compareBaseVersion,
    compareTargetVersion,
    loadVersionText,
    selectedArtifactId,
    versions,
  ])

  const handleDownload = useCallback(async (version: ArtifactVersion) => {
    if (!artifact) return
    try {
      const blob = await downloadArtifactVersion(artifact.id, version.version)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = version.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (_error) {
      message.error('Failed to download artifact')
    }
  }, [artifact, message])

  const confirmAlias = useCallback((alias: string, version: ArtifactVersion) => {
    if (!isStaff) {
      message.error('Alias update requires staff access')
      return
    }
    const actionMeta = {
      actionKind: 'operator.action',
      actionName: `Set artifact alias ${alias}`,
      context: {
        artifact_id: selectedArtifactId,
        alias,
        version: version.version,
      },
    } as const
    const applyAliasUpdate = () => aliasMutation.mutate(
      { alias, version: version.version },
      {
        onSuccess: () => {
          message.success(`Alias ${alias} updated`)
        },
        onError: () => {
          message.error('Failed to update alias')
        },
      }
    )

    if (alias === 'stable' || alias === 'approved') {
      confirmWithTracking(modal, {
        title: `Set alias "${alias}"?`,
        content: `This will point ${alias} to ${version.version}.`,
        onOk: applyAliasUpdate,
      }, actionMeta)
    } else {
      trackUiAction(actionMeta, applyAliasUpdate)
    }
  }, [aliasMutation, isStaff, message, modal, selectedArtifactId])

  const handleCustomAlias = useCallback(() => {
    if (!selectedVersion) return
    const alias = customAlias.trim()
    if (!alias) {
      message.warning('Введите alias')
      return
    }
    confirmAlias(alias, selectedVersion)
    setCustomAlias('')
  }, [confirmAlias, customAlias, message, selectedVersion])

  const versionsColumns: ColumnsType<ArtifactVersion> = useMemo(() => ([
    { title: 'Version', dataIndex: 'version', key: 'version', width: 120 },
    { title: 'Filename', dataIndex: 'filename', key: 'filename', width: 240 },
    {
      title: 'Size',
      dataIndex: 'size',
      key: 'size',
      width: 120,
      render: (value: number) => formatBytes(value),
    },
    {
      title: 'Checksum',
      dataIndex: 'checksum',
      key: 'checksum',
      width: 220,
      render: (value: string) => (
        <Text code style={{ fontSize: 12 }}>{value}</Text>
      ),
    },
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
      width: 180,
      render: (_value, record) => (
        <Space>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => void handleDownload(record)}
          >
            Download
          </Button>
          <Dropdown
            menu={{
              items: aliasMenuItems,
              onClick: (info) => confirmAlias(info.key, record),
            }}
            disabled={!isStaff || aliasMutation.isPending}
          >
            <Button size="small" icon={<CheckOutlined />}>
              Set alias
            </Button>
          </Dropdown>
        </Space>
      ),
    },
  ]), [aliasMutation.isPending, confirmAlias, handleDownload, isStaff])

  const aliasColumns: ColumnsType<ArtifactAlias> = useMemo(() => ([
    { title: 'Alias', dataIndex: 'alias', key: 'alias', width: 160 },
    { title: 'Version', dataIndex: 'version', key: 'version', width: 160 },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 200,
      render: (value: string) => (value ? new Date(value).toLocaleString() : ''),
    },
  ]), [])

  const isPreviewAvailable = Boolean(artifact && selectedVersion)
  const compareVersionOptions = useMemo(() => (
    versions.map((version) => ({
      value: version.version,
      label: `${version.version} (${version.filename})`,
    }))
  ), [versions])

  return (
    <DrawerSurfaceShell
      open={open}
      onClose={onClose}
      title="Artifact details"
      width={860}
      extra={artifact && (
        <Space>
          {catalogTab === 'deleted' ? (
            <>
              <Button disabled={!isStaff} onClick={() => onRestoreArtifact(artifact)}>
                Restore
              </Button>
              <Button danger disabled={!isStaff} onClick={() => onOpenPurgeModal(artifact)}>
                Delete permanently
              </Button>
            </>
          ) : (
            <Button danger disabled={!isStaff} onClick={() => onDeleteArtifact(artifact)}>
              Delete
            </Button>
          )}
        </Space>
      )}
    >
      {error ? (
        <Alert type="error" message={error} showIcon />
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      ) : !artifact ? (
        <Text type="secondary">Select an artifact to view details.</Text>
      ) : (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="Name">{artifact.name}</Descriptions.Item>
            <Descriptions.Item label="Kind">{KIND_LABELS[artifact.kind]}</Descriptions.Item>
            <Descriptions.Item label="Versioned">{artifact.is_versioned ? 'Yes' : 'No'}</Descriptions.Item>
            <Descriptions.Item label="Created">
              {new Date(artifact.created_at).toLocaleString()}
            </Descriptions.Item>
            {artifact.is_deleted && (
              <>
                <Descriptions.Item label="Deleted">
                  {artifact.deleted_at ? new Date(artifact.deleted_at).toLocaleString() : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Auto purge">
                  {renderAutoPurge(artifact)}
                </Descriptions.Item>
              </>
            )}
            <Descriptions.Item label="Tags" span={2}>
              {(artifact.tags ?? []).length === 0
                ? <Text type="secondary">—</Text>
                : artifact.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
            </Descriptions.Item>
          </Descriptions>

          {artifact.is_deleted && artifact.purge_state === 'blocked' && (
            <Alert
              type="warning"
              showIcon
              message="Auto purge blocked"
              description={renderPurgeBlockers(artifact.purge_blockers)}
            />
          )}

          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: 'versions',
                label: `Versions (${versions.length})`,
                children: (
                  <Table
                    size="small"
                    rowKey="id"
                    dataSource={versions}
                    columns={versionsColumns}
                    loading={versionsQuery.isLoading}
                    pagination={false}
                    onRow={(record) => ({
                      onClick: () => setSelectedVersionId(record.id),
                    })}
                    rowClassName={(record) =>
                      record.id === selectedVersionRowKey ? 'ant-table-row-selected' : ''
                    }
                    scroll={{ x: 1000 }}
                  />
                ),
              },
              {
                key: 'aliases',
                label: `Aliases (${aliases.length})`,
                children: (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Space>
                      <Input
                        placeholder="Custom alias"
                        value={customAlias}
                        onChange={(event) => setCustomAlias(event.target.value)}
                        disabled={!isStaff}
                      />
                      <Button
                        type="primary"
                        onClick={handleCustomAlias}
                        disabled={!isStaff || aliasMutation.isPending || !selectedVersion}
                      >
                        Apply alias
                      </Button>
                    </Space>
                    <Table
                      size="small"
                      rowKey="id"
                      dataSource={aliases}
                      columns={aliasColumns}
                      loading={aliasesQuery.isLoading}
                      pagination={false}
                    />
                  </Space>
                ),
              },
              {
                key: 'preview',
                label: 'Preview XML',
                children: (
                  <div>
                    {!isPreviewAvailable && (
                      <Text type="secondary">Select a version to preview.</Text>
                    )}
                    {previewError && <Alert type="warning" message={previewError} />}
                    {previewLoading && <Spin />}
                    {!previewLoading && previewContent && (
                      <>
                        <pre
                          style={{
                            maxHeight: 480,
                            overflow: 'auto',
                            background: '#f7f7f7',
                            border: '1px solid #eee',
                            padding: 12,
                            whiteSpace: 'pre',
                            fontSize: 12,
                          }}
                        >
                          {previewContent}
                        </pre>
                        {previewContent.length >= MAX_PREVIEW_BYTES && (
                          <Text type="secondary">Preview truncated.</Text>
                        )}
                      </>
                    )}
                  </div>
                ),
              },
              {
                key: 'compare',
                label: 'Compare',
                children: (
                  <div>
                    {versions.length < 2 && (
                      <Text type="secondary">Need at least two versions to compare.</Text>
                    )}
                    {versions.length >= 2 && (
                      <Space direction="vertical" style={{ width: '100%' }} size="middle">
                        <Space wrap>
                          <Select
                            value={compareBaseVersion ?? undefined}
                            placeholder="Base version"
                            options={compareVersionOptions}
                            onChange={(value) => setCompareBaseVersion(value)}
                            style={{ minWidth: 200 }}
                          />
                          <Select
                            value={compareTargetVersion ?? undefined}
                            placeholder="Compare version"
                            options={compareVersionOptions}
                            onChange={(value) => setCompareTargetVersion(value)}
                            style={{ minWidth: 200 }}
                          />
                        </Space>
                        {compareError && <Alert type="warning" message={compareError} />}
                        {compareLoading && <Spin />}
                        {!compareLoading && compareDiff.length > 0 && (
                          <div
                            style={{
                              maxHeight: 480,
                              overflow: 'auto',
                              background: '#f7f7f7',
                              border: '1px solid #eee',
                              padding: 12,
                              fontFamily: 'monospace',
                              fontSize: 12,
                              whiteSpace: 'pre',
                            }}
                          >
                            {compareDiff.map((line, index) => {
                              const prefix = line.type === 'insert'
                                ? '+'
                                : line.type === 'delete'
                                  ? '-'
                                  : ' '
                              const background = line.type === 'insert'
                                ? '#e6ffed'
                                : line.type === 'delete'
                                  ? '#ffecec'
                                  : 'transparent'
                              return (
                                <div
                                  key={`${line.type}-${index}`}
                                  style={{ background, paddingLeft: 4 }}
                                >
                                  {prefix}{line.text}
                                </div>
                              )
                            })}
                          </div>
                        )}
                        {compareDiff.length === 0 && !compareLoading && !compareError && (
                          <Text type="secondary">No differences detected.</Text>
                        )}
                      </Space>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </Space>
      )}
    </DrawerSurfaceShell>
  )
}
