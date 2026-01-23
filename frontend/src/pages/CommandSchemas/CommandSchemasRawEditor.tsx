import { useEffect, useMemo, useState } from 'react'
import { Alert, App, Button, Card, Checkbox, Input, Modal, Space, Switch, Tabs, Typography } from 'antd'
import { SaveOutlined } from '@ant-design/icons'

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
      message.error('Editor data is not loaded yet')
      return
    }

    if (target === 'effective' && !dangerousEffectiveEnabled) {
      message.warning('Enable dangerous effective edit first')
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
      const msg = extractBackendMessage(error) || 'Failed to validate catalog'
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
      message.error('Reason is required')
      return
    }

    if (saveTarget === 'effective' && !saveConfirmed) {
      message.error('Confirm the dangerous action')
      return
    }

    const raw = saveTarget === 'base' ? baseRaw : saveTarget === 'overrides' ? overridesRaw : effectiveRaw
    const parsed = parseJsonObject(raw)
    if (!parsed) {
      message.error('Invalid JSON: expected a JSON object')
      return
    }

    const validation = await runValidation(saveTarget, parsed)
    if (!validation) {
      message.error('Validation failed')
      return
    }
    if (!validation.ok) {
      message.error(`Validation failed: ${validation.errors} error(s)`)
      return
    }

    setSaving(true)
    try {
      if (saveTarget === 'base') {
        await updateCommandSchemaBase({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success('Base saved')
      } else if (saveTarget === 'overrides') {
        await updateCommandSchemaOverrides({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success('Overrides saved')
      } else {
        await updateCommandSchemaEffective({ driver, catalog: parsed, reason, expected_etag: view.etag })
        message.success('Effective saved')
        setDangerousEffectiveEnabled(false)
      }

      closeSave()
      await onReload()
    } catch (error) {
      const status = (error as { response?: { status?: number } } | null)?.response?.status
      if (status === 409) {
        message.error('Conflict (ETag mismatch). Refresh and retry.')
        return
      }
      const msg = extractBackendMessage(error) || 'Failed to save catalog'
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
          Save base...
        </Button>
      )}
      {activeTab === 'overrides' && (
        <Button
          icon={<SaveOutlined />}
          type="primary"
          onClick={() => openSave('overrides')}
          disabled={disabled || saving || !view}
        >
          Save overrides...
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
          Save effective...
        </Button>
      )}
    </Space>
  )

  const saveTitle =
    saveTarget === 'base'
      ? 'Save base catalog'
      : saveTarget === 'overrides'
        ? 'Save overrides catalog'
        : 'DANGEROUS: Save effective catalog'

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
            message="Unsaved changes (raw)"
            description="Local JSON differs from server state. Reload to discard, or save the tab you changed."
          />
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(560px, 1fr) 420px', gap: 16, alignItems: 'start' }}>
          <Card size="small" title="Raw JSON" extra={tabBarExtraContent}>
            <Tabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as RawTab)}
              items={[
                {
                  key: 'base',
                  label: 'Base',
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
                  label: 'Overrides',
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
                  label: 'Effective',
                  children: (
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Alert
                        type="warning"
                        showIcon
                        message="Danger zone"
                        description="Saving effective overwrites base and resets overrides. Use only if you fully understand the consequences."
                      />
                      <Space>
                        <Switch
                          data-testid="command-schemas-raw-effective-enable"
                          checked={dangerousEffectiveEnabled}
                          onChange={setDangerousEffectiveEnabled}
                          disabled={disabled || saving}
                        />
                        <Text type="secondary">Enable dangerous effective edit</Text>
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

          <Card size="small" title="Validate">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {!validateSummary && !validateError && (
                <Alert
                  type="info"
                  showIcon
                  message="No validation yet"
                  description="Validation runs automatically before saving a tab."
                />
              )}

              {validateError && (
                <Alert type="warning" showIcon message="Validation failed" description={validateError} />
              )}

              {validateSummary && (
                <Alert
                  type={validateSummary.ok ? 'success' : 'error'}
                  showIcon
                  message={validateSummary.ok ? 'OK' : 'Errors found'}
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
                    <Text type="secondary">Showing first 50 issues.</Text>
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
              message="This will overwrite base and reset overrides"
              description="After saving, effective will become equal to base and all overrides will be cleared."
            />
          )}

          {saveTarget === 'effective' && (
            <Checkbox
              data-testid="command-schemas-raw-effective-confirm"
              checked={saveConfirmed}
              onChange={(e) => setSaveConfirmed(e.target.checked)}
              disabled={saving}
            >
              I understand the consequences
            </Checkbox>
          )}

          <Text type="secondary">Reason (required)</Text>
          <Input.TextArea
            data-testid="command-schemas-raw-save-reason"
            value={saveReason}
            onChange={(e) => setSaveReason(e.target.value)}
            placeholder="Why are you changing command schemas?"
            rows={4}
            disabled={saving}
          />
        </Space>
      </Modal>
    </div>
  )
}

export default CommandSchemasRawEditor
