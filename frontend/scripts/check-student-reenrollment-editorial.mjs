import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  RECURSADO_CHARGED_MAX,
  chosenSummary,
  groupSeats,
  requestFlow,
  shiftIconName,
  shiftTurnoName,
} from '../src/components/student/reenrollment/reenrollment-view.ts'
import { buildReceipt } from '../src/lib/studentReceipt.ts'

// S1-S3 (T6): Rematrícula in the editorial style of artboard 03: turno cards with a seats meter, recursado switch +
// custom combobox, subject chips, summary sheet with the receipt and a sticky glass submit bar.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const page = read('src/pages/student/StudentReenrollmentPage.tsx')
const css = existsSync(resolve(root, 'src/styles/student/reenrollment.css')) ? read('src/styles/student/reenrollment.css') : ''
const dir = resolve(root, 'src/components/student/reenrollment')
const parts = existsSync(dir) ? readdirSync(dir).filter((name) => name.endsWith('.tsx')) : []
const ui = [page, ...parts.map((name) => read(`src/components/student/reenrollment/${name}`))].join('\n')

const group = (over = {}) => ({ id: 1, code: 'M-01', shift: 'M', semester: 4, capacity: 40, taken: 1, free: 39, is_full: false, ...over })

test('the turno of a group picks the sun, sunset or moon icon', () => {
  assert.equal(shiftIconName('M'), 'sun')
  assert.equal(shiftIconName('T'), 'sunset')
  assert.equal(shiftIconName('N'), 'moon')
  assert.equal(shiftIconName('X'), 'sun')
  assert.equal(shiftTurnoName('M'), 'Turno mañana')
  assert.equal(shiftTurnoName('T'), 'Turno tarde')
  assert.equal(shiftTurnoName('N'), 'Turno noche')
  assert.equal(shiftTurnoName('X'), 'Turno X')
})

test('the seats meter reads "N de M libres" from the cupos data and tones by how full the group is', () => {
  assert.deepEqual(groupSeats(group()), { free: 39, capacity: 40, occupied: 1, text: '39 de 40 libres', tone: 'ok', full: false, segments: 40 })
  assert.deepEqual(groupSeats(group({ taken: 34, free: 6 })), { free: 6, capacity: 40, occupied: 34, text: '6 de 40 libres', tone: 'warn', full: false, segments: 40 })
  assert.deepEqual(groupSeats(group({ taken: 40, free: 0, is_full: true })), { free: 0, capacity: 40, occupied: 40, text: '0 de 40 libres', tone: 'bad', full: true, segments: 40 })
  // Large groups draw at most 40 segments.
  assert.equal(groupSeats(group({ capacity: 200, taken: 20, free: 180 })).segments, 40)
  // No capacity data, no meter.
  assert.equal(groupSeats(group({ capacity: null, free: null })), null)
})

test('the request flow marks the step of each status and keeps Registro\'s observation visible', () => {
  const pending = requestFlow('pendiente')
  assert.deepEqual(pending.steps.map((step) => step.label), ['Enviada', 'En revisión', 'Realizada'])
  assert.equal(pending.current, 1)
  assert.equal(pending.label, 'Pendiente')
  assert.equal(pending.tone, 'warn')
  assert.equal(pending.hint, 'Pendiente: Registro todavía no completó tu rematrícula.')
  const done = requestFlow('realizada')
  assert.equal(done.current, 3)
  assert.equal(done.label, 'Realizada')
  assert.equal(done.tone, 'ok')
  const observed = requestFlow('observada')
  assert.deepEqual(observed.steps.map((step) => step.label), ['Enviada', 'Observada', 'Realizada'])
  assert.equal(observed.current, 1)
  assert.equal(observed.label, 'Observada')
  assert.equal(observed.tone, 'bad')
})

test('the sticky bar summarises the chosen group and the recursado count', () => {
  assert.equal(chosenSummary(group(), 0), 'M-01 · Mañana · sin recursado')
  assert.equal(chosenSummary(group({ code: 'T-01', shift: 'T' }), 1), 'T-01 · Tarde · 1 recursado')
  assert.equal(chosenSummary(group({ code: 'N-01', shift: 'N' }), 3), 'N-01 · Noche · 3 recursados')
  assert.equal(chosenSummary(undefined, 2), 'Sin grupo elegido · 2 recursados')
})

test('the recursado cap shown in the tip is the one the receipt charges', () => {
  const subject = (n) => ({ code: `MRF 010${n}`, name: `Materia ${n}`, semester: 2 })
  const recursado = [1, 2, 3, 4, 5].map(subject)
  const choices = Object.fromEntries(recursado.map((item) => [item.code, 1]))
  const receipt = buildReceipt({
    eligibility: { target_semester: 4, recursado, pending: [], scholarship: { label: 'Sin beca', cuota: 1000, cuotas: 1, total: 1000 }, recursado_fee: { per_subject: 100 } },
    choices,
  })
  assert.equal(receipt.limitNote, `Se cobran como máximo ${RECURSADO_CHARGED_MAX} materias.`)
})

test('Rematrícula leaves no native select or details: the picker, switch and chips replace them', () => {
  assert.doesNotMatch(ui, /<select\b/)
  assert.doesNotMatch(ui, /<option\b/)
  assert.doesNotMatch(ui, /<details\b/)
  assert.doesNotMatch(ui, /<summary\b/)
  assert.doesNotMatch(ui, /list-disc/)
  assert.match(ui, /role="switch"/)
  assert.match(ui, /from '@\/components\/ui\/select'/, 'the group picker is built on the base-ui Select (listbox + keyboard)')
  assert.match(ui, /<SelectItem\b/)
  assert.ok(ui.includes('No la curso este período'))
  assert.match(ui, /sp-chip|rm-chip/)
})

test('group cards are keyboard radios with a turno icon, a seats meter and the selected state', () => {
  assert.match(ui, /type="radio"/)
  assert.match(ui, /name="main-group"/)
  assert.match(ui, /sp-radio-card/)
  assert.match(ui, /data-selected=/)
  assert.match(ui, /<Meter\b[^>]*segments=/)
  assert.match(ui, /\b(?:Sun|Sunset|Moon)\b[^\n]*lucide-react|lucide-react[^\n]*\b(?:Sun|Sunset|Moon)\b/s)
  assert.match(ui, /unavailable = group\.is_full && !selected/, 'full groups are unavailable unless already selected')
  assert.match(ui, /disabled=\{disabled \|\| unavailable\}/)
})

test('the summary sheet shows the total as a display figure with tips on the cuota and recursado fee rules', () => {
  assert.match(ui, /<DisplayFigure\b/)
  assert.match(ui, /<InfoTip\b/)
  assert.ok(ui.includes('Resumen de montos (informativo)'))
  assert.match(ui, /<PrintReceipt\b/)
  assert.match(ui, /Se cobran como máximo/)
  assert.match(ui, /receipt\.limitNote/)
})

test('the submit bar is sticky glass above the mobile tab bar, safe-area aware, and keeps the sending state', () => {
  assert.match(ui, /<SubmitBar\b/)
  assert.match(ui, /role="region"/)
  assert.match(ui, /aria-label="Enviar solicitud"/)
  assert.match(css, /\.rm-sbar \{[^}]*position: sticky/)
  assert.match(css, /\.rm-sbar \{[^}]*bottom: calc\([^;]*safe-area-inset-bottom/)
  assert.match(ui, /className="rm-sbar sp-glass-sheet"/, 'the bar is a glass sheet (opaque without backdrop-filter or with reduced transparency)')
  assert.match(css, /@media \(min-width: 48rem\)[\s\S]*\.rm-sbar/, 'above the notch bar only below md')
  assert.match(ui, /<ThermalLoader\b/)
  assert.match(ui, /Enviando tu solicitud a Registro…/)
  assert.match(ui, /submit\.isPending/)
  assert.match(ui, /loading=\{submit\.isPending\}/)
  assert.match(ui, /disabled=\{problem !== null\}/)
})

test('the page keeps its guards: one PageHeader h1, Skeleton, Alerts, key strings and the submit rules', () => {
  assert.equal((page.match(/<PageHeader as="h1"/g) ?? []).length, 1)
  assert.equal((ui.match(/<h1\b/g) ?? []).length, 0)
  assert.match(page, /import \{ Skeleton \} from '@\/components\/ui\/skeleton'/)
  assert.match(page, /<Skeleton\b/)
  assert.match(page, /import \{[^}]*\bAlert\b[^}]*\} from '@\/components\/ui\/alert'/)
  for (const text of ['No se pudo cargar la rematrícula.', 'Todavía no hay una rematrícula programada.', 'La rematrícula no está abierta en este momento.',
    'Tu rematrícula fue realizada por Registro.', 'Observación de Registro:', 'Cuando lo resuelvas, guardá tu solicitud de nuevo.',
    'No encontramos tu historial académico; acercate a Registro.', 'Solicitud enviada. Registro la va a revisar y vas a ver el estado acá.',
    'No se pudo enviar tu solicitud.', 'Guardar cambios', 'Enviar solicitud', 'Materias para recursar', 'Materias pendientes',
    'Antes de que Registro complete tu rematrícula tenés que haber pagado el recursado en caja.',
    'No tienen costo de recursado.']) {
    assert.ok(ui.includes(text), `keeps "${text}"`)
  }
  assert.match(page, /buildSubmission\(mainGroup, choices\)/)
  assert.match(page, /submissionProblem\(view, mainGroup\)/)
  assert.match(page, /buildReceipt\(/)
})

test('the editorial CSS is a stylesheet of its own, imported by the page, with tokens only in the TSX', () => {
  assert.match(page, /import '@\/styles\/student\/reenrollment\.css'/)
  for (const selector of ['.rm-sbar', '.rm-group', '.rm-chip', '.rm-flow']) assert.ok(css.includes(selector), `${selector} is styled`)
  assert.match(css, /prefers-reduced-motion: reduce/)
  assert.match(css, /prefers-reduced-transparency|sp-glass-solid/)
  assert.match(css, /min-height: 2\.75rem|min-height: 44px|min-height: 3[0-9.]*rem/, 'touch targets of 44px or more')
  const HEX = /#[0-9a-fA-F]{3,8}\b/g
  assert.deepEqual(ui.match(HEX) ?? [], [])
  assert.deepEqual(ui.match(/(?:linear|radial)-gradient|\brgba?\(/g) ?? [], [])
  assert.deepEqual(ui.match(/\b(?:bg|text|border|ring|from|to|via|fill|stroke)-(?:gray|slate|zinc|neutral|red|amber|green|emerald|violet|purple|blue)-\d{2,3}\b/g) ?? [], [])
})
