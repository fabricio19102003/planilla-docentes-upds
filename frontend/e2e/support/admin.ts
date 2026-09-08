import type { Page } from '@playwright/test'

export const adminUser = {
  id: 1,
  ci: 'ADMIN-E2E',
  full_name: 'E2E Admin',
  email: null,
  role: 'admin',
  teacher_ci: null,
  is_active: true,
  last_login: null,
  must_change_password: false,
  avatar_url: null,
}

export async function authenticateAdmin(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('auth_token', 'e2e-admin-token'))
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: adminUser }))
}

export function teacherDetail(avatarUrl: string | null) {
  return {
    ci: 'CI-E2E',
    full_name: 'Ana Docente',
    email: null,
    phone: null,
    gender: null,
    external_permanent: null,
    academic_level: null,
    profession: null,
    specialty: null,
    bank: null,
    account_number: null,
    nit: null,
    sap_code: null,
    invoice_retention: null,
    avatar_url: avatarUrl,
    created_at: '2026-01-01T00:00:00',
    updated_at: null,
    designations: [],
    attendance_summary: { total_records: 0, attended: 0, late: 0, absent: 0, no_exit: 0, total_academic_hours: 0 },
  }
}
