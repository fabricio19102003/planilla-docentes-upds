import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const billingPage = readFileSync(resolve(root, 'src/pages/BillingPage.tsx'), 'utf8')
const historyPage = readFileSync(resolve(root, 'src/pages/BillingHistoryPage.tsx'), 'utf8')
const retentionPage = readFileSync(resolve(root, 'src/pages/RetentionLetterPage.tsx'), 'utf8')

// Source text of a top-level `function Name` up to the next top-level function (or EOF).
function functionSource(source, name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `function ${name} must exist`)
  const next = source.indexOf('\nfunction ', start + 1)
  return source.slice(start, next === -1 ? undefined : next)
}

// ─── S2: hero eyebrow ────────────────────────────────────────────────────────

test('S2 hero eyebrow reads "Teóricas — mes año" or "Prácticas Internas — mes año"', () => {
  const card = functionSource(billingPage, 'BillingCard')
  assert.match(card, /isPractice \? 'Prácticas Internas' : 'Teóricas'\} — \{billing\.month_name\} \{billing\.year\}/)
})

test('S2 "Facturación" is no longer used as the hero eyebrow', () => {
  const card = functionSource(billingPage, 'BillingCard')
  assert.doesNotMatch(card, /'Facturación'\} —/)
  assert.doesNotMatch(card, /Facturación\s*—/)
})

test('S2 keeps the invoice instruction headline, amount, note and retention letter link', () => {
  const card = functionSource(billingPage, 'BillingCard')
  assert.match(card, /instruction\.headline/)
  assert.match(card, /formatBs\(displayPayment\)/)
  assert.match(card, /instruction\.note/)
  assert.match(card, /RETENTION_LETTER_PATH/)
})

// ─── S3: cutoff in hero ──────────────────────────────────────────────────────

test('S3 hero shows "Corte: <start> al <end>" using formatPortalDate before the summary card', () => {
  const card = functionSource(billingPage, 'BillingCard')
  const corte = card.indexOf('Corte:')
  assert.notEqual(corte, -1, 'hero must contain "Corte:"')
  assert.ok(corte < card.indexOf('Cómo se calcula tu pago'), '"Corte:" must be inside the hero, above the summary card')
  const subtitle = card.slice(corte, corte + 250)
  assert.match(subtitle, /formatPortalDate\(billing\.start_date\)/)
  assert.match(subtitle, / al /)
  assert.match(subtitle, /formatPortalDate\(billing\.end_date\)/)
  assert.match(card, /hasBillingPeriod && billing\.start_date && billing\.end_date/)
})

test('S3 "Contexto de planilla" card is gated only by excluded days and has no period line', () => {
  const card = functionSource(billingPage, 'BillingCard')
  assert.match(card, /\{hasExcludedDays && \(\s*<Card>/)
  assert.doesNotMatch(card, /\(hasBillingPeriod \|\| hasExcludedDays\)/)
  assert.doesNotMatch(card, /Período:/)
  const context = card.slice(card.indexOf('Contexto de planilla'))
  assert.match(context, /Días no trabajados/)
})

// ─── S4: plain-language copy ─────────────────────────────────────────────────

test('S4 billing and history pages use the new copy and drop accounting jargon', () => {
  assert.match(billingPage, /Cómo se calcula tu pago/)
  assert.match(billingPage, /Total a cobrar/)
  assert.match(historyPage, /Total a cobrar/)
  assert.match(historyPage, /suma de los meses publicados/)
  for (const [name, source] of [['BillingPage', billingPage], ['BillingHistoryPage', historyPage]]) {
    assert.doesNotMatch(source, /Conciliaci[oó]n/, `${name} must not say "Conciliación"`)
    assert.doesNotMatch(source, /conciliable/i, `${name} must not say "conciliables"`)
    assert.doesNotMatch(source, /neto final/i, `${name} must not say "Neto final"`)
  }
})

test('S4 summary card hides the RC-IVA line when the retention amount is 0', () => {
  const card = functionSource(billingPage, 'BillingCard')
  const summary = card.slice(card.indexOf('Cómo se calcula tu pago'), card.indexOf('Contexto de planilla'))
  assert.match(summary, /billing\.retention_amount > 0 &&/)
  assert.ok(
    summary.indexOf('billing.retention_amount > 0') < summary.indexOf('RC-IVA / retención'),
    'the retention gate must wrap the RC-IVA line',
  )
})

test('S4 history desktop detail hides the RC-IVA line when the retention amount is 0', () => {
  const row = functionSource(historyPage, 'BillingRow')
  assert.match(row, /\(billing\.retention_amount \?\? 0\) > 0 &&/)
  assert.ok(
    row.indexOf('(billing.retention_amount ?? 0) > 0') < row.indexOf('RC-IVA / retención'),
    'the retention gate must wrap the RC-IVA line',
  )
})

test('S4 desktop table columns keep Retención and Neto', () => {
  assert.match(billingPage, /'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención'/)
  assert.match(historyPage, /'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención'/)
})

// ─── S1 (page part): retention letter notice ─────────────────────────────────

test('S1 retention page tells invoicing teachers they need no letter when has_retention is false', () => {
  assert.match(retentionPage, /Vos emitís factura: no necesitás carta de retención\./)
  assert.match(retentionPage, /profile\?\.has_retention === false/)
})

test('S1 retention page disables the form and generate button without retention', () => {
  assert.match(retentionPage, /const noRetention = profile\?\.has_retention === false/)
  assert.match(retentionPage, /disabled=\{isGenerating \|\| !isFormValid \|\| noRetention\}/)
  assert.match(retentionPage, /<fieldset disabled=\{noRetention\}/)
  assert.match(retentionPage, /if \(!isFormValid \|\| noRetention\) return/)
})

test('S1 retention page behaves as before when has_retention is true or undefined', () => {
  // Only an explicit false switches the notice on.
  assert.doesNotMatch(retentionPage, /!profile\?\.has_retention/)
  assert.doesNotMatch(retentionPage, /has_retention !== true/)
  assert.match(retentionPage, /Generar y Descargar PDF/)
})
