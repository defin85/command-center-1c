import '../../lib/monacoEnv'

import { useCallback, useMemo } from 'react'
import { Button, Space } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import Editor from '@monaco-editor/react'
import type * as Monaco from 'monaco-editor'

import './JsonCodeEditor.css'

import type { JsonCodeEditorFormFieldProps, JsonCodeEditorProps } from './jsonCodeEditorTypes'

export function JsonCodeEditor({
  id,
  value,
  onChange,
  height = 240,
  readOnly = false,
  title,
  extraToolbar,
  enableFormat = true,
  enableCopy = true,
  path,
}: JsonCodeEditorProps) {
  const resolvedValue = value ?? ''

  const formatValue = useCallback(() => {
    try {
      const parsed = JSON.parse(resolvedValue || '{}')
      onChange(JSON.stringify(parsed, null, 2))
    } catch {
      // Keep current value; Monaco diagnostics will show the error.
    }
  }, [onChange, resolvedValue])

  const copyValue = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(resolvedValue)
    } catch {
      // Ignore clipboard errors (e.g., permissions).
    }
  }, [resolvedValue])

  const options = useMemo<Monaco.editor.IStandaloneEditorConstructionOptions>(() => ({
    readOnly,
    domReadOnly: readOnly,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    tabSize: 2,
    insertSpaces: true,
    formatOnPaste: true,
    formatOnType: true,
    automaticLayout: true,
    lineNumbers: 'on',
    folding: true,
    renderWhitespace: 'selection',
    fontSize: 13,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
    ariaLabel: id || title || 'JSON editor',
  }), [id, readOnly, title])

  return (
    <div className="json-code-editor">
      {(title || enableFormat || enableCopy || extraToolbar) && (
        <div className="json-code-editor-toolbar">
          <div className="json-code-editor-title">{title || ''}</div>
          <Space size="small">
            {extraToolbar}
            {enableFormat && (
              <Button size="small" onClick={formatValue} disabled={readOnly}>
                Format
              </Button>
            )}
            {enableCopy && (
              <Button size="small" icon={<CopyOutlined />} onClick={copyValue}>
                Copy
              </Button>
            )}
          </Space>
        </div>
      )}
      <div className="json-code-editor-container" style={{ height }}>
        <Editor
          height="100%"
          language="json"
          theme="vs"
          value={resolvedValue}
          onChange={(nextValue) => onChange(nextValue ?? '')}
          options={options}
          path={path}
        />
      </div>
    </div>
  )
}

export default JsonCodeEditor

export function JsonCodeEditorFormField({ onChange, ...props }: JsonCodeEditorFormFieldProps) {
  return (
    <JsonCodeEditor
      {...props}
      onChange={onChange ?? (() => {})}
    />
  )
}
