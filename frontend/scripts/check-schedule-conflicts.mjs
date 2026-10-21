import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  clashDescription,
  clashLabel,
  conflictsParams,
  filterFreeSlots,
  loadFormData,
  weekdayLabel,
} from '../src/lib/scheduleConflictsState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const block = (key, extra = {}) => ({
  key, semester: 1, group_code: 'M-1', subject_name: 'Anatomía', activity_type: 'theory',
  start_time: '08:00', end_time: '09:30', teacher_ci: 'T1', teacher_name: 'Ana Pérez', classroom_code: 'COB-NUEVO-P3-A19',
  ...extra,
})

test('labels each clash kind and weekday in Spanish', () => {
  assert.equal(clashLabel('teacher'), 'Docente')
  assert.equal(clashLabel('group'), 'Grupo')
  assert.equal(clashLabel('classroom'), 'Aula')
  assert.equal(clashLabel('split_group'), 'Grupo dividido')
  assert.equal(weekdayLabel('miercoles'), 'Miércoles')
  assert.equal(weekdayLabel('sabado'), 'Sábado')
  assert.equal(weekdayLabel('lunes'), 'Lunes')
})

test('describes who or what is double booked', () => {
  const base = { weekday: 'lunes', start_time: '09:00', end_time: '09:30', overlap_minutes: 30, keys: ['a', 'b'] }
  assert.equal(
    clashDescription({ ...base, kind: 'teacher', severity: 'conflict', teacher_ci: 'T1', group_code: null, semester: null, classroom_code: null,
      blocks: [block('a'), block('b', { group_code: 'M-2' })] }),
    'Ana Pérez tiene dos clases a la vez: Anatomía (1.º M-1) y Anatomía (1.º M-2).',
  )
  assert.equal(
    clashDescription({ ...base, kind: 'group', severity: 'conflict', teacher_ci: null, group_code: 'M-1', semester: 1, classroom_code: null,
      blocks: [block('a'), block('b', { subject_name: 'Bioquímica' })] }),
    '1.º M-1 tiene dos clases a la vez: Anatomía y Bioquímica.',
  )
  assert.equal(
    clashDescription({ ...base, kind: 'classroom', severity: 'conflict', teacher_ci: null, group_code: null, semester: null, classroom_code: 'COB-NUEVO-P3-A19',
      blocks: [block('a'), block('b', { group_code: 'T-1' })] }),
    'COB-NUEVO-P3-A19 está ocupada por dos clases: 1.º M-1 y 1.º T-1.',
  )
  assert.equal(
    clashDescription({ ...base, kind: 'split_group', severity: 'warning', teacher_ci: null, group_code: 'M-1', semester: 1, classroom_code: null,
      blocks: [block('a'), block('b', { activity_type: 'practice' })] }),
    '1.º M-1 tiene teoría y práctica de Anatomía a la vez (grupo dividido).',
  )
})

test('builds the query only when a draft is chosen for the draft source', () => {
  assert.deepEqual(conflictsParams({ period: 'II/2026', source: 'current', draftId: null, date: '2026-11-02', threshold: 40 }), {
    academic_period: 'II/2026', source: 'current', date: '2026-11-02', load_threshold: 40,
  })
  assert.equal(conflictsParams({ period: 'II/2026', source: 'draft', draftId: null, date: '2026-11-02', threshold: 40 }), null)
  assert.deepEqual(conflictsParams({ period: 'II/2026', source: 'draft', draftId: 7, date: '2026-11-02', threshold: 32 }), {
    academic_period: 'II/2026', source: 'draft', draft_id: 7, date: '2026-11-02', load_threshold: 32,
  })
  assert.equal(conflictsParams({ period: '', source: 'current', draftId: null, date: '2026-11-02', threshold: 40 }), null)
  assert.equal(conflictsParams({ period: 'II/2026', source: 'current', draftId: null, date: '2026-11-02', threshold: 0 }), null)
})

test('filters free slots by group or classroom', () => {
  const free = {
    groups: [
      { semester: 1, group_code: 'M-1', weekday: 'lunes', start_time: '06:30', end_time: '08:00', minutes: 90 },
      { semester: 2, group_code: 'M-1', weekday: 'lunes', start_time: '06:30', end_time: '23:05', minutes: 995 },
    ],
    rooms: [{ classroom_code: 'COB-NUEVO-P2-A11', weekday: 'martes', start_time: '06:30', end_time: '23:05', minutes: 995 }],
  }
  assert.deepEqual(filterFreeSlots(free, 'group:1|M-1').map((item) => item.minutes), [90])
  assert.deepEqual(filterFreeSlots(free, 'room:COB-NUEVO-P2-A11').map((item) => item.weekday), ['martes'])
  assert.deepEqual(filterFreeSlots(free, ''), [])
})

test('sends the loader form with the workbook and the preview digest', () => {
  const file = new File(['x'], 'designacion.xlsx')
  const preview = loadFormData({ period: 'II/2026', effectiveFrom: '2026-11-02', file })
  assert.equal(preview.get('academic_period'), 'II/2026')
  assert.equal(preview.get('effective_from'), '2026-11-02')
  assert.equal(preview.get('workbook').name, 'designacion.xlsx')
  assert.equal(preview.get('digest'), null)
  assert.equal(loadFormData({ period: 'II/2026', effectiveFrom: '2026-11-02', file }, 'a'.repeat(64)).get('digest'), 'a'.repeat(64))
})

test('wires hooks, tabs and screens', () => {
  const hooks = read('src/api/hooks/useScheduleConflicts.ts')
  for (const path of ['/schedule-conflicts', '/designation-load/preview', '/designation-load/apply', '/classroom-catalog/preview', '/classroom-catalog/apply']) {
    assert.ok(hooks.includes(path), path)
  }
  const page = read('src/pages/AcademicManagementPage.tsx')
  assert.match(page, /TabsTrigger value="conflicts">Conflictos y huecos</)
  assert.match(page, /TabsTrigger value="designation-load">Cargar designación</)
  const conflicts = read('src/components/academic-management/ScheduleConflictsSection.tsx')
  for (const text of ['Alertar con más de', 'Choques', 'Carga docente', 'Horarios libres', 'Sin docente']) {
    assert.ok(conflicts.includes(text), text)
  }
  const loader = read('src/components/academic-management/DesignationLoadSection.tsx')
  for (const text of ['Catálogo de aulas', 'Excel de designación', 'Vista previa', 'Crear borrador', 'Abrir en el planificador', 'Avisos de la designación']) {
    assert.ok(loader.includes(text), text)
  }
  const types = read('src/api/types.ts')
  for (const name of ['ScheduleConflictsReport', 'DesignationLoadPreview', 'DesignationLoadResult', 'ClassroomCatalogPlan']) {
    assert.match(types, new RegExp(`interface ${name}`))
  }
})
