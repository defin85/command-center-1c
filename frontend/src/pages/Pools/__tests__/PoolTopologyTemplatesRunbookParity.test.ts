import { readFile } from 'node:fs/promises'
import { describe, expect, it } from 'vitest'

const readText = async (relativePath: string): Promise<string> => (
  readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
)

describe('pool topology template runbook parity', () => {
  it('documents the reusable producer workspace and return handoff for pool topology authoring', async () => {
    const runbook = await readText('../../../../../docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md')

    expect(runbook).toContain('- Reusable topology template catalog: `/pools/topology-templates`')
    expect(runbook).toContain('`/pools/topology-templates` является canonical producer surface')
    expect(runbook).toContain('переходи в `/pools/topology-templates`')
    expect(runbook).toContain('`Return to pool topology`')
    expect(runbook).toContain('Во вкладке `Topology Editor` в `/pools/catalog`')
  })
})
