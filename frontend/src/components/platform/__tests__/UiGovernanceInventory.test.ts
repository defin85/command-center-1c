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
const appSourceDir = path.dirname(appSourcePath)

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
  return collectAppRouteEntries().map((entry) => entry.routePath).sort()
}

function createAppSourceFile() {
  const content = readFileSync(appSourcePath, 'utf8')
  return ts.createSourceFile(appSourcePath, content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
}

function extractStaticStringAttribute(attributes, attributeName) {
  for (const attribute of attributes.properties) {
    if (!ts.isJsxAttribute(attribute) || attribute.name.text !== attributeName || !attribute.initializer) {
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

function getJsxExpressionAttribute(attributes, attributeName) {
  for (const attribute of attributes.properties) {
    if (!ts.isJsxAttribute(attribute) || attribute.name.text !== attributeName || !attribute.initializer) {
      continue
    }

    if (ts.isJsxExpression(attribute.initializer)) {
      return attribute.initializer.expression ?? null
    }
  }

  return null
}

function resolveSourceModulePath(moduleSpecifier: string) {
  const basePath = path.resolve(appSourceDir, moduleSpecifier)
  const candidates = [
    `${basePath}.tsx`,
    `${basePath}.ts`,
    path.join(basePath, 'index.tsx'),
    path.join(basePath, 'index.ts'),
  ]

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return path.relative(frontendRoot, candidate).replace(/\\/g, '/')
    }
  }

  return null
}

function findImportSpecifier(node) {
  let specifier = null

  const visit = (current) => {
    if (specifier) {
      return
    }

    if (
      ts.isCallExpression(current)
      && current.expression.kind === ts.SyntaxKind.ImportKeyword
      && current.arguments.length > 0
      && ts.isStringLiteralLike(current.arguments[0])
    ) {
      specifier = current.arguments[0].text
      return
    }

    ts.forEachChild(current, visit)
  }

  visit(node)
  return specifier
}

function collectLazyRouteModules(sourceFile) {
  const declarationBodies = new Map()
  const lazyModules = new Map()

  const registerDeclarationBody = (name, body) => {
    declarationBodies.set(name, body)
  }

  const visitDeclarations = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      registerDeclarationBody(node.name.text, node.initializer)
    }

    if (ts.isFunctionDeclaration(node) && node.name && node.body) {
      registerDeclarationBody(node.name.text, node.body)
    }

    ts.forEachChild(node, visitDeclarations)
  }

  const resolveLazyArgument = (arg) => {
    if (ts.isArrowFunction(arg) || ts.isFunctionExpression(arg)) {
      return findImportSpecifier(arg.body)
    }

    if (ts.isIdentifier(arg)) {
      const declarationBody = declarationBodies.get(arg.text)
      return declarationBody ? findImportSpecifier(declarationBody) : null
    }

    return null
  }

  const visitLazyDeclarations = (node) => {
    if (
      ts.isVariableDeclaration(node)
      && ts.isIdentifier(node.name)
      && node.initializer
      && ts.isCallExpression(node.initializer)
      && ts.isIdentifier(node.initializer.expression)
      && node.initializer.expression.text === 'lazy'
      && node.initializer.arguments.length > 0
    ) {
      const moduleSpecifier = resolveLazyArgument(node.initializer.arguments[0])
      if (moduleSpecifier) {
        const modulePath = resolveSourceModulePath(moduleSpecifier)
        if (modulePath) {
          lazyModules.set(node.name.text, modulePath)
        }
      }
    }

    ts.forEachChild(node, visitLazyDeclarations)
  }

  visitDeclarations(sourceFile)
  visitLazyDeclarations(sourceFile)
  return lazyModules
}

function findRouteEntryModulePath(node, sourceFile, lazyModules) {
  if (!node) {
    return undefined
  }

  if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
    const tagName = node.tagName.getText(sourceFile)
    if (tagName === 'Navigate') {
      return null
    }
    if (lazyModules.has(tagName)) {
      return lazyModules.get(tagName)
    }
  }

  let result
  const visit = (current) => {
    if (result !== undefined) {
      return
    }

    const resolved = findRouteEntryModulePath(current, sourceFile, lazyModules)
    if (resolved !== undefined) {
      result = resolved
      return
    }

    ts.forEachChild(current, visit)
  }

  ts.forEachChild(node, visit)
  return result
}

function collectAppRouteEntries() {
  const sourceFile = createAppSourceFile()
  const lazyModules = collectLazyRouteModules(sourceFile)
  const routes = []

  const visit = (node) => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sourceFile) === 'Route') {
      const routePath = extractStaticStringAttribute(node.attributes, 'path')
      if (!routePath) {
        throw new Error('App route path must stay a static string literal for governance checks')
      }

      const routeElementExpression = getJsxExpressionAttribute(node.attributes, 'element')
      const modulePath = findRouteEntryModulePath(routeElementExpression, sourceFile, lazyModules)
      if (modulePath === undefined) {
        throw new Error(`Could not resolve route entry module for ${routePath}`)
      }

      routes.push({ routePath, modulePath })
    }

    ts.forEachChild(node, visit)
  }

  visit(sourceFile)
  return routes
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

  it('keeps inventory routePath to modulePath wiring aligned with App.tsx', () => {
    const appRouteEntries = collectAppRouteEntries().sort((left, right) => left.routePath.localeCompare(right.routePath))
    const inventoryRouteEntries = routeGovernanceInventory
      .map((entry) => ({ routePath: entry.routePath, modulePath: entry.modulePath ?? null }))
      .sort((left, right) => left.routePath.localeCompare(right.routePath))

    expect(appRouteEntries).toEqual(inventoryRouteEntries)
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
