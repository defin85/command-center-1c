import { useMemo, useEffect, useState } from 'react'
import { Alert, AutoComplete, Form, Input, Select, Space, Spin, Switch, Tabs, Typography, Radio } from 'antd'
import { useCliCommandCatalog } from '../../hooks/useCliCommandCatalog'
import { useArtifacts, useArtifactAliases, useArtifactVersions } from '../../api/queries'
import type { CliCommandDescriptor, CliCommandParamDescriptor } from '../../api/operations'
import type { ArtifactKind } from '../../api/artifacts'

const { Text } = Typography
const { TextArea } = Input

export type CliBuilderMode = 'manual' | 'guided'

export interface DesignerCliConfig {
  command?: string
  args?: string | string[]
  disable_startup_messages?: boolean
  disable_startup_dialogs?: boolean
  cli_mode?: CliBuilderMode
  cli_params?: Record<string, string | boolean>
}

interface DesignerCliBuilderProps {
  config: DesignerCliConfig
  onChange: (updates: Partial<DesignerCliConfig>) => void
  readOnly?: boolean
}

const ARTIFACT_PREFIX = 'artifact://'

const buildArgsFromParams = (
  params: CliCommandParamDescriptor[],
  values: Record<string, string | boolean>
): string[] => {
  const args: string[] = []
  params.forEach((param) => {
    if (param.kind === 'positional') {
      const value = values[param.name]
      if (typeof value === 'string' && value.trim().length > 0) {
        args.push(value.trim())
      }
      return
    }
    if (param.kind === 'flag') {
      const flag = param.flag || `-${param.name}`
      if (param.expects_value) {
        const value = values[param.name]
        if (typeof value === 'string' && value.trim().length > 0) {
          args.push(flag)
          args.push(value.trim())
        }
        return
      }
      if (values[param.name] === true) {
        args.push(flag)
      }
    }
  })
  return args
}

const parseArtifactKey = (value: string | boolean | undefined): string | undefined => {
  if (typeof value !== 'string') {
    return undefined
  }
  if (!value.startsWith(ARTIFACT_PREFIX)) {
    return undefined
  }
  const key = value.slice(ARTIFACT_PREFIX.length).replace(/^\/+/, '')
  return key || undefined
}

const parseArtifactIdFromKey = (key?: string): string | undefined => {
  if (!key) {
    return undefined
  }
  const parts = key.split('/')
  if (parts.length >= 2 && parts[0] === 'artifacts') {
    return parts[1]
  }
  return undefined
}

const normalizeArgsText = (value: DesignerCliConfig['args']): string => {
  if (Array.isArray(value)) {
    return value.join('\n')
  }
  if (typeof value === 'string') {
    return value
  }
  return ''
}

const getCommandOptions = (commands: CliCommandDescriptor[]) =>
  commands.map((cmd) => ({
    value: cmd.id,
    label: cmd.label,
  }))

const getSelectedCommand = (
  commands: CliCommandDescriptor[],
  command?: string
): CliCommandDescriptor | undefined =>
  commands.find((cmd) => cmd.id === command)

const ParamField = ({
  param,
  value,
  onChange,
  disabled,
}: {
  param: CliCommandParamDescriptor
  value: string | boolean | undefined
  onChange: (next: string | boolean) => void
  disabled?: boolean
}) => {
  const label = param.label || param.name
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

  const artifactKinds = useMemo(() => {
    const raw = param.artifact_kinds ?? []
    return raw.filter(Boolean) as ArtifactKind[]
  }, [param.artifact_kinds])

  const artifactsQuery = useArtifacts(
    {
      kind: artifactKinds.length === 1 ? artifactKinds[0] : undefined,
    },
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
        const label = alias
          ? `${alias} (${version.version}) • ${version.filename}`
          : `${version.version} • ${version.filename}`
        return {
          label,
          value: version.storage_key,
        }
      }),
    [aliasByVersion, versionsQuery.data]
  )

  const handleSourceChange = (next: 'artifact' | 'path') => {
    setSource(next)
    if (next === 'path' && artifactKey) {
      onChange('')
    }
    if (next === 'artifact' && typeof value === 'string' && value && !artifactKey) {
      onChange('')
    }
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

  if (param.kind === 'flag' && !param.expects_value) {
    return (
      <Form.Item label={label} style={{ marginBottom: 12 }}>
        <Switch
          checked={value === true}
          disabled={disabled}
          onChange={(checked) => onChange(checked)}
        />
      </Form.Item>
    )
  }

  if (param.input_type === 'artifact') {
    return (
      <Form.Item
        label={label}
        required={param.required}
        style={{ marginBottom: 12 }}
      >
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
              value={typeof value === 'string' ? value : ''}
              disabled={disabled}
              placeholder={param.kind === 'flag' ? param.flag : undefined}
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

  return (
    <Form.Item
      label={label}
      required={param.required}
      style={{ marginBottom: 12 }}
    >
      <Input
        value={typeof value === 'string' ? value : ''}
        disabled={disabled}
        placeholder={param.kind === 'flag' ? param.flag : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Form.Item>
  )
}

export function DesignerCliBuilder({ config, onChange, readOnly }: DesignerCliBuilderProps) {
  const { catalog, commands, loading, error } = useCliCommandCatalog()
  const mode: CliBuilderMode = config.cli_mode ?? 'guided'
  const cliParams = config.cli_params ?? {}

  const commandOptions = useMemo(() => getCommandOptions(commands), [commands])
  const selectedCommand = useMemo(
    () => getSelectedCommand(commands, config.command),
    [commands, config.command]
  )
  const params = (selectedCommand?.params ?? []) as CliCommandParamDescriptor[]

  const handleModeChange = (nextMode: string) => {
    onChange({ cli_mode: nextMode as CliBuilderMode })
  }

  const handleCommandChange = (value: string) => {
    if (mode === 'guided') {
      onChange({ command: value, cli_params: {}, args: [] })
      return
    }
    onChange({ command: value })
  }

  const handleManualArgsChange = (value: string) => {
    onChange({ args: value })
  }

  const handleParamChange = (name: string, value: string | boolean) => {
    const nextParams = { ...cliParams, [name]: value }
    const nextArgs = buildArgsFromParams(params, nextParams)
    onChange({ cli_params: nextParams, args: nextArgs })
  }

  const handleOptionsChange = (field: 'disable_startup_messages' | 'disable_startup_dialogs') =>
    (checked: boolean) => {
      onChange({ [field]: checked })
    }

  const argsPreview = Array.isArray(config.args) ? config.args : []

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Tabs
        activeKey={mode}
        onChange={handleModeChange}
        items={[
          { key: 'guided', label: 'Guided' },
          { key: 'manual', label: 'Manual' },
        ]}
      />

      {mode === 'manual' && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            type="warning"
            showIcon
            message="Manual mode"
            description="You are responsible for the command syntax and parameters."
          />
          <Form layout="vertical">
            <Form.Item label="Command" required>
              <AutoComplete
                value={config.command || ''}
                options={commandOptions}
                placeholder="e.g. LoadCfg"
                disabled={readOnly}
                onChange={handleCommandChange}
              />
            </Form.Item>
            <Form.Item label="Args (one per line)">
              <TextArea
                rows={6}
                value={normalizeArgsText(config.args)}
                disabled={readOnly}
                onChange={(event) => handleManualArgsChange(event.target.value)}
                placeholder="-Extension\nMyExtension"
              />
            </Form.Item>
          </Form>
        </Space>
      )}

      {mode === 'guided' && (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {loading && (
            <Spin tip="Loading CLI catalog..." />
          )}
          {error && (
            <Alert type="warning" showIcon message="CLI catalog unavailable" description={error} />
          )}
          <Form layout="vertical">
            <Form.Item label="Command" required>
              <Select
                showSearch
                placeholder="Select command"
                disabled={readOnly || loading}
                value={config.command}
                onChange={handleCommandChange}
                options={commandOptions}
                optionFilterProp="label"
              />
            </Form.Item>

            {selectedCommand && selectedCommand.description && (
              <Text type="secondary">{selectedCommand.description}</Text>
            )}

            {params.length > 0 && (
              <div style={{ marginTop: 16 }}>
                {params.map((param) => (
                  <ParamField
                    key={param.name}
                    param={param}
                    value={cliParams[param.name]}
                    disabled={readOnly}
                    onChange={(value) => handleParamChange(param.name, value)}
                  />
                ))}
              </div>
            )}
          </Form>

          {argsPreview.length > 0 && (
            <Alert
              type="info"
              showIcon
              message="Args preview"
              description={argsPreview.join('\n')}
            />
          )}
          {catalog?.version && (
            <Text type="secondary">Catalog version: {catalog.version}</Text>
          )}
        </Space>
      )}

      <Space direction="vertical" size="small">
        <Text strong>Startup options</Text>
        <Space>
          <Switch
            checked={config.disable_startup_messages !== false}
            disabled={readOnly}
            onChange={handleOptionsChange('disable_startup_messages')}
          />
          <Text>Disable startup messages</Text>
        </Space>
        <Space>
          <Switch
            checked={config.disable_startup_dialogs !== false}
            disabled={readOnly}
            onChange={handleOptionsChange('disable_startup_dialogs')}
          />
          <Text>Disable startup dialogs</Text>
        </Space>
      </Space>
    </Space>
  )
}

export default DesignerCliBuilder
