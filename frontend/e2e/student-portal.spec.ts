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

const reenrollment = {
  window: { id: 1, term_code: 'I/2027', starts_on: '2027-01-10', ends_on: '2027-01-25', is_open: true },
  eligibility: {
    last_term: 'II/2026', graded_term: 'II/2026', primary_semester: 3, target_semester: 4, regular: [], recursado: [], pending: [],
    scholarship: { category: 'sin_beca', label: 'Sin beca', average: 72, cuota: 1150, cuotas: 5, total: 5750, never_failed: true },
    recursado_fee: {},
  },
  main_groups: [], groups_by_semester: {}, request: null,
}

async function mockStudent(page: Page, extra: Record<string, unknown> = {}) {
  await page.addInitScript(() => {
    window.localStorage.setItem('student_token', 'e2e-student-token')
  })
  // Filter by pathname: a '**/api/**' glob also catches Vite's /src/api modules.
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const pathname = new URL(route.request().url()).pathname
    const mocks: Record<string, unknown> = { '/api/student-portal/me': studentProfile, ...extra }
    const [status, body] =
      pathname in mocks ? [200, mocks[pathname]] : [404, { detail: `Unmocked E2E request: ${pathname}` }]
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

test('Inicio shows the glass hero, the summary cards and does not overflow', async ({ page }, testInfo) => {
  await page.setViewportSize(testInfo.project.name === 'mobile-chromium' ? { width: 320, height: 640 } : { width: 1280, height: 800 })
  await mockStudent(page, {
    '/api/student-portal/reenrollment': reenrollment,
    '/api/student-portal/schedule': { status: { code: 'ok', message: null }, effective_from: null, entries: [], unscheduled: [] },
    '/api/student-portal/history': { history: [] },
    '/api/student-portal/migration-documents': { applies: false },
  })
  await page.goto('/estudiante')

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Hola, Valeria')
  await expect(page.getByRole('link', { name: 'Solicitar rematrícula' })).toHaveAttribute('href', '/estudiante/rematricula')
  await expect(page.getByRole('heading', { level: 2, name: 'Rematrícula' })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'Cuotas' })).toBeVisible()
  await expect(page.getByText('No tenés clases hoy.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Ver mi horario' })).toBeVisible()
  await expect(page.getByText('Todavía no tenés materias en tu historial académico.')).toBeVisible()
  expect(await noHorizontalOverflow(page)).toBe(true)
})

// S1/S2/S8/S9: Rematrícula receipt + sending state, Horario switch.

const group = (id: number, code: string, semester: number) => ({ id, code, shift: 'M', semester, capacity: 40, taken: 10, free: 30, is_full: false })
const reenrollmentWithRecursado = {
  window: { id: 1, term_code: 'I/2027', starts_on: '2027-01-10', ends_on: '2027-01-25', is_open: true },
  eligibility: {
    last_term: 'II/2026', graded_term: 'II/2026', primary_semester: 3, target_semester: 4,
    regular: [], pending: [{ code: 'CBC 0200', name: 'Bioquímica', semester: 2 }],
    recursado: [{ code: 'LIN 0130', name: 'Lingüística', semester: 2 }],
    scholarship: { category: 'sin_beca', label: 'Sin beca', average: 72, cuota: 1600, cuotas: 5, total: 8000, never_failed: false },
    recursado_fee: { per_subject: 1200, subjects: 1, charged_subjects: 1, total: 1200 },
  },
  main_groups: [group(7, 'M-01', 4)],
  groups_by_semester: { '2': [group(3, 'R-01', 2)] },
  request: null,
}

test('Rematrícula prints the receipt with the total, shows the sending state and does not overflow', async ({ page }, testInfo) => {
  await page.setViewportSize(testInfo.project.name === 'mobile-chromium' ? { width: 320, height: 640 } : { width: 1280, height: 800 })
  await mockStudent(page, { '/api/student-portal/reenrollment': reenrollmentWithRecursado })
  // The request takes a moment, so the sending state can be seen.
  await page.route((url) => url.pathname === '/api/student-portal/reenrollment/request', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.goto('/estudiante/rematricula')

  await expect(page.getByText('Resumen de montos (informativo)')).toBeVisible()
  const receipt = page.locator('.sp-receipt-ticket')
  await expect(receipt).toContainText('UPDS COBIJA')
  await expect(receipt).toContainText('Valeria Mamani · 9876543')
  await expect(receipt).toContainText('Cuota: 1.600 Bs × 5')
  await expect(receipt.locator('.sp-receipt-total')).toContainText('8.000 Bs')
  await expect(receipt).toContainText('Montos informativos')

  await page.getByLabel('Lingüística').selectOption('3')
  await expect(receipt).toContainText('Recursado: Lingüística')
  await expect(receipt.locator('.sp-receipt-total')).toContainText('9.200 Bs')
  expect(await noHorizontalOverflow(page)).toBe(true)

  await page.getByRole('radio').check()
  await page.getByRole('button', { name: 'Enviar solicitud' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Enviando tu solicitud a Registro…' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Enviar solicitud/ })).toBeDisabled()
  await expect(page.getByText('Solicitud enviada. Registro la va a revisar y vas a ver el estado acá.')).toBeVisible()
  expect(await noHorizontalOverflow(page)).toBe(true)
})

const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const scheduleEntry = (weekday: string, over: Record<string, unknown> = {}) => ({
  source: 'grupo', subject_code: 'MED 100', subject_name: `Anatomía ${weekday}`, group_code: 'M-01', weekday,
  start_time: '08:00', end_time: '09:30', classroom: { code: 'A-1', name: 'Aula 1' }, activity_type: 'theory',
  teacher_name: 'Docente A', term_code: 'I/2027', effective_from: '2027-02-01', is_upcoming: false, ...over,
})

test('Horario switches between Hoy, Semana and Próximo and does not overflow', async ({ page }, testInfo) => {
  await page.setViewportSize(testInfo.project.name === 'mobile-chromium' ? { width: 320, height: 640 } : { width: 1280, height: 800 })
  await mockStudent(page, {
    '/api/student-portal/schedule': {
      status: { code: 'ok', message: null }, effective_from: null, unscheduled: [],
      entries: [...WEEKDAYS.map((weekday) => scheduleEntry(weekday)), scheduleEntry('monday', { subject_name: 'Genética', start_time: '10:00', end_time: '11:00', is_upcoming: true, effective_from: '2099-03-01' })],
    },
  })
  await page.goto('/estudiante/horario')

  const tabs = page.getByRole('tablist', { name: 'Vista del horario' })
  await expect(tabs.getByRole('tab')).toHaveCount(3)
  // Every weekday has a class, so the switch starts on Hoy: one card for today.
  await expect(tabs.getByRole('tab', { name: 'Hoy' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('tabpanel').getByText(/^Hoy · /)).toHaveCount(1)
  expect(await noHorizontalOverflow(page)).toBe(true)

  await tabs.getByRole('tab', { name: 'Semana' }).click()
  await expect(tabs.getByRole('tab', { name: 'Semana' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('tabpanel').getByText('Anatomía monday')).toBeVisible()
  await expect(page.getByRole('tabpanel').getByText('Anatomía sunday')).toBeVisible()

  await tabs.getByRole('tab', { name: 'Próximo' }).click()
  await expect(page.getByRole('tabpanel').getByText('Genética')).toBeVisible()
  await expect(page.getByRole('tabpanel').getByText('Anatomía monday')).toHaveCount(0)
  await expect(page.getByText('Este horario todavía no empezó a regir; puede cambiar hasta esa fecha.')).toBeVisible()
  expect(await noHorizontalOverflow(page)).toBe(true)
})
