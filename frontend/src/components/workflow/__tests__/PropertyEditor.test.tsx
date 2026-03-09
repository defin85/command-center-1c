import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp } from 'antd'

import type { OperationTemplateListItem, WorkflowNodeData } from '../../../types/workflow'
import PropertyEditor from '../PropertyEditor'

vi.mock('../../code/LazyJsonCodeEditor', () => ({
  LazyJsonCodeEditor: ({ id, value }: { id?: string; value?: string }) => (
    <textarea data-testid={id} value={value} readOnly />
  ),
}))

const renderEditor = ({
  nodeId,
  nodeData,
  onNodeUpdate = vi.fn(),
  availableWorkflows = [],
  availableDecisions = [],
  operationTemplates = [],
}: {
  nodeId: string
  nodeData: WorkflowNodeData
  onNodeUpdate?: ReturnType<typeof vi.fn>
  availableWorkflows?: Array<{
    id: string
    name: string
    workflowDefinitionKey: string
    workflowRevisionId: string
    workflowRevision: number
  }>
  availableDecisions?: Array<{
    id: string
    name: string
    decisionTableId: string
    decisionKey: string
    decisionRevision: number
  }>
  operationTemplates?: OperationTemplateListItem[]
}) => {
  render(
    <AntApp>
      <PropertyEditor
        nodeId={nodeId}
        nodeData={nodeData}
        onNodeUpdate={onNodeUpdate as (nodeId: string, data: Partial<WorkflowNodeData>) => void}
        onNodeDelete={vi.fn()}
        operationTemplates={operationTemplates}
        availableWorkflows={availableWorkflows}
        availableDecisions={availableDecisions}
      />
    </AntApp>
  )
  return { onNodeUpdate }
}

const openSelect = async (testId: string) => {
  const select = await screen.findByTestId(testId)
  const selector = select.querySelector('.ant-select-selector')
  expect(selector).toBeTruthy()
  fireEvent.mouseDown(selector as Element)
}

describe('PropertyEditor', () => {
  it('pins decision_ref and synthesizes compatibility expression for condition nodes', async () => {
    const { onNodeUpdate } = renderEditor({
      nodeId: 'decision-node',
      nodeData: {
        label: 'Invoice Mode',
        nodeType: 'condition',
        config: {
          expression: '{{ amount > 100 }}',
        },
      },
      availableDecisions: [
        {
          id: 'decision-version-1',
          name: 'Invoice Mode',
          decisionTableId: 'decision-table-1',
          decisionKey: 'invoice_mode',
          decisionRevision: 2,
        },
      ],
    })

    await openSelect('workflow-decision-node-condition-decision')
    fireEvent.click(await screen.findByText('Invoice Mode (invoice_mode) · r2'))

    await waitFor(() => {
      expect(onNodeUpdate).toHaveBeenCalledWith(
        'decision-node',
        expect.objectContaining({
          decisionRef: {
            decision_table_id: 'decision-table-1',
            decision_key: 'invoice_mode',
            decision_revision: 2,
          },
          config: expect.objectContaining({
            expression: '{{ decisions.invoice_mode }}',
          }),
        })
      )
    })

    expect(await screen.findByDisplayValue('{{ decisions.invoice_mode }}')).toBeDisabled()
  })

  it('pins workflow revision metadata for subworkflow nodes', async () => {
    const { onNodeUpdate } = renderEditor({
      nodeId: 'subworkflow-node',
      nodeData: {
        label: 'Child Flow',
        nodeType: 'subworkflow',
        config: {},
      },
      availableWorkflows: [
        {
          id: 'workflow-revision-7',
          name: 'Services Publication',
          workflowDefinitionKey: 'workflow-root-1',
          workflowRevisionId: 'workflow-revision-7',
          workflowRevision: 7,
        },
      ],
    })

    await openSelect('workflow-subworkflow-node-subworkflow')
    fireEvent.click(await screen.findByText('Services Publication · r7'))

    await waitFor(() => {
      expect(onNodeUpdate).toHaveBeenCalledWith(
        'subworkflow-node',
        expect.objectContaining({
          config: expect.objectContaining({
            subworkflow_id: 'workflow-revision-7',
            subworkflow_ref: {
              binding_mode: 'pinned_revision',
              workflow_definition_key: 'workflow-root-1',
              workflow_revision_id: 'workflow-revision-7',
              workflow_revision: 7,
            },
          }),
        })
      )
    })
  })

  it('renders execution contract summary and validates required template inputs for operation nodes', async () => {
    renderEditor({
      nodeId: 'operation-node',
      nodeData: {
        label: 'Sync Extension',
        nodeType: 'operation',
        templateId: 'tpl-sync-extension',
        io: {
          mode: 'explicit_strict',
          input_mapping: {
            'params.database_id': 'workflow.input.database_id',
          },
          output_mapping: {},
        },
        config: {},
      },
      operationTemplates: [
        {
          id: 'tpl-sync-extension',
          name: 'Sync Extension',
          operation_type: 'designer_cli',
          exposure_id: 'template-exposure-1',
          exposure_revision: 4,
          executionContract: {
            contractVersion: 'workflow_template_execution_contract.v1',
            capability: {
              id: 'extensions.sync',
              label: 'Sync Extension',
              operationType: 'designer_cli',
              targetEntity: 'infobase',
              executorKind: 'designer_cli',
            },
            input: {
              mode: 'params',
              requiredParameters: ['database_id', 'extension_name'],
              optionalParameters: ['timeout_seconds'],
              parameterSchemas: {
                database_id: { type: 'uuid', description: 'Database identifier', required: true },
                extension_name: { type: 'string', description: 'Extension name', required: true },
                timeout_seconds: { type: 'integer', description: 'Timeout', required: false },
              },
            },
            output: {
              resultPath: 'result',
              supportsStructuredMapping: true,
            },
            sideEffect: {
              executionMode: 'async',
              effectKind: 'mutating',
              summary: 'Updates extension state in the target infobase.',
              timeoutSeconds: 900,
              maxRetries: 5,
            },
            provenance: {
              surface: 'template',
              alias: 'tpl-sync-extension',
              exposureId: 'template-exposure-1',
              exposureRevision: 4,
              definitionId: 'definition-1',
              executorCommandId: 'infobase.extension.sync',
            },
          },
        },
      ],
    })

    expect(await screen.findByText('Execution contract')).toBeInTheDocument()
    expect(screen.getByText('extensions.sync')).toBeInTheDocument()
    expect(screen.getByText('designer_cli -> infobase')).toBeInTheDocument()
    expect(screen.getByText('Updates extension state in the target infobase.')).toBeInTheDocument()
    expect(screen.getByText('Missing required mappings: params.extension_name')).toBeInTheDocument()
  })
})
