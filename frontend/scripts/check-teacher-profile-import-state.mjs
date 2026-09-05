import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { TEACHER_TYPES, teacherTypeLabel } from '../src/domain/teacherTypes.ts'

const uploadPage = readFileSync(new URL('../src/pages/UploadPage.tsx', import.meta.url), 'utf8')
const teacherPage = readFileSync(new URL('../src/pages/TeachersPage.tsx', import.meta.url), 'utf8')
const detailPage = readFileSync(new URL('../src/pages/TeacherDetailPage.tsx', import.meta.url), 'utf8')
const hooks = readFileSync(new URL('../src/api/hooks/useBiometric.ts', import.meta.url), 'utf8')

test('teacher type contract includes exactly the three official values', () => {
  assert.deepEqual([...TEACHER_TYPES], ['EXTERNO', 'PERMANENTE', 'TITULAR'])
  assert.equal(teacherTypeLabel('TITULAR'), 'Titular')
  assert.equal(teacherTypeLabel('UNKNOWN'), 'Tipo desconocido (UNKNOWN)')
})

test('all admin teacher renderers use exhaustive teacher type labels', () => {
  assert.match(teacherPage, /teacherTypeLabel\(teacher\.external_permanent\)/)
  assert.match(detailPage, /teacherTypeLabel\(teacher\.external_permanent\)/)
  assert.doesNotMatch(teacherPage, /external_permanent === 'EXTERNO'/)
  assert.doesNotMatch(detailPage, /external_permanent === 'EXTERNO'/)
})

test('teacher profile upload is preview then digest-bound explicit confirmation', () => {
  assert.match(hooks, /\/teachers\/import\/preview/)
  assert.match(hooks, /confirmation_digest=/)
  assert.match(uploadPage, /Generar vista previa/)
  assert.match(uploadPage, /Confirmar e importar/)
  assert.match(uploadPage, /Object\.entries\(teacherPreview\.fields\)/)
  assert.match(uploadPage, /No activa períodos, elimina datos ni modifica accesos/)
  assert.doesNotMatch(uploadPage, /Subir Lista de Docentes/)
})
