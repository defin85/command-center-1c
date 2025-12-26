import { useMemo, useState, useEffect, useCallback } from 'react'
import {
  Alert,
  Button,
  Drawer,
  Space,
  Tag,
  Typography,
  Descriptions,
  Tabs,
  Table,
  Select,
  Dropdown,
  Modal,
  Spin,
  message,
  Input,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { MenuProps } from 'antd'
import { DownloadOutlined, EyeOutlined, CheckOutlined } from '@ant-design/icons'

import { useMe } from '../../api/queries'
import {
  useArtifacts,
  useArtifactVersions,
  useArtifactAliases,
  useUpsertArtifactAlias,
} from '../../api/queries'
import type { Artifact, ArtifactAlias, ArtifactVersion, ArtifactKind } from '../../api/artifacts'
import { downloadArtifactVersion } from '../../api/artifacts'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'

const { Text, Title } = Typography

const KIND_LABELS: Record<ArtifactKind, string> = {
  extension: 'Extension',
  config_xml: 'Config XML',
  dt_backup: 'DT Backup',
  epf: 'EPF',
  erf: 'ERF',
  ibcmd_package: 'IBCMD Package',
  ras_script: 'RAS Script',
  other: 'Other',
}

const formatBytes = (value: number) => {
  if (!Number.isFinite(value)) return '-'
  if (value < 1024) return `${value} B`
  const kb = value / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  const gb = mb / 1024
  return `${gb.toFixed(1)} GB`
}

const aliasMenuItems: MenuProps['items'] = [
  { key: 'latest', label: 'Set alias: latest' },
  { key: 'approved', label: 'Set alias: approved' },
  { key: 'stable', label: 'Set alias: stable' },
]

const MAX_PREVIEW_BYTES = 1024 * 1024

type DiffLine = {
  type: 'equal' | 'insert' | 'delete'
  text: string
}

const diffLines = (before: string[], after: string[]): DiffLine[] => {
  const n = before.length
  const m = after.length
  const max = n + m
  let v = new Map<number, number>()
  v.set(1, 0)
  const trace: Array<Map<number, number>> = []

  const getV = (map: Map<number, number>, key: number) => map.get(key) ?? -1

  for (let d = 0; d <= max; d += 1) {
    const snapshot = new Map(v)
    for (let k = -d; k <= d; k += 2) {
      let x: number
      if (k === -d || (k !== d && getV(snapshot, k - 1) < getV(snapshot, k + 1))) {
        x = getV(snapshot, k + 1)
      } else {
        x = getV(snapshot, k - 1) + 1
      }
      let y = x - k
      while (x < n && y < m && before[x] === after[y]) {
        x += 1
        y += 1
      }
      snapshot.set(k, x)
      if (x >= n && y >= m) {
        trace.push(snapshot)
        d = max
        break
      }
    }
    trace.push(snapshot)
    v = snapshot
  }

  const result: DiffLine[] = []
  let x = n
  let y = m

  for (let d = trace.length - 1; d >= 0; d -= 1) {
    const snapshot = trace[d]
    const k = x - y
    let prevK: number
    if (k === -d || (k !== d && getV(snapshot, k - 1) < getV(snapshot, k + 1))) {
      prevK = k + 1
    } else {
      prevK = k - 1
    }
    const prevX = getV(snapshot, prevK)
    const prevY = prevX - prevK

    while (x > prevX && y > prevY) {
      result.push({ type: 'equal', text: before[x - 1] })
      x -= 1
      y -= 1
    }

    if (d === 0) {
      break
    }

    if (x === prevX) {
      result.push({ type: 'insert', text: after[y - 1] })
      y -= 1
    } else {
      result.push({ type: 'delete', text: before[x - 1] })
      x -= 1
    }
  }

  return result.reverse()
}

export const ArtifactsPage = () => {
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)

  const [detailsOpen, setDetailsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('versions')
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [customAlias, setCustomAlias] = useState('')
  const [compareBaseVersion, setCompareBaseVersion] = useState<string | null>(null)
  const [compareTargetVersion, setCompareTargetVersion] = useState<string | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [compareDiff, setCompareDiff] = useState<DiffLine[]>([])
  const [versionTextCache, setVersionTextCache] = useState<Record<string, string>>({})

  const handleOpenDetails = useCallback((artifact: Artifact) => {
    setSelectedArtifact(artifact)
    setDetailsOpen(true)
    setActiveTab('versions')
    setPreviewContent('')
    setPreviewError(null)
    setSelectedVersionId(null)
    setCustomAlias('')
    setCompareBaseVersion(null)
    setCompareTargetVersion(null)
    setCompareDiff([])
    setVersionTextCache({})
  }, [])

  const columns = useMemo<ColumnsType<Artifact>>(() => [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 260,
      render: (value: string, record) => (
        <Button type="link" onClick={() => handleOpenDetails(record)}>
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
      width: 140,
      render: (_, record) => (
        <Button
          icon={<EyeOutlined />}
          onClick={() => handleOpenDetails(record)}
        >
          Details
        </Button>
      ),
    },
  ], [handleOpenDetails])

  const fallbackColumnConfigs = useMemo(() => [
    { key: 'name', label: 'Name', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'kind', label: 'Kind', sortable: true, groupKey: 'core', groupLabel: 'Core' },
    { key: 'tags', label: 'Tags', groupKey: 'meta', groupLabel: 'Meta' },
    { key: 'created_at', label: 'Created', sortable: true, groupKey: 'time', groupLabel: 'Time' },
    { key: 'actions', label: 'Actions', groupKey: 'actions', groupLabel: 'Actions' },
  ], [])

  const table = useTableToolkit({
    tableId: 'artifacts',
    columns,
    fallbackColumns: fallbackColumnConfigs,
    initialPageSize: 50,
  })

  const tableFilters = table.filters
  const nameFilter = typeof tableFilters.name === 'string' ? tableFilters.name.trim() : ''
  const kindFilter = typeof tableFilters.kind === 'string' ? tableFilters.kind.trim() : ''
  const tagFilter = typeof tableFilters.tags === 'string' ? tableFilters.tags.trim() : ''
  const searchName = table.search.trim()

  const artifactsQuery = useArtifacts(
    {
      name: nameFilter || searchName || undefined,
      kind: kindFilter || undefined,
      tag: tagFilter.split(',')[0]?.trim() || undefined,
    },
    { enabled: isStaff }
  )

  const artifacts = artifactsQuery.data?.artifacts ?? []
  const totalArtifacts = artifactsQuery.data?.count ?? artifacts.length

  const selectedArtifactId = selectedArtifact?.id
  const versionsQuery = useArtifactVersions(selectedArtifactId)
  const aliasesQuery = useArtifactAliases(selectedArtifactId)
  const aliasMutation = useUpsertArtifactAlias(selectedArtifactId)

  const versions = versionsQuery.data?.versions ?? []
  const aliases = aliasesQuery.data?.aliases ?? []

  const selectedVersion = versions.find((version) => version.id === selectedVersionId) ?? null

  useEffect(() => {
    if (!selectedArtifactId) {
      setCompareBaseVersion(null)
      setCompareTargetVersion(null)
      setCompareDiff([])
      setVersionTextCache({})
      return
    }
    if (!compareBaseVersion && versions.length > 0) {
      setCompareBaseVersion(versions[0].version)
    }
    if (!compareTargetVersion && versions.length > 1) {
      setCompareTargetVersion(versions[1].version)
    }
  }, [compareBaseVersion, compareTargetVersion, selectedArtifactId, versions])

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
    let cancelled = false

    const loadPreview = async () => {
      if (activeTab !== 'preview' || !selectedArtifact || !selectedVersion) {
        return
      }
      const isXmlKind = selectedArtifact.kind === 'config_xml'
      const isXmlFile = selectedVersion.filename.toLowerCase().endsWith('.xml')
      if (!isXmlKind && !isXmlFile) {
        setPreviewContent('')
        setPreviewError('Preview available only for XML artifacts')
        return
      }

      setPreviewLoading(true)
      setPreviewError(null)
      try {
        const blob = await downloadArtifactVersion(selectedArtifact.id, selectedVersion.version)
        const slice = blob.size > MAX_PREVIEW_BYTES ? blob.slice(0, MAX_PREVIEW_BYTES) : blob
        const text = await slice.text()
        if (!cancelled) {
          setPreviewContent(text)
        }
      } catch (error) {
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
  }, [activeTab, selectedArtifact, selectedVersion])

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

      const isXmlKind = selectedArtifact?.kind === 'config_xml'
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
        const diff = diffLines(baseText.split('\n'), targetText.split('\n'))
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
    compareBaseVersion,
    compareTargetVersion,
    loadVersionText,
    selectedArtifact?.kind,
    selectedArtifactId,
    versions,
  ])

  const handleDownload = async (version: ArtifactVersion) => {
    if (!selectedArtifact) return
    try {
      const blob = await downloadArtifactVersion(selectedArtifact.id, version.version)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = version.filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      message.error('Failed to download artifact')
    }
  }

  const confirmAlias = (alias: string, version: ArtifactVersion) => {
    if (!isStaff) {
      message.error('Alias update requires staff access')
      return
    }
    const action = () => aliasMutation.mutate(
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
      Modal.confirm({
        title: `Set alias "${alias}"?`,
        content: `This will point ${alias} to ${version.version}.`,
        onOk: action,
      })
    } else {
      action()
    }
  }

  const handleCustomAlias = () => {
    if (!selectedVersion) return
    const alias = customAlias.trim()
    if (!alias) {
      message.warning('Введите alias')
      return
    }
    confirmAlias(alias, selectedVersion)
    setCustomAlias('')
  }

  const versionsColumns: ColumnsType<ArtifactVersion> = [
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
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => handleDownload(record)}
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
  ]

  const aliasColumns: ColumnsType<ArtifactAlias> = [
    { title: 'Alias', dataIndex: 'alias', key: 'alias', width: 160 },
    { title: 'Version', dataIndex: 'version', key: 'version', width: 160 },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 200,
      render: (value: string) => (value ? new Date(value).toLocaleString() : ''),
    },
  ]

  const selectedVersionRowKey = selectedVersionId ?? undefined
  const isPreviewAvailable = Boolean(selectedArtifact && selectedVersion)
  const compareVersionOptions = versions.map((version) => ({
    value: version.version,
    label: `${version.version} (${version.filename})`,
  }))

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Title level={2} style={{ margin: 0 }}>Artifacts</Title>
      </Space>

      {!isStaff && (
        <Alert
          type="warning"
          message="Доступ ограничен"
          description="Каталог артефактов доступен только сотрудникам."
          style={{ marginBottom: 16 }}
        />
      )}

      {artifactsQuery.error && (
        <Alert
          type="error"
          message="Не удалось загрузить артефакты"
          style={{ marginBottom: 16 }}
        />
      )}

      <TableToolkit
        table={table}
        data={artifacts}
        total={totalArtifacts}
        loading={artifactsQuery.isLoading}
        rowKey="id"
        columns={columns}
        tableLayout="fixed"
        scroll={{ x: table.totalColumnsWidth }}
        searchPlaceholder="Search artifacts"
      />

      <Drawer
        title="Artifact details"
        width={860}
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
      >
        {!selectedArtifact ? (
          <Text type="secondary">Select an artifact to view details.</Text>
        ) : (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="Name">{selectedArtifact.name}</Descriptions.Item>
              <Descriptions.Item label="Kind">{KIND_LABELS[selectedArtifact.kind]}</Descriptions.Item>
              <Descriptions.Item label="Versioned">{selectedArtifact.is_versioned ? 'Yes' : 'No'}</Descriptions.Item>
              <Descriptions.Item label="Created">
                {new Date(selectedArtifact.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="Tags" span={2}>
                {(selectedArtifact.tags ?? []).length === 0
                  ? <Text type="secondary">—</Text>
                  : selectedArtifact.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
              </Descriptions.Item>
            </Descriptions>

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
      </Drawer>
    </div>
  )
}
