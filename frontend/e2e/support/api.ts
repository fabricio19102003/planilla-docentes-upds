import type { Page, Route } from '@playwright/test'

export interface ScheduleResponse {
  teacher_name: string
  designation_count: number
  subject_count: number
  group_count: number
  total_weekly_hours: number
  designations: Array<{
    subject: string
    semester: string
    group_code: string
    weekly_hours: number | null
    monthly_hours: number | null
    schedule: Array<{
      dia: string
      hora_inicio: string
      hora_fin: string
      horas_academicas: number
    }>
  }>
}

const docenteUser = {
  id: 42,
  ci: '12345678',
  full_name: 'E2E Teacher',
  email: 'teacher@example.test',
  role: 'docente',
  teacher_ci: '12345678',
  is_active: true,
  last_login: null,
  must_change_password: false,
  avatar_url: null,
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

export async function mockInvalidCredentials(page: Page) {
  await page.route('**/api/auth/login', async (route) => {
    if (route.request().method() !== 'POST') {
      await json(route, { detail: 'Method not allowed' }, 405)
      return
    }

    await json(route, { detail: 'Invalid credentials' }, 401)
  })
}

export async function mockAuthenticatedDocente(page: Page, schedule: ScheduleResponse) {
  await page.addInitScript(() => {
    window.localStorage.setItem('auth_token', 'e2e-docente-token')
  })

  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname

    if (request.method() === 'GET' && pathname === '/api/auth/me') {
      await json(route, docenteUser)
      return
    }
    if (request.method() === 'GET' && pathname === '/api/portal/notifications/unread-count') {
      await json(route, { count: 0 })
      return
    }
    if (request.method() === 'GET' && pathname === '/api/portal/notifications') {
      await json(route, [])
      return
    }
    if (request.method() === 'GET' && pathname === '/api/portal/schedule') {
      await json(route, schedule)
      return
    }

    await json(route, { detail: `Unexpected E2E request: ${request.method()} ${pathname}` }, 501)
  })
}
