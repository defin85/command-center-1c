import { useMemo, useState, useEffect, useCallback, useRef } from 'react'
import {
  Alert,
  App,
  Button,
  Form,
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
  Input,
  Upload,
  Switch,
  Progress,
  Collapse,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { MenuProps } from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { DownloadOutlined, EyeOutlined, CheckOutlined, PlusOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'

import { useMe } from '../../api/queries'
import {
  useArtifacts,
  useArtifactVersions,
  useArtifactAliases,
  useUpsertArtifactAlias,
  useDeleteArtifact,
  useRestoreArtifact,
} from '../../api/queries'
import type { Artifact, ArtifactAlias, ArtifactVersion, ArtifactKind, UploadProgressInfo } from '../../api/artifacts'
import { createArtifact, downloadArtifactVersion, uploadArtifactVersion, upsertArtifactAlias } from '../../api/artifacts'
import { TableToolkit } from '../../components/table/TableToolkit'
import { useTableToolkit } from '../../components/table/hooks/useTableToolkit'
import { queryKeys } from '../../api/queries'

const { Text, Title } = Typography

const KIND_LABELS: Record<ArtifactKind, string> = {
  extension: 'Расширение конфигурации (.cfe)',
  config_xml: 'Выгрузка конфигурации XML (.xml)',
  dt_backup: 'Выгрузка ИБ (.dt)',
  epf: 'Внешняя обработка (.epf)',
  erf: 'Внешний отчет (.erf)',
  ibcmd_package: 'Пакет IBCMD (.zip)',
  ras_script: 'Скрипт RAS (.txt)',
  other: 'Другое',
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

const formatSpeed = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) return '-'
  return `${formatBytes(value)}/s`
}

const formatDuration = (seconds: number | null) => {
  if (!Number.isFinite(seconds) || seconds === null) return '-'
  const value = Math.max(0, Math.round(seconds))
  const mins = Math.floor(value / 60)
  const secs = value % 60
  if (mins === 0) return `${secs}s`
  return `${mins}m ${secs}s`
}

const stripExtension = (name: string) => name.replace(/\.[^/.]+$/, '')

const buildVersion = (fileName?: string) => {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const base = fileName ? stripExtension(fileName) : ''
  return base ? `${base}-${stamp}` : stamp
}

const buildMetadataTemplate = (payload: {
  name?: string
  kind?: ArtifactKind
  tags?: string[]
  version?: string
  filename?: string
}) => ({
  schema_version: '1',
  source: 'ui',
  labels: [],
  notes: '',
  artifact: {
    name: payload.name || '',
    kind: payload.kind || '',
    tags: payload.tags || [],
  },
  build: {
    version: payload.version || '',
    filename: payload.filename || '',
  },
  created_at: new Date().toISOString(),
})

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
  const { message, modal } = App.useApp()
  const queryClient = useQueryClient()
  const meQuery = useMe()
  const isStaff = Boolean(meQuery.data?.is_staff)
  const [catalogTab, setCatalogTab] = useState<'active' | 'deleted'>('active')
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [uploadStats, setUploadStats] = useState<{ percent: number; speed: number; eta: number | null } | null>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [aliasMode, setAliasMode] = useState<'none' | 'latest' | 'approved' | 'stable' | 'custom'>('none')
  const [customAliasValue, setCustomAliasValue] = useState('')
  const [form] = Form.useForm()
  const uploadStartRef = useRef<number | null>(null)
  const deleteArtifactMutation = useDeleteArtifact()
  const restoreArtifactMutation = useRestoreArtifact()

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

  const resetCreateForm = useCallback(() => {
    form.resetFields()
    setFileList([])
    setUploadStats(null)
    setAliasMode('none')
    setCustomAliasValue('')
    uploadStartRef.current = null
  }, [form])

  const updateUploadStats = useCallback((info: UploadProgressInfo) => {
    const now = Date.now()
    if (!uploadStartRef.current) {
      uploadStartRef.current = now
    }
    const elapsed = (now - uploadStartRef.current) / 1000
    const speed = elapsed > 0 ? info.loaded / elapsed : 0
    const eta = speed > 0 && info.total > info.loaded
      ? (info.total - info.loaded) / speed
      : null
    setUploadStats({ percent: info.percent, speed, eta })
  }, [])

  const maybeAutofillFromFile = useCallback((file?: File) => {
    if (!file) return
    const currentVersion = String(form.getFieldValue('version') || '').trim()
    const currentMetadata = String(form.getFieldValue('metadata') || '').trim()
    const currentName = String(form.getFieldValue('name') || '').trim()
    const currentKind = form.getFieldValue('kind') as ArtifactKind | undefined
    const currentTagsRaw = form.getFieldValue('tags')
    const currentTags = Array.isArray(currentTagsRaw)
      ? currentTagsRaw.map((tag) => String(tag))
      : []

    const nextVersion = currentVersion || buildVersion(file.name)
    const nextMetadata = (!currentMetadata || currentMetadata === '{\n  \n}')
      ? JSON.stringify(
        buildMetadataTemplate({
          name: currentName,
          kind: currentKind,
          tags: currentTags,
          version: nextVersion,
          filename: file.name,
        }),
        null,
        2
      )
      : currentMetadata

    form.setFieldsValue({
      version: nextVersion,
      metadata: nextMetadata,
    })
  }, [form])

  const handleGenerateDefaults = useCallback(() => {
    const file = fileList[0]?.originFileObj as File | undefined
    const currentName = String(form.getFieldValue('name') || '').trim()
    const currentKind = form.getFieldValue('kind') as ArtifactKind | undefined
    const currentTagsRaw = form.getFieldValue('tags')
    const currentTags = Array.isArray(currentTagsRaw)
      ? currentTagsRaw.map((tag) => String(tag))
      : []
    const nextVersion = buildVersion(file?.name)
    const nextMetadata = JSON.stringify(
      buildMetadataTemplate({
        name: currentName,
        kind: currentKind,
        tags: currentTags,
        version: nextVersion,
        filename: file?.name,
      }),
      null,
      2
    )
    form.setFieldsValue({
      version: nextVersion,
      metadata: nextMetadata,
    })
  }, [fileList, form])

  const handleCreateArtifact = useCallback(async () => {
    try {
      const values = await form.validateFields()
      const file = fileList[0]?.originFileObj as File | undefined
      if (!file) {
        message.error('Please select a file')
        return
      }
      let metadata = values.metadata.trim()
      if (!metadata) {
        message.error('Metadata is required')
        return
      }
      try {
        metadata = JSON.stringify(JSON.parse(metadata))
      } catch {
        message.error('Metadata must be valid JSON')
        return
      }

      setCreateLoading(true)
      setUploadStats(null)
      uploadStartRef.current = null

      const artifact = await createArtifact({
        name: values.name.trim(),
        kind: values.kind,
        is_versioned: values.is_versioned,
        tags: values.tags,
      })

      const version = String(values.version).trim()
      const uploadedVersion = await uploadArtifactVersion(artifact.id, {
        file,
        version,
        filename: values.filename?.trim() || file.name,
        metadata,
        onProgress: updateUploadStats,
      })

      const nextAlias = aliasMode === 'custom'
        ? customAliasValue.trim()
        : aliasMode === 'none'
          ? ''
          : aliasMode

      if (nextAlias) {
        await upsertArtifactAlias(artifact.id, {
          alias: nextAlias,
          version: uploadedVersion.version,
        })
      }

      await queryClient.invalidateQueries({ queryKey: queryKeys.artifacts.all })
      setCreateOpen(false)
      resetCreateForm()
      handleOpenDetails(artifact)
      message.success('Artifact created')
    } catch (error) {
      const err = error as { response?: { data?: { error?: { message?: string } | string } } } | null
      const backendMessage = typeof err?.response?.data?.error === 'string'
        ? err.response?.data?.error
        : err?.response?.data?.error?.message
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return
      }
      message.error(backendMessage || 'Failed to create artifact')
    } finally {
      setCreateLoading(false)
    }
  }, [
    aliasMode,
    customAliasValue,
    fileList,
    form,
    handleOpenDetails,
    queryClient,
    resetCreateForm,
    updateUploadStats,
  ])

  const handleDeleteArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Delete requires staff access')
      return
    }
    modal.confirm({
      title: `Delete artifact "${artifact.name}"?`,
      content: 'Artifact will be hidden from the catalog. Versions and aliases remain stored.',
      okText: 'Delete',
      okButtonProps: { danger: true, loading: deleteArtifactMutation.isPending },
      onOk: async () => {
        try {
          await deleteArtifactMutation.mutateAsync(artifact.id)
          message.success('Artifact deleted')
          if (selectedArtifact?.id === artifact.id) {
            setDetailsOpen(false)
            setSelectedArtifact(null)
          }
        } catch {
          message.error('Failed to delete artifact')
        }
      },
    })
  }, [deleteArtifactMutation, isStaff, message, modal, selectedArtifact?.id])

  const handleRestoreArtifact = useCallback((artifact: Artifact) => {
    if (!isStaff) {
      message.error('Restore requires staff access')
      return
    }
    modal.confirm({
      title: `Restore artifact "${artifact.name}"?`,
      content: 'Artifact will be returned to the active catalog.',
      okText: 'Restore',
      onOk: async () => {
        try {
          await restoreArtifactMutation.mutateAsync(artifact.id)
          message.success('Artifact restored')
          if (selectedArtifact?.id === artifact.id) {
            setDetailsOpen(false)
            setSelectedArtifact(null)
          }
        } catch {
          message.error('Failed to restore artifact')
        }
      },
    })
  }, [isStaff, message, modal, restoreArtifactMutation, selectedArtifact?.id])



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
        <Space>
          <Button
            icon={<EyeOutlined />}
            onClick={() => handleOpenDetails(record)}
          >
            Details
          </Button>
          {catalogTab === 'deleted' ? (
            <Button
              disabled={!isStaff}
              onClick={() => handleRestoreArtifact(record)}
            >
              Restore
            </Button>
          ) : (
            <Button
              danger
              disabled={!isStaff}
              onClick={() => handleDeleteArtifact(record)}
            >
              Delete
            </Button>
          )}
        </Space>
      ),
    },
  ], [catalogTab, handleDeleteArtifact, handleOpenDetails, handleRestoreArtifact, isStaff])

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
      include_deleted: catalogTab === 'deleted',
      only_deleted: catalogTab === 'deleted',
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
      const shouldReset = Boolean(
        compareBaseVersion
        || compareTargetVersion
        || compareDiff.length > 0
        || Object.keys(versionTextCache).length > 0
      )
      if (shouldReset) {
        setCompareBaseVersion(null)
        setCompareTargetVersion(null)
        setCompareDiff([])
        setVersionTextCache({})
      }
      return
    }
    if (!compareBaseVersion && versions.length > 0) {
      setCompareBaseVersion(versions[0].version)
    }
    if (!compareTargetVersion && versions.length > 1) {
      setCompareTargetVersion(versions[1].version)
    }
  }, [
    compareBaseVersion,
    compareDiff.length,
    compareTargetVersion,
    selectedArtifactId,
    versionTextCache,
    versions,
  ])

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
    } catch (_error) {
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
      modal.confirm({
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
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          disabled={!isStaff}
        >
          Add artifact
        </Button>
      </Space>

      <Tabs
        activeKey={catalogTab}
        onChange={(key) => setCatalogTab(key as 'active' | 'deleted')}
        items={[
          { key: 'active', label: 'Active' },
          { key: 'deleted', label: 'Deleted' },
        ]}
      />

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

      <Modal
        title="Add artifact"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false)
          resetCreateForm()
        }}
        width={720}
        okText="Create"
        onOk={handleCreateArtifact}
        okButtonProps={{ loading: createLoading, disabled: !isStaff }}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            is_versioned: true,
            kind: 'extension',
            tags: [],
          }}
        >
          <Form.Item
            label="Name"
            name="name"
            htmlFor="artifact-create-name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input
              id="artifact-create-name"
              placeholder="Artifact name"
              autoComplete="off"
            />
          </Form.Item>
          <Form.Item
            label="Kind"
            name="kind"
            htmlFor="artifact-create-kind"
            rules={[{ required: true, message: 'Kind is required' }]}
          >
            <Select
              id="artifact-create-kind"
              options={Object.entries(KIND_LABELS).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item
            label="Tags"
            name="tags"
            htmlFor="artifact-create-tags"
            rules={[{ required: true, type: 'array', min: 1, message: 'At least one tag is required' }]}
          >
            <Select id="artifact-create-tags" mode="tags" placeholder="Add tags" />
          </Form.Item>
          <Form.Item label="Version" htmlFor="artifact-create-version" required>
            <Space.Compact style={{ width: '100%' }}>
              <Form.Item
                name="version"
                noStyle
                rules={[{ required: true, message: 'Version is required' }]}
              >
                <Input
                  id="artifact-create-version"
                  placeholder="e.g. 1.0.0"
                  autoComplete="off"
                />
              </Form.Item>
              <Button icon={<ReloadOutlined />} onClick={handleGenerateDefaults}>
                Generate
              </Button>
            </Space.Compact>
          </Form.Item>
          <Form.Item label="File" htmlFor="artifact-create-file" required>
            <Upload.Dragger
              id="artifact-create-file"
              name="file"
              multiple={false}
              maxCount={1}
              beforeUpload={() => false}
              fileList={fileList}
              onChange={(info) => {
                setFileList(info.fileList)
                const file = info.fileList[0]?.originFileObj as File | undefined
                maybeAutofillFromFile(file)
              }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Drag & drop file here</p>
              <p className="ant-upload-hint">Or click to select a file</p>
            </Upload.Dragger>
          </Form.Item>
          {uploadStats && (
            <Form.Item label="Upload progress">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Progress percent={uploadStats.percent} />
                <Space size="large">
                  <Text type="secondary">Speed: {formatSpeed(uploadStats.speed)}</Text>
                  <Text type="secondary">ETA: {formatDuration(uploadStats.eta)}</Text>
                </Space>
              </Space>
            </Form.Item>
          )}
          <Form.Item label="Set alias (optional)" htmlFor="artifact-create-alias-mode">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Select
                id="artifact-create-alias-mode"
                value={aliasMode}
                onChange={(value) => setAliasMode(value)}
                options={[
                  { value: 'none', label: 'No alias' },
                  { value: 'latest', label: 'latest' },
                  { value: 'approved', label: 'approved' },
                  { value: 'stable', label: 'stable' },
                  { value: 'custom', label: 'custom' },
                ]}
              />
              {aliasMode === 'custom' && (
                <Input
                  id="artifact-create-alias-custom"
                  placeholder="Custom alias"
                  value={customAliasValue}
                  onChange={(event) => setCustomAliasValue(event.target.value)}
                  autoComplete="off"
                />
              )}
            </Space>
          </Form.Item>
          <Collapse
            items={[
              {
                key: 'advanced',
                label: 'Advanced',
                children: (
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Form.Item
                      label="Filename (optional)"
                      name="filename"
                      htmlFor="artifact-create-filename"
                    >
                      <Input
                        id="artifact-create-filename"
                        placeholder="Override filename for storage"
                        autoComplete="off"
                      />
                    </Form.Item>
                    <Form.Item
                      label="Metadata (JSON)"
                      name="metadata"
                      htmlFor="artifact-create-metadata"
                      rules={[{ required: true, message: 'Metadata is required' }]}
                      extra="Use JSON for build notes, labels, and future metadata."
                    >
                      <Input.TextArea
                        id="artifact-create-metadata"
                        rows={6}
                        autoComplete="off"
                      />
                    </Form.Item>
                    <Form.Item
                      label="Versioned"
                      name="is_versioned"
                      htmlFor="artifact-create-versioned"
                      valuePropName="checked"
                    >
                      <Switch id="artifact-create-versioned" />
                    </Form.Item>
                  </Space>
                ),
              },
            ]}
            defaultActiveKey={['advanced']}
          />
        </Form>
      </Modal>

      <Drawer
        title="Artifact details"
        width={860}
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        extra={selectedArtifact && (
          <Space>
            {catalogTab === 'deleted' ? (
              <Button
                disabled={!isStaff}
                onClick={() => handleRestoreArtifact(selectedArtifact)}
              >
                Restore
              </Button>
            ) : (
              <Button
                danger
                disabled={!isStaff}
                onClick={() => handleDeleteArtifact(selectedArtifact)}
              >
                Delete
              </Button>
            )}
          </Space>
        )}
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
