import assert from 'node:assert/strict'
import test from 'node:test'

import {
  emptyMessage,
  groupByWeekday,
  sourceBadge,
  teacherLabel,
  timeRange,
  upcomingNote,
  weekdayLabel,
  WEEKDAY_ORDER,
} from '../src/lib/studentScheduleState.ts'

const entry = (over = {}) => ({
  source: 'grupo', subject_code: 'FUN 0300', subject_name: 'Bioquímica III', group_code: 'M-01',
  weekday: 'monday', start_time: '08:00', end_time: '09:30', classroom: { code: 'A-1', name: 'Aula 1' },
  activity_type: 'theory', teacher_name: 'Docente A', term_code: 'I/2027', effective_from: '2027-02-01',
  is_upcoming: false, ...over,
})

test('weekdays follow the backend values from Monday to Sunday with Spanish labels', () => {
  assert.deepEqual(WEEKDAY_ORDER, ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])
  assert.deepEqual(WEEKDAY_ORDER.map(weekdayLabel),
    ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'])
  assert.equal(weekdayLabel('holiday'), 'holiday')
})

test('entries are grouped by weekday in week order and sorted by start time inside a day', () => {
  const days = groupByWeekday([
    entry({ weekday: 'friday', start_time: '08:00' }),
    entry({ weekday: 'monday', start_time: '14:00', subject_name: 'Tarde' }),
    entry({ weekday: 'monday', start_time: '08:00', subject_name: 'Mañana' }),
    entry({ weekday: 'monday', start_time: '08:00', subject_name: 'Anatomía', end_time: '09:00' }),
    entry({ weekday: 'saturday', start_time: '07:00' }),
  ])

  assert.deepEqual(days.map((d) => [d.weekday, d.label]), [
    ['monday', 'Lunes'], ['friday', 'Viernes'], ['saturday', 'Sábado'],
  ])
  assert.deepEqual(days[0].entries.map((e) => e.subject_name), ['Anatomía', 'Mañana', 'Tarde'])
})

test('unknown weekdays go last instead of disappearing, and the input is not mutated', () => {
  const input = [entry({ weekday: 'xday' }), entry({ weekday: 'tuesday' })]
  const days = groupByWeekday(input)
  assert.deepEqual(days.map((d) => d.weekday), ['tuesday', 'xday'])
  assert.deepEqual(input.map((e) => e.weekday), ['xday', 'tuesday'])
  assert.deepEqual(groupByWeekday([]), [])
})

test('badges only mark recursado, pendiente and intensivo', () => {
  assert.equal(sourceBadge('grupo'), null)
  assert.equal(sourceBadge('recursado')?.label, 'Recursado')
  assert.equal(sourceBadge('pendiente')?.label, 'Pendiente')
  assert.equal(sourceBadge('intensivo')?.label, 'Intensivo')
})

test('time range, teacher and upcoming note read naturally', () => {
  assert.equal(timeRange(entry()), '08:00 – 09:30')
  assert.equal(teacherLabel('Docente A'), 'Docente A')
  assert.equal(teacherLabel(null), 'Docente por asignar')
  assert.equal(upcomingNote([entry()]), null)
  assert.equal(upcomingNote([entry({ is_upcoming: true, effective_from: '2027-03-15' }),
    entry({ is_upcoming: true, effective_from: '2027-03-01' })]), 'Vigente desde 01/03/2027')
})

test('the empty message is the backend status, or a generic one when the schedule has nothing', () => {
  const ok = { code: 'ok', message: null }
  assert.equal(emptyMessage({ status: { code: 'no_request', message: 'Todavía no enviaste tu solicitud de rematrícula.' }, entries: [], unscheduled: [] }),
    'Todavía no enviaste tu solicitud de rematrícula.')
  assert.equal(emptyMessage({ status: ok, entries: [], unscheduled: [] }), 'No tenés clases en el horario publicado.')
  assert.equal(emptyMessage({ status: ok, entries: [entry()], unscheduled: [] }), null)
  // A status explaining a missing request does not hide entries that exist (intensive courses).
  assert.equal(emptyMessage({ status: { code: 'no_request', message: 'x' }, entries: [entry()], unscheduled: [] }), null)
})
