import { useEffect, useMemo, useState } from 'react'
import { Alert, Form, Input, InputNumber, Radio, Select, Space, Spin, Switch } from 'antd'

import { useArtifacts, useArtifactAliases, useArtifactVersions } from '../../../api/queries'
import type { DriverCommandParamV2 } from '../../../api/driverCommands'
import type { ArtifactKind } from '../../../api/artifacts'
import { ARTIFACT_PREFIX, normalizeText, parseArtifactIdFromKey, parseArtifactKey, parseLines, safeString } from './utils'

function ArtifactValueField({
  label,
  value,
  required,
  artifactKinds,
  disabled,
  onChange,
}: {
  label: string
  value: string | undefined
  required?: boolean
  artifactKinds: ArtifactKind[]
  disabled?: boolean
  onChange: (next: string) => void
}) {
  const artifactKey = parseArtifactKey(value)
  const [source, setSource] = useState<'artifact' | 'path'>(artifactKey ? 'artifact' : 'path')
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | undefined>(
    parseArtifactIdFromKey(artifactKey)
  )

  useEffect(() => {
    setSource(artifactKey ? 'artifact' : 'path')
    if (artifactKey) {
      setSelectedArtifactId((current) => current || parseArtifactIdFromKey(artifactKey))
    }
  }, [artifactKey])

  const artifactsQuery = useArtifacts(
    { kind: artifactKinds.length === 1 ? artifactKinds[0] : undefined },
    { enabled: source === 'artifact' }
  )
  const versionsQuery = useArtifactVersions(selectedArtifactId)
  const aliasesQuery = useArtifactAliases(selectedArtifactId)

  const artifacts = useMemo(() => {
    const list = artifactsQuery.data?.artifacts ?? []
    if (artifactKinds.length <= 1) {
      return list
    }
    return list.filter((artifact) => artifactKinds.includes(artifact.kind))
  }, [artifactKinds, artifactsQuery.data])

  const artifactOptions = useMemo(
    () =>
      artifacts.map((artifact) => ({
        label: `${artifact.name} (${artifact.kind})`,
        value: artifact.id,
      })),
    [artifacts]
  )

  const aliasByVersion = useMemo(() => {
    const map = new Map<string, string>()
    for (const alias of aliasesQuery.data?.aliases ?? []) {
      map.set(alias.version_id, alias.alias)
    }
    return map
  }, [aliasesQuery.data])

  const versionOptions = useMemo(
    () =>
      (versionsQuery.data?.versions ?? []).map((version) => {
        const alias = aliasByVersion.get(version.id)
        const versionLabel = alias
          ? `${alias} (${version.version}) • ${version.filename}`
          : `${version.version} • ${version.filename}`
        return {
          label: versionLabel,
          value: version.storage_key,
        }
      }),
    [aliasByVersion, versionsQuery.data]
  )

  const handleSourceChange = (next: 'artifact' | 'path') => {
    setSource(next)
    onChange('')
  }

  const handleArtifactChange = (nextArtifactId?: string) => {
    setSelectedArtifactId(nextArtifactId)
    onChange('')
  }

  const handleArtifactVersionChange = (storageKey?: string) => {
    if (!storageKey) {
      onChange('')
      return
    }
    onChange(`${ARTIFACT_PREFIX}${storageKey}`)
  }

  return (
    <Form.Item label={label} required={required} style={{ marginBottom: 12 }}>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Radio.Group
          value={source}
          disabled={disabled}
          onChange={(event) => handleSourceChange(event.target.value)}
        >
          <Radio.Button value="artifact">Artifact</Radio.Button>
          <Radio.Button value="path">Path</Radio.Button>
        </Radio.Group>

        {source === 'path' && (
          <Input
            value={value || ''}
            disabled={disabled}
            placeholder="/path/to/file"
            onChange={(event) => onChange(event.target.value)}
          />
        )}

        {source === 'artifact' && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {artifactsQuery.error && (
              <Alert
                type="warning"
                showIcon
                message="Artifact list unavailable"
                description={artifactsQuery.error.message}
              />
            )}
            <Select
              showSearch
              placeholder="Select artifact"
              disabled={disabled || artifactsQuery.isLoading}
              value={selectedArtifactId}
              options={artifactOptions}
              optionFilterProp="label"
              onChange={handleArtifactChange}
              notFoundContent={artifactsQuery.isLoading ? <Spin size="small" /> : null}
            />
            <Select
              showSearch
              placeholder="Select version"
              disabled={disabled || versionsQuery.isLoading || !selectedArtifactId}
              value={parseArtifactKey(value)}
              options={versionOptions}
              optionFilterProp="label"
              onChange={handleArtifactVersionChange}
              notFoundContent={versionsQuery.isLoading ? <Spin size="small" /> : null}
            />
          </Space>
        )}
      </Space>
    </Form.Item>
  )
}

export function ParamField({
  name,
  schema,
  value,
  disabled,
  onChange,
}: {
  name: string
  schema: DriverCommandParamV2
  value: unknown
  disabled?: boolean
  onChange: (next: unknown) => void
}) {
  const label = (schema.label || name).trim()
  const description = typeof schema.description === 'string' ? schema.description : undefined
  const isRequired = schema.required === true

  const artifactKinds = useMemo(() => {
    const artifact = schema.artifact as { kinds?: unknown } | undefined
    const rawKinds = artifact?.kinds
    if (!Array.isArray(rawKinds)) return []
    return rawKinds.filter((item): item is ArtifactKind => typeof item === 'string' && item.length > 0)
  }, [schema.artifact])

  if (artifactKinds.length > 0) {
    return (
      <ArtifactValueField
        label={label}
        value={typeof value === 'string' ? value : ''}
        required={isRequired}
        disabled={disabled}
        artifactKinds={artifactKinds}
        onChange={(next) => onChange(next)}
      />
    )
  }

  if (schema.kind === 'flag' && !schema.expects_value) {
    return (
      <Form.Item
        label={label}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <Switch checked={value === true} disabled={disabled} onChange={(checked) => onChange(checked)} />
      </Form.Item>
    )
  }

  if (schema.enum && Array.isArray(schema.enum) && schema.enum.length > 0) {
    const options = schema.enum.map((item) => ({ value: item, label: item }))
    const mode = schema.repeatable ? 'multiple' : undefined
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <Select
          showSearch
          allowClear
          mode={mode as 'multiple' | undefined}
          disabled={disabled}
          value={schema.repeatable ? (Array.isArray(value) ? value : undefined) : safeString(value) || undefined}
          options={options}
          onChange={(next) => onChange(next)}
          optionFilterProp="value"
        />
      </Form.Item>
    )
  }

  if (schema.repeatable && schema.expects_value) {
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description || 'One value per line'}
      >
        <Input.TextArea
          rows={4}
          disabled={disabled}
          value={normalizeText(value)}
          onChange={(event) => onChange(parseLines(event.target.value))}
        />
      </Form.Item>
    )
  }

  if (schema.value_type === 'int' || schema.value_type === 'float') {
    const numericValue = typeof value === 'number' ? value : undefined
    return (
      <Form.Item
        label={label}
        required={isRequired}
        style={{ marginBottom: 12 }}
        help={description}
      >
        <InputNumber
          style={{ width: '100%' }}
          disabled={disabled}
          value={numericValue}
          onChange={(next) => onChange(typeof next === 'number' ? next : undefined)}
        />
      </Form.Item>
    )
  }

  return (
    <Form.Item
      label={label}
      required={isRequired}
      style={{ marginBottom: 12 }}
      help={description}
    >
      <Input
        disabled={disabled}
        value={safeString(value)}
        placeholder={schema.kind === 'flag' ? schema.flag : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Form.Item>
  )
}

