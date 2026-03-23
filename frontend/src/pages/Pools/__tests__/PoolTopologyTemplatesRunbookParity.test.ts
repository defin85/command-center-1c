import { readFile } from 'node:fs/promises'
import { describe, expect, it } from 'vitest'

const readText = async (relativePath: string): Promise<string> => (
  readFile(new URL(relativePath, import.meta.url).pathname, 'utf8')
)

describe('pool topology template runbook parity', () => {
  it('keeps the release note and runbook aligned on the dedicated producer workspace and return handoff', async () => {
    const runbook = await readText('../../../../../docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md')
    const releaseNote = await readText('../../../../../docs/release-notes/2026-03-22-pool-topology-templates.md')

    expect(releaseNote).toContain('dedicated reusable topology template workspace `/pools/topology-templates`')
    expect(releaseNote).toContain('`Create template` публикует новый reusable topology template')
    expect(releaseNote).toContain('`Publish new revision` создаёт следующую immutable revision')
    expect(releaseNote).toContain('`Return to pool topology`')
    expect(releaseNote).toContain('`/pools/catalog` остаётся consumer/assembly surface')

    expect(runbook).toContain('- Reusable topology template catalog: `/pools/topology-templates`')
    expect(runbook).toContain('`/pools/topology-templates` является canonical producer surface')
    expect(runbook).toContain('переходи в `/pools/topology-templates`')
    expect(runbook).toContain('`Return to pool topology`')
    expect(runbook).toContain('Во вкладке `Topology Editor` в `/pools/catalog`')
  })
})
