import { useCallback, useRef, useState } from 'react'
import {
  App,
  Button,
  Collapse,
  Form,
  Input,
  Modal,
  Progress,
  Select,
  Space,
  Switch,
  Upload,
  Typography,
} from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'

import type { Artifact, ArtifactKind, UploadProgressInfo } from '../../api/artifacts'
import { createArtifact, uploadArtifactVersion, upsertArtifactAlias } from '../../api/artifacts'
import { LazyJsonCodeEditorFormField } from '../../components/code/LazyJsonCodeEditor'
import { queryKeys } from '../../api/queries'
import { buildMetadataTemplate, buildVersion, formatDuration, formatSpeed, KIND_LABELS } from './artifactsUtils'

const { Text } = Typography

export type ArtifactsCreateModalProps = {
  open: boolean
  isStaff: boolean
  onClose: () => void
  onCreated: (artifact: Artifact) => void
}

export function ArtifactsCreateModal({ open, isStaff, onClose, onCreated }: ArtifactsCreateModalProps) {
  const { message } = App.useApp()
  const queryClient = useQueryClient()

  const [createLoading, setCreateLoading] = useState(false)
  const [uploadStats, setUploadStats] = useState<{ percent: number; speed: number; eta: number | null } | null>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [aliasMode, setAliasMode] = useState<'none' | 'latest' | 'approved' | 'stable' | 'custom'>('none')
  const [customAliasValue, setCustomAliasValue] = useState('')
  const [form] = Form.useForm()
  const uploadStartRef = useRef<number | null>(null)

  const resetForm = useCallback(() => {
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
    const nextMetadata = (!currentMetadata || currentMetadata === '{\\n  \\n}')
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
      message.success('Artifact created')
      onClose()
      resetForm()
      onCreated(artifact)
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
    message,
    onClose,
    onCreated,
    queryClient,
    resetForm,
    updateUploadStats,
  ])

  return (
    <Modal
      title="Add artifact"
      open={open}
      onCancel={() => {
        onClose()
        resetForm()
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
                    <LazyJsonCodeEditorFormField
                      id="artifact-create-metadata"
                      height={220}
                      path="artifact-create-metadata.json"
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
  )
}

