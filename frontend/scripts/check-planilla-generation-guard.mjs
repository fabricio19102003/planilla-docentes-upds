import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  buildConfirmSummary,
  DISCOUNT_MODE_LABELS,
  formatDisplayDate,
  formatGenerationSummary,
  getGenerationGuard,
  optionalDate,
  resolveDiscountMode,
} from '../src/lib/planillaGenerationGuard.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const theoryPage = read('src/pages/PlanillaPage.tsx')
const practicePage = read('src/pages/PracticaPlanillaContent.tsx')
const dialog = read('src/components/shared/ConfirmActionDialog.tsx')

const bs = (value) => value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

test('missing start date blocks generation with the date reason', () => {
  const guard = getGenerationGuard({ startDate: '', endDate: '2026-10-20', mode: 'attendance' })
  assert.equal(guard.canGenerate, false)
  assert.deepEqual(guard.reasons, ['Completá las fechas de corte'])
})

test('missing end date blocks generation with the date reason', () => {
  const guard = getGenerationGuard({ startDate: '2026-09-21', endDate: '', mode: 'full' })
  assert.equal(guard.canGenerate, false)
  assert.deepEqual(guard.reasons, ['Completá las fechas de corte'])
})

test('start after end blocks generation', () => {
  const guard = getGenerationGuard({ startDate: '2026-10-21', endDate: '2026-10-20', mode: 'attendance' })
  assert.equal(guard.canGenerate, false)
  assert.deepEqual(guard.reasons, ['La fecha de inicio no puede ser posterior a la fecha de fin'])
})

test('start equal to end is allowed', () => {
  const guard = getGenerationGuard({ startDate: '2026-10-20', endDate: '2026-10-20', mode: 'attendance' })
  assert.equal(guard.canGenerate, true)
  assert.deepEqual(guard.reasons, [])
})

test('no mode blocks generation with the mode reason', () => {
  const guard = getGenerationGuard({ startDate: '2026-09-21', endDate: '2026-10-20', mode: null })
  assert.equal(guard.canGenerate, false)
  assert.deepEqual(guard.reasons, ['Elegí el modo de cálculo'])
})

test('missing dates and mode report both reasons, dates first', () => {
  const guard = getGenerationGuard({ startDate: '', endDate: '', mode: null })
  assert.equal(guard.canGenerate, false)
  assert.deepEqual(guard.reasons, ['Completá las fechas de corte', 'Elegí el modo de cálculo'])
})

test('a loading stored-planilla status blocks generation', () => {
  const guard = getGenerationGuard({ startDate: '2026-09-21', endDate: '2026-10-20', mode: 'full', statusLoading: true })
  assert.equal(guard.canGenerate, false)
  assert.equal(guard.reasons.length, 1)
})

test('valid dates and mode allow generation', () => {
  const guard = getGenerationGuard({ startDate: '2026-09-21', endDate: '2026-10-20', mode: 'full' })
  assert.deepEqual(guard, { canGenerate: true, reasons: [] })
})

test('no stored planilla and no manual choice resolves to no mode', () => {
  assert.equal(resolveDiscountMode({ manualMode: null, storedMode: null }), null)
  assert.equal(resolveDiscountMode({ manualMode: null, storedMode: undefined }), null)
  assert.equal(resolveDiscountMode({ manualMode: null, storedMode: 'bogus' }), null)
})

test('stored planilla mode is preselected', () => {
  assert.equal(resolveDiscountMode({ manualMode: null, storedMode: 'full' }), 'full')
  assert.equal(resolveDiscountMode({ manualMode: null, storedMode: 'attendance' }), 'attendance')
})

test('a manual choice wins over the stored mode', () => {
  assert.equal(resolveDiscountMode({ manualMode: 'attendance', storedMode: 'full' }), 'attendance')
  assert.equal(resolveDiscountMode({ manualMode: 'full', storedMode: null }), 'full')
})

test('mode labels are the two named options', () => {
  assert.equal(DISCOUNT_MODE_LABELS.attendance, 'Con descuentos por asistencia')
  assert.equal(DISCOUNT_MODE_LABELS.full, 'Sin descuentos (pago completo)')
})

test('dates are shown as dd/mm/yyyy without timezone shifts', () => {
  assert.equal(formatDisplayDate('2026-09-21'), '21/09/2026')
  assert.equal(formatDisplayDate('2026-01-01'), '01/01/2026')
  assert.equal(formatDisplayDate(''), '—')
  assert.equal(formatDisplayDate(null), '—')
})

test('generation summary has the exact agreed format', () => {
  assert.equal(
    formatGenerationSummary({
      kind: 'teoricas', month: 10, year: 2026, startDate: '2026-09-21', endDate: '2026-10-20', mode: 'attendance',
    }),
    'Se generará: Teóricas · Octubre 2026 · 21/09/2026–20/10/2026 · Con descuentos por asistencia',
  )
  assert.equal(
    formatGenerationSummary({
      kind: 'practicas', month: 1, year: 2027, startDate: '2026-12-21', endDate: '2027-01-20', mode: 'full',
    }),
    'Se generará: Prácticas · Enero 2027 · 21/12/2026–20/01/2027 · Sin descuentos (pago completo)',
  )
})

test('generate confirmation lists planilla, period, cutoff and mode', () => {
  const summary = buildConfirmSummary({
    action: 'generate', kind: 'teoricas', month: 10, year: 2026,
    startDate: '2026-09-21', endDate: '2026-10-20', mode: 'full',
  })
  const rows = Object.fromEntries(summary.rows.map((row) => [row.label, row.value]))
  assert.equal(rows['Planilla'], 'Teóricas')
  assert.equal(rows['Período'], 'Octubre 2026')
  assert.equal(rows['Corte'], '21/09/2026–20/10/2026')
  assert.equal(rows['Modo'], 'Sin descuentos (pago completo)')
  assert.equal('Docentes' in rows, false)
  assert.equal('Total (Bs)' in rows, false)
  assert.equal(summary.warning, null)
})

test('confirmation includes docentes and total when provided', () => {
  const summary = buildConfirmSummary({
    action: 'approve', kind: 'practicas', month: 10, year: 2026,
    startDate: '2026-09-21', endDate: '2026-10-20', mode: 'attendance',
    docentes: 42, totalPayment: 12345.5,
  })
  const rows = Object.fromEntries(summary.rows.map((row) => [row.label, row.value]))
  assert.equal(rows['Planilla'], 'Prácticas')
  assert.equal(rows['Docentes'], '42')
  assert.equal(rows['Total (Bs)'], bs(12345.5))
})

test('generate over a stored planilla warns that it replaces it', () => {
  const summary = buildConfirmSummary({
    action: 'generate', kind: 'teoricas', month: 10, year: 2026,
    startDate: '2026-09-21', endDate: '2026-10-20', mode: 'attendance',
    hasStoredPlanilla: true,
  })
  assert.match(summary.warning, /reemplazar/)
})

test('publish and unpublish state their consequence', () => {
  const base = {
    kind: 'teoricas', month: 10, year: 2026,
    startDate: '2026-09-21', endDate: '2026-10-20', mode: 'attendance',
  }
  assert.match(buildConfirmSummary({ ...base, action: 'publish' }).consequence, /^Los docentes verán/)
  assert.match(buildConfirmSummary({ ...base, action: 'unpublish' }).consequence, /^Los docentes dejarán de ver/)
})

test('reject is a destructive-toned confirmation', () => {
  const summary = buildConfirmSummary({
    action: 'reject', kind: 'teoricas', month: 10, year: 2026,
    startDate: '2026-09-21', endDate: '2026-10-20', mode: 'attendance',
  })
  assert.equal(summary.tone, 'destructive')
  assert.equal(summary.confirmLabel, 'Rechazar')
})

test('confirm dialog is built on the shadcn dialog primitives', () => {
  assert.match(dialog, /@\/components\/ui\/dialog/)
  assert.match(dialog, /export function ConfirmActionDialog/)
})

for (const [name, source] of [['PlanillaPage', theoryPage], ['PracticaPlanillaContent', practicePage]]) {
  test(`${name} uses the generation guard and the confirm dialog`, () => {
    assert.match(source, /@\/lib\/planillaGenerationGuard/)
    assert.match(source, /ConfirmActionDialog/)
    assert.match(source, /getGenerationGuard\(/)
    assert.match(source, /formatGenerationSummary\(/)
    assert.match(source, /buildConfirmSummary\(/)
  })

  test(`${name} never sends undefined cutoff dates when generating`, () => {
    assert.equal(source.includes('startDate || undefined'), false)
    assert.equal(source.includes('endDate || undefined'), false)
  })

  test(`${name} no longer renders the unlabeled discount switch`, () => {
    assert.doesNotMatch(source, /role="switch"/)
    assert.match(source, /role="radiogroup"/)
    assert.match(source, /DISCOUNT_MODE_LABELS/)
  })

  test(`${name} shows an explicit detail error state with retry`, () => {
    assert.match(source, /No se pudo cargar el detalle de la planilla\./)
    assert.match(source, /Reintentar/)
    assert.match(source, /detailQuery\.refetch\(\)/)
    assert.match(source, /detailQuery\.isError/)
  })

  test(`${name} routes every payroll action through the confirmation`, () => {
    for (const action of ['generate', 'approve', 'reject', 'publish', 'unpublish']) {
      assert.match(source, new RegExp(`requestConfirm\\('${action}'\\)`), `${name} must confirm ${action}`)
    }
    assert.doesNotMatch(source, /onClick=\{\(\) => approvePlanilla\.mutate/)
    assert.doesNotMatch(source, /onClick=\{\(\) => rejectPlanilla\.mutate/)
    assert.doesNotMatch(source, /onClick=\{\(\) => publishBilling\.mutate/)
    assert.doesNotMatch(source, /onClick=\{\(\) => unpublishBilling\.mutate/)
    assert.doesNotMatch(source, /onClick=\{handleGenerate\}/)
  })
}

test('optionalDate maps blank dates to undefined for read-only queries', () => {
  assert.equal(optionalDate(''), undefined)
  assert.equal(optionalDate('2026-09-21'), '2026-09-21')
})
