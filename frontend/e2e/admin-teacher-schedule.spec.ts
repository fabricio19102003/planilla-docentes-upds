import { expect, test } from '@playwright/test'

import { authenticateAdmin, teacherDetail } from './support/admin'

test('admin downloads a teacher schedule from teacher detail', async ({ page }) => {
  await authenticateAdmin(page)
  await page.route('**/api/teachers/CI-E2E/schedule/pdf', (route) => route.fulfill({
    status: 200,
    contentType: 'application/pdf',
    body: '%PDF-1.4 e2e',
  }))
  await page.route('**/api/teachers/CI-E2E', (route) => route.fulfill({ json: teacherDetail(null) }))

  await page.goto('/teachers/CI-E2E')
  const scheduleDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar horario' }).click()

  expect((await scheduleDownload).suggestedFilename()).toBe(
    `Horario_de_Ana_Docente_Gestion_${new Date().getFullYear()}.pdf`,
  )
})
