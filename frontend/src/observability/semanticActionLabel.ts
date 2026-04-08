import { Children, isValidElement, type ReactNode } from 'react'

const normalizeLabel = (value: string): string | undefined => {
  const normalized = value.replace(/\s+/g, ' ').trim()
  return normalized || undefined
}

const collectTextParts = (node: ReactNode): string[] => {
  if (node === null || node === undefined || typeof node === 'boolean') {
    return []
  }

  if (typeof node === 'string' || typeof node === 'number') {
    const normalized = normalizeLabel(String(node))
    return normalized ? [normalized] : []
  }

  if (Array.isArray(node)) {
    return node.flatMap((value) => collectTextParts(value))
  }

  if (isValidElement<{ children?: ReactNode }>(node)) {
    return collectTextParts(node.props.children)
  }

  return Children.toArray(node).flatMap((value) => collectTextParts(value))
}

export const semanticActionLabelFromNode = (node: ReactNode): string | undefined => {
  const parts = collectTextParts(node)
  return normalizeLabel(parts.join(' '))
}

export const firstSemanticActionLabel = (...values: ReactNode[]): string | undefined => {
  for (const value of values) {
    const label = semanticActionLabelFromNode(value)
    if (label) {
      return label
    }
  }
  return undefined
}
