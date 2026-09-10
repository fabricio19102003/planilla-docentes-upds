import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
const source = async (path) => readFile(new URL(path, root), 'utf8')

const [types, hooks, card, detail] = await Promise.all([
  source('src/api/types.ts'),
  source('src/api/hooks/useTeachers.ts'),
  source('src/components/teachers/WhatsAppConsentCard.tsx'),
  source('src/pages/TeacherDetailPage.tsx'),
])

assert.match(types, /interface WhatsAppPreferenceAdminResponse/)
assert.match(types, /phone_masked: string \| null/)
assert.doesNotMatch(types, /phone_e164.*WhatsAppPreferenceAdminResponse/)
assert.match(hooks, /\/teachers\/\$\{encodeURIComponent\(ci\)\}\/whatsapp-preference/)
assert.match(hooks, /\/whatsapp-preference\/opt-out/)
assert.match(hooks, /\['whatsapp-preference', variables\.ci\]/)
assert.match(hooks, /\['whatsapp-preference', teacher\.ci\]/)
assert.doesNotMatch(card, /teacher\.phone/)
assert.match(card, /phone_masked/)
assert.match(card, /window\.confirm/)
assert.match(card, /role="status"/)
assert.match(card, /role="alert"/)
assert.match(card, /aria-describedby/)
assert.match(card, /setPhoneE164\(''\)/)
assert.match(card, /setConsentEvidenceReference\(''\)/)
assert.match(card, /setOptOutEvidenceReference\(''\)/)
assert.match(card, /setConsentedAt\(''\)\n      savePreference\.reset\(\)/)
assert.match(card, /setOptOutEvidenceReference\(''\)\n      optOut\.reset\(\)/)
assert.match(card, /preference\.error/)
assert.match(card, /No se pudo cargar la preferencia de WhatsApp/)
assert.match(card, /Número verificado/)
assert.match(card, /Baja registrada/)
assert.match(card, /No habilitado para envíos/)
assert.match(card, /Revisión de consentimiento:/)
assert.match(card, /Fecha de consentimiento:/)
assert.match(detail, /WhatsAppConsentCard/)
assert.match(detail, /Teléfono de contacto \(no es consentimiento de WhatsApp\)/)

console.log('WhatsApp consent card structural/privacy checks passed.')
