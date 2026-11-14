import { expect, test, type Page } from '@playwright/test'

// S1/S2/S4/S6/S9: the redesigned student shell (desktop top nav, mobile notch bar, 404).

const studentProfile = {
  id: 7,
  document_number: '9876543',
  document_type: 'CI',
  first_names: 'Valeria',
  last_names: 'Mamani',
  full_name: 'Valeria Mamani',
  is_foreign: false,
  must_change_password: false,
}

async function mockStudent(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('student_token', 'e2e-student-token')
  })
  // Filter by pathname: a '**/api/**' glob also catches Vite's /src/api modules.
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const pathname = new URL(route.request().url()).pathname
    const [status, body] =
      pathname === '/api/student-portal/me' ? [200, studentProfile] : [404, { detail: `Unmocked E2E request: ${pathname}` }]
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
}

const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)

test('desktop top nav marks the active destination and follows navigation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop navigation behavior')
  await mockStudent(page)
  await page.goto('/estudiante')

  const nav = page.getByRole('navigation', { name: 'Principal' })
  await expect(nav.getByRole('link')).toHaveCount(5)
  await expect(nav.getByRole('link', { name: 'Inicio' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('navigation', { name: 'Navegación' })).toBeHidden()

  await nav.getByRole('link', { name: 'Mi horario' }).click()
  await expect(page).toHaveURL('/estudiante/horario')
  await expect(nav.getByRole('link', { name: 'Mi horario' })).toHaveAttribute('aria-current', 'page')
  await expect(nav.getByRole('link', { name: 'Inicio' })).not.toHaveAttribute('aria-current', 'page')
  expect(await noHorizontalOverflow(page)).toBe(true)
})

test('desktop account menu holds Cambiar contraseña and Salir', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chromium', 'Desktop navigation behavior')
  await mockStudent(page)
  await page.goto('/estudiante')

  await page.getByRole('button', { name: 'Cuenta de Valeria Mamani' }).click()
  await expect(page.getByRole('menuitem', { name: 'Cambiar contraseña' })).toBeVisible()
  await page.getByRole('menuitem', { name: 'Salir' }).click()
  await expect(page).toHaveURL('/estudiante/login')
})

for (const size of [{ width: 390, height: 844 }, { width: 320, height: 640 }]) {
  test(`mobile notch bar at ${size.width}px is visible and nothing overflows`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mobile-chromium', 'Mobile navigation behavior')
    await page.setViewportSize(size)
    await mockStudent(page)
    await page.goto('/estudiante')

    const bar = page.getByRole('navigation', { name: 'Navegación' })
    await expect(bar).toBeVisible()
    await expect(bar.getByRole('link')).toHaveCount(5)
    await expect(bar.getByRole('link', { name: 'Inicio' })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('navigation', { name: 'Principal' })).toBeHidden()
    expect(await noHorizontalOverflow(page)).toBe(true)

    for (const link of await bar.getByRole('link').all()) {
      const box = await link.boundingBox()
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
    }

    await bar.getByRole('link', { name: 'Historial' }).click()
    await expect(page).toHaveURL('/estudiante/historial')
    await expect(bar.getByRole('link', { name: 'Historial' })).toHaveAttribute('aria-current', 'page')

    // Salir is two taps away: the avatar, then the menu item.
    await page.getByRole('button', { name: 'Cuenta de Valeria Mamani' }).click()
    await expect(page.getByRole('menuitem', { name: 'Salir' })).toBeVisible()
  })
}

test('unknown /estudiante route renders the contained 404 inside the shell', async ({ page }) => {
  await mockStudent(page)
  await page.goto('/estudiante/no-existe')

  await expect(page.getByRole('heading', { name: 'Esta página no tiene pulso.' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Volver a recepción' })).toHaveAttribute('href', '/estudiante')
  expect(await noHorizontalOverflow(page)).toBe(true)
  await page.getByRole('link', { name: 'Volver a recepción' }).click()
  await expect(page).toHaveURL('/estudiante')
})
