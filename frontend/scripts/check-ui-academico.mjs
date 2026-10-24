import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const src = join(root, 'src')

const PAGES = [
  'TeachersPage',
  'TeacherDetailPage',
  'ContractsPage',
  'AcademicManagementPage',
  'SchedulePlannerPage',
  'AdminRequestsPage',
  'UsersPage',
  'ActivityLogPage',
  'BackupPage',
  'SettingsPage',
  'LoginPage',
  'ForceChangePasswordPage',
]

// Pages that live under the admin layout and therefore open with the shared PageHeader.
const ADMIN_PAGES = PAGES.filter((name) => !['LoginPage', 'ForceChangePasswordPage'].includes(name))

const COMPONENT_DIRS = ['academic-management', 'requests', 'teachers', 'auth']

function read(relative) {
  return readFileSync(join(src, relative), 'utf8')
}

function componentFiles() {
  return COMPONENT_DIRS.flatMap((dir) =>
    readdirSync(join(src, 'components', dir))
      .filter((name) => name.endsWith('.tsx'))
      .map((name) => `components/${dir}/${name}`),
  )
}

function assertNoLegacyChrome(file) {
  const code = read(file)
  assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${file} must not contain hex colors`)
  assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${file} must not use gradient-* classes`)
  assert.deepEqual(code.match(/(?:linear|radial)-gradient/g) ?? [], [], `${file} must not use CSS gradients`)
  assert.deepEqual(code.match(/\bcard-3d\b/g) ?? [], [], `${file} must not use card-3d`)
  assert.doesNotMatch(code, /style=\{\{[^}]*(?:color|Color|background)/, `${file} must not set colors through style`)
}

test('the 12 academic and admin pages use theme tokens only', () => {
  for (const page of PAGES) assertNoLegacyChrome(`pages/${page}.tsx`)
})

test('the academic, requests, teachers and auth components use theme tokens only', () => {
  for (const file of componentFiles()) assertNoLegacyChrome(file)
})

test('admin pages open with the shared PageHeader', () => {
  for (const page of ADMIN_PAGES) {
    const code = read(`pages/${page}.tsx`)
    assert.match(code, /from '@\/components\/shared\/PageHeader'/, `${page} must import PageHeader`)
    assert.match(code, /<PageHeader\b/, `${page} must render PageHeader`)
  }
})

test('pages do not keep navy table headers or hand-rolled status colors', () => {
  for (const page of PAGES) {
    const code = read(`pages/${page}.tsx`)
    assert.doesNotMatch(code, /bg-(?:red|green|yellow|amber|emerald|blue|orange|slate|gray)-\d{2,3}/, `${page} must use semantic tokens`)
    assert.doesNotMatch(code, /text-(?:red|green|yellow|amber|emerald|blue|orange|slate|gray)-\d{2,3}/, `${page} must use semantic tokens`)
  }
})

test('destructive actions confirm through ConfirmAlertDialog', () => {
  const required = {
    'pages/UsersPage.tsx': 'deactivate user',
    'pages/TeacherDetailPage.tsx': 'delete teacher and delete photo',
    'pages/TeachersPage.tsx': 'bulk delete teachers',
    'pages/BackupPage.tsx': 'delete backup',
    'pages/AdminRequestsPage.tsx': 'reject request',
  }
  for (const [file, action] of Object.entries(required)) {
    const code = read(file)
    assert.match(code, /from '@\/components\/shared\/ConfirmAlertDialog'/, `${file} must import ConfirmAlertDialog (${action})`)
    assert.match(code, /<ConfirmAlertDialog\b/, `${file} must render ConfirmAlertDialog (${action})`)
  }
})

// WhatsAppConsentCard keeps its window.confirm: check-whatsapp-consent-card.mjs and the e2e opt-out spec depend on it.
test('no page confirms with window.confirm or a hand-built delete dialog', () => {
  for (const page of PAGES) {
    assert.doesNotMatch(read(`pages/${page}.tsx`), /window\.confirm\(/, `${page} must not use window.confirm`)
  }
  assert.doesNotMatch(read('pages/TeacherDetailPage.tsx'), /function DeleteConfirmDialog/)
})

test('the login pages keep the e2e contract and use the UPDS brand logo', () => {
  const login = read('pages/LoginPage.tsx')
  assert.match(login, /from '@\/components\/layout\/Logo'/)
  assert.match(login, /Cédula de Identidad/)
  assert.match(login, /Ingresar al Sistema/)
  assert.match(login, /Mostrar contraseña/)
  assert.match(login, /Ocultar contraseña/)
  assert.match(login, /<Alert\b/, 'errors render through the coss Alert (role=alert)')
  const force = read('pages/ForceChangePasswordPage.tsx')
  assert.match(force, /from '@\/components\/layout\/Logo'/)
})
