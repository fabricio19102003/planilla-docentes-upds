import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  assignmentForReferenceDate,
  assignmentPayload,
  replacementWarning,
} from '../src/lib/schedulePlannerState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const page = read('src/pages/SchedulePlannerPage.tsx')
const hooks = read('src/api/hooks/useSchedulePlanner.ts')
const types = read('src/api/types.ts')

const history = [
  { id: 2, block_id: 1, teacher_ci: 'T-2', teacher_name: 'Dos', effective_from: '2026-02-01', effective_to: null, created_at: '', updated_at: '' },
  { id: 1, block_id: 1, teacher_ci: 'T-1', teacher_name: 'Uno', effective_from: '2026-01-01', effective_to: '2026-01-31', created_at: '', updated_at: '' },
]

test('selects the current teacher using inclusive effective dates', () => {
  assert.equal(assignmentForReferenceDate(history, '2026-01-31')?.teacher_ci, 'T-1')
  assert.equal(assignmentForReferenceDate(history, '2026-02-01')?.teacher_ci, 'T-2')
  assert.equal(assignmentForReferenceDate(history, '2025-12-31'), null)
})

test('builds cutover payload and explains the prior end date', () => {
  assert.deepEqual(assignmentPayload('T-2', '2026-02-01', ''), {
    teacher_ci: 'T-2', effective_from: '2026-02-01', effective_to: null,
  })
  assert.equal(replacementWarning('2026-02-01'), 'La asignación anterior finalizará el 2026-01-31.')
})

test('defines assignment, history, compatible-teacher, and workload contracts', () => {
  for (const contract of [
    'AcademicScheduleAssignment', 'CompatibleScheduleTeachersPage', 'ScheduleWorkloadResponse',
  ]) assert.match(types, new RegExp(`interface ${contract}`))
  assert.match(hooks, /\/assignments/)
  assert.match(hooks, /\/compatible-teachers/)
  assert.match(hooks, /\/workload/)
  assert.match(hooks, /per_page: 20/)
})

test('renders accessible assignment, history, workload, and conflict states', () => {
  assert.match(page, /Fecha de referencia/)
  assert.match(page, /Asignar docente/)
  assert.match(page, /Reemplazar docente/)
  assert.match(page, /Historial de asignaciones/)
  assert.match(page, /Carga docente semanal/)
  assert.match(page, /role="alert"/)
  assert.match(page, /role="status"/)
  assert.match(page, /aria-describedby=/)
  assert.match(page, /No existe un docente con disponibilidad completa y sin cruces/)
  assert.doesNotMatch(page, /toast\s*\(/)
})
