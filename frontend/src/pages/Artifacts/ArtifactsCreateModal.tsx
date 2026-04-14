import { useCallback, useMemo, useRef, useState } from 'react'
import {
  App,
  Button,
  Collapse,
  Form,
  Input,
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
import { ModalSurfaceShell } from '../../components/platform'
import { queryKeys } from '../../api/queries'
import { useArtifactsTranslation } from '../../i18n'
import { buildMetadataTemplate, buildVersion, formatDuration, formatSpeed, type ArtifactKindLabels } from './artifactsUtils'

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
  const { t } = useArtifactsTranslation()

  const [createLoading, setCreateLoading] = useState(false)
  const [uploadStats, setUploadStats] = useState<{ percent: number; speed: number; eta: number | null } | null>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [aliasMode, setAliasMode] = useState<'none' | 'latest' | 'approved' | 'stable' | 'custom'>('none')
  const [customAliasValue, setCustomAliasValue] = useState('')
  const [form] = Form.useForm()
  const uploadStartRef = useRef<number | null>(null)
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
        message.error(t(($) => $.create.fileRequired))
        return
      }
      let metadata = values.metadata.trim()
      if (!metadata) {
        message.error(t(($) => $.create.metadataRequired))
        return
      }
      try {
        metadata = JSON.stringify(JSON.parse(metadata))
      } catch {
        message.error(t(($) => $.create.metadataInvalid))
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
      message.success(t(($) => $.create.success))
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
      message.error(backendMessage || t(($) => $.create.failed))
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
    <ModalSurfaceShell
      open={open}
      onClose={() => {
        onClose()
        resetForm()
      }}
      title={t(($) => $.create.title)}
      width={720}
      submitText={t(($) => $.create.submit)}
      onSubmit={() => { void handleCreateArtifact() }}
      confirmLoading={createLoading}
      okButtonProps={{ disabled: !isStaff }}
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
          label={t(($) => $.create.name)}
          name="name"
          htmlFor="artifact-create-name"
          rules={[{ required: true, message: t(($) => $.create.nameRequired) }]}
        >
          <Input
            id="artifact-create-name"
            placeholder={t(($) => $.create.namePlaceholder)}
            autoComplete="off"
          />
        </Form.Item>
        <Form.Item
          label={t(($) => $.create.kind)}
          name="kind"
          htmlFor="artifact-create-kind"
          rules={[{ required: true, message: t(($) => $.create.kindRequired) }]}
        >
          <Select
            id="artifact-create-kind"
            options={Object.entries(kindLabels).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Form.Item>
        <Form.Item
          label={t(($) => $.create.tags)}
          name="tags"
          htmlFor="artifact-create-tags"
          rules={[{ required: true, type: 'array', min: 1, message: t(($) => $.create.tagsRequired) }]}
        >
          <Select id="artifact-create-tags" mode="tags" placeholder={t(($) => $.create.tagsPlaceholder)} />
        </Form.Item>
        <Form.Item label={t(($) => $.create.version)} htmlFor="artifact-create-version" required>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              name="version"
              noStyle
              rules={[{ required: true, message: t(($) => $.create.versionRequired) }]}
            >
              <Input
                id="artifact-create-version"
                placeholder={t(($) => $.create.versionPlaceholder)}
                autoComplete="off"
              />
            </Form.Item>
            <Button icon={<ReloadOutlined />} onClick={handleGenerateDefaults}>
              {t(($) => $.create.generate)}
            </Button>
          </Space.Compact>
        </Form.Item>
        <Form.Item label={t(($) => $.create.file)} htmlFor="artifact-create-file" required>
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
            <p className="ant-upload-text">{t(($) => $.create.fileDropText)}</p>
            <p className="ant-upload-hint">{t(($) => $.create.fileDropHint)}</p>
          </Upload.Dragger>
        </Form.Item>
        {uploadStats && (
          <Form.Item label={t(($) => $.create.uploadProgress)}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Progress percent={uploadStats.percent} />
              <Space size="large">
                <Text type="secondary">
                  {t(($) => $.create.speed, { value: formatSpeed(uploadStats.speed) })}
                </Text>
                <Text type="secondary">
                  {t(($) => $.create.eta, { value: formatDuration(uploadStats.eta) })}
                </Text>
              </Space>
            </Space>
          </Form.Item>
        )}
        <Form.Item label={t(($) => $.create.alias)} htmlFor="artifact-create-alias-mode">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Select
              id="artifact-create-alias-mode"
              value={aliasMode}
              onChange={(value) => setAliasMode(value)}
              options={[
                { value: 'none', label: t(($) => $.create.aliasOptions.none) },
                { value: 'latest', label: t(($) => $.create.aliasOptions.latest) },
                { value: 'approved', label: t(($) => $.create.aliasOptions.approved) },
                { value: 'stable', label: t(($) => $.create.aliasOptions.stable) },
                { value: 'custom', label: t(($) => $.create.aliasOptions.custom) },
              ]}
            />
            {aliasMode === 'custom' && (
              <Input
                id="artifact-create-alias-custom"
                placeholder={t(($) => $.create.aliasPlaceholder)}
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
              label: t(($) => $.create.advanced),
              children: (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Form.Item
                    label={t(($) => $.create.filename)}
                    name="filename"
                    htmlFor="artifact-create-filename"
                  >
                    <Input
                      id="artifact-create-filename"
                      placeholder={t(($) => $.create.filenamePlaceholder)}
                      autoComplete="off"
                    />
                  </Form.Item>
                  <Form.Item
                    label={t(($) => $.create.metadata)}
                    name="metadata"
                    htmlFor="artifact-create-metadata"
                    rules={[{ required: true, message: t(($) => $.create.metadataRequired) }]}
                    extra={t(($) => $.create.metadataExtra)}
                  >
                    <LazyJsonCodeEditorFormField
                      id="artifact-create-metadata"
                      height={220}
                      path="artifact-create-metadata.json"
                    />
                  </Form.Item>
                  <Form.Item
                    label={t(($) => $.create.versioned)}
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
    </ModalSurfaceShell>
  )
}
