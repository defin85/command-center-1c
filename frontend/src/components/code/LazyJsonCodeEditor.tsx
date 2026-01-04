import { lazy, Suspense } from 'react'
import { Spin } from 'antd'

import type { JsonCodeEditorFormFieldProps, JsonCodeEditorProps } from './jsonCodeEditorTypes'

const JsonCodeEditorLazy = lazy(() => import('./JsonCodeEditor'))
const JsonCodeEditorFormFieldLazy = lazy(() =>
  import('./JsonCodeEditor').then((module) => ({ default: module.JsonCodeEditorFormField }))
)

function EditorFallback({ height }: { height: number | string }) {
  return (
    <div
      style={{
        height,
        border: '1px solid rgba(0, 0, 0, 0.15)',
        borderRadius: 6,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.02)',
      }}
    >
      <Spin size="small" />
    </div>
  )
}

export function LazyJsonCodeEditor(props: JsonCodeEditorProps) {
  const height = props.height ?? 240
  return (
    <Suspense fallback={<EditorFallback height={height} />}>
      <JsonCodeEditorLazy {...props} />
    </Suspense>
  )
}

export function LazyJsonCodeEditorFormField(props: JsonCodeEditorFormFieldProps) {
  const height = props.height ?? 240
  return (
    <Suspense fallback={<EditorFallback height={height} />}>
      <JsonCodeEditorFormFieldLazy {...props} />
    </Suspense>
  )
}

