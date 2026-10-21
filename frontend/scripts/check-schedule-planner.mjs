import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  addMinutes,
  blockTimeError,
  BLOCK_DURATION_PRESETS,
  cellForStart,
  defaultAcademicHours,
  parseScheduleCellId,
  scheduleBlockPayload,
  scheduleCellId,
  SCHEDULE_TIMES,
  SCHEDULE_WEEKDAYS,
} from '../src/lib/schedulePlannerState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const app = read('src/App.tsx')
// Navigation entries live in the shared nav definition consumed by the sidebar.
const sidebar = read('src/lib/navigation.ts')
const page = read('src/pages/SchedulePlannerPage.tsx')
const hooks = read('src/api/hooks/useSchedulePlanner.ts')

test('registers a dedicated protected planner route and navigation entry', () => {
  assert.match(app, /path="schedule-planner"/)
  assert.match(app, /<SchedulePlannerPage/)
  assert.match(sidebar, /to: '\/schedule-planner'/)
  assert.match(sidebar, /Planificador de horarios/)
})

test('defines Monday through Saturday with 30-minute drop cells from 06:00 to 23:00', () => {
  assert.equal(SCHEDULE_WEEKDAYS.length, 6)
  assert.deepEqual(SCHEDULE_WEEKDAYS.map((day) => day.value), [
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
  ])
  assert.equal(SCHEDULE_TIMES.length, 35)
  assert.equal(SCHEDULE_TIMES[0], '06:00')
  assert.equal(SCHEDULE_TIMES.at(-1), '23:00')
  assert.equal(addMinutes('23:00', 60), '23:30')
})

test('blocks use any 5-minute time and show in the cell of their start', () => {
  assert.equal(cellForStart('08:05'), '08:00')
  assert.equal(cellForStart('09:50'), '09:30')
  assert.equal(cellForStart('06:00'), '06:00')
  assert.equal(blockTimeError('08:05', '08:50'), '')
  assert.equal(blockTimeError('05:55', '06:40'), 'El bloque debe estar entre las 06:00 y las 23:30.')
  assert.equal(blockTimeError('08:03', '08:50'), 'Las horas deben usar intervalos de 5 minutos.')
  assert.equal(blockTimeError('08:00', '08:10'), 'El bloque debe durar entre 15 minutos y 6 horas.')
  assert.equal(blockTimeError('09:00', '08:00'), 'La hora de inicio debe ser anterior a la hora de fin.')
  assert.deepEqual(BLOCK_DURATION_PRESETS, [45, 90, 135])
})

test('prefills academic hours from the duration and the configured hour length', () => {
  assert.equal(defaultAcademicHours('08:05', '08:50', 45), 1)
  assert.equal(defaultAcademicHours('08:00', '09:30', 45), 2)
  assert.equal(defaultAcademicHours('10:35', '12:15', 45), 2)
  assert.equal(defaultAcademicHours('08:00', '09:20', 40), 2)
  assert.equal(defaultAcademicHours('08:00', '08:15', 45), 1)
})

test('round-trips drop targets and creates the API payload', () => {
  const id = scheduleCellId('wednesday', '13:30')
  assert.deepEqual(parseScheduleCellId(id), { weekday: 'wednesday', start_time: '13:30' })
  assert.equal(parseScheduleCellId('invalid'), null)
  assert.deepEqual(scheduleBlockPayload({
    offering_id: '2', group_id: '3', classroom_id: '4', activity_type: 'practice',
    weekday: 'saturday', start_time: '09:00', end_time: '10:30', academic_hours: '',
  }), {
    offering_id: 2, group_id: 3, classroom_id: 4, activity_type: 'practice',
    weekday: 'saturday', start_time: '09:00', end_time: '10:30',
  })
  assert.equal(scheduleBlockPayload({
    offering_id: '2', group_id: '3', classroom_id: '4', activity_type: 'theory',
    weekday: 'monday', start_time: '09:00', end_time: '10:30', academic_hours: '3',
  }).academic_hours, 3)
})

test('uses official dnd-kit primitives with accessible fallback and states', () => {
  for (const primitive of ['DragDropProvider', 'useDraggable', 'useDroppable', 'DragOverlay']) {
    assert.match(page, new RegExp(primitive))
  }
  assert.match(page, /Agregar al horario/)
  assert.match(page, /aria-live="assertive"/)
  assert.match(page, /role="alert"/)
  assert.match(page, /role="status"/)
  assert.match(page, /focus-visible:ring/)
})

test('keeps schedule editing on draft and block APIs while bootstrap stays isolated', () => {
  assert.match(hooks, /schedule-drafts/)
  assert.match(hooks, /\/blocks/)
  assert.doesNotMatch(hooks, /designation-bootstrap/i)
  assert.match(page, /DesignationBootstrapDialog/)
})

test('the block form offers free times, duration presets and editable academic hours', () => {
  assert.match(page, /type="time"/)
  assert.match(page, /step=\{300\}/)
  assert.match(page, /BLOCK_DURATION_PRESETS/)
  assert.match(page, /Horas académicas/)
  assert.match(page, /cellForStart/)
  assert.match(page, /paid_hours/)
})
