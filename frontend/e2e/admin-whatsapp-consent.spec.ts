import { expect, test } from '@playwright/test'

import type { WhatsAppPreferenceAdminResponse } from '../src/api/types'
import { authenticateAdmin, teacherDetail } from './support/admin'

const preference: WhatsAppPreferenceAdminResponse = {
  teacher_ci: 'CI-E2E',
  exists: false,
  phone_masked: null,
  is_verified: false,
  eligible: false,
  consent_revision: 0,
  consent_source: null,
  consented_at: null,
  opted_out: false,
  opted_out_at: null,
  has_consent_evidence: false,
  has_opt_out_evidence: false,
}

test('admin creates, opts out, and re-consents a masked WhatsApp preference', async ({ page }) => {
  await authenticateAdmin(page)
  await page.route('**/api/teachers/CI-E2E', (route) => route.fulfill({ json: teacherDetail(null) }))
  await page.route('**/api/teachers/CI-E2E/whatsapp-preference', async (route) => {
    if (route.request().method() === 'GET') return route.fulfill({ json: preference })
    const body = route.request().postDataJSON() as Record<string, unknown>
    expect(body).toMatchObject({ phone_e164: '+59170000000', is_verified: true, consent_source: 'written_record' })
    preference.exists = true
    preference.phone_masked = '+591 70•• ••••'
    preference.is_verified = true
    preference.eligible = true
    preference.consent_revision += 1
    preference.consented_at = body.consented_at as string
    preference.consent_source = body.consent_source as WhatsAppPreferenceAdminResponse['consent_source']
    preference.has_consent_evidence = true
    preference.opted_out = false
    return route.fulfill({ json: preference })
  })
  await page.route('**/api/teachers/CI-E2E/whatsapp-preference/opt-out', async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    expect(body).toEqual({ opt_out_evidence_reference: 'Solicitud firmada' })
    preference.eligible = false
    preference.opted_out = true
    preference.opted_out_at = '2026-01-02T00:00:00Z'
    preference.has_opt_out_evidence = true
    preference.consent_revision += 1
    return route.fulfill({ json: preference })
  })

  await page.goto('/teachers/CI-E2E')
  await expect(page.getByRole('region', { name: 'Preferencia de WhatsApp' })).toContainText('Sin preferencia registrada')

  await page.getByLabel('Número de WhatsApp en formato internacional').fill('+59170000000')
  await page.getByLabel('Referencia de evidencia de consentimiento').fill('Formulario firmado')
  await page.getByLabel('Fecha y hora del consentimiento').fill('2026-01-01T00:00')
  await page.getByLabel('Fuente del consentimiento').selectOption('written_record')
  await page.getByRole('button', { name: 'Guardar consentimiento' }).click()
  await expect(page.getByRole('status')).toContainText('actualizada')
  await expect(page.getByLabel('Número de WhatsApp en formato internacional')).toHaveValue('')
  await expect(page.getByLabel('Referencia de evidencia de consentimiento')).toHaveValue('')
  await expect(page.getByText('+591 70•• ••••')).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByLabel('Referencia de evidencia de baja').fill('Solicitud firmada')
  await page.getByRole('button', { name: 'Registrar baja' }).press('Enter')
  await expect(page.getByRole('status')).toContainText('baja')
  await expect(page.getByLabel('Referencia de evidencia de baja')).toHaveCount(0)

  await page.getByLabel('Número de WhatsApp en formato internacional').fill('+59170000000')
  await page.getByLabel('Referencia de evidencia de consentimiento').fill('Nueva autorización')
  await page.getByLabel('Fecha y hora del consentimiento').fill('2026-01-03T00:00')
  await page.getByRole('button', { name: 'Guardar consentimiento' }).click()
  await expect(page.getByText('Número verificado')).toBeVisible()
  await expect(page.getByText('Revisión de consentimiento: 3')).toBeVisible()
  await expect(page.getByText('Fuente: Registro escrito')).toBeVisible()
  await expect(page.getByText('Fecha de consentimiento:')).toBeVisible()
})

test('admin sees an ineligible verified preference and its revision', async ({ page }) => {
  await authenticateAdmin(page)
  await page.route('**/api/teachers/CI-E2E', (route) => route.fulfill({ json: teacherDetail(null) }))
  await page.route('**/api/teachers/CI-E2E/whatsapp-preference', (route) => route.fulfill({ json: { ...preference, exists: true, phone_masked: '+591 70•• ••••', is_verified: true, eligible: false, consent_revision: 7 } }))
  await page.goto('/teachers/CI-E2E')
  await expect(page.getByText('Número verificado')).toBeVisible()
  await expect(page.getByText('No habilitado para envíos')).toBeVisible()
  await expect(page.getByText('Revisión de consentimiento: 7')).toBeVisible()
})

test('admin sees a preference load failure instead of an empty state', async ({ page }) => {
  await authenticateAdmin(page)
  await page.route('**/api/teachers/CI-E2E', (route) => route.fulfill({ json: teacherDetail(null) }))
  await page.route('**/api/teachers/CI-E2E/whatsapp-preference', (route) => route.fulfill({ status: 500, json: { detail: 'protected' } }))
  await page.goto('/teachers/CI-E2E')
  await expect(page.getByRole('alert')).toContainText('No se pudo cargar la preferencia de WhatsApp.')
  await expect(page.getByText('Sin preferencia registrada')).toHaveCount(0)
})
