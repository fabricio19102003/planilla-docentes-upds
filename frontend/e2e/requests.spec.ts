import { expect, test } from '@playwright/test'

import { mockAuthenticatedDocente } from './support/api'
import { collidingMondaySchedule } from './support/fixtures'

test('responded request shows the historical resolution separately from admin observations', async ({ page }) => {
  await mockAuthenticatedDocente(page, collidingMondaySchedule, [
    {
      id: 7,
      teacher_ci: '12345678',
      month: 4,
      year: 2026,
      request_type: 'schedule_detail',
      message: 'Please confirm my Monday schedule.',
      status: 'approved',
      admin_response: 'Verified against the active assignment.',
      responded_at: '2026-04-10T12:00:00',
      created_at: '2026-04-09T12:00:00',
      resolution_snapshot: {
        kind: 'schedule_detail',
        academic_period: 'I/2026',
        designations: collidingMondaySchedule.designations,
      },
    },
  ])

  await page.goto('/portal/requests')
  await page.getByRole('button', { name: 'Ver detalle' }).click()

  await expect(page.getByRole('heading', { name: 'Información resuelta' })).toBeVisible()
  const anatomy = page.getByRole('article').filter({ hasText: 'Anatomy I (M1)' })
  await expect(anatomy).toBeVisible()
  await expect(anatomy.getByText('Lunes: 08:00–09:30 · 2h')).toBeVisible()
  await expect(page.getByText('Observaciones del administrador', { exact: true })).toBeVisible()
  await expect(page.getByText('Verified against the active assignment.')).toBeVisible()
})
