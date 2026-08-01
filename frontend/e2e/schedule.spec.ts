import { expect, test } from '@playwright/test'

import { mockAuthenticatedDocente } from './support/api'
import { collidingMondaySchedule } from './support/fixtures'

async function openWeeklySchedule(page: Parameters<typeof mockAuthenticatedDocente>[0]) {
  await mockAuthenticatedDocente(page, collidingMondaySchedule)
  await page.goto('/portal/schedule')
  await page.getByRole('button', { name: 'Grilla Semanal' }).click()
}

test('desktop weekly grid keeps simultaneous Monday subjects in one cell', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop weekly grid behavior')
  await openWeeklySchedule(page)

  const weeklyGrid = page.getByRole('table', {
    name: 'Horario semanal agrupado por día y hora de inicio',
  })
  const mondayCell = weeklyGrid.getByRole('cell', { name: /Anatomy I/ })

  await expect(weeklyGrid).toBeVisible()
  await expect(mondayCell).toContainText('Anatomy I')
  await expect(mondayCell).toContainText('Physiology I')
  await expect(mondayCell).toContainText('08:00-09:30')
})

test('mobile weekly mode exposes simultaneous subjects in the day-list fallback', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile weekly fallback behavior')
  await openWeeklySchedule(page)

  await expect(page.getByText('En pantallas pequeñas, la grilla se presenta como una lista por día.')).toBeVisible()
  const mondayList = page.getByRole('region', { name: 'Lunes' })

  await expect(mondayList).toContainText('2 clase(s)')
  await expect(mondayList).toContainText('Anatomy I')
  await expect(mondayList).toContainText('Physiology I')
  await expect(page.getByRole('table', { name: 'Horario semanal agrupado por día y hora de inicio' })).toBeHidden()
})
