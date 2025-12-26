import { test, expect } from '@playwright/test'

const PAGES = ['/', '/operations', '/databases', '/clusters', '/rbac', '/workflows']

const extractIssues = () => {
  const results = {
    duplicates: [] as Array<{ formIndex: number; id: string }>,
    missing: [] as Array<{ formIndex: number; tag: string; type: string }>,
  }

  const forms = Array.from(document.querySelectorAll('form'))
  forms.forEach((form, formIndex) => {
    const inputs = Array.from(form.querySelectorAll('input, select, textarea'))
      .filter((el) => (el instanceof HTMLInputElement ? el.type !== 'hidden' : true))

    const idMap = new Set<string>()
    inputs.forEach((el) => {
      const id = el.getAttribute('id')?.trim()
      const name = el.getAttribute('name')?.trim()
      if (!id && !name) {
        results.missing.push({
          formIndex,
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
        })
      }
      if (id) {
        if (idMap.has(id)) {
          results.duplicates.push({ formIndex, id })
        } else {
          idMap.add(id)
        }
      }
    })
  })

  return results
}

test.describe('Form field ids', () => {
  for (const path of PAGES) {
    test(`no duplicate ids or missing id/name in ${path}`, async ({ page }) => {
      await page.goto(path, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector('form', { timeout: 10_000 })

      const issues = await page.evaluate(extractIssues)

      expect(issues.duplicates, `Duplicate ids found on ${path}`).toEqual([])
      expect(issues.missing, `Missing id/name fields found on ${path}`).toEqual([])
    })
  }
})
