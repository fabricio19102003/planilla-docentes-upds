import assert from 'node:assert/strict'
import test from 'node:test'

import {
  courseFormProblem,
  courseStatus,
  coursePayload,
  courseUpdatePayload,
  emptyCourseForm,
  isValidTerm,
  priceLabel,
  seatsLabel,
  settingsFormFrom,
  settingsPayload,
  settingsProblem,
  studentPriceNote,
  termLabel,
} from '../src/lib/intensiveCoursesState.ts'

const settings = {
  theory_hourly_rate: 50, practice_hourly_rate: 40, margin_factor: 1.1, min_price: 1200, max_price: 1600,
  is_configured: true,
}
const goodForm = () => settingsFormFrom(settings)

test('terms follow VER/YYYY or INV/YYYY and have a Spanish label', () => {
  assert.equal(isValidTerm('VER/2027'), true)
  assert.equal(isValidTerm('INV/2026'), true)
  for (const bad of ['', 'I/2027', 'ver/2027', 'VER/27', 'VER-2027', 'VER/20277', ' VER/2027']) assert.equal(isValidTerm(bad), false, bad)
  assert.equal(termLabel('VER/2027'), 'Verano 2027')
  assert.equal(termLabel('INV/2026'), 'Invierno 2026')
  assert.equal(termLabel('I/2027'), 'I/2027')
})

test('settings form starts empty for unset rates and carries the defaults', () => {
  const form = settingsFormFrom({ ...settings, theory_hourly_rate: null, practice_hourly_rate: null, is_configured: false })
  assert.deepEqual(form, { theory_hourly_rate: '', practice_hourly_rate: '', margin_factor: '1.1', min_price: '1200', max_price: '1600' })
  assert.match(settingsProblem(form) ?? '', /tarifa/i)
})

test('settings validation mirrors the backend rules', () => {
  assert.equal(settingsProblem(goodForm()), null)
  assert.match(settingsProblem({ ...goodForm(), theory_hourly_rate: '0' }) ?? '', /teoría.*mayor a 0/i)
  assert.match(settingsProblem({ ...goodForm(), practice_hourly_rate: '-3' }) ?? '', /práctica.*mayor a 0/i)
  assert.match(settingsProblem({ ...goodForm(), practice_hourly_rate: 'abc' }) ?? '', /práctica/i)
  assert.match(settingsProblem({ ...goodForm(), theory_hourly_rate: '50.123' }) ?? '', /2 decimales/)
  assert.match(settingsProblem({ ...goodForm(), margin_factor: '0.99' }) ?? '', /1 o más/)
  assert.equal(settingsProblem({ ...goodForm(), margin_factor: '1' }), null)
  assert.match(settingsProblem({ ...goodForm(), margin_factor: '1.1234' }) ?? '', /3 decimales/)
  assert.match(settingsProblem({ ...goodForm(), min_price: '0' }) ?? '', /mínimo/i)
  assert.match(settingsProblem({ ...goodForm(), max_price: '12.5' }) ?? '', /máximo/i)
  assert.equal(settingsProblem({ ...goodForm(), min_price: '1500', max_price: '1500' }), null)
  assert.equal(settingsProblem({ ...goodForm(), min_price: '1601' }), 'El precio mínimo no puede superar al máximo')
})

test('settings payload converts to numbers and accepts a decimal comma', () => {
  assert.deepEqual(settingsPayload({ ...goodForm(), theory_hourly_rate: '55,5' }), {
    theory_hourly_rate: 55.5, practice_hourly_rate: 40, margin_factor: 1.1, min_price: 1200, max_price: 1600,
  })
})

test('course status separates closed, scheduled, open and expired enrollment', () => {
  const base = { status: 'open', is_enrollment_open: true, enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20' }
  assert.deepEqual(courseStatus(base, '2027-01-15'), { label: 'Inscripción abierta', variant: 'success' })
  assert.deepEqual(courseStatus({ ...base, is_enrollment_open: false }, '2027-01-05'), { label: 'Programado', variant: 'info' })
  assert.deepEqual(courseStatus({ ...base, is_enrollment_open: false }, '2027-01-25'), { label: 'Inscripción vencida', variant: 'warning' })
  assert.deepEqual(courseStatus({ ...base, status: 'closed', is_enrollment_open: false }, '2027-01-15'), { label: 'Cerrado', variant: 'outline' })
})

test('price labels tell an estimate from the fixed price', () => {
  assert.equal(priceLabel({ amount: 1400, is_final: false }), '1.400 Bs (estimado)')
  assert.equal(priceLabel({ amount: 1250, is_final: true }), '1.250 Bs (fijo)')
  assert.equal(studentPriceNote({ amount: 1400, is_final: false }), 'Estimado: baja si se inscriben más')
  assert.equal(studentPriceNote({ amount: 1400, is_final: true }), 'Precio fijo')
  assert.equal(seatsLabel({ enrolled: 12, capacity: 40 }), '12 / 40')
})

test('course form validation and payload leave empty hours to the curriculum', () => {
  const form = { ...emptyCourseForm(), term_code: 'VER/2027', subject_code: 'BIO 0100', teacher_ci: '123', capacity: '30',
    enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20' }
  assert.equal(courseFormProblem(form, 'create'), null)
  assert.deepEqual(coursePayload(form), {
    term_code: 'VER/2027', subject_code: 'BIO 0100', teacher_ci: '123', capacity: 30,
    enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20',
  })
  assert.deepEqual(coursePayload({ ...form, theory_hours: '48', practice_hours: '0' }).theory_hours, 48)
  assert.equal(coursePayload({ ...form, theory_hours: '48', practice_hours: '0' }).practice_hours, 0)
  assert.match(courseFormProblem({ ...form, term_code: 'I/2027' }, 'create') ?? '', /VER\/AAAA o INV\/AAAA/)
  assert.match(courseFormProblem({ ...form, subject_code: '' }, 'create') ?? '', /materia/i)
  assert.match(courseFormProblem({ ...form, teacher_ci: '' }, 'create') ?? '', /docente/i)
  assert.match(courseFormProblem({ ...form, capacity: '0' }, 'create') ?? '', /cupos/i)
  assert.match(courseFormProblem({ ...form, capacity: '1001' }, 'create') ?? '', /cupos/i)
  assert.match(courseFormProblem({ ...form, enrollment_ends_on: '2027-01-09' }, 'create') ?? '', /fecha de fin/i)
  assert.match(courseFormProblem({ ...form, enrollment_starts_on: '' }, 'create') ?? '', /fechas/i)
  assert.match(courseFormProblem({ ...form, theory_hours: '-1' }, 'create') ?? '', /horas/i)
  assert.match(courseFormProblem({ ...form, theory_hours: '0', practice_hours: '0' }, 'create') ?? '', /ambas cero/)
})

test('editing keeps term and subject fixed and always sends the hours', () => {
  const form = { ...emptyCourseForm(), term_code: 'VER/2027', subject_code: 'BIO 0100', teacher_ci: '123', capacity: '30',
    enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20', theory_hours: '48', practice_hours: '16' }
  assert.equal(courseFormProblem({ ...form, term_code: 'bad' }, 'edit'), null)
  assert.match(courseFormProblem({ ...form, theory_hours: '' }, 'edit') ?? '', /horas/i)
  assert.deepEqual(courseUpdatePayload(form), {
    teacher_ci: '123', capacity: 30, enrollment_starts_on: '2027-01-10', enrollment_ends_on: '2027-01-20',
    theory_hours: 48, practice_hours: 16,
  })
})
