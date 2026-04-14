import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  App as AntApp,
  Button,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Typography,
} from 'antd'
import { useSearchParams } from 'react-router-dom'

import {
  createPoolSchemaTemplate,
  listPoolSchemaTemplates,
  updatePoolSchemaTemplate,
  type PoolSchemaTemplate,
  type PoolSchemaTemplateFormat,
} from '../../api/intercompanyPools'
import {
  EntityDetails,
  EntityList,
  JsonBlock,
  MasterDetailShell,
  ModalFormShell,
  PageHeader,
  WorkspacePage,
} from '../../components/platform'
import { useLocaleFormatters, usePoolsTranslation } from '../../i18n'

const { Text } = Typography
const { TextArea } = Input

type FormValues = {
  code: string
  name: string
  format: PoolSchemaTemplateFormat
  is_public: boolean
  is_active: boolean
  workflow_template_id?: string
  schema_json: string
  metadata_json: string
}

type SchemaTemplateComposeMode = 'create' | 'edit' | null
type SchemaTemplateFilter = 'all' | PoolSchemaTemplateFormat

const DEFAULT_SCHEMA_JSON = JSON.stringify(
  {
    columns: {
      inn: 'inn',
      amount: 'amount',
    },
  },
  null,
  2
)

const DEFAULT_METADATA_JSON = JSON.stringify({}, null, 2)

const stringifyJsonObject = (value: unknown): string => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return DEFAULT_METADATA_JSON
  }
  return JSON.stringify(value, null, 2)
}

const parseJsonObject = (
  text: string,
  invalidJsonMessage: string,
  objectExpectedMessage: string,
): Record<string, unknown> => {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(invalidJsonMessage)
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(objectExpectedMessage)
  }
  return parsed as Record<string, unknown>
}

const resolveWorkflowBindingHint = (metadata: Record<string, unknown>): string | null => {
  const raw = metadata.workflow_binding
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null
  }
  const binding = raw as Record<string, unknown>
  const bindingTemplateId = typeof binding.workflow_template_id === 'string'
    ? binding.workflow_template_id.trim()
    : ''
  const bindingVersion = typeof binding.version === 'string' ? binding.version.trim() : ''
  const bindingLabel = typeof binding.label === 'string' ? binding.label.trim() : ''

  if (bindingTemplateId) {
    if (bindingVersion) {
      return `${bindingTemplateId} (${bindingVersion})`
    }
    return bindingTemplateId
  }
  if (bindingLabel) {
    return bindingLabel
  }
  return JSON.stringify(binding)
}

const normalizeRouteParam = (value: string | null): string | null => {
  const normalized = value?.trim() ?? ''
  return normalized.length > 0 ? normalized : null
}

const parseComposeMode = (value: string | null): SchemaTemplateComposeMode => {
  if (value === 'create' || value === 'edit') {
    return value
  }
  return null
}

const parseFormatFilter = (value: string | null): SchemaTemplateFilter => (
  value === 'xlsx' || value === 'json' ? value : 'all'
)

const filterTemplates = (templates: PoolSchemaTemplate[], searchTerm: string) => {
  const normalizedSearch = searchTerm.trim().toLowerCase()
  if (!normalizedSearch) {
    return templates
  }

  return templates.filter((template) => {
    const bindingHint = resolveWorkflowBindingHint(template.metadata ?? {}) ?? ''
    return [
      template.code,
      template.name,
      template.workflow_template_id ?? '',
      bindingHint,
      template.format,
    ]
      .join(' ')
      .toLowerCase()
      .includes(normalizedSearch)
  })
}

const buildListButtonStyle = (selected: boolean) => ({
  width: '100%',
  border: selected ? '1px solid #91caff' : '1px solid #f0f0f0',
  borderInlineStart: selected ? '4px solid #1677ff' : '4px solid transparent',
  borderRadius: 8,
  padding: '12px',
  background: selected ? '#e6f4ff' : '#fff',
  boxShadow: selected ? '0 1px 2px rgba(22, 119, 255, 0.12)' : 'none',
  textAlign: 'left' as const,
  cursor: 'pointer',
})

export function PoolSchemaTemplatesPage() {
  const { message } = AntApp.useApp()
  const { t } = usePoolsTranslation()
  const formatters = useLocaleFormatters()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeUpdateModeRef = useRef<'push' | 'replace'>('replace')
  const searchFromUrl = searchParams.get('q') ?? ''
  const formatFilterFromUrl = parseFormatFilter(searchParams.get('format'))
  const selectedTemplateFromUrl = normalizeRouteParam(searchParams.get('template'))
  const detailOpenFromUrl = searchParams.get('detail') === '1'
  const composeModeFromUrl = parseComposeMode(searchParams.get('compose'))
  const includePrivateFromUrl = searchParams.get('private') === '1'
  const includeInactiveFromUrl = searchParams.get('inactive') === '1'

  const [templates, setTemplates] = useState<PoolSchemaTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState(searchFromUrl)
  const [formatFilter, setFormatFilter] = useState<SchemaTemplateFilter>(formatFilterFromUrl)
  const [includePrivate, setIncludePrivate] = useState(includePrivateFromUrl)
  const [includeInactive, setIncludeInactive] = useState(includeInactiveFromUrl)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null | undefined>(
    () => selectedTemplateFromUrl ?? undefined
  )
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(detailOpenFromUrl)
  const [composeMode, setComposeMode] = useState<SchemaTemplateComposeMode>(composeModeFromUrl)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [form] = Form.useForm<FormValues>()
  const formatDateTime = useCallback(
    (value?: string | null) => formatters.dateTime(value, { fallback: t('common.noValue') }),
    [formatters, t]
  )
  const formatVisibility = useCallback(
    (isPublic: boolean) => t(isPublic ? 'common.public' : 'common.private'),
    [t]
  )
  const formatStatus = useCallback(
    (isActive: boolean) => t(isActive ? 'common.active' : 'common.inactive'),
    [t]
  )

  useEffect(() => {
    setSearch((current) => (current === searchFromUrl ? current : searchFromUrl))
  }, [searchFromUrl])

  useEffect(() => {
    setFormatFilter((current) => (current === formatFilterFromUrl ? current : formatFilterFromUrl))
  }, [formatFilterFromUrl])

  useEffect(() => {
    setIncludePrivate((current) => (current === includePrivateFromUrl ? current : includePrivateFromUrl))
  }, [includePrivateFromUrl])

  useEffect(() => {
    setIncludeInactive((current) => (current === includeInactiveFromUrl ? current : includeInactiveFromUrl))
  }, [includeInactiveFromUrl])

  useEffect(() => {
    setSelectedTemplateId((current) => {
      if (selectedTemplateFromUrl) {
        return current === selectedTemplateFromUrl ? current : selectedTemplateFromUrl
      }
      return current === null ? current : null
    })
  }, [selectedTemplateFromUrl])

  useEffect(() => {
    setIsDetailDrawerOpen((current) => (current === detailOpenFromUrl ? current : detailOpenFromUrl))
  }, [detailOpenFromUrl])

  useEffect(() => {
    setComposeMode((current) => (current === composeModeFromUrl ? current : composeModeFromUrl))
  }, [composeModeFromUrl])

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listPoolSchemaTemplates({
        format: formatFilter === 'all' ? undefined : formatFilter,
        isPublic: includePrivate ? undefined : true,
        isActive: includeInactive ? undefined : true,
      })
      setTemplates(data)
      setSelectedTemplateId((current) => {
        if (current && data.some((template) => template.id === current)) {
          return current
        }
        return data[0]?.id ?? null
      })
    } catch {
      setError(t('schemaTemplates.messages.failedToLoad'))
    } finally {
      setLoading(false)
    }
  }, [formatFilter, includePrivate, includeInactive, t])

  useEffect(() => {
    void loadTemplates()
  }, [loadTemplates])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    const normalizedSearch = search.trim()

    if (normalizedSearch) {
      next.set('q', normalizedSearch)
    } else {
      next.delete('q')
    }

    if (formatFilter !== 'all') {
      next.set('format', formatFilter)
    } else {
      next.delete('format')
    }

    if (includePrivate) {
      next.set('private', '1')
    } else {
      next.delete('private')
    }

    if (includeInactive) {
      next.set('inactive', '1')
    } else {
      next.delete('inactive')
    }

    if (selectedTemplateId !== undefined) {
      if (selectedTemplateId) {
        next.set('template', selectedTemplateId)
      } else {
        next.delete('template')
      }
    }

    if (selectedTemplateId !== undefined) {
      if (isDetailDrawerOpen && selectedTemplateId) {
        next.set('detail', '1')
      } else {
        next.delete('detail')
      }
    }

    if (composeMode) {
      next.set('compose', composeMode)
    } else {
      next.delete('compose')
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(
        next,
        routeUpdateModeRef.current === 'replace'
          ? { replace: true }
          : undefined
      )
    }
    routeUpdateModeRef.current = 'replace'
  }, [
    composeMode,
    formatFilter,
    includeInactive,
    includePrivate,
    isDetailDrawerOpen,
    search,
    searchParams,
    selectedTemplateId,
    setSearchParams,
  ])

  const filteredTemplates = useMemo(
    () => filterTemplates(templates, search),
    [search, templates]
  )

  useEffect(() => {
    if (loading) {
      return
    }
    if (!filteredTemplates.length) {
      routeUpdateModeRef.current = 'replace'
      setSelectedTemplateId(null)
      setIsDetailDrawerOpen(false)
      return
    }
    if (selectedTemplateId && filteredTemplates.some((item) => item.id === selectedTemplateId)) {
      return
    }
    routeUpdateModeRef.current = 'replace'
    setSelectedTemplateId(filteredTemplates[0].id)
  }, [filteredTemplates, loading, selectedTemplateId])

  const selectedTemplate = useMemo(
    () => filteredTemplates.find((item) => item.id === selectedTemplateId)
      ?? templates.find((item) => item.id === selectedTemplateId)
      ?? null,
    [filteredTemplates, selectedTemplateId, templates]
  )

  useEffect(() => {
    if (composeMode === null) {
      return
    }

    if (composeMode === 'create') {
      form.setFieldsValue({
        code: '',
        name: '',
        format: 'xlsx',
        is_public: true,
        is_active: true,
        workflow_template_id: '',
        schema_json: DEFAULT_SCHEMA_JSON,
        metadata_json: DEFAULT_METADATA_JSON,
      })
      setSubmitError(null)
      return
    }

    if (!selectedTemplate) {
      return
    }

    form.setFieldsValue({
      code: selectedTemplate.code,
      name: selectedTemplate.name,
      format: selectedTemplate.format,
      is_public: selectedTemplate.is_public,
      is_active: selectedTemplate.is_active,
      workflow_template_id: selectedTemplate.workflow_template_id ?? '',
      schema_json: stringifyJsonObject(selectedTemplate.schema),
      metadata_json: stringifyJsonObject(selectedTemplate.metadata),
    })
    setSubmitError(null)
  }, [composeMode, form, selectedTemplate])

  const handleSearchChange = (nextSearch: string) => {
    const nextFilteredTemplates = filterTemplates(templates, nextSearch)
    const nextSelectedTemplateId = selectedTemplateId && nextFilteredTemplates.some(
      (template) => template.id === selectedTemplateId
    )
      ? selectedTemplateId
      : (nextFilteredTemplates[0]?.id ?? null)
    const nextDetailOpen = Boolean(nextSelectedTemplateId) && isDetailDrawerOpen

    routeUpdateModeRef.current = 'push'
    setSearch(nextSearch)
    setSelectedTemplateId(nextSelectedTemplateId)
    setIsDetailDrawerOpen(nextDetailOpen)
  }

  const handleSubmitTemplate = useCallback(async () => {
    setSubmitError(null)
    let values: FormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }

    let schema: Record<string, unknown>
    let metadata: Record<string, unknown>
    try {
      schema = parseJsonObject(
        values.schema_json,
        t('schemaTemplates.form.jsonErrors.invalidJson', { field: t('schemaTemplates.form.jsonErrors.schemaField') }),
        t('schemaTemplates.form.jsonErrors.objectExpected', { field: t('schemaTemplates.form.jsonErrors.schemaField') }),
      )
      metadata = parseJsonObject(
        values.metadata_json,
        t('schemaTemplates.form.jsonErrors.invalidJson', { field: t('schemaTemplates.form.jsonErrors.metadataField') }),
        t('schemaTemplates.form.jsonErrors.objectExpected', { field: t('schemaTemplates.form.jsonErrors.metadataField') }),
      )
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : t('schemaTemplates.messages.invalidJson'))
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        code: values.code,
        name: values.name,
        format: values.format,
        is_public: values.is_public,
        is_active: values.is_active,
        schema,
        metadata,
        workflow_template_id: values.workflow_template_id?.trim() || null,
      }
      if (composeMode === 'edit') {
        if (!selectedTemplate) {
          setSubmitError(t('schemaTemplates.messages.noTemplateSelected'))
          return
        }
        await updatePoolSchemaTemplate(selectedTemplate.id, payload)
        message.success(t('schemaTemplates.messages.updated'))
      } else {
        await createPoolSchemaTemplate(payload)
        message.success(t('schemaTemplates.messages.created'))
      }
      routeUpdateModeRef.current = 'push'
      setComposeMode(null)
      await loadTemplates()
    } catch {
      setSubmitError(
        composeMode === 'edit'
          ? t('schemaTemplates.messages.failedToUpdate')
          : t('schemaTemplates.messages.failedToCreate')
      )
    } finally {
      setIsSubmitting(false)
    }
  }, [composeMode, form, loadTemplates, message, selectedTemplate, t])

  const selectedWorkflowBindingHint = resolveWorkflowBindingHint(selectedTemplate?.metadata ?? {})

  return (
    <WorkspacePage
      header={(
        <PageHeader
          title={t('schemaTemplates.page.title')}
          subtitle={t('schemaTemplates.page.subtitle')}
          actions={(
            <Button
              type="primary"
              onClick={() => {
                routeUpdateModeRef.current = 'push'
                setComposeMode('create')
              }}
            >
              {t('schemaTemplates.page.create')}
            </Button>
          )}
        />
      )}
    >
      <Alert
        type="info"
        showIcon
        message={t('schemaTemplates.alerts.sourceOfTruthTitle')}
        description={t('schemaTemplates.alerts.sourceOfTruthDescription')}
      />

      <MasterDetailShell
        detailOpen={Boolean(selectedTemplateId) && isDetailDrawerOpen}
        onCloseDetail={() => {
          routeUpdateModeRef.current = 'push'
          setIsDetailDrawerOpen(false)
        }}
        detailDrawerTitle={selectedTemplate ? `${selectedTemplate.code} · ${t('schemaTemplates.detail.title').toLowerCase()}` : t('schemaTemplates.detail.drawerTitle')}
        list={(
          <EntityList
            title={t('schemaTemplates.list.title')}
            loading={loading}
            error={error}
            emptyDescription={t('schemaTemplates.list.emptyDescription')}
            toolbar={(
              <Space direction="vertical" size={12} style={{ width: '100%', marginBottom: 16 }}>
                <Input
                  allowClear
                  placeholder={t('schemaTemplates.list.searchPlaceholder')}
                  value={search}
                  onChange={(event) => handleSearchChange(event.target.value)}
                />
                <Space size="middle" wrap>
                  <Select
                    value={formatFilter}
                    style={{ width: 180 }}
                    options={[
                      { value: 'all', label: t('schemaTemplates.filters.allFormats') },
                      { value: 'xlsx', label: 'XLSX' },
                      { value: 'json', label: 'JSON' },
                    ]}
                    onChange={(value) => {
                      routeUpdateModeRef.current = 'push'
                      setFormatFilter(value)
                    }}
                  />
                  <Space size={6}>
                    <Switch
                      checked={includePrivate}
                      onChange={(value) => {
                        routeUpdateModeRef.current = 'push'
                        setIncludePrivate(value)
                      }}
                    />
                    <Text>{t('schemaTemplates.filters.includePrivate')}</Text>
                  </Space>
                  <Space size={6}>
                    <Switch
                      checked={includeInactive}
                      onChange={(value) => {
                        routeUpdateModeRef.current = 'push'
                        setIncludeInactive(value)
                      }}
                    />
                    <Text>{t('schemaTemplates.filters.includeInactive')}</Text>
                  </Space>
                  <Button onClick={() => void loadTemplates()} loading={loading}>
                    {t('schemaTemplates.page.refresh')}
                  </Button>
                </Space>
              </Space>
            )}
            dataSource={filteredTemplates}
            renderItem={(template) => {
              const selected = template.id === selectedTemplateId
              const workflowBindingHint = resolveWorkflowBindingHint(template.metadata ?? {})
              return (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => {
                    routeUpdateModeRef.current = 'push'
                    setSelectedTemplateId(template.id)
                    setIsDetailDrawerOpen(true)
                  }}
                  aria-label={t('schemaTemplates.list.openTemplate', { name: template.name })}
                  aria-pressed={selected}
                  style={buildListButtonStyle(selected)}
                >
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space direction="vertical" size={0} style={{ width: '100%' }}>
                      <Text strong>{template.name}</Text>
                      <Text type="secondary" code>{template.code}</Text>
                    </Space>
                    <Text type="secondary">
                      {t('schemaTemplates.list.summary', {
                        format: template.format.toUpperCase(),
                        visibility: formatVisibility(template.is_public),
                        status: formatStatus(template.is_active),
                      })}
                    </Text>
                    {workflowBindingHint ? (
                      <Text type="secondary">{t('schemaTemplates.list.workflowBindingHint', { value: workflowBindingHint })}</Text>
                    ) : null}
                  </Space>
                </button>
              )
            }}
          />
        )}
        detail={(
          <EntityDetails
            title={selectedTemplate ? selectedTemplate.name : t('schemaTemplates.detail.title')}
            empty={!selectedTemplate}
            emptyDescription={t('schemaTemplates.detail.emptyDescription')}
            extra={selectedTemplate ? (
              <Button
                onClick={() => {
                  routeUpdateModeRef.current = 'push'
                  setComposeMode('edit')
                  setIsDetailDrawerOpen(true)
                }}
              >
                {t('schemaTemplates.detail.edit')}
              </Button>
            ) : null}
          >
            {selectedTemplate ? (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Descriptions bordered size="small" column={1}>
                  <Descriptions.Item label={t('common.code')}>
                    <Text strong>{selectedTemplate.code}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.format')}>
                    {selectedTemplate.format.toUpperCase()}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.visibility')}>
                    {formatVisibility(selectedTemplate.is_public)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('common.status')}>
                    {formatStatus(selectedTemplate.is_active)}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('schemaTemplates.detail.workflowTemplate')}>
                    {selectedTemplate.workflow_template_id || t('common.notLinked')}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('schemaTemplates.detail.workflowBindingHint')}>
                    {selectedWorkflowBindingHint ? (
                      <Space size={8} data-testid="pool-template-workflow-binding-hint">
                        <Text strong>{t('common.compat')}</Text>
                        <Text code>{selectedWorkflowBindingHint}</Text>
                      </Space>
                    ) : (
                      t('common.absent')
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('schemaTemplates.detail.updated')}>
                    {formatDateTime(selectedTemplate.updated_at)}
                  </Descriptions.Item>
                </Descriptions>

                <JsonBlock title={t('schemaTemplates.detail.schemaJson')} value={selectedTemplate.schema} dataTestId="pool-schema-template-schema-json" />
                <JsonBlock title={t('schemaTemplates.detail.metadataJson')} value={selectedTemplate.metadata} dataTestId="pool-schema-template-metadata-json" />
              </Space>
            ) : null}
          </EntityDetails>
        )}
      />

      <ModalFormShell
        open={composeMode === 'create' || (composeMode === 'edit' && Boolean(selectedTemplate))}
        onClose={() => {
          if (isSubmitting) {
            return
          }
          routeUpdateModeRef.current = 'push'
          setComposeMode(null)
          setSubmitError(null)
        }}
        onSubmit={() => { void handleSubmitTemplate() }}
        title={composeMode === 'edit' ? t('schemaTemplates.form.editTitle') : t('schemaTemplates.form.createTitle')}
        submitText={composeMode === 'edit' ? t('schemaTemplates.form.editSubmit') : t('schemaTemplates.form.createSubmit')}
        confirmLoading={isSubmitting}
        width={760}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {submitError ? <Alert type="error" message={submitError} /> : null}
          <Form form={form} layout="vertical" requiredMark={false}>
            <Form.Item
              name="code"
              label={t('common.code')}
              rules={[{ required: true, message: t('schemaTemplates.form.validation.codeRequired') }]}
            >
              <Input placeholder={t('schemaTemplates.form.codePlaceholder')} />
            </Form.Item>
            <Form.Item
              name="name"
              label={t('common.name')}
              rules={[{ required: true, message: t('schemaTemplates.form.validation.nameRequired') }]}
            >
              <Input placeholder={t('schemaTemplates.form.namePlaceholder')} />
            </Form.Item>
            <Form.Item
              name="format"
              label={t('common.format')}
              rules={[{ required: true, message: t('schemaTemplates.form.validation.formatRequired') }]}
            >
              <Select
                options={[
                  { value: 'xlsx', label: 'XLSX' },
                  { value: 'json', label: 'JSON' },
                ]}
              />
            </Form.Item>
            <Form.Item name="workflow_template_id" label={t('schemaTemplates.form.workflowTemplateId')}>
              <Input placeholder={t('schemaTemplates.form.workflowTemplateIdPlaceholder')} />
            </Form.Item>
            <Form.Item name="is_public" label={t('schemaTemplates.form.public')} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_active" label={t('schemaTemplates.form.active')} valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="schema_json"
              label={t('schemaTemplates.form.schemaJson')}
              rules={[{ required: true, message: t('schemaTemplates.form.validation.schemaRequired') }]}
            >
              <TextArea rows={8} />
            </Form.Item>
            <Form.Item
              name="metadata_json"
              label={t('schemaTemplates.form.metadataJson')}
              rules={[{ required: true, message: t('schemaTemplates.form.validation.metadataRequired') }]}
            >
              <TextArea rows={6} />
            </Form.Item>
          </Form>
        </Space>
      </ModalFormShell>
    </WorkspacePage>
  )
}
