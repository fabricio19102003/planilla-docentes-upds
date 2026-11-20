import { expect, test, type Page } from '@playwright/test'

// First login: after the forced password change the user lands on the portal home and is not sent
// back to the change-password form, while the must_change_password guard still blocks every portal page.

const NEW_PASSWORD = 'Nueva2026x'
const REFETCH_DELAY_MS = 800

const studentProfile = {
  id: 7,
  document_number: '9876543',
  document_type: 'CI',
  first_names: 'Valeria',
  last_names: 'Mamani',
  full_name: 'Valeria Mamani',
  is_foreign: false,
}

const staffUser = {
  id: 42,
  ci: '12345678',
  full_name: 'E2E Teacher',
  email: 'teacher@example.test',
  role: 'docente',
  teacher_ci: '12345678',
  is_active: true,
  last_login: null,
  avatar_url: null,
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Mocks the student portal: the temporary-password flag lives server-side and clears on a successful change. */
async function mockStudentApi(page: Page, options: { mustChange: boolean }) {
  let mustChange = options.mustChange
  let changed = 0
  await page.addInitScript(() => window.localStorage.setItem('student_token', 'e2e-student-token'))
  // Filter by pathname: a '**/api/**' glob also catches Vite's /src/api modules.
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const { pathname } = new URL(request.url())
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

    if (pathname === '/api/student-portal/auth/change-password' && request.method() === 'PUT') {
      mustChange = false
      changed += 1
      return json(200, { access_token: 'e2e-student-token-2', must_change_password: false })
    }
    if (pathname === '/api/student-portal/me') {
      // The refetch that follows the password change is slow: the guard must not trust the stale cache.
      if (changed > 0) await sleep(REFETCH_DELAY_MS)
      return json(200, { ...studentProfile, must_change_password: mustChange })
    }
    return json(404, { detail: `Unmocked E2E request: ${pathname}` })
  })
}

async function mockStaffApi(page: Page) {
  let mustChange = true
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const { pathname } = new URL(request.url())
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

    if (pathname === '/api/auth/login' && request.method() === 'POST') {
      return json(200, {
        access_token: 'e2e-staff-token', token_type: 'bearer', must_change_password: true,
        user: { ...staffUser, must_change_password: true },
      })
    }
    if (pathname === '/api/auth/change-password' && request.method() === 'PUT') {
      mustChange = false
      return json(200, { ...staffUser, must_change_password: false })
    }
    if (pathname === '/api/auth/me') return json(200, { ...staffUser, must_change_password: mustChange })
    return json(404, { detail: `Unmocked E2E request: ${pathname}` })
  })
}

test('student: the forced password change lands on the portal home, not on the form again', async ({ page }) => {
  await mockStudentApi(page, { mustChange: true })
  await page.goto('/estudiante/cambiar-clave')
  await expect(page.getByRole('heading', { name: 'Creá tu contraseña' })).toBeVisible()

  await page.getByLabel('Clave actual').fill('Temporal123')
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Repetí la nueva contraseña').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()

  await expect(page).toHaveURL('/estudiante')
  await expect(page.getByRole('button', { name: 'Cuenta de Valeria Mamani' })).toBeVisible()
  // Stays on the home through the slow refetch and after it settles.
  await page.waitForTimeout(REFETCH_DELAY_MS + 700)
  await expect(page).toHaveURL('/estudiante')
  await expect(page.getByRole('heading', { name: 'Creá tu contraseña' })).toHaveCount(0)
})

test('student: the guard still sends a pending temporary password to the change form', async ({ page }) => {
  await mockStudentApi(page, { mustChange: true })
  await page.goto('/estudiante')

  await expect(page).toHaveURL('/estudiante/cambiar-clave')
  await expect(page.getByRole('heading', { name: 'Creá tu contraseña' })).toBeVisible()
})

test('staff: the forced password change lands on the portal, not on the form again', async ({ page }) => {
  await mockStaffApi(page)
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Cédula de Identidad' }).fill('12345678')
  await page.getByLabel('Contraseña', { exact: true }).fill('Temporal123')
  await page.getByRole('button', { name: 'Ingresar al Sistema' }).click()

  await expect(page).toHaveURL('/change-password')
  await page.getByLabel('Contraseña temporal actual').fill('Temporal123')
  await page.locator('#force-new-password').fill(NEW_PASSWORD)
  await page.locator('#force-confirm-password').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Establecer nueva contraseña' }).click()

  await expect(page).toHaveURL('/portal', { timeout: 10_000 })
  await page.waitForTimeout(1000)
  await expect(page).toHaveURL('/portal')
  await expect(page.getByRole('heading', { name: 'Debés cambiar tu contraseña' })).toHaveCount(0)
})
