import { describe, expect, it } from 'vitest'

import enPoolFactual from '../locales/en/poolFactual'
import enPools from '../locales/en/pools'
import enWorkflows from '../locales/en/workflows'
import ruPoolFactual from '../locales/ru/poolFactual'
import ruPools from '../locales/ru/pools'
import ruWorkflows from '../locales/ru/workflows'

const collectLeafPaths = (value: unknown, prefix = ''): string[] => {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return prefix ? [prefix] : []
  }

  return Object.entries(value as Record<string, unknown>)
    .flatMap(([key, nested]) => collectLeafPaths(nested, prefix ? `${prefix}.${key}` : key))
    .sort()
}

describe('route namespace parity', () => {
  it('keeps pools locale catalogs aligned between english and russian', () => {
    expect(collectLeafPaths(ruPools)).toEqual(collectLeafPaths(enPools))
  })

  it('keeps factual locale catalogs aligned between english and russian', () => {
    expect(collectLeafPaths(ruPoolFactual)).toEqual(collectLeafPaths(enPoolFactual))
  })

  it('keeps workflows locale catalogs aligned between english and russian', () => {
    expect(collectLeafPaths(ruWorkflows)).toEqual(collectLeafPaths(enWorkflows))
  })
})
