import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  GRID_END_MINUTES,
  GRID_START_MINUTES,
  layoutDay,
  minutesOf,
  scheduleViewRequest,
  scheduleExportRequest,
  subjectColor,
  exportFilename,
  groupBlocksBySchedule,
} from '../src/lib/academicScheduleGrid.ts'
import { groupSubjectsBySemester, groupGroupsBySemester, matchesCatalogSearch } from '../src/lib/academicManagementState.ts'

const root = resolve(import.meta.dirname, '..')
const page = readFileSync(resolve(root, 'src/pages/AcademicManagementPage.tsx'), 'utf8')
const schedules = readFileSync(resolve(root, 'src/components/academic-management/SchedulesSection.tsx'), 'utf8')

const block = (overrides) => ({
  key: overrides.key ?? 'k', semester: 1, group_code: 'M-1', subject_code: null, subject_name: 'Anatomía',
  activity_type: 'theory', weekday: 'lunes', start_time: '06:30', end_time: '08:00', teacher_ci: '1',
  teacher_name: 'Docente', classroom_code: null, classroom_name: null, source_type: 'legacy', ...overrides,
})

test('grid spans 06:30 to 23:05', () => {
  assert.equal(GRID_START_MINUTES, 390)
  assert.equal(GRID_END_MINUTES, 23 * 60 + 5)
  assert.equal(minutesOf('09:50'), 590)
})

test('lays out a block as a percentage of the grid height', () => {
  const [item] = layoutDay([block({ start_time: '06:30', end_time: '08:00' })])
  assert.equal(item.top, 0)
  assert.equal(item.height, (90 / (GRID_END_MINUTES - GRID_START_MINUTES)) * 100)
  assert.equal(item.column, 0)
  assert.equal(item.columns, 1)
})

test('splits overlapping blocks into side-by-side columns and keeps adjacent blocks full width', () => {
  const items = layoutDay([
    block({ key: 'a', start_time: '09:50', end_time: '12:05' }),
    block({ key: 'b', start_time: '10:35', end_time: '12:05' }),
    block({ key: 'c', start_time: '12:05', end_time: '13:30' }),
  ])
  const byKey = Object.fromEntries(items.map((item) => [item.block.key, item]))
  assert.deepEqual([byKey.a.column, byKey.a.columns], [0, 2])
  assert.deepEqual([byKey.b.column, byKey.b.columns], [1, 2])
  assert.deepEqual([byKey.c.column, byKey.c.columns], [0, 1])
})

test('clamps blocks outside the visible range', () => {
  const [item] = layoutDay([block({ start_time: '06:00', end_time: '23:30' })])
  assert.equal(item.top, 0)
  assert.equal(item.height, 100)
})

test('subject colours are stable and distinct per subject name', () => {
  assert.deepEqual(subjectColor('Anatomía'), subjectColor('Anatomía'))
  assert.notDeepEqual(subjectColor('Anatomía Humana I'), subjectColor('Fisiología I'))
  assert.match(subjectColor('X').background, /^#[0-9a-f]{6}$/i)
})

test('builds view and export requests with only the active filters', () => {
  assert.deepEqual(scheduleViewRequest({ period: 'II/2026', source: 'current', date: '2026-10-21', semester: 3, group: '' }), {
    queryKey: ['academic-management', 'schedule-view', 'II/2026', 'current', null, '2026-10-21', 3, null],
    url: '/admin/academic-management/schedule-view',
    params: { academic_period: 'II/2026', source: 'current', date: '2026-10-21', semester: 3 },
    enabled: true,
  })
  assert.deepEqual(scheduleViewRequest({ period: 'II/2026', source: 'draft', draftId: 4, date: '2026-10-21', semester: null, group: 'M-1' }).params,
    { academic_period: 'II/2026', source: 'draft', draft_id: 4, date: '2026-10-21', group: 'M-1' })
  assert.equal(scheduleViewRequest({ period: 'II/2026', source: 'draft', draftId: null, date: '2026-10-21' }).enabled, false)
  assert.equal(scheduleExportRequest({ period: 'II/2026', source: 'current', date: '2026-10-21', semester: 1, group: 'M-1' }).url,
    '/admin/academic-management/schedule-view/export')
})

test('reads the export filename from Content-Disposition', () => {
  assert.equal(exportFilename('attachment; filename="horarios_II-2026_sem1_M-1.xlsx"'), 'horarios_II-2026_sem1_M-1.xlsx')
  assert.equal(exportFilename(undefined), 'horarios.xlsx')
})

test('groups blocks into one schedule per semester and group in order', () => {
  const groups = groupBlocksBySchedule([
    block({ key: '1', semester: 2, group_code: 'T-1' }),
    block({ key: '2', semester: 1, group_code: 'M-2' }),
    block({ key: '3', semester: 1, group_code: 'M-1' }),
    block({ key: '4', semester: null, group_code: 'A' }),
  ])
  assert.deepEqual(groups.map((item) => [item.semester, item.group]), [[1, 'M-1'], [1, 'M-2'], [2, 'T-1'], [null, 'A']])
})

test('groups subjects by the semester of their offerings in the period', () => {
  const subjects = [{ id: 1, code: 'MRF 0100', name: 'Anatomía I' }, { id: 2, code: 'FUN 0300', name: 'Farmacología I' }, { id: 3, code: 'X', name: 'Sin oferta' }]
  const offerings = [
    { subject_id: 1, academic_period: 'II/2026', semester: 1, theory_hours: 51, practice_hours: 51, active: true },
    { subject_id: 2, academic_period: 'II/2026', semester: 3, theory_hours: 68, practice_hours: 68, active: true },
    { subject_id: 2, academic_period: 'I/2026', semester: 9, theory_hours: 1, practice_hours: 1, active: true },
  ]
  const sections = groupSubjectsBySemester(subjects, offerings, 'II/2026')
  assert.deepEqual(sections.map((section) => [section.semester, section.rows.map((row) => row.subject.code)]),
    [[1, ['MRF 0100']], [3, ['FUN 0300']], [null, ['X']]])
  assert.equal(sections[0].rows[0].offering.theory_hours, 51)
})

test('groups academic groups by semester in shift and number order', () => {
  const sections = groupGroupsBySemester([
    { id: 1, academic_period: 'II/2026', semester: 2, code: 'N-1' },
    { id: 2, academic_period: 'II/2026', semester: 2, code: 'M-10' },
    { id: 3, academic_period: 'II/2026', semester: 2, code: 'M-2' },
    { id: 4, academic_period: 'I/2026', semester: 1, code: 'M-1' },
  ], 'II/2026')
  assert.deepEqual(sections.map((section) => [section.semester, section.rows.map((row) => row.code)]), [[2, ['M-2', 'M-10', 'N-1']]])
})

test('catalog search ignores accents and case', () => {
  assert.equal(matchesCatalogSearch({ code: 'FUN 0300', name: 'Farmacología I' }, 'farmacologia'), true)
  assert.equal(matchesCatalogSearch({ code: 'FUN 0300', name: 'Farmacología I' }, 'fun 03'), true)
  assert.equal(matchesCatalogSearch({ code: 'FUN 0300', name: 'Farmacología I' }, 'anatomía'), false)
  assert.equal(matchesCatalogSearch({ code: 'FUN 0300', name: 'Farmacología I' }, '  '), true)
})

test('the page exposes the Horarios tab, Excel download and per-semester catalogs', () => {
  assert.match(page, /value="schedules"/)
  assert.match(page, />Horarios</)
  assert.match(page, /<SchedulesSection \/>/)
  assert.match(schedules, /Descargar Excel/)
  assert.match(schedules, /useDownloadScheduleExcel/)
  assert.match(schedules, /No hay clases para este filtro/)
  assert.match(page, /groupSubjectsBySemester/)
  assert.match(page, /groupGroupsBySemester/)
})
