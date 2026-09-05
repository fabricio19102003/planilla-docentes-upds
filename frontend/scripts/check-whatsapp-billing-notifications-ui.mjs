import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const hook = readFileSync(new URL('../src/api/hooks/useBillingPublication.ts', import.meta.url), 'utf8')
const page = readFileSync(new URL('../src/pages/PlanillaPage.tsx', import.meta.url), 'utf8')

assert.match(hook, /\/billing\/notifications\/readiness/)
assert.match(hook, /\/billing\/notifications\/preview/)
assert.match(hook, /\/billing\/notifications\/confirm/)
assert.match(hook, /\/billing\/notifications\/batches\//)
assert.match(hook, /teacher_cis: string\[\]; digest: string/)
assert.match(page, /WhatsApp oficial/)
assert.match(page, /Generar vista previa/)
assert.match(page, /Confirmar envío/)
assert.match(page, /phone_masked/)
assert.doesNotMatch(page, /phone_e164/)
assert.match(page, /notification_readiness_unavailable/)
assert.match(page, /notification_capacity_exceeded/)
assert.match(page, /stale_notification_plan/)
assert.match(page, /jobs\.reduce/)
assert.match(page, /job\.status/)

console.log('Official WhatsApp billing UI contract: OK')
