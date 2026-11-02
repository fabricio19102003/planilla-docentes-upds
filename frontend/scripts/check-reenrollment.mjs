import assert from 'node:assert/strict'
import test from 'node:test'

import {
  OBSERVATION_REASONS,
  accountStatus,
  credentialsCsv,
  formatBs,
  inboxQueryParams,
  requestStatus,
  windowState,
} from '../src/lib/reenrollmentState.ts'

test('request statuses map to Spanish labels and badge variants', () => {
  assert.deepEqual(requestStatus('pendiente'), { label: 'Pendiente', variant: 'warning' })
  assert.deepEqual(requestStatus('realizada'), { label: 'Realizada', variant: 'success' })
  assert.deepEqual(requestStatus('observada'), { label: 'Observada', variant: 'error' })
})

test('observation reasons match the API values', () => {
  assert.deepEqual(OBSERVATION_REASONS.map((r) => [r.value, r.label]), [
    ['documentos_migracion', 'Documentos de migración'],
    ['pago_pendiente', 'Pago pendiente'],
    ['otro', 'Otro'],
  ])
})

test('portal account status covers every state', () => {
  assert.deepEqual(accountStatus(null), { label: 'Sin cuenta', variant: 'outline' })
  const base = { is_active: true, must_change_password: false, temporary_issued_at: null, last_login: null }
  assert.deepEqual(accountStatus(base), { label: 'Activa', variant: 'success' })
  assert.deepEqual(accountStatus({ ...base, must_change_password: true }), { label: 'Con clave temporal', variant: 'warning' })
  assert.deepEqual(accountStatus({ ...base, is_active: false, must_change_password: true }), { label: 'Deshabilitada', variant: 'error' })
})

test('credentials export as an Excel-friendly CSV without formula injection', () => {
  const csv = credentialsCsv([
    { student_id: 1, document_number: 'I-11626046', full_name: 'Raimunda "Ray" Paiva', temporary_password: 'Abcd-Efgh-Jkm' },
    { student_id: 2, document_number: '7485000', full_name: '=HYPERLINK("x")', temporary_password: '+Abc-Defg-Hjk' },
  ])
  assert.equal(csv, '\ufeffDocumento,Nombre,Clave temporal\r\n'
    + 'I-11626046,"Raimunda ""Ray"" Paiva",Abcd-Efgh-Jkm\r\n'
    + '7485000,"\'=HYPERLINK(""x"")",\'+Abc-Defg-Hjk\r\n')
})

test('amounts are shown in bolivianos with thousands separators', () => {
  assert.equal(formatBs(850), '850 Bs')
  assert.equal(formatBs(8000), '8.000 Bs')
  assert.equal(formatBs(0), '0 Bs')
})

test('inbox filters drop empty values', () => {
  assert.deepEqual(inboxQueryParams({ status: '', semester: '', search: '  ', foreign: 'all', page: 1 }), { page: 1, page_size: 25 })
  assert.deepEqual(inboxQueryParams({ status: 'observada', semester: '3', search: ' Paiva ', foreign: 'foreign', page: 2 }), {
    status: 'observada', semester: 3, search: 'Paiva', foreign: true, page: 2, page_size: 25,
  })
})

test('a window is open, scheduled or closed relative to today', () => {
  const window = { id: 1, term_code: 'I/2027', starts_on: '2026-12-01', ends_on: '2026-12-20', is_open: true }
  assert.deepEqual(windowState(window, '2026-12-10'), { label: 'Abierta', variant: 'success' })
  assert.deepEqual(windowState({ ...window, is_open: false }, '2026-11-30'), { label: 'Programada', variant: 'info' })
  assert.deepEqual(windowState({ ...window, is_open: false }, '2026-12-21'), { label: 'Cerrada', variant: 'outline' })
})
