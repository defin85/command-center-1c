import { useEffect, useMemo, useState } from 'react'
import { Alert, Space, Typography } from 'antd'
import Editor from '@monaco-editor/react'
import type * as Monaco from 'monaco-editor'

import type { DriverName } from '../../../api/driverCommands'
import type { DriverCommandBuilderMode, DriverCommandOperationConfig } from './types'
import { ARGV_LANGUAGE_ID, ARGV_MARKER_OWNER, buildArgsMarkers, detectIbcmdPidInArgs, ensureArgvLanguage } from './utils'

const { Text } = Typography

type MonacoInstance = typeof import('monaco-editor')

function buildEditorOptions(readOnly?: boolean): Monaco.editor.IStandaloneEditorConstructionOptions {
  return {
    readOnly,
    domReadOnly: readOnly,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    tabSize: 2,
    insertSpaces: true,
    automaticLayout: true,
    lineNumbers: 'on',
    renderWhitespace: 'selection',
    fontSize: 13,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  }
}

export function ArgsEditorSection({
  driver,
  mode,
  config,
  onChange,
  readOnly,
}: {
  driver: DriverName
  mode: DriverCommandBuilderMode
  config: DriverCommandOperationConfig
  onChange: (updates: Partial<DriverCommandOperationConfig>) => void
  readOnly?: boolean
}) {
  const pidInArgsLines = useMemo(
    () => (driver === 'ibcmd' ? detectIbcmdPidInArgs(config.args_text) : []),
    [config.args_text, driver]
  )

  const [argsEditorRef, setArgsEditorRef] = useState<{
    monaco: MonacoInstance
    model: Monaco.editor.ITextModel
  } | null>(null)

  useEffect(() => {
    if (!argsEditorRef) return
    const { monaco, model } = argsEditorRef
    const markers = buildArgsMarkers(monaco, driver, config.args_text)
    monaco.editor.setModelMarkers(model, ARGV_MARKER_OWNER, markers)
    return () => {
      monaco.editor.setModelMarkers(model, ARGV_MARKER_OWNER, [])
    }
  }, [argsEditorRef, config.args_text, driver])

  if (mode !== 'manual' && driver !== 'ibcmd') {
    return null
  }

  const argsEditorTitle = driver === 'cli' ? 'Args (one per line)' : 'Additional args (one per line)'
  const argsEditorDescription =
    driver === 'cli'
      ? 'Manual mode: you are responsible for the command syntax and parameters.'
      : 'Extra ibcmd arguments appended after canonical argv.'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      {mode === 'manual' && (
        <Alert type="warning" showIcon message="Manual mode" description={argsEditorDescription} />
      )}
      {driver === 'ibcmd' && pidInArgsLines.length > 0 && (
        <Alert
          type="error"
          showIcon
          message="--pid is not allowed in args"
          description={`Remove --pid from args and set it via Connection → PID. Lines: ${pidInArgsLines.join(', ')}`}
        />
      )}
      <Text strong>{argsEditorTitle}</Text>
      <div style={{ border: '1px solid #d9d9d9', borderRadius: 6, overflow: 'hidden' }}>
        <Editor
          height={driver === 'cli' ? 220 : 160}
          language={ARGV_LANGUAGE_ID}
          theme="vs"
          value={config.args_text || ''}
          onChange={(next) => onChange({ args_text: next ?? '' })}
          beforeMount={ensureArgvLanguage}
          onMount={(editor, monaco) => {
            const model = editor.getModel()
            if (model) {
              setArgsEditorRef({ monaco, model })
            }
          }}
          options={buildEditorOptions(readOnly)}
        />
      </div>
    </Space>
  )
}

