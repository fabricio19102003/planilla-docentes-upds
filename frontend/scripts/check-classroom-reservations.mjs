import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  MAX_PERIODS,
  STEP_MINUTES,
  computeEndTime,
  daySegments,
  findOverlap,
  freeGaps,
  rangeProblem,
  rangesOverlap,
  startTimeOptions,
  timelinePosition,
} from '../src/lib/classroomReservations.ts'
import { docenteNav } from '../src/lib/navigation.ts'

const root = resolve(import.meta.dirname, '..')
const app = readFileSync(resolve(root, 'src/App.tsx'), 'utf8')

const DAY = { dayStart: '06:30', dayEnd: '23:05' }
const busy = (start_time, end_time, patch = {}) => ({
  start_time, end_time, kind: 'class', label: 'Ocupada', detail: null, mine: false, ...patch,
})

test('end time is start plus periods times the academic hour', () => {
  assert.equal(computeEndTime('08:00', 1, 45), '08:45')
  assert.equal(computeEndTime('08:00', 2, 45), '09:30')
  assert.equal(computeEndTime('18:30', 4, 45), '21:30')
  assert.equal(computeEndTime('08:00', 3, 40), '10:00')
  assert.equal(computeEndTime('06:30', 8, 45), '12:30')
  assert.equal(computeEndTime('', 2, 45), null)
  assert.equal(computeEndTime('08:00', 0, 45), null)
})

test('end times past midnight are reported as null', () => {
  assert.equal(computeEndTime('22:30', 8, 45), null)
})

test('ranges overlap with half-open semantics, back-to-back is allowed', () => {
  assert.equal(rangesOverlap('08:00', '09:30', '09:00', '10:00'), true)
  assert.equal(rangesOverlap('08:00', '09:30', '09:30', '10:00'), false)
  assert.equal(rangesOverlap('09:30', '10:00', '08:00', '09:30'), false)
  assert.equal(rangesOverlap('08:00', '12:00', '09:00', '10:00'), true)
  assert.equal(rangesOverlap('09:00', '10:00', '08:00', '12:00'), true)
})

test('findOverlap returns the first busy range that collides', () => {
  const ranges = [busy('08:00', '09:30'), busy('10:00', '11:00', { kind: 'reservation' })]
  assert.equal(findOverlap(ranges, '09:30', '10:00'), null)
  assert.equal(findOverlap(ranges, '09:00', '10:15'), ranges[0])
  assert.equal(findOverlap(ranges, '10:30', '11:15'), ranges[1])
})

test('range problems cover the window limits and busy collisions', () => {
  const ranges = [busy('08:00', '09:30', { detail: 'Álgebra' })]
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '06:30', end: '07:15' }), null)
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '22:20', end: '23:05' }), null)
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '06:25', end: '07:10' }), 'La reserva debe quedar entre las 06:30 y las 23:05.')
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '22:30', end: '23:15' }), 'La reserva debe quedar entre las 06:30 y las 23:05.')
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '22:30', end: null }), 'La reserva debe quedar entre las 06:30 y las 23:05.')
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '09:00', end: '09:45' }), 'El aula está ocupada por una clase de 08:00 a 09:30.')
  assert.equal(rangeProblem({ ...DAY, busy: ranges, start: '09:30', end: '10:15' }), null)
  assert.equal(
    rangeProblem({ ...DAY, busy: [busy('10:00', '11:00', { kind: 'reservation' })], start: '10:30', end: '11:15' }),
    'El aula ya está reservada de 10:00 a 11:00.',
  )
  assert.equal(rangeProblem({ ...DAY, busy: [], start: '', end: null }), null)
})

test('free gaps are the stretches between busy ranges inside the window', () => {
  assert.deepEqual(freeGaps([], '06:30', '23:05'), [{ start: '06:30', end: '23:05' }])
  assert.deepEqual(
    freeGaps([busy('08:00', '09:30'), busy('09:30', '10:15'), busy('12:00', '13:00')], '06:30', '23:05'),
    [{ start: '06:30', end: '08:00' }, { start: '10:15', end: '12:00' }, { start: '13:00', end: '23:05' }],
  )
  assert.deepEqual(freeGaps([busy('06:30', '23:05')], '06:30', '23:05'), [])
  assert.deepEqual(
    freeGaps([busy('12:00', '13:00'), busy('08:00', '12:30')], '06:30', '23:05'),
    [{ start: '06:30', end: '08:00' }, { start: '13:00', end: '23:05' }],
  )
})

test('day segments interleave free gaps and busy ranges in order', () => {
  const segments = daySegments([busy('08:00', '09:30', { detail: 'Álgebra' })], '06:30', '23:05')
  assert.deepEqual(segments.map((segment) => [segment.type, segment.start, segment.end]), [
    ['free', '06:30', '08:00'],
    ['busy', '08:00', '09:30'],
    ['free', '09:30', '23:05'],
  ])
  assert.equal(segments[1].busy.detail, 'Álgebra')
})

test('start times go in 5 minute steps inside the window', () => {
  const options = startTimeOptions('06:30', '23:05')
  assert.equal(STEP_MINUTES, 5)
  assert.equal(options[0], '06:30')
  assert.equal(options[1], '06:35')
  assert.equal(options.at(-1), '23:00')
  assert.equal(options.includes('23:05'), false)
  assert.equal(options.includes('12:05'), true)
  assert.equal(options.length, (23 * 60 + 0 - (6 * 60 + 30)) / 5 + 1)
})

test('a reservation is capped at 8 academic periods', () => {
  assert.equal(MAX_PERIODS, 8)
})

test('timeline positions are percentages of the day window', () => {
  assert.deepEqual(timelinePosition('06:30', '23:05', '06:30', '23:05'), { top: 0, height: 100 })
  const position = timelinePosition('14:47', '15:32', '06:30', '23:05')
  assert.ok(Math.abs(position.top - (497 / 995) * 100) < 0.01)
  assert.ok(Math.abs(position.height - (45 / 995) * 100) < 0.01)
})

test('the app routes the reservation page inside the portal', () => {
  assert.match(app, /path="classroom-reservations"\s+element=\{<ClassroomReservationPage \/>\}/)
  assert.match(app, /import \{ ClassroomReservationPage \} from '\.\/pages\/ClassroomReservationPage'/)
  const portalStart = app.indexOf('path="/portal"')
  assert.ok(app.indexOf('element={<ClassroomReservationPage />}') > portalStart)
})

test('the docente menu offers Reservar aula after Mi Horario', () => {
  const labels = docenteNav.map((item) => item.label)
  assert.equal(labels.indexOf('Reservar aula'), labels.indexOf('Mi Horario') + 1)
  const item = docenteNav.find((entry) => entry.label === 'Reservar aula')
  assert.equal(item.to, '/portal/classroom-reservations')
})
