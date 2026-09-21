import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  addMinutes,
  parseScheduleCellId,
  scheduleBlockPayload,
  scheduleCellId,
  SCHEDULE_TIMES,
  SCHEDULE_WEEKDAYS,
} from '../src/lib/schedulePlannerState.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const app = read('src/App.tsx')
const sidebar = read('src/components/layout/Sidebar.tsx')
const page = read('src/pages/SchedulePlannerPage.tsx')
const hooks = read('src/api/hooks/useSchedulePlanner.ts')

test('registers a dedicated protected planner route and navigation entry', () => {
  assert.match(app, /path="schedule-planner"/)
  assert.match(app, /<SchedulePlannerPage/)
  assert.match(sidebar, /to: '\/schedule-planner'/)
  assert.match(sidebar, /Planificador de horarios/)
})

test('defines Monday through Saturday in 30-minute slots from 07:00 to 22:00', () => {
  assert.equal(SCHEDULE_WEEKDAYS.length, 6)
  assert.deepEqual(SCHEDULE_WEEKDAYS.map((day) => day.value), [
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
  ])
  assert.equal(SCHEDULE_TIMES.length, 30)
  assert.equal(SCHEDULE_TIMES[0], '07:00')
  assert.equal(SCHEDULE_TIMES.at(-1), '21:30')
  assert.equal(addMinutes('21:30', 60), '22:00')
})

test('round-trips drop targets and creates the API payload', () => {
  const id = scheduleCellId('wednesday', '13:30')
  assert.deepEqual(parseScheduleCellId(id), { weekday: 'wednesday', start_time: '13:30' })
  assert.equal(parseScheduleCellId('invalid'), null)
  assert.deepEqual(scheduleBlockPayload({
    offering_id: '2', group_id: '3', classroom_id: '4', activity_type: 'practice',
    weekday: 'saturday', start_time: '09:00', end_time: '10:30',
  }), {
    offering_id: 2, group_id: 3, classroom_id: 4, activity_type: 'practice',
    weekday: 'saturday', start_time: '09:00', end_time: '10:30',
  })
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

test('uses draft and block APIs without touching designation endpoints', () => {
  assert.match(hooks, /schedule-drafts/)
  assert.match(hooks, /\/blocks/)
  assert.doesNotMatch(`${page}\n${hooks}`, /designation/i)
})
