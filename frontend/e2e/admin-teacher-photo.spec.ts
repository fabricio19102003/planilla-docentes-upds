import { expect, test } from '@playwright/test'

import { authenticateAdmin, teacherDetail } from './support/admin'

test('teacher detail shows a prominent downloadable photo with initials fallback', async ({ page }) => {
  await authenticateAdmin(page)
  let avatarUrl: string | null = '/uploads/teacher-photos/e2e.png'
  await page.route('**/uploads/teacher-photos/e2e.png', (route) => route.fulfill({
    status: 200,
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2Z1sAAAAASUVORK5CYII=', 'base64'),
  }))
  await page.route('**/api/teachers/CI-E2E/photo/download', (route) => route.fulfill({
    status: 200,
    contentType: 'image/png',
    headers: { 'Content-Disposition': 'attachment; filename="Foto_Docente_CI-E2E.png"' },
    body: 'photo-bytes',
  }))
  await page.route('**/api/teachers/CI-E2E', (route) => route.fulfill({ json: teacherDetail(avatarUrl) }))

  await page.goto('/teachers/CI-E2E')
  const photo = page.getByRole('img', { name: 'Foto de perfil de Ana Docente' })
  await expect(photo).toBeVisible()
  const photoBox = await photo.boundingBox()
  expect(photoBox?.width).toBeGreaterThanOrEqual(127)
  expect(photoBox?.height).toBeGreaterThanOrEqual(127)

  const photoDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar foto' }).click()
  expect((await photoDownload).suggestedFilename()).toBe('Foto_Docente_CI-E2E.png')

  avatarUrl = null
  await page.reload()
  await expect(page.getByRole('region', { name: 'Foto institucional' })).toContainText('AD')
})
