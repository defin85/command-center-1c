import type { ReactNode } from 'react'

export type JsonCodeEditorProps = {
  id?: string
  value?: string
  onChange: (value: string) => void
  height?: number | string
  readOnly?: boolean
  title?: string
  extraToolbar?: ReactNode
  enableFormat?: boolean
  enableCopy?: boolean
  path?: string
}

export type JsonCodeEditorFormFieldProps = Omit<JsonCodeEditorProps, 'onChange'> & {
  onChange?: (value: string) => void
}

