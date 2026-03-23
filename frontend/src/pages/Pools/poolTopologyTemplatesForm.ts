import type { NamePath } from 'antd/es/form/interface'

import type {
  CreatePoolTopologyTemplatePayload,
  CreatePoolTopologyTemplateRevisionPayload,
  PoolTopologyTemplate,
} from '../../api/intercompanyPools'

export type TopologyTemplateEditorMode = 'create' | 'revise'

export type TopologyTemplateNodeFormValue = {
  slot_key: string
  label: string
  is_root: boolean
  metadata_json: string
}

export type TopologyTemplateEdgeFormValue = {
  parent_slot_key: string
  child_slot_key: string
  weight: string
  min_amount: string
  max_amount: string
  document_policy_key: string
  metadata_json: string
}

export type TopologyTemplateEditorFormValues = {
  code: string
  name: string
  description: string
  metadata_json: string
  revision_metadata_json: string
  nodes: TopologyTemplateNodeFormValue[]
  edges: TopologyTemplateEdgeFormValue[]
}

export type TopologyTemplateEditorFieldError = {
  name: NamePath
  errors: string[]
}

type BuildRequestResult<TRequest> = {
  request: TRequest | null
  errors: TopologyTemplateEditorFieldError[]
}

const DEFAULT_JSON = JSON.stringify({}, null, 2)

export const createBlankTopologyTemplateNodeFormValue = (): TopologyTemplateNodeFormValue => ({
  slot_key: '',
  label: '',
  is_root: false,
  metadata_json: DEFAULT_JSON,
})

export const createBlankTopologyTemplateEdgeFormValue = (): TopologyTemplateEdgeFormValue => ({
  parent_slot_key: '',
  child_slot_key: '',
  weight: '1',
  min_amount: '',
  max_amount: '',
  document_policy_key: '',
  metadata_json: DEFAULT_JSON,
})

const stringifyJsonObject = (value: unknown) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return DEFAULT_JSON
  }
  return JSON.stringify(value, null, 2)
}

const parseJsonObject = (text: string, fieldLabel: string) => {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(`${fieldLabel}: invalid JSON`)
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel}: object expected`)
  }
  return parsed as Record<string, unknown>
}

const parseOptionalAmount = (value: string) => {
  const normalized = value.trim()
  return normalized ? normalized : null
}

const validateRevisionPayload = (
  values: TopologyTemplateEditorFormValues,
): BuildRequestResult<CreatePoolTopologyTemplatePayload['revision']> => {
  const errors: TopologyTemplateEditorFieldError[] = []

  let revisionMetadata: Record<string, unknown>
  try {
    revisionMetadata = parseJsonObject(values.revision_metadata_json, 'Revision metadata')
  } catch (error) {
    errors.push({
      name: 'revision_metadata_json',
      errors: [error instanceof Error ? error.message : 'Revision metadata: invalid JSON'],
    })
    revisionMetadata = {}
  }

  const nodes = values.nodes.map((node, index) => {
    const slotKey = node.slot_key.trim()
    const label = node.label.trim()

    if (!slotKey) {
      errors.push({
        name: ['nodes', index, 'slot_key'],
        errors: ['Slot key is required.'],
      })
    }

    let metadata: Record<string, unknown>
    try {
      metadata = parseJsonObject(node.metadata_json, `Node ${index + 1} metadata`)
    } catch (error) {
      errors.push({
        name: ['nodes', index, 'metadata_json'],
        errors: [error instanceof Error ? error.message : 'Node metadata: invalid JSON'],
      })
      metadata = {}
    }

    return {
      slot_key: slotKey,
      label: label || null,
      is_root: Boolean(node.is_root),
      metadata,
    }
  })

  if (nodes.length === 0) {
    errors.push({
      name: 'nodes',
      errors: ['Add at least one abstract node.'],
    })
  }

  const seenSlotKeys = new Set<string>()
  for (const [index, node] of nodes.entries()) {
    if (!node.slot_key) {
      continue
    }
    if (seenSlotKeys.has(node.slot_key)) {
      errors.push({
        name: ['nodes', index, 'slot_key'],
        errors: ['Slot key must be unique.'],
      })
      continue
    }
    seenSlotKeys.add(node.slot_key)
  }

  const edges = values.edges.map((edge, index) => {
    const parentSlotKey = edge.parent_slot_key.trim()
    const childSlotKey = edge.child_slot_key.trim()
    const weight = edge.weight.trim() || '1'

    if (!parentSlotKey) {
      errors.push({
        name: ['edges', index, 'parent_slot_key'],
        errors: ['Parent slot key is required.'],
      })
    }
    if (!childSlotKey) {
      errors.push({
        name: ['edges', index, 'child_slot_key'],
        errors: ['Child slot key is required.'],
      })
    }

    let metadata: Record<string, unknown>
    try {
      metadata = parseJsonObject(edge.metadata_json, `Edge ${index + 1} metadata`)
    } catch (error) {
      errors.push({
        name: ['edges', index, 'metadata_json'],
        errors: [error instanceof Error ? error.message : 'Edge metadata: invalid JSON'],
      })
      metadata = {}
    }

    return {
      parent_slot_key: parentSlotKey,
      child_slot_key: childSlotKey,
      weight,
      min_amount: parseOptionalAmount(edge.min_amount),
      max_amount: parseOptionalAmount(edge.max_amount),
      document_policy_key: edge.document_policy_key.trim() || null,
      metadata,
    }
  })

  for (const [index, edge] of edges.entries()) {
    if (edge.parent_slot_key && !seenSlotKeys.has(edge.parent_slot_key)) {
      errors.push({
        name: ['edges', index, 'parent_slot_key'],
        errors: ['Parent slot key must reference an existing node.'],
      })
    }
    if (edge.child_slot_key && !seenSlotKeys.has(edge.child_slot_key)) {
      errors.push({
        name: ['edges', index, 'child_slot_key'],
        errors: ['Child slot key must reference an existing node.'],
      })
    }
  }

  if (errors.length > 0) {
    return { request: null, errors }
  }

  return {
    request: {
      nodes,
      edges,
      metadata: revisionMetadata,
    },
    errors: [],
  }
}

export const buildCreatePoolTopologyTemplateRequest = (
  values: TopologyTemplateEditorFormValues,
): BuildRequestResult<CreatePoolTopologyTemplatePayload> => {
  const errors: TopologyTemplateEditorFieldError[] = []

  let metadata: Record<string, unknown>
  try {
    metadata = parseJsonObject(values.metadata_json, 'Template metadata')
  } catch (error) {
    errors.push({
      name: 'metadata_json',
      errors: [error instanceof Error ? error.message : 'Template metadata: invalid JSON'],
    })
    metadata = {}
  }

  const revision = validateRevisionPayload(values)
  if (revision.errors.length > 0 || !revision.request) {
    return {
      request: null,
      errors: [...errors, ...revision.errors],
    }
  }

  if (errors.length > 0) {
    return {
      request: null,
      errors,
    }
  }

  return {
    request: {
      code: values.code.trim(),
      name: values.name.trim(),
      description: values.description.trim(),
      metadata,
      revision: revision.request,
    },
    errors: [],
  }
}

export const buildRevisePoolTopologyTemplateRequest = (
  values: TopologyTemplateEditorFormValues,
): BuildRequestResult<CreatePoolTopologyTemplateRevisionPayload> => {
  const revision = validateRevisionPayload(values)
  if (!revision.request) {
    return revision
  }

  return {
    request: {
      revision: revision.request,
    },
    errors: [],
  }
}

export const buildTopologyTemplateEditorInitialValues = (
  template?: PoolTopologyTemplate | null,
): TopologyTemplateEditorFormValues => {
  const latestRevision = template?.latest_revision

  return {
    code: template?.code ?? '',
    name: template?.name ?? '',
    description: template?.description ?? '',
    metadata_json: stringifyJsonObject(template?.metadata),
    revision_metadata_json: stringifyJsonObject(latestRevision?.metadata),
    nodes: latestRevision?.nodes.length
      ? latestRevision.nodes.map((node) => ({
        slot_key: node.slot_key,
        label: node.label ?? '',
        is_root: Boolean(node.is_root),
        metadata_json: stringifyJsonObject(node.metadata),
      }))
      : [createBlankTopologyTemplateNodeFormValue()],
    edges: latestRevision?.edges.length
      ? latestRevision.edges.map((edge) => ({
        parent_slot_key: edge.parent_slot_key,
        child_slot_key: edge.child_slot_key,
        weight: String(edge.weight || '1'),
        min_amount: edge.min_amount == null ? '' : String(edge.min_amount),
        max_amount: edge.max_amount == null ? '' : String(edge.max_amount),
        document_policy_key: edge.document_policy_key ?? '',
        metadata_json: stringifyJsonObject(edge.metadata),
      }))
      : [],
  }
}
