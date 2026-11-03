import assert from 'node:assert/strict'
import test from 'node:test'

import { deriveMonthlyClose, MONTHLY_CLOSE_STEP_KEYS } from '../src/lib/monthlyClose.ts'

const PERIOD = { month: 10, year: 2026 }
const upload = (overrides = {}) => ({ ...PERIOD, status: 'PROCESSED', total_records: 120, ...overrides })

function derive(overrides = {}) {
  return deriveMonthlyClose({
    ...PERIOD,
    uploads: [],
    attendanceSlots: null,
    planilla: null,
    publication: null,
    ...overrides,
  })
}

const states = (steps) => Object.fromEntries(steps.map((step) => [step.key, step.state]))
const step = (steps, key) => steps.find((item) => item.key === key)

test('steps come in the monthly-close order with their page routes', () => {
  const steps = derive()
  assert.deepEqual(steps.map((item) => item.key), ['biometrico', 'asistencia', 'planilla', 'aprobacion', 'publicacion'])
  assert.deepEqual(MONTHLY_CLOSE_STEP_KEYS, ['biometrico', 'asistencia', 'planilla', 'aprobacion', 'publicacion'])
  assert.deepEqual(steps.map((item) => item.label), ['Biométrico', 'Asistencia', 'Planilla', 'Aprobación', 'Publicación'])
  assert.deepEqual(steps.map((item) => item.href), ['/upload', '/attendance', '/planilla', '/planilla', '/planilla'])
})

test('no data: biométrico is the current step and the rest are pending', () => {
  const steps = derive({ month: null, year: null })
  assert.deepEqual(states(steps), {
    biometrico: 'current',
    asistencia: 'pending',
    planilla: 'pending',
    aprobacion: 'pending',
    publicacion: 'pending',
  })
  assert.equal(step(steps, 'biometrico').detail, 'Sin datos cargados')
})

test('biométrico is done once a processed upload exists for the billing period', () => {
  const steps = derive({ uploads: [upload()] })
  assert.equal(step(steps, 'biometrico').state, 'done')
  assert.equal(step(steps, 'biometrico').detail, 'Octubre 2026 cargado')
  assert.equal(step(steps, 'asistencia').state, 'current')
})

test('uploads from another period or not processed do not complete biométrico', () => {
  const other = derive({ uploads: [upload({ month: 9 }), upload({ year: 2025 })] })
  assert.equal(step(other, 'biometrico').state, 'current')
  assert.equal(step(other, 'biometrico').detail, 'Sin archivo de Octubre 2026')
  const failed = derive({ uploads: [upload({ status: 'FAILED' })] })
  assert.equal(step(failed, 'biometrico').state, 'current')
})

test('asistencia is done when the attendance summary has slots', () => {
  const steps = derive({ uploads: [upload()], attendanceSlots: 915 })
  assert.equal(step(steps, 'asistencia').state, 'done')
  assert.equal(step(steps, 'asistencia').detail, '915 horarios procesados')
  assert.equal(step(steps, 'planilla').state, 'current')
  const empty = derive({ uploads: [upload()], attendanceSlots: 0 })
  assert.equal(step(empty, 'asistencia').state, 'current')
  assert.equal(step(empty, 'asistencia').detail, 'Sin procesar')
})

test('planilla is done once generated and not rejected', () => {
  const steps = derive({ uploads: [upload()], attendanceSlots: 10, planilla: { status: 'pending' } })
  assert.equal(step(steps, 'planilla').state, 'done')
  assert.equal(step(steps, 'planilla').detail, 'Generada')
  assert.equal(step(steps, 'aprobacion').state, 'current')
  assert.equal(step(steps, 'aprobacion').detail, 'Pendiente de aprobación')
  assert.equal(step(derive({ uploads: [upload()], attendanceSlots: 10 }), 'planilla').detail, 'Sin generar')
})

test('a rejected planilla keeps planilla as the current step', () => {
  const steps = derive({ uploads: [upload()], attendanceSlots: 10, planilla: { status: 'rejected' } })
  assert.deepEqual(states(steps), {
    biometrico: 'done',
    asistencia: 'done',
    planilla: 'current',
    aprobacion: 'pending',
    publicacion: 'pending',
  })
  assert.equal(step(steps, 'planilla').detail, 'Rechazada · regenerar')
})

test('aprobación is done when the planilla is approved; publicación becomes current', () => {
  const steps = derive({ uploads: [upload()], attendanceSlots: 10, planilla: { status: 'approved' } })
  assert.equal(step(steps, 'aprobacion').state, 'done')
  assert.equal(step(steps, 'aprobacion').detail, 'Aprobada')
  assert.equal(step(steps, 'publicacion').state, 'current')
  assert.equal(step(steps, 'publicacion').detail, 'Sin publicar')
})

test('publicación is done when the billing is published and the whole close is done', () => {
  const steps = derive({
    uploads: [upload()],
    attendanceSlots: 10,
    planilla: { status: 'approved' },
    publication: { status: 'published' },
  })
  assert.deepEqual(states(steps), {
    biometrico: 'done',
    asistencia: 'done',
    planilla: 'done',
    aprobacion: 'done',
    publicacion: 'done',
  })
  assert.equal(step(steps, 'publicacion').detail, 'Publicada')
  const draft = derive({ uploads: [upload()], attendanceSlots: 10, planilla: { status: 'approved' }, publication: { status: 'draft' } })
  assert.equal(step(draft, 'publicacion').state, 'current')
})

test('the first step that is not done is the only current one', () => {
  const cases = [
    [{}, 'biometrico'],
    [{ uploads: [upload()] }, 'asistencia'],
    [{ uploads: [upload()], attendanceSlots: 5 }, 'planilla'],
    [{ uploads: [upload()], attendanceSlots: 5, planilla: { status: 'pending' } }, 'aprobacion'],
    [{ uploads: [upload()], attendanceSlots: 5, planilla: { status: 'approved' } }, 'publicacion'],
  ]
  for (const [overrides, expected] of cases) {
    const steps = derive(overrides)
    const current = steps.filter((item) => item.state === 'current')
    assert.deepEqual(current.map((item) => item.key), [expected])
    const index = steps.findIndex((item) => item.key === expected)
    assert.ok(steps.slice(0, index).every((item) => item.state === 'done'))
    assert.ok(steps.slice(index + 1).every((item) => item.state === 'pending'))
  }
})

test('a later step with evidence completes the earlier ones', () => {
  // The recent-uploads list is short, so a published month must not show biométrico as missing.
  const steps = derive({ planilla: { status: 'approved' }, publication: { status: 'published' } })
  assert.deepEqual(states(steps), {
    biometrico: 'done',
    asistencia: 'done',
    planilla: 'done',
    aprobacion: 'done',
    publicacion: 'done',
  })
})
