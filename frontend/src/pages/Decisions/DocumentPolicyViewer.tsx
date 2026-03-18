import { Descriptions, Space, Typography } from 'antd'

import { EmptyState, EntityDetails } from '../../components/platform'
import type {
  DocumentPolicyChainOutput,
  DocumentPolicyDocumentOutput,
  DocumentPolicyOutput,
} from './documentPolicyBuilder'

const { Text } = Typography

type MappingViewerProps = {
  title: string
  entries: Array<[string, string]>
  emptyLabel: string
}

const renderText = (value: string | undefined): string => {
  const normalized = String(value ?? '').trim()
  return normalized || '—'
}

function MappingViewer({ title, entries, emptyLabel }: MappingViewerProps) {
  return (
    <EntityDetails
      title={title}
      empty={entries.length === 0}
      emptyDescription={emptyLabel}
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {entries.map(([target, source]) => (
          <div
            key={`${title}:${target}`}
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(180px, 260px) minmax(0, 1fr)',
              gap: 12,
              alignItems: 'start',
            }}
          >
            <Text strong>{target}</Text>
            <Text code>{source}</Text>
          </div>
        ))}
      </Space>
    </EntityDetails>
  )
}

function DocumentViewer({
  document,
  index,
}: {
  document: DocumentPolicyDocumentOutput
  index: number
}) {
  const fieldMappings = Object.entries(document.field_mapping ?? {})
  const linkRules = Object.entries(document.link_rules ?? {})
  const tableParts = Object.entries(document.table_parts_mapping ?? {})

  return (
    <EntityDetails title={`Document ${index + 1}: ${renderText(document.document_id)}`}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Descriptions
          size="small"
          column={{ xs: 1, md: 2 }}
          items={[
            {
              key: 'entity',
              label: 'Entity',
              children: renderText(document.entity_name),
            },
            {
              key: 'role',
              label: 'Role',
              children: renderText(document.document_role),
            },
            {
              key: 'invoice-mode',
              label: 'Invoice mode',
              children: renderText(document.invoice_mode),
            },
            {
              key: 'link-to',
              label: 'Link to',
              children: renderText(document.link_to),
            },
          ]}
        />

        <MappingViewer
          title="Field mapping"
          entries={fieldMappings}
          emptyLabel="No field mapping configured."
        />

        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text strong>Table-part mapping</Text>
          {tableParts.length === 0 ? (
            <Text type="secondary">No table-part mapping configured.</Text>
          ) : tableParts.map(([tablePart, rowMappings]) => (
            <MappingViewer
              key={tablePart}
              title={`Table part: ${tablePart}`}
              entries={Object.entries(rowMappings)}
              emptyLabel="No row mappings configured."
            />
          ))}
        </Space>

        <MappingViewer
          title="Link rules"
          entries={linkRules}
          emptyLabel="No link rules configured."
        />
      </Space>
    </EntityDetails>
  )
}

function ChainViewer({
  chain,
  index,
}: {
  chain: DocumentPolicyChainOutput
  index: number
}) {
  const documents = Array.isArray(chain.documents) ? chain.documents : []

  return (
    <EntityDetails
      title={`Chain ${index + 1}: ${renderText(chain.chain_id)}`}
      empty={documents.length === 0}
      emptyDescription="No documents configured for this chain."
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {documents.map((document, documentIndex) => (
          <DocumentViewer
            key={`${chain.chain_id}:${document.document_id}:${documentIndex}`}
            document={document}
            index={documentIndex}
          />
        ))}
      </Space>
    </EntityDetails>
  )
}

export function DocumentPolicyViewer({
  policy,
}: {
  policy: DocumentPolicyOutput | null
}) {
  const chains = Array.isArray(policy?.chains) ? policy.chains : []
  const documentsCount = chains.reduce(
    (total, chain) => total + (Array.isArray(chain.documents) ? chain.documents.length : 0),
    0,
  )

  if (!policy || chains.length === 0) {
    return <EmptyState description="No structured document policy data available." />
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Descriptions
        size="small"
        column={{ xs: 1, md: 3 }}
        items={[
          {
            key: 'version',
            label: 'Version',
            children: renderText(policy.version),
          },
          {
            key: 'chains',
            label: 'Chains',
            children: String(chains.length),
          },
          {
            key: 'documents',
            label: 'Documents',
            children: String(documentsCount),
          },
        ]}
      />

      {chains.map((chain, chainIndex) => (
        <ChainViewer
          key={`${chain.chain_id}:${chainIndex}`}
          chain={chain}
          index={chainIndex}
        />
      ))}
    </Space>
  )
}

export default DocumentPolicyViewer
