import { expect, test, type Page } from '@playwright/test'

// Guard pins for the student first-login fix: clearing the cached flag must never let a student into the
// portal unless the server accepted the new password and still agrees after the profile refetch.

const NEW_PASSWORD = 'Nueva2026x'

const studentProfile = {
  id: 7,
  document_number: '9876543',
  document_type: 'CI',
  first_names: 'Valeria',
  last_names: 'Mamani',
  full_name: 'Valeria Mamani',
  is_foreign: false,
}

type ChangeOutcome = 'accepted' | 'rejected' | 'accepted-but-still-flagged'

/** Mocks the student portal; records the bearer token of every profile request. */
async function mockStudentApi(page: Page, outcome: ChangeOutcome) {
  let mustChange = true
  const profileTokens: string[] = []
  await page.addInitScript(() => {
    if (!window.localStorage.getItem('student_token')) window.localStorage.setItem('student_token', 'tok-1')
  })
  // Filter by pathname: a '**/api/**' glob also catches Vite's /src/api modules.
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const { pathname } = new URL(request.url())
    const json = (status: number, body: unknown) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

    if (pathname === '/api/student-portal/auth/change-password' && request.method() === 'PUT') {
      if (outcome === 'rejected') return json(400, { detail: 'La clave actual no es correcta.' })
      if (outcome === 'accepted') mustChange = false
      return json(200, { access_token: 'tok-2', must_change_password: false })
    }
    if (pathname === '/api/student-portal/me') {
      profileTokens.push(request.headers().authorization ?? '')
      return json(200, { ...studentProfile, must_change_password: mustChange })
    }
    return json(404, { detail: `Unmocked E2E request: ${pathname}` })
  })
  return { profileTokens }
}

async function submitPasswordChange(page: Page) {
  await page.goto('/estudiante/cambiar-clave')
  await expect(page.getByRole('heading', { name: 'Creá tu contraseña' })).toBeVisible()
  await page.getByLabel('Clave actual').fill('Temporal123')
  await page.getByLabel('Nueva contraseña', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Repetí la nueva contraseña').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()
}

const storedToken = (page: Page) => page.evaluate(() => window.localStorage.getItem('student_token'))

test('student: a rejected change keeps the flag, the old token and the guard', async ({ page }) => {
  await mockStudentApi(page, 'rejected')
  await submitPasswordChange(page)

  await expect(page.getByText('La clave actual no es correcta.')).toBeVisible()
  await expect(page).toHaveURL('/estudiante/cambiar-clave')
  expect(await storedToken(page)).toBe('tok-1')

  await page.goto('/estudiante')
  await expect(page).toHaveURL('/estudiante/cambiar-clave')
})

test('student: after an accepted change a reload stays on the portal with the new token', async ({ page }) => {
  const { profileTokens } = await mockStudentApi(page, 'accepted')
  await submitPasswordChange(page)
  await expect(page).toHaveURL('/estudiante')

  await page.reload()
  await expect(page).toHaveURL('/estudiante')
  await expect(page.getByRole('button', { name: 'Cuenta de Valeria Mamani' })).toBeVisible()
  expect(await storedToken(page)).toBe('tok-2')
  expect(profileTokens.at(-1)).toBe('Bearer tok-2')
})

test('student: if the server still reports the flag after the change, the refetch sends the student back', async ({ page }) => {
  await mockStudentApi(page, 'accepted-but-still-flagged')
  await submitPasswordChange(page)

  await expect(page).toHaveURL('/estudiante/cambiar-clave', { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Creá tu contraseña' })).toBeVisible()
})
