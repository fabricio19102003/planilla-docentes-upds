import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { NO_CLASSES_NOTE, planillaRowNote, portalRowNote } from '../src/lib/closedDesignation.ts'

const root = resolve(import.meta.dirname, '..')
const page = (name) => readFileSync(resolve(root, 'src/pages', name), 'utf8')
const types = readFileSync(resolve(root, 'src/api/types.ts'), 'utf8')

const DATED = 'Sin clases en este período (designación finalizada el 20/09/2026)'

test('portal rows show the backend note only when every amount is zero', () => {
  assert.equal(portalRowNote({ period_note: DATED, gross_payment: 0, net_payment: 0 }), DATED)
  assert.equal(portalRowNote({ period_note: null, gross_payment: 0, net_payment: 0 }), null)
  assert.equal(portalRowNote({ gross_payment: 0, net_payment: 0 }), null)
  assert.equal(portalRowNote({ period_note: DATED, gross_payment: 0, net_payment: 50 }), null)
})

test('admin rows use the dated note, fall back to the plain one and never hide absences', () => {
  const zero = { base_monthly_hours: 0, payable_hours: 0, calculated_payment: 0, final_payment: 0 }
  assert.equal(planillaRowNote({ ...zero, period_note: DATED }), DATED)
  assert.equal(planillaRowNote(zero), NO_CLASSES_NOTE)
  // Absence row: base 12, payable 0 keeps its amount cells.
  assert.equal(planillaRowNote({ ...zero, base_monthly_hours: 12 }), null)
  assert.equal(planillaRowNote({ ...zero, base_monthly_hours: 12, period_note: null }), null)
  assert.equal(planillaRowNote({ ...zero, final_payment: 70 }), null)
  assert.equal(planillaRowNote({ ...zero, final_payment: undefined, calculated_payment: 70 }), null)
})

test('response types carry the optional period_note', () => {
  assert.match(types, /effective_to\?: string \| null\n  period_note\?: string \| null\n\}/)
  assert.match(types, /observations: string\[\]\n  period_note\?: string \| null\n\}/)
})

test('billing page replaces the amounts with the note on cards and table rows', () => {
  const source = page('BillingPage.tsx')
  assert.match(source, /from '@\/lib\/closedDesignation'/)
  assert.match(source, /const periodNote = portalRowNote\(designation\)/)
  assert.match(source, /periodNote \? \(\s*<p className="mt-3 text-sm text-muted-foreground">\{periodNote\}<\/p>/)
  assert.match(source, /portalRowNote\(d\) \? \(\s*<td colSpan=\{hasAdjustments \? 4 : 3\}[^>]*text-muted-foreground/)
})

test('history page replaces the amounts with the note on cards and table rows', () => {
  const source = page('BillingHistoryPage.tsx')
  assert.match(source, /from '@\/lib\/closedDesignation'/)
  assert.match(source, /portalRowNote\(designation\) \? \(\s*<td colSpan=\{billing\.has_admin_override \? 4 : 3\}[^>]*text-muted-foreground/)
  assert.match(source, /portalRowNote\(designation\) \? \(\s*<p className="mt-2 text-muted-foreground">/)
})

test('theory and practice admin planilla replace the amount cells with the note', () => {
  const theory = page('PlanillaPage.tsx')
  assert.match(theory, /from '@\/lib\/closedDesignation'/)
  assert.equal(theory.match(/planillaRowNote\((d|row)\) \? \(/g)?.length, 2)
  const practice = page('PracticaPlanillaContent.tsx')
  assert.match(practice, /from '@\/lib\/closedDesignation'/)
  assert.equal(practice.match(/planillaRowNote\(row\) \? \(/g)?.length, 2)
  assert.match(practice, /<TableCell colSpan=\{3\} className="text-right text-muted-foreground">\{planillaRowNote\(row\)\}/)
})
