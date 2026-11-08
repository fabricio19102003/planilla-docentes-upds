import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  GRID_DAY_END,
  GRID_DAY_START,
  blockPosition,
  filterRoomsByType,
  groupReservationsByRoom,
  gridHourMarks,
  shiftDate,
  sortDayReservations,
  weekdayName,
} from '../src/lib/classroomReservationsGrid.ts'
import { adminNav } from '../src/lib/navigation.ts'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const app = read('src/App.tsx')
const client = read('src/api/client.ts')

const room = (id, code, classroom_type = 'classroom') => ({ id, code, name: `Aula ${code}`, capacity: 54, classroom_type })
const reservation = (id, classroom, start_time, end_time, patch = {}) => ({
  id, classroom, date: '2026-11-10', start_time, end_time, academic_periods: 2,
  status: 'confirmed', teacher_ci: '1', teacher_name: `Docente ${id}`, ...patch,
})

const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.001, `${actual} !== ${expected}`)

test('the grid covers the bookable day window 06:30 to 23:05', () => {
  assert.equal(GRID_DAY_START, '06:30')
  assert.equal(GRID_DAY_END, '23:05')
})

test('a block is positioned as a percentage of the day window', () => {
  assert.deepEqual(blockPosition('06:30', '23:05'), { top: 0, height: 100 })
  const block = blockPosition('14:47', '15:32')
  near(block.top, (497 / 995) * 100)
  near(block.height, (45 / 995) * 100)
  const first = blockPosition('06:30', '07:15')
  assert.equal(first.top, 0)
  near(first.height, (45 / 995) * 100)
})

test('blocks sticking out of the window are clamped to it', () => {
  const early = blockPosition('06:00', '07:15')
  assert.equal(early.top, 0)
  near(early.height, (45 / 995) * 100)
  const late = blockPosition('22:30', '23:30')
  near(late.top, (960 / 995) * 100)
  near(late.top + late.height, 100)
})

test('hour marks run from 07:00 to 23:00 with their offset in the window', () => {
  const marks = gridHourMarks()
  assert.equal(marks[0].time, '07:00')
  assert.equal(marks.at(-1).time, '23:00')
  assert.equal(marks.length, 17)
  near(marks[0].top, (30 / 995) * 100)
  near(marks.at(-1).top, (990 / 995) * 100)
  assert.deepEqual(gridHourMarks('08:00', '10:30').map((mark) => mark.time), ['08:00', '09:00', '10:00'])
})

test('rooms are filtered by type and keep their order', () => {
  const rooms = [room(1, '1'), room(2, '2'), room(7, 'LAB-1', 'laboratory'), room(8, 'LAB-2', 'laboratory')]
  assert.deepEqual(filterRoomsByType(rooms, 'all').map((entry) => entry.id), [1, 2, 7, 8])
  assert.deepEqual(filterRoomsByType(rooms, 'classroom').map((entry) => entry.id), [1, 2])
  assert.deepEqual(filterRoomsByType(rooms, 'laboratory').map((entry) => entry.id), [7, 8])
  assert.deepEqual(filterRoomsByType([], 'laboratory'), [])
})

test('reservations are grouped by room id and sorted by start inside each room', () => {
  const rooms = [room(1, '1'), room(2, '2'), room(3, '3')]
  const grouped = groupReservationsByRoom([
    reservation(10, rooms[1], '10:00', '11:30'),
    reservation(11, rooms[0], '14:00', '15:30'),
    reservation(12, rooms[1], '08:00', '09:30'),
    reservation(13, rooms[0], '07:00', '07:45'),
  ])
  assert.deepEqual(grouped.get(1).map((entry) => entry.id), [13, 11])
  assert.deepEqual(grouped.get(2).map((entry) => entry.id), [12, 10])
  assert.equal(grouped.get(3), undefined)
})

test('the day list sorts by start time, then room code, without touching the input', () => {
  const a = room(1, '10')
  const b = room(2, '2')
  const input = [
    reservation(1, a, '09:00', '10:30'),
    reservation(2, b, '09:00', '10:30'),
    reservation(3, a, '07:00', '07:45'),
    reservation(4, b, '08:05', '09:35'),
  ]
  const before = input.map((entry) => entry.id)
  assert.deepEqual(sortDayReservations(input).map((entry) => entry.id), [3, 4, 2, 1])
  assert.deepEqual(input.map((entry) => entry.id), before)
})

test('shifting a date moves whole days across month and year ends', () => {
  assert.equal(shiftDate('2026-11-10', 1), '2026-11-11')
  assert.equal(shiftDate('2026-11-10', -1), '2026-11-09')
  assert.equal(shiftDate('2026-11-30', 1), '2026-12-01')
  assert.equal(shiftDate('2026-12-31', 1), '2027-01-01')
  assert.equal(shiftDate('2026-03-01', -1), '2026-02-28')
})

test('the weekday name comes from the calendar date, not the local zone', () => {
  assert.equal(weekdayName('2026-11-10'), 'martes')
  assert.equal(weekdayName('2026-11-08'), 'domingo')
  assert.equal(weekdayName('2027-01-01'), 'viernes')
})

test('the app routes the admin grid page inside the admin block, before the portal', () => {
  assert.match(app, /path="classroom-reservations"\s+element=\{<ClassroomReservationsAdminPage \/>\}/)
  assert.match(app, /import \{ ClassroomReservationsAdminPage \} from '\.\/pages\/ClassroomReservationsAdminPage'/)
  const adminRoute = app.indexOf('element={<ClassroomReservationsAdminPage />}')
  assert.ok(adminRoute > 0 && adminRoute < app.indexOf('path="/portal"'))
  assert.ok(adminRoute > app.indexOf('path="schedule-planner"'))
})

test('the admin menu offers Reservas de aulas right after Planificador de horarios', () => {
  const group = adminNav.find((entry) => 'children' in entry && entry.label === 'Docentes y académico')
  const labels = group.children.map((item) => item.label)
  assert.equal(labels.indexOf('Reservas de aulas'), labels.indexOf('Planificador de horarios') + 1)
  const item = group.children.find((entry) => entry.label === 'Reservas de aulas')
  assert.equal(item.to, '/classroom-reservations')
  assert.equal(item.icon, 'classroom')
})

test('an expired admin session on the grid page returns to it after login', () => {
  const roots = client.match(/const adminRoots = new Set\(\[([\s\S]*?)\]\)/)?.[1] ?? ''
  assert.match(roots, /'classroom-reservations'/)
})

test('the admin page reads the admin hook and offers day navigation', () => {
  const page = read('src/pages/ClassroomReservationsAdminPage.tsx')
  assert.match(page, /useAdminClassroomReservations\(/)
  assert.match(page, /getTodayInBolivia/)
  assert.match(page, /Hoy/)
  assert.match(page, /type="date"/)
})
