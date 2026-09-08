import { expect, test } from '@playwright/test'

import { adminUser, authenticateAdmin } from './support/admin'

test('admin user list sends accessible server-side search and filters', async ({ page }) => {
  await authenticateAdmin(page)
  const requestedUrls: URL[] = []
  await page.route('**/api/users**', async (route) => {
    const url = new URL(route.request().url())
    requestedUrls.push(url)
    await route.fulfill({
      json: {
        items: [{ ...adminUser, id: 2, ci: 'DOC-1', full_name: 'Ana Docente', role: 'docente', teacher_ci: 'DOC-1' }],
        total: 1,
        page: Number(url.searchParams.get('page') ?? 1),
        per_page: 15,
        summary: { total: 4, admins: 1, docentes: 3, active: 3 },
      },
    })
  })
  await page.route('**/api/teachers**', (route) => route.fulfill({
    json: { items: [], total: 0, page: 1, per_page: 200 },
  }))

  await page.goto('/users')
  await expect(page.getByText('4 usuarios registrados')).toBeVisible()
  await page.getByLabel('Buscar usuarios').fill('Ana')
  await page.getByLabel('Rol').click()
  await page.getByRole('option', { name: 'Docentes' }).click()
  await page.getByLabel('Estado').click()
  await page.getByRole('option', { name: 'Activos', exact: true }).click()

  await expect.poll(() => requestedUrls.some((url) =>
    url.searchParams.get('search') === 'Ana'
    && url.searchParams.get('role') === 'docente'
    && url.searchParams.get('active') === 'true'
    && url.searchParams.get('page') === '1',
  )).toBe(true)
  await expect(page.getByRole('button', { name: 'Resetear contraseña de Ana Docente' })).toBeVisible()
})
