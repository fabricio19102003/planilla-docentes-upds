import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

// T10.1 Cierre mensual: S11 page rules for the six monthly-close pages.
const src = join(resolve(import.meta.dirname, '..'), 'src')

const PAGES = [
  'pages/DashboardPage.tsx',
  'pages/UploadPage.tsx',
  'pages/AttendancePage.tsx',
  'pages/PracticeAttendancePage.tsx',
  'pages/ObservationsPage.tsx',
  'pages/AttendanceAuditPage.tsx',
]

const PALETTE = 'gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose'

function read(relative) {
  const path = join(src, relative)
  assert.ok(existsSync(path), `src/${relative} is missing`)
  return readFileSync(path, 'utf8')
}

function eachPage(check) {
  for (const file of PAGES) check(file, read(file))
}

test('pages carry no hex colors, color styles, gradients or card-3d', () => {
  eachPage((file, code) => {
    assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${file} must not contain hex colors`)
    assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${file} must not use gradient-* classes`)
    assert.deepEqual(code.match(/(?:linear|radial)-gradient/g) ?? [], [], `${file} must not use CSS gradients`)
    assert.deepEqual(code.match(/\bcard-3d[\w-]*/g) ?? [], [], `${file} must not use card-3d`)
    assert.doesNotMatch(code, /style=\{\{[^}]*(?:color|Color|background)/, `${file} must not set colors through style`)
  })
})

test('pages use theme tokens instead of raw palette classes', () => {
  const rawPalette = new RegExp(`\\b(?:bg|text|border|ring|fill|stroke|from|to|via|divide|outline)-(?:${PALETTE})-\\d{2,3}`, 'g')
  eachPage((file, code) => {
    assert.deepEqual(code.match(rawPalette) ?? [], [], `${file} must use token colors only`)
    assert.deepEqual(code.match(/\b(?:bg|text|border)-(?:white|black)\b/g) ?? [], [], `${file} must not use bg/text-white or black`)
  })
})

test('every page renders the shared PageHeader and leaves the h1 to the app header', () => {
  eachPage((file, code) => {
    assert.match(code, /import \{[^}]*\bPageHeader\b[^}]*\} from '@\/components\/shared\/PageHeader'/, `${file} must import PageHeader`)
    assert.match(code, /<PageHeader\b/, `${file} must render PageHeader`)
    assert.doesNotMatch(code, /<h1\b/, `${file} must not render its own h1`)
  })
})

test('tables go through TableCard or DataTable, with skeleton loading instead of a page spinner', () => {
  eachPage((file, code) => {
    assert.doesNotMatch(code, /<table\b/, `${file} must not hand-roll a <table>`)
    assert.doesNotMatch(code, /LoadingPage|LoadingSpinner/, `${file} must use Skeleton for loading states`)
  })
})

test('empty, error and status states use EmptyState, Alert and StatusBadge', () => {
  const dashboard = read('pages/DashboardPage.tsx')
  assert.match(dashboard, /@\/components\/ui\/skeleton/)
  assert.match(dashboard, /@\/components\/ui\/alert'/)
  assert.match(dashboard, /StatusBadge/)
  assert.match(dashboard, /tone=/)
  assert.doesNotMatch(dashboard, /\bcolor=\{?['"]/, 'Dashboard StatCards must use tone, not legacy color')

  for (const file of ['pages/AttendancePage.tsx', 'pages/ObservationsPage.tsx', 'pages/PracticeAttendancePage.tsx', 'pages/AttendanceAuditPage.tsx']) {
    const code = read(file)
    assert.match(code, /EmptyState/, `${file} needs EmptyState`)
    assert.match(code, /StatusBadge/, `${file} needs StatusBadge for statuses`)
  }
  assert.match(read('pages/AttendanceAuditPage.tsx'), /@\/components\/ui\/alert'/, 'audit error uses Alert')
  assert.match(read('pages/AttendanceAuditPage.tsx'), /@\/components\/ui\/skeleton/, 'audit loading uses Skeleton')
})

test('UploadPage shows FileUploader progress while uploading', () => {
  const code = read('pages/UploadPage.tsx')
  assert.match(code, /progress=\{/)
  assert.match(code, /onProgress/)
  assert.match(code, /StatusBadge/)
})

test('data-changing actions confirm through ConfirmAlertDialog', () => {
  // UploadPage confirms the designation import through the shared wizard it renders.
  assert.match(read('pages/UploadPage.tsx'), /<DesignationImportWizard \/>/)
  for (const file of ['pages/PracticeAttendancePage.tsx', 'pages/AttendancePage.tsx', 'components/designations/DesignationImportWizard.tsx']) {
    const code = read(file)
    assert.match(code, /ConfirmAlertDialog/, `${file} must confirm destructive or overwriting actions`)
  }
  const practice = read('pages/PracticeAttendancePage.tsx')
  assert.doesNotMatch(practice, /\bconfirm\(/, 'PracticeAttendance must not use window.confirm')
  assert.match(practice, /tone: 'destructive'/, 'deleting a record uses the destructive tone')
})

test('behavior contracts the other checks and e2e rely on are kept', () => {
  const dashboard = read('pages/DashboardPage.tsx')
  assert.match(dashboard, /title="Total a pagar \(teoría \+ asistencial\)"/)
  assert.match(dashboard, /formatPaymentBreakdown/)

  const upload = read('pages/UploadPage.tsx')
  const designationImport = read('components/designations/DesignationImportWizard.tsx')
  for (const text of ['Generar vista previa', 'Confirmar e importar', 'no lo activa automáticamente']) {
    assert.ok(designationImport.includes(text), `the designation import must keep "${text}"`)
  }
  for (const text of ['Generar vista previa', 'Confirmar e importar', 'No activa períodos, elimina datos ni modifica accesos']) {
    assert.ok(upload.includes(text), `UploadPage must keep "${text}"`)
  }
  assert.match(designationImport, /confirmation_digest: desPreview\.digest/)
  assert.match(upload, /Object\.entries\(teacherPreview\.fields\)/)

  const practice = read('pages/PracticeAttendancePage.tsx')
  assert.match(practice, /aria-label=\{`Eliminar asistencia de /)
  assert.match(practice, /aria-label="Guardar observación"/)
})
