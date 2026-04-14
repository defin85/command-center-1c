import { Descriptions, Space, Typography } from 'antd'

import { EmptyState, EntityDetails } from '../../components/platform'
import { useDecisionsTranslation } from '../../i18n'
import type {
  DocumentPolicyChainOutput,
  DocumentPolicyDocumentOutput,
  DocumentPolicyMappingValue,
  DocumentPolicyOutput,
} from './documentPolicyBuilder'

const { Text } = Typography

type MappingViewerProps = {
  title: string
  entries: Array<[string, DocumentPolicyMappingValue]>
  emptyLabel: string
}

const renderText = (value: string | undefined): string => {
  const normalized = String(value ?? '').trim()
  return normalized || '—'
}

const renderMappingValue = (value: DocumentPolicyMappingValue | undefined): string => {
  if (typeof value === 'string') {
    return value === '' ? '""' : value
  }
  return JSON.stringify(value)
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
            <Text code>{renderMappingValue(source)}</Text>
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
  const { t } = useDecisionsTranslation()
  const fieldMappings = Object.entries(document.field_mapping ?? {})
  const linkRules = Object.entries(document.link_rules ?? {})
  const tableParts = Object.entries(document.table_parts_mapping ?? {})

  return (
    <EntityDetails title={t(($) => $.viewer.documentTitle, { index: String(index + 1), id: renderText(document.document_id) })}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Descriptions
          size="small"
          column={{ xs: 1, md: 2 }}
          items={[
            {
              key: 'entity',
              label: t(($) => $.viewer.entity),
              children: renderText(document.entity_name),
            },
            {
              key: 'role',
              label: t(($) => $.viewer.role),
              children: renderText(document.document_role),
            },
            {
              key: 'invoice-mode',
              label: t(($) => $.viewer.invoiceMode),
              children: renderText(document.invoice_mode),
            },
            {
              key: 'link-to',
              label: t(($) => $.viewer.linkTo),
              children: renderText(document.link_to),
            },
          ]}
        />

        <MappingViewer
          title={t(($) => $.viewer.fieldMapping)}
          entries={fieldMappings}
          emptyLabel={t(($) => $.viewer.noFieldMapping)}
        />

        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Text strong>{t(($) => $.viewer.tablePartMapping)}</Text>
          {tableParts.length === 0 ? (
            <Text type="secondary">{t(($) => $.viewer.noTablePartMapping)}</Text>
          ) : tableParts.map(([tablePart, rowMappings]) => (
            rowMappings.length === 0 ? (
              <EntityDetails
                key={tablePart}
                title={t(($) => $.viewer.tablePartTitle, { name: tablePart })}
                empty
                emptyDescription={t(($) => $.viewer.noRowMappings)}
              />
            ) : rowMappings.map((rowMapping, rowIndex) => (
              <MappingViewer
                key={`${tablePart}:${rowIndex}`}
                title={rowMappings.length > 1
                  ? t(($) => $.viewer.tablePartRowTitle, { name: tablePart, row: String(rowIndex + 1) })
                  : t(($) => $.viewer.tablePartTitle, { name: tablePart })}
                entries={Object.entries(rowMapping)}
                emptyLabel={t(($) => $.viewer.noRowMappings)}
              />
            ))
          ))}
        </Space>

        <MappingViewer
          title={t(($) => $.viewer.linkRules)}
          entries={linkRules}
          emptyLabel={t(($) => $.viewer.noLinkRules)}
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
  const { t } = useDecisionsTranslation()
  const documents = Array.isArray(chain.documents) ? chain.documents : []

  return (
    <EntityDetails
      title={t(($) => $.viewer.chainTitle, { index: String(index + 1), id: renderText(chain.chain_id) })}
      empty={documents.length === 0}
      emptyDescription={t(($) => $.viewer.chainEmpty)}
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
  const { t } = useDecisionsTranslation()
  const chains = Array.isArray(policy?.chains) ? policy.chains : []
  const documentsCount = chains.reduce(
    (total, chain) => total + (Array.isArray(chain.documents) ? chain.documents.length : 0),
    0,
  )

  if (!policy || chains.length === 0) {
    return <EmptyState description={t(($) => $.viewer.noStructuredData)} />
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Descriptions
        size="small"
        column={{ xs: 1, md: 3 }}
        items={[
          {
            key: 'version',
            label: t(($) => $.viewer.version),
            children: renderText(policy.version),
          },
          {
            key: 'chains',
            label: t(($) => $.viewer.chains),
            children: String(chains.length),
          },
          {
            key: 'documents',
            label: t(($) => $.viewer.documents),
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
