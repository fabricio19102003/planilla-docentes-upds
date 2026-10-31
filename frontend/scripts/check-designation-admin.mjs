import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  academicHours,
  changeSummary,
  detectDesignationType,
  emptyDesignationForm,
  errorDetails,
  formatSlots,
  formErrors,
  formToPayload,
  itemToForm,
  regenerateText,
  suggestedMonthlyHours,
  suggestedSemesterHours,
  weeklyHours,
} from '../src/lib/designationAdminState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const item = {
  id: 7, teacher_ci: 'T1', teacher_name: 'ANA PEREZ', subject: 'ANATOMIA', semester: 'PRIMERO', group_code: 'M-1',
  academic_period: 'II/2026', designation_type: 'regular',
  schedule_json: [
    { dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30', duracion_minutos: 90, horas_academicas: 2 },
    { dia: 'miercoles', hora_inicio: '17:00', hora_fin: '19:15', duracion_minutos: 135, horas_academicas: 3 },
  ],
  semester_hours: 100, monthly_hours: 20, weekly_hours: 5, weekly_hours_calculated: 5, schedule_raw: null,
  contract_start_date: '2026-08-10', contract_end_date: null, created_at: '2026-08-01T00:00:00',
  status: 'active', has_contract: false, attendance_count: 0,
  actions: { edit: { allowed: true, reason: null }, edit_dates: { allowed: true, reason: null },
    finalize: { allowed: true, reason: null }, delete: { allowed: true, reason: null } },
}

test('academic hours follow the import rule (45-minute hours, rounded)', () => {
  assert.equal(academicHours('08:00', '09:30'), 2)
  assert.equal(academicHours('17:00', '19:15'), 3)
  assert.equal(academicHours('19:15', '23:00'), 5)
  assert.equal(academicHours('10:00', '09:00'), 0)
  assert.equal(academicHours('', '09:00'), 0)
})

test('weekly hours add every complete block and suggestions follow the usual ratios', () => {
  const slots = [{ dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30' }, { dia: 'martes', hora_inicio: '', hora_fin: '' }]
  assert.equal(weeklyHours(slots), 2)
  assert.equal(suggestedMonthlyHours(7), 28)
  assert.equal(suggestedSemesterHours(28), 140)
})

test('practice designations are detected from the subject like the import does', () => {
  assert.equal(detectDesignationType('Práctica Clínica I'), 'practice')
  assert.equal(detectDesignationType('PRACTICAS INTERNAS'), 'practice')
  assert.equal(detectDesignationType('Anatomía'), 'regular')
})

test('a schedule is shown as short readable text', () => {
  assert.equal(formatSlots(item.schedule_json), 'Lun 08:00–09:30 · Mié 17:00–19:15')
  assert.equal(formatSlots([]), 'Sin horario')
})

test('an item becomes an editable form and back into the API payload', () => {
  const form = itemToForm(item)
  assert.deepEqual(form, {
    teacherCi: 'T1', subject: 'ANATOMIA', semester: 'PRIMERO', groupCode: 'M-1', academicPeriod: 'II/2026',
    designationType: 'regular',
    slots: [
      { dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30' },
      { dia: 'miercoles', hora_inicio: '17:00', hora_fin: '19:15' },
    ],
    monthlyHours: '20', semesterHours: '100', contractStartDate: '2026-08-10', contractEndDate: '',
  })
  assert.deepEqual(formToPayload(form), {
    teacher_ci: 'T1', subject: 'ANATOMIA', semester: 'PRIMERO', group_code: 'M-1', academic_period: 'II/2026',
    designation_type: 'regular',
    schedule: [
      { dia: 'lunes', hora_inicio: '08:00', hora_fin: '09:30' },
      { dia: 'miercoles', hora_inicio: '17:00', hora_fin: '19:15' },
    ],
    monthly_hours: 20, semester_hours: 100, contract_start_date: '2026-08-10', contract_end_date: null,
  })
})

test('the form explains every missing or wrong value in plain words', () => {
  const empty = emptyDesignationForm('II/2026')
  assert.deepEqual(formErrors(empty), [
    'Elegí un docente.',
    'Escribí la materia.',
    'Elegí el semestre.',
    'Escribí el grupo.',
    'Bloque 1: elegí el día.',
    'Bloque 1: completá la hora de inicio y de fin.',
    'Indicá las horas mensuales.',
  ])
  const form = { ...itemToForm(item), slots: [{ dia: 'lunes', hora_inicio: '10:00', hora_fin: '09:00' }], contractEndDate: '2026-08-01' }
  assert.deepEqual(formErrors(form), [
    'Bloque 1: la hora de fin tiene que ser posterior a la de inicio.',
    'La fecha de fin no puede ser anterior a la fecha de inicio.',
  ])
  assert.deepEqual(formErrors(itemToForm(item)), [])
})

test('import rows are summarized by what will happen', () => {
  const changes = [
    { row: 1, action: 'create', fields: [] },
    { row: 2, action: 'update', fields: ['monthly_hours', 'schedule_json'] },
    { row: 3, action: 'noop', fields: [] },
    { row: 4, action: 'noop', fields: [] },
  ]
  assert.deepEqual(changeSummary(changes), { create: 1, update: 1, noop: 2 })
})

test('server answers become a title and a list of reasons', () => {
  const response = (detail) => ({ response: { data: { detail } } })
  assert.deepEqual(errorDetails(response('Docente no encontrado'), 'x'), { title: 'Docente no encontrado', items: [] })
  assert.deepEqual(errorDetails(response({ message: 'Revisá los datos de la designación.', errors: ['Falta la materia.'] }), 'x'),
    { title: 'Revisá los datos de la designación.', items: ['Falta la materia.'] })
  assert.deepEqual(errorDetails(response({ message: 'No se puede guardar porque ya se pagó con estos datos.',
    blockers: [{ code: 'payroll_approved', message: 'La planilla de teoría 9/2026 ya está aprobada.' }] }), 'x'),
  { title: 'No se puede guardar porque ya se pagó con estos datos.', items: ['La planilla de teoría 9/2026 ya está aprobada.'] })
  assert.deepEqual(errorDetails(new Error('network'), 'No se pudo guardar.'), { title: 'No se pudo guardar.', items: [] })
})

test('payroll months to regenerate are named in plain words', () => {
  assert.equal(regenerateText([]), '')
  assert.equal(regenerateText([{ planilla: 'regular', month: 10, year: 2026 }, { planilla: 'practice', month: 11, year: 2026 }]),
    'Regenerá la planilla de teoría 10/2026, práctica 11/2026 para que tome el cambio.')
})

test('page, route, menu entry and hooks are wired to the admin designations API', () => {
  const nav = read('src/lib/navigation.ts')
  assert.match(nav, /\{ to: '\/designations', label: 'Designaciones', icon: 'designations' \}/)
  assert.match(read('src/components/layout/Sidebar.tsx'), /designations: /)
  assert.match(read('src/App.tsx'), /<Route path="designations" element={<DesignationsPage \/>} \/>/)
  const hooks = read('src/api/hooks/useDesignationAdmin.ts')
  for (const fragment of ["'/admin/designations'", '/finalize', 'api.delete', 'api.put', 'api.post']) {
    assert.ok(hooks.includes(fragment), fragment)
  }
  const page = read('src/pages/DesignationsPage.tsx')
  for (const text of ['Nueva designación', 'Importar archivo', 'Finalizar', 'Eliminar', 'Buscar docente o materia']) {
    assert.ok(page.includes(text), text)
  }
})

test('teacher detail links to the designations page filtered by that teacher', () => {
  const detail = read('src/pages/TeacherDetailPage.tsx')
  assert.match(detail, /\/designations\?teacher=\$\{encodeURIComponent\(teacher\.ci\)\}/)
  assert.ok(detail.includes('Gestionar designaciones'))
  assert.match(read('src/pages/DesignationsPage.tsx'), /searchParams\.get\('teacher'\)/)
  assert.match(read('src/pages/UploadPage.tsx'), /to="\/designations"/)
})
