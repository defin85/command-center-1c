import { useEffect, useMemo } from 'react'
import { Button, Space, Switch, Typography } from 'antd'
import type { FormInstance } from 'antd'

import type { ActionCatalogEditorHintsResponse } from '../../../api/generated/model/actionCatalogEditorHintsResponse'
import type { ActionFormValues } from '../actionCatalogTypes'

type JsonObject = Record<string, unknown>

const isObject = (value: unknown): value is JsonObject => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const getSchemaObject = (value: unknown): JsonObject | null => (isObject(value) ? value : null)

const getSchemaString = (schema: JsonObject, key: string): string | null => {
  const raw = schema[key]
  return typeof raw === 'string' && raw.trim() ? raw.trim() : null
}

const getSchemaProperties = (schema: JsonObject): JsonObject | null => {
  const raw = schema.properties
  return getSchemaObject(raw)
}

const getSchemaRequired = (schema: JsonObject): string[] => {
  const raw = schema.required
  if (!Array.isArray(raw)) return []
  return raw.filter((item): item is string => typeof item === 'string' && item.length > 0)
}

const getSchemaDefault = (schema: JsonObject): unknown => schema.default

function buildDefaultsFromSchema(schema: JsonObject): JsonObject {
  const out: JsonObject = {}
  const props = getSchemaProperties(schema)
  if (!props) return out
  for (const [key, value] of Object.entries(props)) {
    const propSchema = getSchemaObject(value)
    if (!propSchema) continue
    const propType = getSchemaString(propSchema, 'type')
    if (propType === 'boolean') {
      const def = getSchemaDefault(propSchema)
      if (typeof def === 'boolean') out[key] = def
      else out[key] = false
      continue
    }
    if (propType === 'object') {
      out[key] = buildDefaultsFromSchema(propSchema)
      continue
    }
  }
  return out
}

export function ActionCatalogCapabilityFixedSection({
  form,
  capability,
  hints,
}: {
  form: FormInstance<ActionFormValues>
  capability: string
  hints: ActionCatalogEditorHintsResponse | undefined
}) {
  const { Text } = Typography
  const anyForm = form as unknown as FormInstance<any>

  const capabilityHints = useMemo(() => {
    const key = capability.trim()
    if (!key) return null
    const caps = hints?.capabilities
    if (!caps) return null
    return caps[key] ?? null
  }, [capability, hints?.capabilities])

  const fixedSchema = useMemo(() => (
    getSchemaObject(capabilityHints?.fixed_schema) ?? null
  ), [capabilityHints?.fixed_schema])

  const fixedHelp = capabilityHints?.help
  const fixedProps = useMemo(() => (
    fixedSchema ? getSchemaProperties(fixedSchema) : null
  ), [fixedSchema])

  useEffect(() => {
    if (!fixedProps) return

    for (const [propKey, propSchemaRaw] of Object.entries(fixedProps)) {
      const propSchema = getSchemaObject(propSchemaRaw)
      if (!propSchema) continue
      const propType = getSchemaString(propSchema, 'type')
      if (propType !== 'object') continue

      const required = getSchemaRequired(propSchema)
      if (required.length === 0) continue

      const basePath = ['executor', 'fixed', propKey]
      const current = anyForm.getFieldValue(basePath)
      if (!isObject(current)) continue

      const next: JsonObject = { ...current }
      let changed = false
      const nestedProps = getSchemaProperties(propSchema) ?? {}
      for (const reqKey of required) {
        if (next[reqKey] !== undefined) continue
        const childSchema = getSchemaObject(nestedProps[reqKey]) ?? {}
        const childType = getSchemaString(childSchema, 'type')
        if (childType === 'boolean') {
          const def = getSchemaDefault(childSchema)
          next[reqKey] = typeof def === 'boolean' ? def : false
          changed = true
        }
      }

      if (changed) {
        anyForm.setFieldValue(basePath, next)
      }
    }
  }, [anyForm, fixedProps])

  if (!fixedSchema || !fixedProps) return null

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {(fixedHelp?.title || fixedHelp?.description) && (
        <div>
          {fixedHelp?.title && <Text strong>{fixedHelp.title}</Text>}
          {fixedHelp?.description && (
            <div>
              <Text type="secondary">{fixedHelp.description}</Text>
            </div>
          )}
        </div>
      )}

      {Object.entries(fixedProps).map(([propKey, propSchemaRaw]) => {
        const propSchema = getSchemaObject(propSchemaRaw)
        if (!propSchema) return null
        const propType = getSchemaString(propSchema, 'type')
        if (propType !== 'object') return null

        const title = getSchemaString(propSchema, 'title') ?? propKey
        const description = getSchemaString(propSchema, 'description')
        const groupPath = ['executor', 'fixed', propKey]
        const groupValue = anyForm.getFieldValue(groupPath)
        const enabled = isObject(groupValue)

        const groupDefaults = buildDefaultsFromSchema(propSchema)
        const nestedProps = getSchemaProperties(propSchema)

        const anySelected = enabled && nestedProps
          ? Object.keys(nestedProps).some((k) => anyForm.getFieldValue(['executor', 'fixed', propKey, k]) === true)
          : true

        return (
          <div key={propKey} style={{ marginTop: 8 }}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text strong>{title}</Text>
                <Space size="small">
                  {!enabled && (
                    <Button
                      size="small"
                      onClick={() => {
                        anyForm.setFieldValue(groupPath, groupDefaults)
                      }}
                      data-testid={`action-catalog-editor-fixed-${propKey}-enable`}
                    >
                      Enable
                    </Button>
                  )}
                  {enabled && (
                    <Button
                      size="small"
                      onClick={() => anyForm.setFieldValue(groupPath, undefined)}
                      data-testid={`action-catalog-editor-fixed-${propKey}-clear`}
                    >
                      Clear
                    </Button>
                  )}
                </Space>
              </div>

              {description && <Text type="secondary">{description}</Text>}

              {!enabled ? (
                <Text type="secondary">Not set.</Text>
              ) : !nestedProps ? (
                <Text type="secondary">No fields in schema.</Text>
              ) : (
                <Space size="middle" wrap>
                  {Object.entries(nestedProps).map(([fieldKey, fieldSchemaRaw]) => {
                    const fieldSchema = getSchemaObject(fieldSchemaRaw)
                    if (!fieldSchema) return null
                    const fieldType = getSchemaString(fieldSchema, 'type')
                    if (fieldType !== 'boolean') return null

                    const fieldLabel = getSchemaString(fieldSchema, 'title') ?? fieldKey
                    const fieldHelp = getSchemaString(fieldSchema, 'description')

                    return (
                      <div key={fieldKey} style={{ minWidth: 180 }}>
                        <Text>{fieldLabel}</Text>
                        {fieldHelp && (
                          <div>
                            <Text type="secondary">{fieldHelp}</Text>
                          </div>
                        )}
                        <div style={{ marginTop: 4 }}>
                          <Switch
                            checked={anyForm.getFieldValue(['executor', 'fixed', propKey, fieldKey]) === true}
                            onChange={(checked) => {
                              anyForm.setFieldValue(['executor', 'fixed', propKey, fieldKey], checked)
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </Space>
              )}

              {enabled && !anySelected && (
                <Text type="warning">Select at least one flag, or Clear to disable preset.</Text>
              )}
            </Space>
          </div>
        )
      })}
    </Space>
  )
}
