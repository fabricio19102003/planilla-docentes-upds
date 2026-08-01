import { expect, test } from '@playwright/test'

import { mockAuthenticatedDocente } from './support/api'
import { collidingMondaySchedule } from './support/fixtures'

test('desktop portal keeps the sidebar visible while navigating', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop navigation behavior')
  await mockAuthenticatedDocente(page, collidingMondaySchedule)
  await page.goto('/portal/notifications')

  const sidebar = page.getByRole('complementary').filter({ visible: true })
  await expect(sidebar).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abrir menú de navegación' })).toBeHidden()
  await sidebar.getByRole('link', { name: 'Mi Horario' }).click()

  await expect(page).toHaveURL('/portal/schedule')
  await expect(page.getByRole('heading', { name: 'Mi Horario Semanal' })).toBeVisible()
  await expect(sidebar).toBeVisible()
})

test('mobile portal drawer opens and closes after navigation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile navigation behavior')
  await mockAuthenticatedDocente(page, collidingMondaySchedule)
  await page.goto('/portal/notifications')

  await page.getByRole('button', { name: 'Abrir menú de navegación' }).click()
  const drawer = page.getByRole('dialog', { name: 'Navegación principal' })
  await expect(drawer).toBeVisible()
  await drawer.getByRole('link', { name: 'Mi Horario' }).click()

  await expect(page).toHaveURL('/portal/schedule')
  await expect(page.getByRole('heading', { name: 'Mi Horario Semanal' })).toBeVisible()
  await expect(drawer).toBeHidden()
})
