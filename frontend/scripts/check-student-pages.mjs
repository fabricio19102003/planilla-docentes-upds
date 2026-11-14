import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { buildReceipt } from '../src/lib/studentReceipt.ts'
import { defaultScheduleMode, scheduleViewDays, scheduleViewEmpty } from '../src/lib/studentScheduleView.ts'

// S1/S2/S8/S9: Rematrícula (R2 receipt, R3 sending state), Horario (R6 switch Hoy / Semana / Próximo),
// Historial and Cursos de verano e invierno (icons, micro-interactions).

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const subject = (code, name) => ({ code, name, semester: 2 })
const eligibility = (over = {}) => ({
  target_semester: 4,
  recursado: [subject('LIN 0130', 'Lingüística'), subject('MRF 0110', 'Morfología'), subject('MRF 0120', 'Fisiología'), subject('MRF 0200', 'Histología')],
  pending: [subject('CBC 0200', 'Bioquímica')],
  scholarship: { label: 'Sin beca', cuota: 1600, cuotas: 5, total: 8000 },
  recursado_fee: { per_subject: 1200 },
  ...over,
})
const student = { termCode: 'I/2027', studentName: 'Valeria Mamani', documentNumber: '9876543' }
const receipt = (choices, over = {}) => buildReceipt({ eligibility: eligibility(over.eligibility), choices, ...student })

test('without recursado the receipt has the cuotas line and the total is the cuotas total', () => {
  const result = receipt({})
  assert.equal(result.title, 'UPDS COBIJA')
  assert.deepEqual(result.subtitle, ['Rematrícula I/2027', 'Valeria Mamani · 9876543'])
  assert.deepEqual(result.items, [{ qty: 5, label: 'Cuotas × 1.600 Bs', amount: '8.000 Bs' }])
  assert.equal(result.total, '8.000 Bs')
  assert.deepEqual(result.notes, ['Montos informativos', 'se paga en caja'])
  assert.equal(result.limitNote, null)
})

test('each chosen recursado subject is a line with its fee; pending subjects never are', () => {
  const result = receipt({ 'LIN 0130': 1, 'MRF 0110': '', 'CBC 0200': 4 })
  assert.deepEqual(result.items, [
    { qty: 5, label: 'Cuotas × 1.600 Bs', amount: '8.000 Bs' },
    { qty: 1, label: 'Recursado: Lingüística', amount: '1.200 Bs' },
  ])
  assert.equal(result.total, '9.200 Bs')
  assert.equal(result.limitNote, null)
})

test('three recursado subjects are all charged and four charge only three', () => {
  const three = receipt({ 'LIN 0130': 1, 'MRF 0110': 1, 'MRF 0120': 1 })
  assert.deepEqual(three.items.map((item) => item.amount), ['8.000 Bs', '1.200 Bs', '1.200 Bs', '1.200 Bs'])
  assert.equal(three.total, '11.600 Bs')
  assert.equal(three.limitNote, null)

  const four = receipt({ 'LIN 0130': 1, 'MRF 0110': 1, 'MRF 0120': 1, 'MRF 0200': 2 })
  assert.deepEqual(four.items.map((item) => item.amount), ['8.000 Bs', '1.200 Bs', '1.200 Bs', '1.200 Bs', 'Sin cobro'])
  assert.equal(four.items[4].label, 'Recursado: Histología')
  assert.equal(four.total, '11.600 Bs')
  assert.equal(four.limitNote, 'Se cobran como máximo 3 materias.')
})

test('zero cuotas leave no cuotas line and the total only has the recursado fees', () => {
  const none = receipt({}, { eligibility: { scholarship: { label: 'Beca completa', cuota: 0, cuotas: 0, total: 0 } } })
  assert.deepEqual(none.items, [])
  assert.equal(none.total, '0 Bs')
  const some = receipt({ 'LIN 0130': 1 }, { eligibility: { scholarship: { label: 'Beca completa', cuota: 0, cuotas: 0, total: 0 } } })
  assert.deepEqual(some.items, [{ qty: 1, label: 'Recursado: Lingüística', amount: '1.200 Bs' }])
  assert.equal(some.total, '1.200 Bs')
})

test('the receipt header skips what is not known yet', () => {
  assert.deepEqual(buildReceipt({ eligibility: eligibility(), choices: {}, termCode: 'I/2027' }).subtitle, ['Rematrícula I/2027'])
  assert.deepEqual(buildReceipt({ eligibility: eligibility(), choices: {} }).subtitle, [])
})

// 2027-02-01 is a Monday; Bolivia is UTC-4, so 12:00Z is 08:00 in La Paz.
const MONDAY_NOON = new Date('2027-02-01T16:00:00Z')
const entry = (over = {}) => ({
  source: 'grupo', subject_code: 'MED 100', subject_name: 'Anatomía', group_code: 'M-01',
  weekday: 'monday', start_time: '08:00', end_time: '09:30', classroom: { code: 'A-1', name: 'Aula 1' },
  activity_type: 'theory', teacher_name: 'Docente A', term_code: 'I/2027', effective_from: '2027-02-01',
  is_upcoming: false, ...over,
})
const ENTRIES = [
  entry({ subject_name: 'Fisiopatología', start_time: '14:00', end_time: '15:30' }),
  entry({ subject_name: 'Anatomía' }),
  entry({ subject_name: 'Física', weekday: 'tuesday' }),
  entry({ subject_name: 'Genética', weekday: 'monday', start_time: '10:00', end_time: '11:00', is_upcoming: true, effective_from: '2027-03-01' }),
]
const names = (days) => days.flatMap((day) => day.entries.map((item) => item.subject_name))

test('Hoy lists only today\'s classes in La Paz time, in order, ignoring publications that have not started', () => {
  const days = scheduleViewDays(ENTRIES, 'today', MONDAY_NOON)
  assert.equal(days.length, 1)
  assert.equal(days[0].label, 'Hoy · Lunes')
  assert.deepEqual(names(days), ['Anatomía', 'Fisiopatología'])
  // 03:00Z on Tuesday is still Monday night in La Paz.
  assert.equal(scheduleViewDays(ENTRIES, 'today', new Date('2027-02-02T03:00:00Z'))[0].label, 'Hoy · Lunes')
})

test('Semana keeps the per-weekday cards of every entry', () => {
  const days = scheduleViewDays(ENTRIES, 'week', MONDAY_NOON)
  assert.deepEqual(days.map((day) => day.label), ['Lunes', 'Martes'])
  assert.deepEqual(names(days), ['Anatomía', 'Genética', 'Fisiopatología', 'Física'])
})

test('Próximo lists only entries of a publication that has not started, by weekday', () => {
  const days = scheduleViewDays(ENTRIES, 'upcoming', MONDAY_NOON)
  assert.deepEqual(days.map((day) => day.label), ['Lunes'])
  assert.deepEqual(names(days), ['Genética'])
})

test('every view is empty with no entries, and each says why', () => {
  for (const mode of ['today', 'week', 'upcoming']) {
    assert.deepEqual(scheduleViewDays([], mode, MONDAY_NOON), [])
    assert.ok(scheduleViewEmpty(mode).length > 0)
  }
  assert.equal(scheduleViewEmpty('today'), 'No tenés clases hoy.')
  assert.equal(scheduleViewEmpty('upcoming'), 'No hay un horario próximo publicado.')
  assert.deepEqual(scheduleViewDays([entry({ weekday: 'tuesday' })], 'today', MONDAY_NOON), [])
  assert.deepEqual(scheduleViewDays([entry()], 'upcoming', MONDAY_NOON), [])
})

test('the switch starts on Hoy when there are classes today and on Semana otherwise', () => {
  assert.equal(defaultScheduleMode(ENTRIES, MONDAY_NOON), 'today')
  assert.equal(defaultScheduleMode([entry({ weekday: 'tuesday' })], MONDAY_NOON), 'week')
  assert.equal(defaultScheduleMode([entry({ is_upcoming: true })], MONDAY_NOON), 'week')
  assert.equal(defaultScheduleMode([], MONDAY_NOON), 'week')
})

test('Rematrícula prints the receipt and shows the thermal loader while sending', () => {
  const code = read('src/pages/student/StudentReenrollmentPage.tsx')
  assert.match(code, /<PrintReceipt\b/)
  assert.match(code, /buildReceipt\(/)
  assert.match(code, /<ThermalLoader\b/)
  assert.match(code, /Enviando tu solicitud a Registro…/)
  assert.match(code, /submit\.isPending/)
  assert.ok(code.includes('Resumen de montos (informativo)'))
  assert.ok(code.includes('<select'), 'recursado keeps native selects')
  assert.doesNotMatch(code, /<dl\b/, 'the amounts live in the receipt now')
})

test('Horario switches Hoy / Semana / Próximo with the glass switch on a glass stage', () => {
  const code = read('src/pages/student/StudentSchedulePage.tsx')
  assert.match(code, /<GlassSwitch\b/)
  assert.match(code, /<GlassStage\b/)
  for (const text of ['Hoy', 'Semana', 'Próximo']) assert.ok(code.includes(`'${text}'`), `${text} is an option`)
  assert.ok(code.includes('Este horario todavía no empezó a regir; puede cambiar hasta esa fecha.'))
  assert.match(code, /role="tabpanel"/)
  for (const icon of ['Clock', 'MapPin', 'User']) assert.match(code, new RegExp(`\\b${icon}\\b[^\\n]*lucide-react|lucide-react[^\\n]*\\b${icon}\\b`), `${icon} icon`)
  assert.match(code, /<EmptyState\b[^>]*icon=\{/)
})

test('Historial adds metric icons, an animated fill and staggered timeline dots, keeping the outcome chips', () => {
  const code = read('src/components/students/StudentHistoryTimeline.tsx')
  assert.match(code, /from 'lucide-react'/)
  assert.match(code, /useReducedMotion/)
  assert.match(code, /sp-timeline-dot/)
  assert.match(code, /TONE_CHIP\[OUTCOME_TONE\[outcome\]\]/)
  assert.ok(code.includes('Promedio general') && code.includes('Materias aprobadas'))
})

test('Cursos de verano e invierno puts an icon on each course and keeps the confirmation', () => {
  const code = read('src/pages/student/StudentIntensivePage.tsx')
  assert.match(code, /\b(?:Sun|Snowflake)\b/)
  assert.match(code, /<ConfirmAlertDialog\b/)
  assert.match(code, /active:scale-/)
})

test('the new CSS lives in index.css, with reduced motion ending on the same state', () => {
  const css = read('src/index.css')
  for (const name of ['sp-timeline-dot', 'sp-radio-card', 'sp-sched-row']) assert.ok(css.includes(`.${name}`), `${name} is styled`)
})

test('the portal scopes the violet accent, keeps the notch edge visible and the switch 74px wide', () => {
  const css = read('src/index.css')
  assert.match(css, /\.student-scope \{[^}]*--primary: var\(--student-accent\)[^}]*--brand-strong: var\(--student-accent\)/)
  assert.match(read('src/pages/student/StudentPortalLayout.tsx'), /student-scope/)
  assert.doesNotMatch(read('src/pages/student/StudentPortalLayout.tsx'), /\boutline-none\b/, 'outline-none hides the nav focus ring')
  assert.match(css, /\.sp-notch-shade \{[^}]*drop-shadow/)
  assert.match(css, /\.sp-glass-switch-tab \{[^}]*width: 74px/)
})
