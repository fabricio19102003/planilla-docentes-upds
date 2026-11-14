import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  boliviaClock,
  countdownLabel,
  formatAverage,
  nextClassToday,
  rematriculaCta,
} from '../src/lib/studentHomeState.ts'

// S1/S2/S8/S9: the redesigned Inicio (R5 glass hero, cards Rematrícula / Cuotas / Mi horario de hoy / Avance).
// Bolivia is UTC-4 all year, so 12:00Z is 08:00 in La Paz.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const entry = (over = {}) => ({
  source: 'grupo', subject_code: 'MED 100', subject_name: 'Anatomía', group_code: 'M-01',
  weekday: 'monday', start_time: '08:00', end_time: '09:30', classroom: { code: 'A-1', name: 'Aula 1' },
  activity_type: 'theory', teacher_name: 'Docente A', term_code: 'I/2027', effective_from: '2027-02-01',
  is_upcoming: false, ...over,
})
const MONDAY = [
  entry({ subject_name: 'Fisiopatología', start_time: '14:00', end_time: '15:30' }),
  entry({ subject_name: 'Anatomía' }),
  entry({ subject_name: 'Microbiología', start_time: '10:15', end_time: '11:45' }),
  entry({ subject_name: 'Física', weekday: 'tuesday' }),
]
// 2027-02-01 is a Monday.
const at = (hhmm) => new Date(`2027-02-01T${String(Number(hhmm.slice(0, 2)) + 4).padStart(2, '0')}:${hhmm.slice(3)}:00Z`)
const names = (list) => list.map((item) => item.subject_name)

test('the Bolivia clock gives the weekday and minutes in America/La_Paz, not UTC', () => {
  assert.deepEqual(boliviaClock(new Date('2027-02-01T12:00:00Z')), { weekday: 'monday', minutes: 480 })
  // 03:59Z on Monday is still Sunday 23:59 in La Paz.
  assert.deepEqual(boliviaClock(new Date('2027-02-01T03:59:00Z')), { weekday: 'sunday', minutes: 1439 })
  // Tuesday 02:00Z is Monday 22:00 in La Paz.
  assert.deepEqual(boliviaClock(new Date('2027-02-02T02:00:00Z')), { weekday: 'monday', minutes: 1320 })
})

test('before the first class the next class is the first one, with the minutes left', () => {
  const plan = nextClassToday(MONDAY, at('07:00'))
  assert.equal(plan.next.entry.subject_name, 'Anatomía')
  assert.equal(plan.next.state, 'upcoming')
  assert.equal(plan.next.minutes, 60)
  assert.deepEqual(names(plan.later), ['Microbiología', 'Fisiopatología'])
  assert.equal(plan.total, 3)
})

test('a class that has started is in progress until its end time, and then it is over', () => {
  const started = nextClassToday(MONDAY, at('08:00'))
  assert.equal(started.next.entry.subject_name, 'Anatomía')
  assert.equal(started.next.state, 'in_progress')
  assert.equal(started.next.minutes, 90)
  const over = nextClassToday(MONDAY, at('09:30'))
  assert.equal(over.next.entry.subject_name, 'Microbiología', 'the end time is exclusive')
  assert.equal(over.next.state, 'upcoming')
  assert.equal(over.next.minutes, 45)
})

test('between classes the next one is the following class', () => {
  const plan = nextClassToday(MONDAY, at('12:00'))
  assert.equal(plan.next.entry.subject_name, 'Fisiopatología')
  assert.equal(plan.next.minutes, 120)
  assert.deepEqual(plan.later, [])
})

test('after the last class there is no next class but the day had classes', () => {
  const plan = nextClassToday(MONDAY, at('15:30'))
  assert.equal(plan.next, null)
  assert.deepEqual(plan.later, [])
  assert.equal(plan.total, 3)
})

test('no classes, a weekend day or an unpublished (upcoming) schedule give nothing for today', () => {
  assert.deepEqual(nextClassToday([], at('08:00')), { next: null, later: [], total: 0 })
  assert.equal(nextClassToday(MONDAY, new Date('2027-02-07T15:00:00Z')).total, 0, 'Sunday')
  assert.equal(nextClassToday(MONDAY.map((item) => ({ ...item, is_upcoming: true })), at('07:00')).total, 0)
  const saturday = [entry({ weekday: 'saturday', subject_name: 'Taller' })]
  assert.equal(nextClassToday(saturday, new Date('2027-02-06T12:00:00Z')).next.entry.subject_name, 'Taller')
})

test('the day follows La Paz: a late Monday class is still found after midnight UTC', () => {
  const evening = [entry({ start_time: '21:00', end_time: '22:30', subject_name: 'Nocturna' })]
  const plan = nextClassToday(evening, new Date('2027-02-02T02:00:00Z'))
  assert.equal(plan.next.entry.subject_name, 'Nocturna')
  assert.equal(plan.next.state, 'in_progress')
  assert.equal(plan.next.minutes, 30)
})

test('classes of the same hour are ordered by end time and the input is not mutated', () => {
  const input = [entry({ subject_name: 'B', end_time: '10:00' }), entry({ subject_name: 'A', end_time: '09:00' })]
  const copy = structuredClone(input)
  assert.deepEqual(names(nextClassToday(input, at('07:00')).later), ['B'])
  assert.deepEqual(input, copy)
})

test('countdown labels read as minutes, whole hours or hours and minutes', () => {
  const upcoming = (minutes) => countdownLabel({ state: 'upcoming', minutes })
  assert.equal(upcoming(1), 'En 1 min')
  assert.equal(upcoming(34), 'En 34 min')
  assert.equal(upcoming(60), 'En 1 h')
  assert.equal(upcoming(80), 'En 1 h 20 min')
  assert.equal(countdownLabel({ state: 'in_progress', minutes: 30 }), 'En curso')
})

test('the average uses a decimal comma and a dash when there is none', () => {
  assert.equal(formatAverage(74.2), '74,2')
  assert.equal(formatAverage(74), '74,0')
  assert.equal(formatAverage(null), '—')
})

test('the hero call to action keeps the open-window copy and falls back to "Ver mi rematrícula"', () => {
  assert.equal(rematriculaCta({ is_open: true }, null), 'Solicitar rematrícula')
  assert.equal(rematriculaCta({ is_open: true }, { status: 'pendiente' }), 'Ver o editar mi solicitud')
  assert.equal(rematriculaCta({ is_open: false }, null), 'Ver mi rematrícula')
  assert.equal(rematriculaCta(null, null), 'Ver mi rematrícula')
  assert.equal(rematriculaCta(undefined, { status: 'realizada' }), 'Ver mi rematrícula')
})

const page = read('src/pages/student/StudentHomePage.tsx')
const card = read('src/components/student/HomeCard.tsx')
const css = read('src/index.css')

test('Inicio has exactly one h1 inside the glass hero (R5) on an Aurora stage', () => {
  assert.equal((page.match(/<h1\b/g) ?? []).length, 1)
  assert.match(page, /Hola/)
  assert.match(page, /import \{[^}]*\bGlassCard\b[^}]*\} from '@\/components\/student'/)
  assert.match(page, /import \{[^}]*\bGlassStage\b[^}]*\} from '@\/components\/student'/)
  assert.match(page, /<GlassStage\b[^>]*wallpaper="aurora"/)
  assert.match(page, /<GlassCard\b/)
  assert.ok(page.indexOf('<GlassCard') < page.indexOf('<h1') && page.indexOf('<h1') < page.indexOf('</GlassCard>'))
  assert.match(page, /to="\/estudiante\/rematricula"/)
  assert.match(page, /rematriculaCta\(/)
})

test('Inicio shows the Rematrícula, Cuotas, Mi horario de hoy and Avance de carrera cards with icons', () => {
  for (const title of ['Rematrícula', 'Cuotas', 'Mi horario de hoy', 'Avance de carrera', 'Documentos migratorios', 'Mis datos']) {
    assert.match(page, new RegExp(`title="${title}"|>${title}<`), `${title} card`)
  }
  assert.equal((page.match(/<HomeCard\b/g) ?? []).length >= 6, true)
  assert.match(page, /icon=\{CalendarCheck\}|icon=\{ClipboardPen\}/)
  for (const text of ['Montos informativos; el pago se realiza en caja.', 'No tenés clases hoy', 'Ver mi horario', 'Ver historial', 'Cargando tu rematrícula']) {
    assert.ok(page.includes(text), `keeps "${text}"`)
  }
  assert.match(page, /Cuota: <strong>/)
})

test('Inicio reuses the schedule and history data with the pure helpers', () => {
  assert.match(page, /useStudentSchedule\(\)/)
  assert.match(page, /useStudentHistory\(\)/)
  assert.match(page, /nextClassToday\(/)
  assert.match(page, /summarizeHistory\(/)
  assert.match(page, /<Progress\b/)
})

test('Inicio has loading skeletons and error states for the reenrollment query and the new cards', () => {
  assert.match(page, /import \{ Skeleton \} from '@\/components\/ui\/skeleton'/)
  assert.match(page, /aria-label="Cargando tu rematrícula"/)
  assert.match(page, /import \{[^}]*\bAlert\b[^}]*\} from '@\/components\/ui\/alert'/)
  assert.match(page, /view\.isError[\s\S]*?<Alert variant="error" role="alert">[\s\S]*?No se pudo cargar tu rematrícula\./)
  assert.match(page, /No se pudo cargar tu horario\./)
  assert.match(page, /No se pudo cargar tu avance\./)
  assert.match(page, /request\?\.status === 'observada'/, 'keeps the observada alert')
})

test('cards lift on hover, give press feedback and fade in with a stagger that respects reduced motion', () => {
  assert.match(card, /<Card\b[^>]*interactive/)
  assert.match(card, /active:scale-/)
  assert.match(card, /motion-reduce:/)
  assert.match(card, /useReducedMotion/)
  assert.match(card, /initial=\{reduceMotion \? false/)
  assert.match(card, /delay: index \*/)
  assert.match(card, /<CardTitle\b[^>]*render=\{<h2/)
  assert.match(page, /sp-pop/)
  assert.match(css, /@keyframes sp-pop\b/)
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  for (const name of ['.sp-pop', '.sp-home-cta']) assert.ok(reduced.includes(name), `reduced motion covers ${name}`)
})

test('Inicio keeps colors in tokens: no hex, gradients or palette classes in the TSX and the cards are single-column on phones', () => {
  for (const code of [page, card]) {
    assert.doesNotMatch(code, /#[0-9a-fA-F]{3,8}\b/)
    assert.doesNotMatch(code, /gradient|rgba?\(/)
  }
  assert.match(page, /grid gap-4 md:grid-cols-2/)
  assert.doesNotMatch(page, /["'\s]grid-cols-[2-9]/, 'no multi-column grid without a breakpoint')
})
