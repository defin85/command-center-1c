import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

const productionTrackUiActionFiles = [
  'src/components/platform/DrawerFormShell.tsx',
  'src/components/platform/ModalFormShell.tsx',
  'src/components/platform/ModalSurfaceShell.tsx',
  'src/components/platform/RouteButton.tsx',
  'src/components/workflow/PropertyEditor.tsx',
  'src/observability/confirmWithTracking.ts',
  'src/pages/Artifacts/ArtifactDetailsDrawer.tsx',
  'src/pages/DLQ/DLQPage.tsx',
  'src/pages/Databases/components/DatabaseMetadataManagementDrawer.tsx',
  'src/pages/Databases/components/ExtensionsDrawer.tsx',
  'src/pages/Decisions/DecisionEditorPanel.tsx',
  'src/pages/Decisions/DecisionLegacyImportPanel.tsx',
  'src/pages/Pools/PoolCatalogRouteCanvas.tsx',
  'src/pages/Pools/PoolMasterDataPage.tsx',
  'src/pages/Settings/RuntimeSettingsPage.tsx',
]

const asyncTrackUiActionPattern = /trackUiAction\([\s\S]{0,500}?,\s*async\b/

describe('trackUiAction production usage', () => {
  it('keeps shipped callsites on the supported sync or microtask-detached path', () => {
    const matches = productionTrackUiActionFiles
      .map((relativePath) => {
        const absolutePath = join(process.cwd(), relativePath)
        const source = readFileSync(absolutePath, 'utf8')
        return {
          relativePath,
          hasAsyncHandler: asyncTrackUiActionPattern.test(source),
        }
      })
      .filter((entry) => entry.hasAsyncHandler)
      .map((entry) => entry.relativePath)

    expect(matches).toEqual([])
  })
})
