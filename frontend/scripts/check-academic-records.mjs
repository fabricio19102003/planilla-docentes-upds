import assert from 'node:assert/strict'
import { gunzipSync } from 'node:zlib'
import test from 'node:test'

import {
  formatGrade,
  gzipCsv,
  importCountRows,
  recordStatus,
  splitIssues,
  studentQueryParams,
  termAverage,
} from '../src/lib/academicRecordsState.ts'

test('record statuses map to Spanish labels and badge variants', () => {
  assert.deepEqual(recordStatus('aprobado'), { label: 'Aprobado', variant: 'success' })
  assert.deepEqual(recordStatus('reprobado'), { label: 'Reprobado', variant: 'error' })
  assert.deepEqual(recordStatus('retirado'), { label: 'Retirado', variant: 'outline' })
  assert.deepEqual(recordStatus('pendiente'), { label: 'En curso', variant: 'info' })
})

test('a missing grade is shown as a dash', () => {
  assert.equal(formatGrade(73), '73')
  assert.equal(formatGrade(0), '0')
  assert.equal(formatGrade(null), '—')
})

test('term average counts only graded approved and failed subjects', () => {
  const records = [
    { status: 'aprobado', grade: 80 },
    { status: 'reprobado', grade: 0 },
    { status: 'retirado', grade: 45 },
    { status: 'pendiente', grade: null },
  ]
  assert.equal(termAverage(records), 40)
  assert.equal(termAverage([{ status: 'pendiente', grade: null }]), null)
  assert.equal(termAverage([{ status: 'aprobado', grade: 71 }, { status: 'aprobado', grade: 72 }]), 71.5)
})

test('student filters become query params without empty values', () => {
  assert.deepEqual(studentQueryParams({ search: '  paiva ', status: '', nationality: 'all', page: 1 }), { page: 1, page_size: 25, search: 'paiva' })
  assert.deepEqual(studentQueryParams({ search: '', status: 'Antiguo', nationality: 'foreign', page: 3 }), {
    page: 3, page_size: 25, status: 'Antiguo', foreign: true,
  })
  assert.deepEqual(studentQueryParams({ search: '', status: '', nationality: 'national', page: 1 }), {
    page: 1, page_size: 25, foreign: false,
  })
})

test('import issues are split into errors and warnings', () => {
  const issues = [
    { level: 'error', row: 3, rows: 1, message: 'Período desconocido: Trimestre' },
    { level: 'warning', row: null, rows: 12, message: 'Materia fuera de malla: SPC 0100' },
  ]
  assert.deepEqual(splitIssues(issues), { errors: [issues[0]], warnings: [issues[1]] })
})

test('import counts become labelled rows', () => {
  const counts = {
    rows: 10, valid_rows: 9, error_rows: 1, students_new: 2, students_updated: 1, students_unchanged: 3,
    records_new: 5, records_updated: 2, records_unchanged: 2, terms_new: 1, subjects_new: 0, teachers_linked: 7, warnings: 0,
  }
  assert.deepEqual(importCountRows(counts), [
    { label: 'Filas leídas', value: 10 },
    { label: 'Filas con error (se omiten)', value: 1 },
    { label: 'Estudiantes nuevos', value: 2 },
    { label: 'Estudiantes actualizados', value: 1 },
    { label: 'Estudiantes sin cambios', value: 3 },
    { label: 'Materias cursadas nuevas', value: 5 },
    { label: 'Materias cursadas actualizadas', value: 2 },
    { label: 'Materias cursadas sin cambios', value: 2 },
    { label: 'Períodos nuevos', value: 1 },
    { label: 'Materias nuevas en el catálogo', value: 0 },
    { label: 'Registros vinculados a un docente de SIPAD', value: 7 },
  ])
})

test('the CSV is gzipped losslessly and keeps a .gz name', async () => {
  const text = '\ufeffEstudianteNombre,EstudianteApellidos\nJúlia,Dos Santos\n'
  const file = new File([text], 'gestion-2026.csv', { type: 'text/csv' })
  const compressed = await gzipCsv(file)
  assert.equal(compressed.name, 'gestion-2026.csv.gz')
  assert.equal(compressed.type, 'application/gzip')
  assert.equal(gunzipSync(Buffer.from(await compressed.arrayBuffer())).toString('utf8'), text)
})
