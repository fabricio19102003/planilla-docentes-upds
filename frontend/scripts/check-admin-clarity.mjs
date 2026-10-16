import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

import {
  ACTIVITY_CATEGORY_LABELS,
  describeWhatsappReason,
  describeWhatsappReasons,
  formatHours,
  formatPaymentBreakdown,
  humanizeCode,
  resolveActivityCategoryLabel,
} from '../src/lib/displayFormat.ts'

const root = resolve(import.meta.dirname, '..')
const backendApp = resolve(root, '../backend/app')
const source = (path) => readFileSync(resolve(root, path), 'utf8')

function pythonFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return name === '__pycache__' ? [] : pythonFiles(full)
    return name.endsWith('.py') ? [full] : []
  })
}

function backendCategoryCodes() {
  const codes = new Set()
  for (const file of pythonFiles(backendApp)) {
    const text = readFileSync(file, 'utf8')
    for (const match of text.matchAll(/log_activity\(\s*[A-Za-z_.]+,\s*[^,]+,\s*["']([^"']+)["']/g)) codes.add(match[1])
    for (const match of text.matchAll(/ActivityLog\([^)]*?category=["']([^"']+)["']/gs)) codes.add(match[1])
  }
  return [...codes].sort()
}

function backendReasonCodes() {
  const codes = new Set(['admin_disabled', 'readiness_adapter_unavailable'])
  const control = readFileSync(resolve(backendApp, 'services/whatsapp_delivery_control.py'), 'utf8')
  const block = control.match(/_REASON_CODES = \{([^}]*)\}/s)
  for (const match of block[1].matchAll(/["']([a-z_]+)["']/g)) codes.add(match[1])
  const adapter = readFileSync(resolve(backendApp, 'services/twilio_readiness_adapter.py'), 'utf8')
  for (const match of adapter.matchAll(/reason = ["']([a-z_]+)["']/g)) codes.add(match[1])
  return [...codes].sort()
}

test('formatHours uses es-BO with at most two decimals and thousands separators', () => {
  assert.equal(formatHours(9.666666666666666), '9,67 h')
  assert.equal(formatHours(8524), '8.524 h')
  assert.equal(formatHours(8), '8 h')
  assert.equal(formatHours(1.5), '1,5 h')
  assert.equal(formatHours(0), '0 h')
  assert.equal(formatHours(null), '—')
  assert.equal(formatHours(undefined), '—')
})

test('formatPaymentBreakdown renders theory and practice amounts in es-BO', () => {
  assert.equal(formatPaymentBreakdown(500000, 103728.3), 'Teoría Bs 500.000,00 · Asistencial Bs 103.728,30')
})

test('every activity category written by the backend has a Spanish label', () => {
  const codes = backendCategoryCodes()
  assert.ok(codes.length >= 15, `expected to find backend category codes, found ${codes.join(', ')}`)
  for (const required of ['practice-planilla', 'academic_schedule', 'whatsapp', 'billing', 'auth', 'profile', 'teachers', 'users', 'contracts']) {
    assert.ok(codes.includes(required), `backend scan missed ${required}`)
  }
  for (const code of codes) {
    assert.ok(ACTIVITY_CATEGORY_LABELS[code], `missing label for category ${code}`)
    assert.equal(resolveActivityCategoryLabel(code), ACTIVITY_CATEGORY_LABELS[code])
    assert.doesNotMatch(ACTIVITY_CATEGORY_LABELS[code], /[_-]/, `label for ${code} still looks like a code`)
  }
  assert.equal(resolveActivityCategoryLabel('practice-planilla'), 'Planilla de prácticas')
  assert.equal(resolveActivityCategoryLabel('academic_schedule'), 'Horarios académicos')
  assert.equal(resolveActivityCategoryLabel('whatsapp'), 'WhatsApp')
})

test('unknown activity categories fall back to a humanized label, never the raw code', () => {
  assert.equal(resolveActivityCategoryLabel('new_thing-here'), 'New thing here')
  assert.equal(humanizeCode('some_code'), 'Some code')
  assert.equal(resolveActivityCategoryLabel(''), '—')
})

test('every WhatsApp readiness reason code maps to a Spanish phrase', () => {
  const codes = backendReasonCodes()
  assert.ok(codes.length >= 10, `expected readiness codes, found ${codes.join(', ')}`)
  for (const code of ['configuration_missing', 'provider_unavailable', 'worker_unavailable']) assert.ok(codes.includes(code))
  for (const code of codes) {
    const phrase = describeWhatsappReason(code)
    assert.ok(phrase, `missing phrase for ${code}`)
    assert.doesNotMatch(phrase, /_/, `phrase for ${code} still contains a raw code`)
    assert.notEqual(phrase, code)
  }
  assert.equal(describeWhatsappReason('worker_unavailable'), 'el proceso de envío no está activo')
  assert.equal(describeWhatsappReason('mystery_code'), 'mystery code')
  assert.equal(
    describeWhatsappReasons(['configuration_missing', 'worker_unavailable']),
    'falta la configuración del proveedor, el proceso de envío no está activo',
  )
})

test('dashboard states that the total is theory plus practice and shows the breakdown', () => {
  const page = source('src/pages/DashboardPage.tsx')
  assert.match(page, /title="Total a pagar \(teoría \+ asistencial\)"/)
  assert.doesNotMatch(page, /Total Facturación/)
  assert.match(page, /total_regular_payment/)
  assert.match(page, /total_practice_payment/)
  assert.match(page, /formatPaymentBreakdown/)
})

test('planilla page syncs the tab with ?tab= using replace navigation', () => {
  const page = source('src/pages/PlanillaPage.tsx')
  assert.match(page, /useSearchParams/)
  assert.match(page, /searchParams\.get\('tab'\)\s*===\s*'practicas'/)
  assert.match(page, /tab:\s*'teoricas'|\{ tab: next \}|set\('tab'/)
  assert.match(page, /replace:\s*true/)
  assert.doesNotMatch(page, /useState<'teoricas' \| 'practicas'>/)
})

test('admin pages use the shared display helpers instead of raw codes and raw hours', () => {
  const log = source('src/pages/ActivityLogPage.tsx')
  assert.match(log, /resolveActivityCategoryLabel/)
  assert.doesNotMatch(log, /CATEGORY_LABELS\[[^\]]+\]\s*\?\?\s*[a-zA-Z.]*category/)
  const settings = source('src/pages/SettingsPage.tsx')
  assert.match(settings, /describeWhatsappReasons/)
  assert.doesNotMatch(settings, /blocking_reasons\.join/)
  const planner = source('src/pages/SchedulePlannerPage.tsx')
  assert.match(planner, /formatHours\(item\.theory_minutes_week \/ 60\)/)
  assert.doesNotMatch(planner, /_minutes_week \/ 60\}\s*h/)
  const planilla = source('src/pages/PlanillaPage.tsx')
  assert.match(planilla, /formatHours\(item\.total_hours\)/)
  assert.match(planilla, /formatHours\(lastResult\.total_hours\)/)
})
