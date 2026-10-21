import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  activeDesignations,
  apiErrorText,
  changeRequestBody,
  formatBs,
  impactRows,
  impactTotals,
  outgoingUntil,
} from '../src/lib/teacherChangeState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const designations = [
  { id: 1, teacher_ci: 'T1', subject: 'Anatomia', semester: '1', group_code: 'M-1', designation_type: 'regular', monthly_hours: 8, weekly_hours: 2, schedule_raw: null, contract_start_date: null, contract_end_date: null },
  { id: 2, teacher_ci: 'T1', subject: 'Ended', semester: '1', group_code: 'M-1', designation_type: 'regular', monthly_hours: 8, weekly_hours: 2, schedule_raw: null, contract_start_date: null, contract_end_date: '2026-04-30' },
  { id: 3, teacher_ci: 'T1', subject: 'Late', semester: '1', group_code: 'M-2', designation_type: 'practice', monthly_hours: 4, weekly_hours: 1, schedule_raw: null, contract_start_date: '2026-06-01', contract_end_date: null },
]

test('only designations still running on the change date can be changed', () => {
  assert.deepEqual(activeDesignations(designations, '2026-05-18').map((d) => d.id), [1, 3])
  assert.deepEqual(activeDesignations(designations, '2026-04-30').map((d) => d.id), [1, 2, 3])
})

test('builds the request for one designation or every active one of the teacher', () => {
  assert.deepEqual(
    changeRequestBody({ period: 'II/2026', effectiveFrom: '2026-05-18', incomingCi: 'T2', outgoingCi: 'T1', designationId: 1 }),
    { academic_period: 'II/2026', effective_from: '2026-05-18', incoming_teacher_ci: 'T2', scope: 'designation', designation_id: 1 },
  )
  assert.deepEqual(
    changeRequestBody({ period: 'II/2026', effectiveFrom: '2026-05-18', incomingCi: 'T2', outgoingCi: 'T1', designationId: null }),
    { academic_period: 'II/2026', effective_from: '2026-05-18', incoming_teacher_ci: 'T2', scope: 'teacher', outgoing_teacher_ci: 'T1' },
  )
  assert.equal(changeRequestBody({ period: 'II/2026', effectiveFrom: '', incomingCi: 'T2', outgoingCi: 'T1', designationId: 1 }), null)
  assert.equal(changeRequestBody({ period: 'II/2026', effectiveFrom: '2026-05-18', incomingCi: '', outgoingCi: 'T1', designationId: 1 }), null)
})

test('explains the outgoing end date', () => {
  assert.equal(outgoingUntil('2026-05-18'), '2026-05-17')
  assert.equal(outgoingUntil('2026-03-01'), '2026-02-28')
})

test('impact rows carry the Bs difference and totals', () => {
  const teachers = [
    { teacher_ci: 'T1', teacher_name: 'Uno', activity: 'theory', hours_before: 8, hours_after: 4, amount_before: 560, amount_after: 280 },
    { teacher_ci: 'T2', teacher_name: 'Dos', activity: 'theory', hours_before: 0, hours_after: 4, amount_before: 0, amount_after: 280 },
  ]
  assert.deepEqual(impactRows(teachers).map((row) => [row.teacher_ci, row.hours_delta, row.amount_delta]), [
    ['T1', -4, -280], ['T2', 4, 280],
  ])
  assert.deepEqual(impactTotals(teachers), { before: 560, after: 560, delta: 0 })
  assert.equal(formatBs(1234.5), 'Bs 1.234,50')
  assert.equal(formatBs(-280), '-Bs 280,00')
})

test('wires the wizard, hooks, simulator and tab', () => {
  const hooks = read('src/api/hooks/useTeacherChange.ts')
  for (const path of ['/designation-changes/preview', '/designation-changes/apply', '/designation-changes/designations', '/payroll-simulation']) {
    assert.match(hooks, new RegExp(path.replace(/[/-]/g, '\\$&')))
  }
  const wizard = read('src/components/academic-management/TeacherChangeSection.tsx')
  for (const text of ['Docente saliente', 'Docente entrante', 'Fecha del cambio', 'Vista previa', 'Aplicar cambio', 'Planillas para regenerar']) {
    assert.ok(wizard.includes(text), text)
  }
  assert.match(read('src/pages/AcademicManagementPage.tsx'), /TabsTrigger value="teacher-change">Cambiar docente</)
  assert.match(read('src/pages/SchedulePlannerPage.tsx'), /Simular planilla/)
  const types = read('src/api/types.ts')
  for (const name of ['DesignationChangePreview', 'DesignationChangeResult', 'PublicationPayrollSimulation', 'TeacherDesignationSummary']) {
    assert.match(types, new RegExp(`interface ${name}`))
  }
})

test('error text shows the server reason and every blocker', () => {
  const error = (detail) => ({ response: { data: { detail } } })
  assert.equal(apiErrorText(error('Solo se puede simular un borrador editable.'), 'x'), 'Solo se puede simular un borrador editable.')
  assert.equal(
    apiErrorText(error({ message: 'El cambio de docente no se puede aplicar.', blockers: [{ message: 'A.' }, { message: 'B.' }] }), 'x'),
    'El cambio de docente no se puede aplicar. A. B.',
  )
  assert.equal(apiErrorText(new Error('network'), 'No se pudo.'), 'No se pudo.')
  const planner = read('src/pages/SchedulePlannerPage.tsx')
  assert.match(planner, /apiErrorText\(simulatePayroll\.error/)
})
