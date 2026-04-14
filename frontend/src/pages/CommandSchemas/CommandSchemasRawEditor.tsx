import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Card, Checkbox, Input, Modal, Space, Switch, Tabs, Typography } from 'antd'
import { SaveOutlined } from '@ant-design/icons'
import { useAdminSupportTranslation } from '@/i18n'

import type { DriverCatalogV2 } from '../../api/driverCommands'
import {
  updateCommandSchemaBase,
  updateCommandSchemaEffective,
  updateCommandSchemaOverrides,
  validateCommandSchemas,
  type CommandSchemaDriver,
  type CommandSchemaIssue,
  type CommandSchemasEditorView,
  type CommandSchemasOverridesCatalogV2,
} from '../../api/commandSchemas'
import { LazyJsonCodeEditor } from '../../components/code/LazyJsonCodeEditor'

const { Text } = Typography

type RawTab = 'base' | 'overrides' | 'effective'

type SaveTarget = RawTab

export interface CommandSchemasRawEditorProps {
  driver: CommandSchemaDriver
  view: CommandSchemasEditorView | null
  disabled?: boolean
  onReload: () => Promise<void>
  onDirtyChange?: (dirty: boolean) => void
}

type ValidateSummary = { ok: boolean; errors: number; warnings: number }

const safeJsonStringify = (value: unknown): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (_err) {
    return '{}'
  }
}

const parseJsonObject = (raw: string): Record<string, unknown> | null => {
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null
    }
    return parsed as Record<string, unknown>
  } catch (_err) {
    return null
  }
}

const extractBackendMessage = (error: unknown): string | null => {
  const err = error as { response?: { status?: number; data?: { error?: { message?: string } | string } } } | null
  const value = err?.response?.data?.error
  if (typeof value === 'string') return value
  if (value && typeof value === 'object' && typeof value.message === 'string') return value.message
  return null
}

export function CommandSchemasRawEditor({
  driver,
  view,
  disabled = false,
  onReload,
  onDirtyChange,
}: CommandSchemasRawEditorProps) {
  const { message } = App.useApp()
  const { t } = useAdminSupportTranslation()

  const [activeTab, setActiveTab] = useState<RawTab>('base')

  const [baseRaw, setBaseRaw] = useState('{}')
  const [overridesRaw, setOverridesRaw] = useState('{}')
  const [effectiveRaw, setEffectiveRaw] = useState('{}')

  const [dangerousEffectiveEnabled, setDangerousEffectiveEnabled] = useState(false)

  const [saveTarget, setSaveTarget] = useState<SaveTarget | null>(null)
  const [saveReason, setSaveReason] = useState('')
  const [saveConfirmed, setSaveConfirmed] = useState(false)
  const [saving, setSaving] = useState(false)

  const [validateLoading, setValidateLoading] = useState(false)
  const [validateError, setValidateError] = useState<string | null>(null)
  const [validateIssues, setValidateIssues] = useState<CommandSchemaIssue[]>([])
  const [validateSummary, setValidateSummary] = useState<ValidateSummary | null>(null)

  useEffect(() => {
    setDangerousEffectiveEnabled(false)
    setSaveTarget(null)
    setSaveReason('')
    setSaveConfirmed(false)
    setValidateLoading(false)
    setValidateError(null)
    setValidateIssues([])
    setValidateSummary(null)

    if (!view) {
      setBaseRaw('{}')
      setOverridesRaw('{}')
      setEffectiveRaw('{}')
      return
    }

    setBaseRaw(safeJsonStringify(view.catalogs?.base ?? {}))
    setOverridesRaw(safeJsonStringify(view.catalogs?.overrides ?? {}))
    setEffectiveRaw(safeJsonStringify(view.catalogs?.effective?.catalog ?? {}))
  }, [driver, view])

  const serverBaseRaw = useMemo(() => safeJsonStringify(view?.catalogs?.base ?? {}), [view])
  const serverOverridesRaw = useMemo(() => safeJsonStringify(view?.catalogs?.overrides ?? {}), [view])
  const serverEffectiveRaw = useMemo(() => safeJsonStringify(view?.catalogs?.effective?.catalog ?? {}), [view])

  const isDirty = useMemo(() => {
    return baseRaw !== serverBaseRaw || overridesRaw !== serverOverridesRaw || effectiveRaw !== serverEffectiveRaw
  }, [baseRaw, effectiveRaw, overridesRaw, serverBaseRaw, serverEffectiveRaw, serverOverridesRaw])

  useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])

  const openSave = (target: SaveTarget) => {
    if (disabled || saving) return
    if (!view) {
      message.error(t(($) => $.commandSchemas.raw.editorNotLoaded))
      return
    }

    if (target === 'effective' && !dangerousEffectiveEnabled) {
      message.warning(t(($) => $.commandSchemas.raw.enableDangerousEditFirst))
      return
    }

    setSaveTarget(target)
    setSaveReason('')
    setSaveConfirmed(false)
  }

  const closeSave = () => {
    if (saving) return
    setSaveTarget(null)
    setSaveReason('')
    setSaveConfirmed(false)
  }

  const runValidation = async (
    target: SaveTarget,
    catalog: Record<string, unknown>
  ): Promise<{ ok: boolean; errors: number } | null> => {
    setValidateLoading(true)
    setValidateError(null)
    try {
      const payload =
        target === 'overrides'
          ? { driver, catalog: catalog as unknown as CommandSchemasOverridesCatalogV2 }
          : { driver, effective_catalog: catalog as unknown as DriverCatalogV2 }

      const response = await validateCommandSchemas(payload)
      setValidateIssues(response.issues ?? [])
      setValidateSummary({ ok: response.ok, errors: response.errors_count, warnings: response.warnings_count })
      return { ok: response.ok, errors: response.errors_count }
    } catch (error) {
      const msg = extractBackendMessage(error) || t(($) => $.commandSchemas.raw.failedValidateCatalog)
      setValidateError(msg)
      setValidateIssues([])
      setValidateSummary(null)
      return null
    } finally {
      setValidateLoading(false)
    }
  }

  const handleSave = async () => {
    if (!saveTarget || !view) {
      return
    }
    const reason = saveReason.trim()
    if (!reason) {
      message.error(t(($) => $.commandSchemas.raw.reasonRequired))
      return
    }

    if (saveTarget === 'effective' && !saveConfirmed) {
      message.error(t(($) => $.commandSchemas.raw.confirmDangerousAction))
      return
    }

    const raw = saveTarget === 'base' ? baseRaw : saveTarget === 'overrides' ? overridesRaw : effectiveRaw
    const parsed = parseJsonObject(raw)
    if (!parsed) {
      message.error(t(($) => $.commandSchemas.raw.invalidJsonExpectedObject))
      return
    }

    const validation = await runValidation(saveTarget, parsed)
    if (!validation) {
      message.error(t(($) => $.commandSchemas.raw.validationFailed))
      return
    }
    if (!validation.ok) {
      message.error(t(($) => $.commandSchemas.raw.validationFailedWithErrors, { count: validation.errors }))
      return
    }

    setSaving(true)
    try {
      if (saveTarget === 'base') {
        await updateCommandSchemaBase({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success(t(($) => $.commandSchemas.raw.baseSaved))
      } else if (saveTarget === 'overrides') {
        await updateCommandSchemaOverrides({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success(t(($) => $.commandSchemas.raw.overridesSaved))
      } else {
        await updateCommandSchemaEffective({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success(t(($) => $.commandSchemas.raw.effectiveSaved))
        setDangerousEffectiveEnabled(false)
      }

      closeSave()
      await onReload()
    } catch (error) {
      const status = (error as { response?: { status?: number } } | null)?.response?.status
      if (status === 409) {
        message.error(t(($) => $.commandSchemas.raw.conflictEtag))
        return
      }
      const msg = extractBackendMessage(error) || t(($) => $.commandSchemas.raw.failedSaveCatalog)
      message.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const tabBarExtraContent = (
    <Space size="small">
      {activeTab === 'base' && (
        <Button
          icon={<SaveOutlined />}
          type="primary"
          onClick={() => openSave('base')}
          disabled={disabled || saving || !view}
        >
          {t(($) => $.commandSchemas.raw.saveBase)}
        </Button>
      )}
      {activeTab === 'overrides' && (
        <Button
          icon={<SaveOutlined />}
          type="primary"
          onClick={() => openSave('overrides')}
          disabled={disabled || saving || !view}
        >
          {t(($) => $.commandSchemas.raw.saveOverrides)}
        </Button>
      )}
      {activeTab === 'effective' && (
        <Button
          icon={<SaveOutlined />}
          type="primary"
          danger
          onClick={() => openSave('effective')}
          disabled={disabled || saving || !view || !dangerousEffectiveEnabled}
        >
          {t(($) => $.commandSchemas.raw.saveEffective)}
        </Button>
      )}
    </Space>
  )

  const saveTitle =
    saveTarget === 'base'
      ? t(($) => $.commandSchemas.raw.saveBaseTitle)
      : saveTarget === 'overrides'
        ? t(($) => $.commandSchemas.raw.saveOverridesTitle)
        : t(($) => $.commandSchemas.raw.saveEffectiveTitle)

  const okDisabled = !saveReason.trim() || saving || validateLoading || !view || (
    saveTarget === 'effective' && !saveConfirmed
  )

  return (
    <div data-testid="command-schemas-raw-mode">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {isDirty && (
          <Alert
            type="warning"
            showIcon
            message={t(($) => $.commandSchemas.raw.unsavedTitle)}
            description={t(($) => $.commandSchemas.raw.unsavedDescription)}
          />
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(560px, 1fr) 420px', gap: 16, alignItems: 'start' }}>
          <Card size="small" title={t(($) => $.commandSchemas.raw.rawJsonTitle)} extra={tabBarExtraContent}>
            <Tabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as RawTab)}
              items={[
                {
                  key: 'base',
                  label: t(($) => $.commandSchemas.raw.base),
                  children: (
                    <LazyJsonCodeEditor
                      value={baseRaw}
                      onChange={setBaseRaw}
                      height={520}
                      path={`command-schemas-base-${driver}.json`}
                      readOnly={disabled || saving}
                    />
                  ),
                },
                {
                  key: 'overrides',
                  label: t(($) => $.commandSchemas.raw.overrides),
                  children: (
                    <LazyJsonCodeEditor
                      value={overridesRaw}
                      onChange={setOverridesRaw}
                      height={520}
                      path={`command-schemas-overrides-${driver}.json`}
                      readOnly={disabled || saving}
                    />
                  ),
                },
                {
                  key: 'effective',
                  label: t(($) => $.commandSchemas.raw.effective),
                  children: (
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Alert
                        type="warning"
                        showIcon
                        message={t(($) => $.commandSchemas.raw.dangerZoneTitle)}
                        description={t(($) => $.commandSchemas.raw.dangerZoneDescription)}
                      />
                      <Space>
                        <Switch
                          data-testid="command-schemas-raw-effective-enable"
                          checked={dangerousEffectiveEnabled}
                          onChange={setDangerousEffectiveEnabled}
                          disabled={disabled || saving}
                        />
                        <Text type="secondary">{t(($) => $.commandSchemas.raw.enableDangerousEffectiveEdit)}</Text>
                      </Space>
                      <LazyJsonCodeEditor
                        value={effectiveRaw}
                        onChange={setEffectiveRaw}
                        height={480}
                        path={`command-schemas-effective-${driver}.json`}
                        readOnly={!dangerousEffectiveEnabled || disabled || saving}
                      />
                    </Space>
                  ),
                },
              ]}
            />
          </Card>

          <Card size="small" title={t(($) => $.commandSchemas.raw.validateTitle)}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {!validateSummary && !validateError && (
                <Alert
                  type="info"
                  showIcon
                  message={t(($) => $.commandSchemas.raw.noValidationYetTitle)}
                  description={t(($) => $.commandSchemas.raw.noValidationYetDescription)}
                />
              )}

              {validateError && (
                <Alert type="warning" showIcon message={t(($) => $.commandSchemas.raw.validationFailed)} description={validateError} />
              )}

              {validateSummary && (
                <Alert
                  type={validateSummary.ok ? 'success' : 'error'}
                  showIcon
                  message={validateSummary.ok ? t(($) => $.commandSchemas.sidePanel.ok) : t(($) => $.commandSchemas.raw.errorsFound)}
                  description={`errors=${validateSummary.errors}, warnings=${validateSummary.warnings}`}
                />
              )}

              {validateIssues.length > 0 && (
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  {validateIssues.slice(0, 50).map((issue, idx) => (
                    <Alert
                      key={`${issue.code}-${idx}`}
                      type={issue.severity === 'error' ? 'error' : 'warning'}
                      showIcon
                      message={`${issue.code}: ${issue.message}`}
                      description={issue.path ? <Text code>{issue.path}</Text> : undefined}
                    />
                  ))}
                  {validateIssues.length > 50 && (
                    <Text type="secondary">{t(($) => $.commandSchemas.raw.showingFirstIssues, { count: 50 })}</Text>
                  )}
                </Space>
              )}
            </Space>
          </Card>
        </div>
      </Space>

      <Modal
        title={saveTitle}
        open={saveTarget !== null}
        onCancel={closeSave}
        onOk={handleSave}
        okText="Save"
        okButtonProps={{ disabled: okDisabled, loading: saving, 'data-testid': 'command-schemas-raw-save-confirm' }}
        cancelButtonProps={{ disabled: saving }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          {saveTarget === 'effective' && (
            <Alert
              type="warning"
              showIcon
              message={t(($) => $.commandSchemas.raw.overwriteBaseTitle)}
              description={t(($) => $.commandSchemas.raw.overwriteBaseDescription)}
            />
          )}

          {saveTarget === 'effective' && (
            <Checkbox
              data-testid="command-schemas-raw-effective-confirm"
              checked={saveConfirmed}
              onChange={(e) => setSaveConfirmed(e.target.checked)}
              disabled={saving}
            >
              {t(($) => $.commandSchemas.raw.understandConsequences)}
            </Checkbox>
          )}

          <Text type="secondary">{t(($) => $.commandSchemas.raw.reasonLabel)}</Text>
          <Input.TextArea
            data-testid="command-schemas-raw-save-reason"
            value={saveReason}
            onChange={(e) => setSaveReason(e.target.value)}
            placeholder={t(($) => $.commandSchemas.raw.reasonPlaceholder)}
            rows={4}
            disabled={saving}
          />
        </Space>
      </Modal>
    </div>
  )
}

export default CommandSchemasRawEditor
