import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

import { authenticateAdmin } from './support/admin'

const allowed = { allowed: true, reason: null }

function designation(overrides: Record<string, unknown> = {}) {
  return {
    id: 1, teacher_ci: 'CI-E2E', teacher_name: 'ANA DOCENTE', subject: 'ANATOMIA HUMANA I', semester: 'PRIMERO',
    group_code: 'M-1', academic_period: 'II/2026', designation_type: 'regular',
    schedule_json: [{ dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30', duracion_minutos: 90, horas_academicas: 2 }],
    semester_hours: 40, monthly_hours: 8, weekly_hours: 2, weekly_hours_calculated: 2, schedule_raw: 'Lunes: 08:00-09:30',
    contract_start_date: '2026-08-10', contract_end_date: '2026-12-18', created_at: '2026-08-01T00:00:00',
    status: 'active', has_contract: false, attendance_count: 0,
    actions: { edit: allowed, edit_dates: allowed, finalize: allowed, delete: allowed },
    ...overrides,
  }
}

const used = designation({
  id: 2, teacher_ci: 'CI-2', teacher_name: 'BRUNO ROJAS', subject: 'PRACTICA CLINICA', designation_type: 'practice',
  attendance_count: 12, has_contract: true,
  actions: {
    edit: { allowed: false, reason: 'La planilla de práctica 9/2026 ya está aprobada.' },
    edit_dates: { allowed: false, reason: 'La planilla de práctica 9/2026 ya está aprobada.' },
    finalize: allowed,
    delete: { allowed: false, reason: 'Tiene asistencia registrada; usá Finalizar.' },
  },
})

async function mockApi(page: Page) {
  const posted: unknown[] = []
  await authenticateAdmin(page)
  await page.route('**/api/config/active-period', (route) => route.fulfill({ json: { academic_period: 'II/2026' } }))
  await page.route('**/api/teachers?*', (route) => route.fulfill({
    json: { items: [{ ci: 'CI-E2E', full_name: 'ANA DOCENTE' }], total: 1, page: 1, per_page: 20 },
  }))
  await page.route('**/api/admin/designations?*', (route) => route.fulfill({
    json: { academic_period: 'II/2026', periods: ['II/2026', 'I/2026'], items: [designation(), used] },
  }))
  await page.route('**/api/admin/designations', async (route) => {
    posted.push(route.request().postDataJSON())
    await route.fulfill({ status: 201, json: { ...designation({ id: 3, subject: 'HISTOLOGIA' }), regenerate: [], warnings: [] } })
  })
  return posted
}

test('admin finds, creates and safely removes designations', async ({ page }, testInfo) => {
  const posted = await mockApi(page)
  await page.goto('/designations')

  await expect(page.getByRole('heading', { name: 'Designaciones', level: 2 })).toBeVisible()
  await expect(page.getByText('ANATOMIA HUMANA I')).toBeVisible()
  await expect(page.getByText('Lun 08:00–09:30').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('designations-list.png'), fullPage: true })

  await page.getByRole('button', { name: 'Nueva designación' }).click()
  const dialog = page.getByRole('dialog', { name: 'Nueva designación' })
  await dialog.getByRole('button', { name: 'Crear designación' }).click()
  await expect(dialog.getByText('Elegí un docente.')).toBeVisible()

  await dialog.locator('#designation-teacher').click()
  await page.getByRole('option', { name: /ANA DOCENTE/ }).click()
  await dialog.getByLabel('Materia').fill('Histologia')
  await dialog.getByLabel('Semestre', { exact: true }).selectOption('SEGUNDO')
  await dialog.getByLabel('Grupo').fill('T-2')
  await dialog.getByLabel('Bloque 1: día').selectOption('martes')
  await dialog.getByLabel('Desde').fill('06:30')
  await dialog.getByLabel('Hasta').fill('08:00')
  await expect(dialog.getByText('Total: 2 horas académicas por semana')).toBeVisible()
  await dialog.getByRole('button', { name: /Usar sugerido: 8/ }).click()
  await page.screenshot({ path: testInfo.outputPath('designations-create.png'), fullPage: true })
  await dialog.getByRole('button', { name: 'Crear designación' }).click()

  await expect(page.getByText('Designación creada.')).toBeVisible()
  expect(posted).toEqual([{
    teacher_ci: 'CI-E2E', subject: 'Histologia', semester: 'SEGUNDO', group_code: 'T-2', academic_period: 'II/2026',
    designation_type: 'regular', schedule: [{ dia: 'martes', hora_inicio: '06:30', hora_fin: '08:00' }],
    monthly_hours: 8, semester_hours: null, contract_start_date: null, contract_end_date: null,
  }])

  await page.getByRole('button', { name: 'Eliminar PRACTICA CLINICA M-1' }).click()
  const blocked = page.getByRole('dialog', { name: 'Esta designación no se puede eliminar' })
  await expect(blocked.getByText('Tiene asistencia registrada; usá Finalizar.')).toBeVisible()
  await blocked.getByRole('button', { name: 'Finalizar en su lugar' }).click()
  await expect(page.getByRole('dialog', { name: 'Finalizar designación' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('designations-finalize.png'), fullPage: true })
})

test('editing a paid designation explains why and offers to finalize', async ({ page }) => {
  await mockApi(page)
  await page.goto('/designations')
  await page.getByRole('row', { name: /PRACTICA CLINICA/ }).getByRole('button', { name: 'Editar' }).click()
  const dialog = page.getByRole('dialog', { name: 'Editar designación' })
  await expect(dialog.getByText('Esta designación ya se pagó y no se puede editar')).toBeVisible()
  await expect(dialog.getByText('La planilla de práctica 9/2026 ya está aprobada.')).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
})
