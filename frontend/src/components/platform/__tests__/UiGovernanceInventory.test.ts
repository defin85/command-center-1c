import path from 'node:path'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'

import * as ts from 'typescript'
import { describe, expect, it } from 'vitest'

import {
  detailMobileFallbackKinds,
  governanceTiers,
  routeGovernanceInventory,
  routeStateTransports,
  shellSurfaceGovernanceInventory,
} from '../../../uiGovernanceInventory.js'

const frontendRoot = path.resolve(__dirname, '../../../..')
const appSourcePath = path.join(frontendRoot, 'src/App.tsx')

function collectSourceFiles(rootPath: string): string[] {
  const entries = readdirSync(rootPath)
  return entries.flatMap((entry) => {
    const absoluteEntry = path.join(rootPath, entry)
    const relativeEntry = path.relative(frontendRoot, absoluteEntry)
    const stat = statSync(absoluteEntry)

    if (stat.isDirectory()) {
      if (entry === '__tests__' || entry === 'dist') {
        return []
      }
      return collectSourceFiles(absoluteEntry)
    }

    if (!/\.(ts|tsx)$/.test(entry) || /\.test\.(ts|tsx)$/.test(entry)) {
      return []
    }

    return [relativeEntry]
  })
}

function collectAppRoutePaths() {
  const content = readFileSync(appSourcePath, 'utf8')
  const sourceFile = ts.createSourceFile(appSourcePath, content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const routePaths = []

  const extractStaticPathAttribute = (attributes) => {
    for (const attribute of attributes.properties) {
      if (!ts.isJsxAttribute(attribute) || attribute.name.text !== 'path' || !attribute.initializer) {
        continue
      }

      if (ts.isStringLiteral(attribute.initializer)) {
        return attribute.initializer.text
      }

      if (
        ts.isJsxExpression(attribute.initializer)
        && attribute.initializer.expression
        && ts.isStringLiteral(attribute.initializer.expression)
      ) {
        return attribute.initializer.expression.text
      }
    }

    return null
  }

  const visit = (node) => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sourceFile) === 'Route') {
      const routePath = extractStaticPathAttribute(node.attributes)
      if (routePath) {
        routePaths.push(routePath)
      }
    }

    ts.forEachChild(node, visit)
  }

  visit(sourceFile)
  return routePaths.sort()
}

function collectPlatformShellSurfaceUsage() {
  return collectSourceFiles(path.join(frontendRoot, 'src'))
    .filter((relativePath) => !relativePath.startsWith('src/components/platform/'))
    .map((relativePath) => {
      const content = readFileSync(path.join(frontendRoot, relativePath), 'utf8')
      const shellKinds = []
      if (content.includes('ModalFormShell')) {
        shellKinds.push('modal')
      }
      if (content.includes('DrawerFormShell')) {
        shellKinds.push('drawer')
      }
      if (shellKinds.length === 0) {
        return null
      }
      return {
        filePath: relativePath,
        shellKinds: shellKinds.sort(),
      }
    })
    .filter(Boolean)
}

describe('ui governance inventory', () => {
  it('covers every route path declared in App.tsx', () => {
    const appRoutePaths = collectAppRoutePaths()
    const inventoryRoutePaths = routeGovernanceInventory.map((entry) => entry.routePath).sort()

    expect(inventoryRoutePaths).toEqual(appRoutePaths)
    expect(new Set(inventoryRoutePaths).size).toBe(inventoryRoutePaths.length)
  })

  it('keeps route entries on valid tiers and existing source modules', () => {
    for (const entry of routeGovernanceInventory) {
      expect(governanceTiers).toContain(entry.tier)
      if (!entry.modulePath) {
        expect(entry.tier).toBe('excluded')
        expect(typeof entry.redirectTarget).toBe('string')
        continue
      }

      expect(existsSync(path.join(frontendRoot, entry.modulePath))).toBe(true)
    }
  })

  it('requires route semantics metadata for platform-governed route entries', () => {
    for (const entry of routeGovernanceInventory.filter((candidate) => candidate.tier === 'platform-governed')) {
      expect(typeof entry.workspaceKind).toBe('string')
      expect(routeStateTransports).toContain(entry.stateTransport)
      expect(detailMobileFallbackKinds).toContain(entry.detailMobileFallback)
      expect(typeof entry.lintProfile).toBe('string')
    }
  })

  it('keeps shell-backed inventory aligned with current platform shell usages', () => {
    const actualUsage = collectPlatformShellSurfaceUsage()
    const actualFiles = actualUsage.map((entry) => entry.filePath).sort()
    const inventoryFiles = shellSurfaceGovernanceInventory.map((entry) => entry.filePath).sort()

    expect(inventoryFiles).toEqual(actualFiles)
    expect(new Set(inventoryFiles).size).toBe(inventoryFiles.length)

    const actualUsageByFile = new Map(actualUsage.map((entry) => [entry.filePath, entry.shellKinds]))
    for (const entry of shellSurfaceGovernanceInventory) {
      expect(governanceTiers).toContain(entry.tier)
      expect(existsSync(path.join(frontendRoot, entry.filePath))).toBe(true)
      expect([...entry.shellKinds].sort()).toEqual(actualUsageByFile.get(entry.filePath))
    }
  })
})
