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
  stepPeriods,
  timelinePosition,
} from '../src/lib/classroomReservations.ts'
import {
  formatDuration,
  formatLongDate,
  freeTimeLabel,
  getBoliviaMinutes,
  groupRooms,
  isBookableDay,
  nextBookableDate,
  occupancyBar,
  parseDateKey,
  parseRoomCode,
  roomGroupKey,
  roomLocation,
  startOptions,
  timeAtPosition,
  toDateKey,
} from '../src/lib/classroomReservationDay.ts'
import { docenteNav } from '../src/lib/navigation.ts'

const root = resolve(import.meta.dirname, '..')
const app = readFileSync(resolve(root, 'src/App.tsx'), 'utf8')
const page = readFileSync(resolve(root, 'src/pages/ClassroomReservationPage.tsx'), 'utf8')
const packageJson = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'))

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

const room = (id, code, name, classroom_type = 'classroom') => ({ id, code, name, capacity: 54, classroom_type })
const ROOMS = [
  room(1, 'COB-ANTIGUO-P1-A5', 'Aula 5'),
  room(2, 'COB-ANTIGUO-P2-A6', 'Aula 6'),
  room(3, 'COB-ANTIGUO-P1-AB', 'Aula B'),
  room(4, 'COB-NUEVO-P3-A19', 'Aula 19'),
  room(5, 'LAB-ANATOMIA', 'Laboratorio de Anatomía', 'laboratory'),
  room(6, 'COB-NUEVO-P4-A1', 'Lab. de Simulación', 'laboratory'),
  room(7, 'SALON-MAGNO', 'Salón Magno'),
]

test('room codes are parsed into building, floor and room', () => {
  assert.deepEqual(parseRoomCode('COB-ANTIGUO-P1-A5'), { building: 'ANTIGUO', floor: 1, room: '5' })
  assert.deepEqual(parseRoomCode('COB-NUEVO-P3-A19'), { building: 'NUEVO', floor: 3, room: '19' })
  assert.deepEqual(parseRoomCode('COB-ANTIGUO-P1-AB'), { building: 'ANTIGUO', floor: 1, room: 'B' })
  assert.deepEqual(parseRoomCode('LAB-ANATOMIA'), { building: null, floor: null, room: null })
  assert.deepEqual(parseRoomCode(''), { building: null, floor: null, room: null })
})

test('rooms are grouped by building, laboratories by type, the rest as Otros', () => {
  assert.deepEqual(ROOMS.map(roomGroupKey), ['antiguo', 'antiguo', 'antiguo', 'nuevo', 'laboratory', 'laboratory', 'other'])
  assert.equal(roomLocation(ROOMS[0]), 'Antiguo · Piso 1')
  assert.equal(roomLocation(ROOMS[3]), 'Nuevo · Piso 3')
  assert.equal(roomLocation(ROOMS[5]), 'Nuevo · Piso 4')
  assert.equal(roomLocation(ROOMS[4]), null)
  assert.equal(roomLocation(ROOMS[6]), null)
})

test('groupRooms keeps the group order, drops empty groups and keeps the input order inside', () => {
  const groups = groupRooms(ROOMS, { query: '', kind: 'all' })
  assert.deepEqual(groups.map((group) => group.title), ['Edificio Antiguo', 'Edificio Nuevo', 'Laboratorios', 'Otros'])
  assert.deepEqual(groups[0].rooms.map((entry) => entry.id), [1, 2, 3])
  assert.deepEqual(groups[2].rooms.map((entry) => entry.id), [5, 6])
})

test('groupRooms filters by kind and by accent-insensitive name or code search', () => {
  const only = (options) => groupRooms(ROOMS, options).flatMap((group) => group.rooms.map((entry) => entry.id))
  assert.deepEqual(only({ query: '', kind: 'laboratory' }), [5, 6])
  assert.deepEqual(only({ query: '', kind: 'classroom' }), [1, 2, 3, 4, 7])
  assert.deepEqual(only({ query: 'anatomia', kind: 'all' }), [5])
  assert.deepEqual(only({ query: '  P1-a5 ', kind: 'all' }), [1])
  assert.deepEqual(only({ query: 'aula', kind: 'laboratory' }), [])
  assert.deepEqual(only({ query: 'aula 1', kind: 'classroom' }), [4])
  assert.deepEqual(groupRooms(ROOMS, { query: 'zzz', kind: 'all' }), [])
})

test('the occupancy bar positions busy ranges over the day window in percent', () => {
  const bar = occupancyBar([busy('08:00', '09:30'), busy('10:00', '11:00', { kind: 'reservation', mine: true })], '06:30', '23:05')
  assert.equal(bar.length, 2)
  assert.ok(Math.abs(bar[0].left - (90 / 995) * 100) < 0.01)
  assert.ok(Math.abs(bar[0].width - (90 / 995) * 100) < 0.01)
  assert.equal(bar[0].kind, 'class')
  assert.equal(bar[1].kind, 'reservation')
  assert.equal(bar[1].mine, true)
  assert.deepEqual(occupancyBar([], '06:30', '23:05'), [])
  const clipped = occupancyBar([busy('06:00', '07:30')], '06:30', '23:05')
  assert.equal(clipped[0].left, 0)
  assert.ok(Math.abs(clipped[0].width - (60 / 995) * 100) < 0.01)
})

test('durations and free time read in Spanish', () => {
  assert.equal(formatDuration(45), '45 min')
  assert.equal(formatDuration(60), '1 h')
  assert.equal(formatDuration(90), '1 h 30 min')
  assert.equal(formatDuration(860), '14 h 20 min')
  assert.equal(freeTimeLabel(995), 'Libre todo el día')
  assert.equal(freeTimeLabel(860), '14 h 20 min libres')
  assert.equal(freeTimeLabel(60), '1 h libres')
  assert.equal(freeTimeLabel(45), '45 min libres')
  assert.equal(freeTimeLabel(0), 'Sin tiempo libre')
  assert.equal(freeTimeLabel(800, 800), 'Libre todo el día')
})

test('start options go in 15 minute steps and only keep the ones that fit the duration', () => {
  const options = startOptions({ busy: [], dayStart: '06:30', dayEnd: '23:05', durationMinutes: 90 })
  assert.equal(options[0].time, '06:30')
  assert.equal(options[1].time, '06:45')
  assert.equal(options.at(-1).time, '23:00')
  const availableTimes = options.filter((option) => option.available).map((option) => option.time)
  assert.equal(availableTimes.at(-1), '21:30')
  assert.equal(availableTimes.includes('21:45'), false)
  assert.equal(options.find((option) => option.time === '21:45').available, false)
})

test('start options avoid busy ranges with half-open semantics', () => {
  const options = startOptions({ busy: [busy('08:00', '09:30')], dayStart: '06:30', dayEnd: '23:05', durationMinutes: 90 })
  const available = (time) => options.find((option) => option.time === time).available
  assert.equal(available('06:30'), true)
  assert.equal(available('06:45'), false)
  assert.equal(available('08:00'), false)
  assert.equal(available('09:15'), false)
  assert.equal(available('09:30'), true)
  assert.equal(startOptions({ busy: [busy('08:00', '09:30')], dayStart: '06:30', dayEnd: '23:05', durationMinutes: 90 })
    .find((option) => option.time === '06:30').available, true)
})

test('start options skip times that are not later than now', () => {
  const options = startOptions({ busy: [], dayStart: '06:30', dayEnd: '23:05', durationMinutes: 45, after: 11 * 60 + 20 })
  const available = (time) => options.find((option) => option.time === time).available
  assert.equal(available('11:15'), false)
  assert.equal(available('11:30'), true)
  const exact = startOptions({ busy: [], dayStart: '06:30', dayEnd: '23:05', durationMinutes: 45, after: 11 * 60 + 30 })
  assert.equal(exact.find((option) => option.time === '11:30').available, false)
  assert.equal(exact.find((option) => option.time === '11:45').available, true)
})

test('a click position snaps down to the 15 minute grid inside the day window', () => {
  assert.equal(timeAtPosition(0, '06:30', '23:05'), '06:30')
  assert.equal(timeAtPosition(1, '06:30', '23:05'), '23:00')
  assert.equal(timeAtPosition(-0.5, '06:30', '23:05'), '06:30')
  assert.equal(timeAtPosition(2, '06:30', '23:05'), '23:00')
  assert.equal(timeAtPosition(90 / 995, '06:30', '23:05'), '08:00')
  assert.equal(timeAtPosition(104 / 995, '06:30', '23:05'), '08:00')
  assert.equal(timeAtPosition(105 / 995, '06:30', '23:05'), '08:15')
})

test('the period stepper stays between 1 and 8', () => {
  assert.equal(stepPeriods(2, 1), 3)
  assert.equal(stepPeriods(2, -1), 1)
  assert.equal(stepPeriods(1, -1), 1)
  assert.equal(stepPeriods(8, 1), 8)
  assert.equal(stepPeriods(MAX_PERIODS, 1), MAX_PERIODS)
})

test('date keys round trip and Sundays are not bookable', () => {
  assert.equal(toDateKey(parseDateKey('2026-11-12')), '2026-11-12')
  assert.equal(parseDateKey('2026-11-12').getDay(), 4)
  assert.equal(isBookableDay(parseDateKey('2026-11-08')), false)
  assert.equal(isBookableDay(parseDateKey('2026-11-09')), true)
  assert.equal(nextBookableDate('2026-11-08'), '2026-11-09')
  assert.equal(nextBookableDate('2026-11-09'), '2026-11-09')
  assert.equal(nextBookableDate('2026-12-31'), '2026-12-31')
  assert.equal(formatLongDate('2026-11-12'), 'jueves 12 de noviembre')
  assert.equal(formatLongDate('2026-12-01'), 'martes 1 de diciembre')
})

test('Bolivia clock minutes follow America/La_Paz', () => {
  assert.equal(getBoliviaMinutes(new Date('2026-11-09T15:20:00Z')), 11 * 60 + 20)
  assert.equal(getBoliviaMinutes(new Date('2026-11-09T02:05:00Z')), 22 * 60 + 5)
})

test('the page uses the coss Calendar, room cards and no select or native date input', () => {
  assert.match(page, /from '@\/components\/ui\/calendar'/)
  assert.doesNotMatch(page, /components\/ui\/select/)
  assert.doesNotMatch(page, /type="date"/)
  assert.doesNotMatch(page, /<select/i)
  assert.match(page, /useClassroomDay/)
})

test('@daypicker/react is declared with an exact version', () => {
  assert.match(packageJson.dependencies['@daypicker/react'], /^\d+\.\d+\.\d+$/)
})
