import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  buildSettingsPayload,
  MONEY_INPUT_MIN,
  MONEY_INPUT_STEP,
  toSettingsFormState,
} from '../src/lib/settingsForm.ts'

const root = resolve(import.meta.dirname, '..')
const page = readFileSync(resolve(root, 'src/pages/SettingsPage.tsx'), 'utf8')

const seededSettings = {
  active_academic_period: 'I/2026',
  company_name: 'UNIPANDO S.R.L.',
  company_nit: '456850023',
  hourly_rate: 70,
  practice_hourly_rate: 50,
  docente_can_edit_profile: false,
  docente_can_edit_photo: false,
  whatsapp_billing_delivery: {
    requested_enabled: false,
    effective_enabled: false,
    can_enable: false,
    blocking_reasons: ['worker_unavailable'],
    readiness: { ready: false },
    worker_heartbeat_at: null,
  },
}

function isStepAligned(value, min, step) {
  const distance = (value - min) / step
  return Math.abs(distance - Math.round(distance)) < 1e-9
}

test('allows period-only save with unchanged seeded rates 70 and 50', () => {
  const form = {
    ...toSettingsFormState(seededSettings),
    active_academic_period: 'II/2026',
  }

  assert.deepEqual(buildSettingsPayload(form, seededSettings), {
    active_academic_period: 'II/2026',
  })
})

test('accepts centavo-aligned theory and practice rates, including integers and two decimals', () => {
  assert.equal(MONEY_INPUT_MIN, 0.01)
  assert.equal(MONEY_INPUT_STEP, 0.01)
  for (const rate of [70, 50, 70.25, 50.99]) {
    assert.equal(isStepAligned(rate, MONEY_INPUT_MIN, MONEY_INPUT_STEP), true)
  }

  assert.equal((page.match(/min=\{MONEY_INPUT_MIN\}/g) ?? []).length, 2)
  assert.equal((page.match(/step=\{MONEY_INPUT_STEP\}/g) ?? []).length, 2)
  assert.doesNotMatch(page, /step=\{0\.5\}/)
})

test('maps WhatsApp intent and renders an accessible non-optimistic switch', () => {
  const form = {
    ...toSettingsFormState(seededSettings),
    whatsapp_billing_requested_enabled: true,
  }

  assert.deepEqual(buildSettingsPayload(form, seededSettings), {
    whatsapp_billing_requested_enabled: true,
  })
  assert.match(page, /role="switch"/)
  assert.match(page, /aria-checked=/)
  assert.match(page, /whatsapp_billing_delivery\.effective_enabled/)
  assert.match(page, /whatsapp_billing_delivery\.blocking_reasons/)
})
