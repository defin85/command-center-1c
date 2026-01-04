import { useEffect, useMemo, useState } from 'react'
import { Alert, Form, Input, InputNumber, Radio, Select, Space, Switch, Tabs, Typography } from 'antd'
import { useArtifacts, useArtifactAliases, useArtifactVersions } from '../../api/queries'
import type { ArtifactKind } from '../../api/artifacts'

const { Text } = Typography
const { TextArea } = Input

export type IbcmdBuilderMode = 'guided' | 'manual'

export type IbcmdOperationType =
  | 'ibcmd_backup'
  | 'ibcmd_restore'
  | 'ibcmd_replicate'
  | 'ibcmd_create'
  | 'ibcmd_load_cfg'
  | 'ibcmd_extension_update'

export interface IbcmdOperationConfig {
  ibcmd_mode?: IbcmdBuilderMode
  args?: string[] | string
  stdin?: string

  dbms?: string
  db_server?: string
  db_name?: string
  db_user?: string
  db_password?: string

  user?: string
  password?: string

  output_path?: string
  input_path?: string
  create_database?: boolean
  force?: boolean

  target_dbms?: string
  target_db_server?: string
  target_db_name?: string
  target_db_user?: string
  target_db_password?: string
  jobs_count?: number
  target_jobs_count?: number

  file?: string
  extension?: string

  name?: string
  active?: boolean
  safe_mode?: boolean
  scope?: 'infobase' | 'data-separation'
  security_profile_name?: string
  unsafe_action_protection?: boolean
  used_in_distributed_infobase?: boolean

  additional_args?: string[] | string
}

interface IbcmdOperationBuilderProps {
  operationType: IbcmdOperationType
  config: IbcmdOperationConfig
  onChange: (updates: Partial<IbcmdOperationConfig>) => void
  readOnly?: boolean
}

const ARTIFACT_PREFIX = 'artifact://'

const normalizeMultilineText = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value
      .filter((item): item is string => typeof item === 'string')
      .join('\n')
  }
  if (typeof value === 'string') {
    return value
  }
  return ''
}

const parseLines = (value: string): string[] | undefined => {
  const list = value
    .split('\n')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
  return list.length > 0 ? list : undefined
}

const parseArtifactKey = (value: string | undefined): string | undefined => {
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

const ArtifactPathField = ({
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
}) => {
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
            placeholder="/path/to/file.cfe"
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
            />
            <Select
              showSearch
              placeholder="Select version"
              disabled={disabled || versionsQuery.isLoading || !selectedArtifactId}
              value={parseArtifactKey(value)}
              options={versionOptions}
              optionFilterProp="label"
              onChange={handleArtifactVersionChange}
            />
          </Space>
        )}
      </Space>
    </Form.Item>
  )
}

export function IbcmdOperationBuilder({ operationType, config, onChange, readOnly }: IbcmdOperationBuilderProps) {
  const mode: IbcmdBuilderMode = config.ibcmd_mode ?? 'guided'

  const handleModeChange = (nextMode: string) => {
    if (nextMode === 'guided') {
      onChange({ ibcmd_mode: 'guided', args: undefined })
      return
    }
    onChange({ ibcmd_mode: nextMode as IbcmdBuilderMode })
  }

  const handleManualArgsChange = (value: string) => {
    onChange({ args: parseLines(value) })
  }

  const handleAdditionalArgsChange = (value: string) => {
    onChange({ additional_args: parseLines(value) })
  }

  const handleStdinChange = (value: string) => {
    onChange({ stdin: value })
  }

  const renderDbConfig = () => (
    <Form layout="vertical">
      <Form.Item label="DBMS" required style={{ marginBottom: 12 }}>
        <Input
          value={config.dbms || ''}
          disabled={readOnly}
          placeholder="PostgreSQL"
          onChange={(event) => onChange({ dbms: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB server" required style={{ marginBottom: 12 }}>
        <Input
          value={config.db_server || ''}
          disabled={readOnly}
          placeholder="db-host:5432"
          onChange={(event) => onChange({ db_server: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB name" required style={{ marginBottom: 12 }}>
        <Input
          value={config.db_name || ''}
          disabled={readOnly}
          placeholder="infobase_db"
          onChange={(event) => onChange({ db_name: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB user" required style={{ marginBottom: 12 }}>
        <Input
          value={config.db_user || ''}
          disabled={readOnly}
          placeholder="dbuser"
          onChange={(event) => onChange({ db_user: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="DB password" required style={{ marginBottom: 12 }}>
        <Input.Password
          value={config.db_password || ''}
          disabled={readOnly}
          placeholder="db password"
          onChange={(event) => onChange({ db_password: event.target.value })}
        />
      </Form.Item>

      <Form.Item label="1C user (optional)" style={{ marginBottom: 12 }}>
        <Input
          value={config.user || ''}
          disabled={readOnly}
          placeholder="override user"
          onChange={(event) => onChange({ user: event.target.value })}
        />
      </Form.Item>
      <Form.Item label="1C password (optional)" style={{ marginBottom: 12 }}>
        <Input.Password
          value={config.password || ''}
          disabled={readOnly}
          placeholder="override password"
          onChange={(event) => onChange({ password: event.target.value })}
        />
      </Form.Item>
    </Form>
  )

  const renderOperationConfig = () => {
    switch (operationType) {
      case 'ibcmd_backup':
        return (
          <Form layout="vertical">
            <Form.Item label="Output path (optional)" style={{ marginBottom: 12 }}>
              <Input
                value={config.output_path || ''}
                disabled={readOnly}
                placeholder="leave empty for auto"
                onChange={(event) => onChange({ output_path: event.target.value })}
              />
            </Form.Item>
          </Form>
        )
      case 'ibcmd_restore':
        return (
          <Form layout="vertical">
            <Form.Item
              label="Input path"
              required
              help="Path in IBCMD storage (local relative) or s3://bucket/key if IBCMD_STORAGE_BACKEND=s3"
              style={{ marginBottom: 12 }}
            >
              <Input
                value={config.input_path || ''}
                disabled={readOnly}
                placeholder="s3://bucket/path/to/backup.dt"
                onChange={(event) => onChange({ input_path: event.target.value })}
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.create_database === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ create_database: checked })}
              />{' '}
              <Text>Create database</Text>
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.force === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ force: checked })}
              />{' '}
              <Text>Force</Text>
            </Form.Item>
          </Form>
        )
      case 'ibcmd_replicate':
        return (
          <Form layout="vertical">
            <Form.Item label="Target DBMS" required style={{ marginBottom: 12 }}>
              <Input
                value={config.target_dbms || ''}
                disabled={readOnly}
                placeholder="PostgreSQL"
                onChange={(event) => onChange({ target_dbms: event.target.value })}
              />
            </Form.Item>
            <Form.Item label="Target DB server" required style={{ marginBottom: 12 }}>
              <Input
                value={config.target_db_server || ''}
                disabled={readOnly}
                placeholder="db-host:5432"
                onChange={(event) => onChange({ target_db_server: event.target.value })}
              />
            </Form.Item>
            <Form.Item label="Target DB name" required style={{ marginBottom: 12 }}>
              <Input
                value={config.target_db_name || ''}
                disabled={readOnly}
                placeholder="target_db"
                onChange={(event) => onChange({ target_db_name: event.target.value })}
              />
            </Form.Item>
            <Form.Item label="Target DB user" required style={{ marginBottom: 12 }}>
              <Input
                value={config.target_db_user || ''}
                disabled={readOnly}
                placeholder="dbuser"
                onChange={(event) => onChange({ target_db_user: event.target.value })}
              />
            </Form.Item>
            <Form.Item label="Target DB password" required style={{ marginBottom: 12 }}>
              <Input.Password
                value={config.target_db_password || ''}
                disabled={readOnly}
                placeholder="db password"
                onChange={(event) => onChange({ target_db_password: event.target.value })}
              />
            </Form.Item>
            <Form.Item label="Jobs count (optional)" style={{ marginBottom: 12 }}>
              <InputNumber
                min={1}
                value={typeof config.jobs_count === 'number' ? config.jobs_count : undefined}
                disabled={readOnly}
                onChange={(value) => onChange({ jobs_count: value ?? undefined })}
                style={{ width: '100%' }}
              />
            </Form.Item>
            <Form.Item label="Target jobs count (optional)" style={{ marginBottom: 12 }}>
              <InputNumber
                min={1}
                value={typeof config.target_jobs_count === 'number' ? config.target_jobs_count : undefined}
                disabled={readOnly}
                onChange={(value) => onChange({ target_jobs_count: value ?? undefined })}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Form>
        )
      case 'ibcmd_create':
        return (
          <Alert
            type="info"
            showIcon
            message="Create infobase"
            description="This operation creates database objects. Review parameters carefully."
          />
        )
      case 'ibcmd_load_cfg':
        return (
          <Form layout="vertical">
            <ArtifactPathField
              label="File (.cf / .cfe)"
              required
              value={config.file}
              disabled={readOnly}
              artifactKinds={['extension', 'config_cf']}
              onChange={(next) => onChange({ file: next })}
            />
            <Form.Item label="Extension name (optional)" style={{ marginBottom: 12 }}>
              <Input
                value={config.extension || ''}
                disabled={readOnly}
                placeholder="MyExtension"
                onChange={(event) => onChange({ extension: event.target.value })}
              />
            </Form.Item>
          </Form>
        )
      case 'ibcmd_extension_update':
        return (
          <Form layout="vertical">
            <Form.Item label="Extension name" required style={{ marginBottom: 12 }}>
              <Input
                value={config.name || ''}
                disabled={readOnly}
                placeholder="MyExtension"
                onChange={(event) => onChange({ name: event.target.value })}
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.active === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ active: checked })}
              />{' '}
              <Text>Active</Text>
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.safe_mode === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ safe_mode: checked })}
              />{' '}
              <Text>Safe mode</Text>
            </Form.Item>
            <Form.Item label="Scope (optional)" style={{ marginBottom: 12 }}>
              <Select
                allowClear
                value={config.scope}
                disabled={readOnly}
                options={[
                  { value: 'infobase', label: 'infobase' },
                  { value: 'data-separation', label: 'data-separation' },
                ]}
                onChange={(value) => onChange({ scope: value })}
              />
            </Form.Item>
            <Form.Item label="Security profile name (optional)" style={{ marginBottom: 12 }}>
              <Input
                value={config.security_profile_name || ''}
                disabled={readOnly}
                placeholder="ProfileName"
                onChange={(event) => onChange({ security_profile_name: event.target.value })}
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.unsafe_action_protection === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ unsafe_action_protection: checked })}
              />{' '}
              <Text>Unsafe action protection</Text>
            </Form.Item>
            <Form.Item style={{ marginBottom: 12 }}>
              <Switch
                checked={config.used_in_distributed_infobase === true}
                disabled={readOnly}
                onChange={(checked) => onChange({ used_in_distributed_infobase: checked })}
              />{' '}
              <Text>Used in distributed infobase</Text>
            </Form.Item>
          </Form>
        )
      default:
        return null
    }
  }

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
            description="Provide raw ibcmd arguments (one per line). If args are set, the driver will execute them directly."
          />
          <Form layout="vertical">
            <Form.Item label="Args (one per line)" required>
              <TextArea
                rows={8}
                value={normalizeMultilineText(config.args)}
                disabled={readOnly}
                onChange={(event) => handleManualArgsChange(event.target.value)}
                placeholder="infobase\nconfig\nload-cfg\n--dbms=PostgreSQL\n--db-server=..."
              />
            </Form.Item>
            <Form.Item label="Stdin (optional)">
              <TextArea
                rows={4}
                value={config.stdin || ''}
                disabled={readOnly}
                onChange={(event) => handleStdinChange(event.target.value)}
              />
            </Form.Item>
          </Form>
        </Space>
      )}

      {mode === 'guided' && (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {renderDbConfig()}
          {renderOperationConfig()}
          <Form layout="vertical">
            <Form.Item label="Additional args (optional, one per line)" style={{ marginBottom: 12 }}>
              <TextArea
                rows={4}
                value={normalizeMultilineText(config.additional_args)}
                disabled={readOnly}
                onChange={(event) => handleAdditionalArgsChange(event.target.value)}
                placeholder="--some-flag=value"
              />
            </Form.Item>
            <Form.Item label="Stdin (optional)" style={{ marginBottom: 0 }}>
              <TextArea
                rows={3}
                value={config.stdin || ''}
                disabled={readOnly}
                onChange={(event) => handleStdinChange(event.target.value)}
              />
            </Form.Item>
          </Form>
        </Space>
      )}
    </Space>
  )
}

export default IbcmdOperationBuilder

