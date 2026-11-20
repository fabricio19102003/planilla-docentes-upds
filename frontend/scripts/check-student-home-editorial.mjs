import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  REQUEST_STEPS,
  STAT_TIPS,
  careerSemesters,
  classProgress,
  countdownParts,
  dataValue,
  requestFlow,
  requestStepNotes,
} from '../src/components/student/home/home-state.ts'

// S1/S2/S3: the editorial shell and Inicio (artboard 03): request stepper, stats strip with tooltips, "Hoy" sheet,
// career track, Mis datos icon grid and a content-shaped skeleton, all on tokens and the sp- editorial classes.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const homeDir = resolve(root, 'src/components/student/home')
const homeFiles = existsSync(homeDir) ? readdirSync(homeDir).filter((name) => name.endsWith('.tsx')) : []
const homeSources = Object.fromEntries(homeFiles.map((name) => [name, read(`src/components/student/home/${name}`)]))
const page = read('src/pages/student/StudentHomePage.tsx')
const layout = read('src/pages/student/StudentPortalLayout.tsx')
const homeCss = existsSync(resolve(root, 'src/styles/student/home.css')) ? read('src/styles/student/home.css') : ''
const shellCss = existsSync(resolve(root, 'src/styles/student/shell.css')) ? read('src/styles/student/shell.css') : ''
const tsx = { StudentHomePage: page, StudentPortalLayout: layout, ...homeSources }
const homeTsx = [page, ...Object.values(homeSources)].join('\n')

// --- request stepper: Enviada -> En revisión -> Realizada from the real request status --------------------------

test('the stepper has the three request steps in order', () => {
  assert.deepEqual(REQUEST_STEPS, ['Enviada', 'En revisión', 'Realizada'])
})

test('no request: nothing is done and the first step is the current one', () => {
  assert.deepEqual(requestFlow(null), { current: 0, alert: false })
  assert.deepEqual(requestFlow(undefined), { current: 0, alert: false })
})

test('pendiente: sent is done and the review is the current step', () => {
  assert.deepEqual(requestFlow('pendiente'), { current: 1, alert: false })
})

test('realizada: every step is done (current = steps.length)', () => {
  assert.deepEqual(requestFlow('realizada'), { current: REQUEST_STEPS.length, alert: false })
})

test('observada: stays on the review step and is shown as an alert state', () => {
  assert.deepEqual(requestFlow('observada'), { current: 1, alert: true })
})

test('step notes explain each step with the dates and the observation', () => {
  assert.deepEqual(requestStepNotes(null, { closesOn: '05/12/2026' }), ['Todavía no la enviaste', 'Registro la revisa cuando la recibe', 'Abierta hasta el 05/12/2026'])
  assert.deepEqual(requestStepNotes('pendiente', { submittedOn: '20/11/2026' }), ['Enviada el 20/11/2026', 'Registro la está revisando', 'Se confirma al aprobarla'])
  assert.equal(requestStepNotes('realizada', { submittedOn: '20/11/2026', handledOn: '22/11/2026' })[2], 'Realizada el 22/11/2026')
  assert.equal(requestStepNotes('observada', { submittedOn: '20/11/2026', observationLabel: 'Pago pendiente' })[1], 'Observada: Pago pendiente')
  assert.equal(requestStepNotes('observada', { submittedOn: '20/11/2026' })[1], 'Tiene una observación de Registro')
})

// --- career track -------------------------------------------------------------------------------------------------

test('career semesters: done before the current one, then current, next and pending, with recursado flagged', () => {
  const track = careerSemesters({ primary: 3, target: 4, retake: [2] })
  assert.equal(track.length, 10)
  assert.deepEqual(track.slice(0, 5).map((item) => [item.semester, item.state]), [[1, 'done'], [2, 'retake'], [3, 'current'], [4, 'next'], [5, 'pending']])
  assert.equal(track[1].tip, 'Semestre 2 · tenés materias por recursar.')
  assert.equal(track[2].tip, 'Estás aquí: semestre 3.')
  assert.equal(track[3].tip, 'Te corresponde cursar el semestre 4.')
  assert.equal(track[0].tip, 'Semestre 1 · completo.')
  assert.equal(track[9].tip, 'Semestre 10 · todavía no cursado.')
})

test('career semesters: the track grows past 10 and falls back without a primary semester', () => {
  assert.equal(careerSemesters({ primary: 11, target: 12, retake: [] }).length, 12)
  const noPrimary = careerSemesters({ primary: null, target: 4, retake: [] })
  assert.deepEqual(noPrimary.slice(0, 4).map((item) => item.state), ['done', 'done', 'current', 'next'])
  assert.ok(careerSemesters({ primary: null, target: null, retake: [] }).every((item) => item.state === 'pending'))
  const same = careerSemesters({ primary: 4, target: 4, retake: [] })
  assert.equal(same[3].state, 'current', 'the current semester wins over next')
})

// --- small display rules ------------------------------------------------------------------------------------------

test('missing data reads as null so the UI can show a styled "Sin dato"', () => {
  assert.equal(dataValue('712 34567'), '712 34567')
  assert.equal(dataValue(''), null)
  assert.equal(dataValue('   '), null)
  assert.equal(dataValue(null), null)
  assert.equal(dataValue(undefined), null)
})

test('the countdown splits into a figure and a unit', () => {
  assert.deepEqual(countdownParts({ state: 'upcoming', minutes: 48 }), { value: 48, unit: 'min', caption: 'para que empiece' })
  assert.deepEqual(countdownParts({ state: 'upcoming', minutes: 60 }), { value: 1, unit: 'h', caption: 'para que empiece' })
  assert.deepEqual(countdownParts({ state: 'upcoming', minutes: 80 }), { value: 1, unit: 'h 20 min', caption: 'para que empiece' })
  assert.deepEqual(countdownParts({ state: 'in_progress', minutes: 30 }), { value: 30, unit: 'min', caption: 'para que termine' })
})

test('class progress is the elapsed share of an in-progress class and 0 before it starts', () => {
  const entry = { start_time: '08:00', end_time: '09:30' }
  assert.equal(classProgress({ entry, state: 'in_progress', minutes: 45 }), 50)
  assert.equal(classProgress({ entry, state: 'in_progress', minutes: 90 }), 0)
  assert.equal(classProgress({ entry, state: 'upcoming', minutes: 10 }), 0)
  assert.equal(classProgress({ entry: { start_time: '09:00', end_time: '09:00' }, state: 'in_progress', minutes: 0 }), 0)
})

// --- stats strip with tooltips ---------------------------------------------------------------------------------

test('each stat explains itself with a tip', () => {
  assert.deepEqual(Object.keys(STAT_TIPS).sort(), ['aprobadas', 'avance', 'cuota', 'promedio'])
  for (const text of Object.values(STAT_TIPS)) assert.ok(text.length > 30 && text.endsWith('.'), text)
})

test('the stats strip shows the four figures with DisplayFigure, a ring and one InfoTip each', () => {
  const strip = homeSources['StatsStrip.tsx']
  assert.ok(strip, 'StatsStrip.tsx exists')
  assert.match(strip, /import \{[^}]*\bDisplayFigure\b[^}]*\bProgressRing\b[^}]*\} from '@\/components\/student'|import \{[^}]*\bProgressRing\b[^}]*\bDisplayFigure\b[^}]*\} from '@\/components\/student'/)
  assert.ok((strip.match(/<DisplayFigure\b/g) ?? []).length >= 3, 'promedio, aprobadas and cuota use DisplayFigure')
  assert.match(strip, /<ProgressRing\b/)
  for (const key of ['promedio', 'avance', 'aprobadas', 'cuota']) assert.ok(strip.includes(`STAT_TIPS.${key}`), `${key} tip`)
  assert.match(strip, /<InfoTip\b/)
  assert.equal((strip.match(/<StatCell\b/g) ?? []).length, 4, 'each of the four stats is a StatCell that carries its InfoTip')
  for (const text of ['Promedio', 'Avance de carrera', 'Aprobadas', 'Cuota mensual']) assert.ok(strip.includes(text), text)
})

// --- structure of the page ---------------------------------------------------------------------------------------

test('Inicio keeps exactly one h1 "Hola" in the page and the request stepper sits on the glass poster', () => {
  assert.equal((page.match(/<h1\b/g) ?? []).length, 1)
  for (const [name, source] of Object.entries(homeSources)) assert.doesNotMatch(source, /<h1\b/, `${name} must not add another h1`)
  assert.match(page, /<h1\b[^>]*sp-display[^>]*>[\s\S]*?Hola/)
  assert.match(page, /first_names/)
  assert.match(page, /<GlassStage\b[^>]*wallpaper="aurora"/)
  assert.match(page, /<GlassCard\b/)
  assert.match(page, /<RequestStepper\b/)
  assert.match(homeSources['RequestStepper.tsx'] ?? '', /<Stepper\b[^>]*inverse/)
  assert.match(homeSources['RequestStepper.tsx'] ?? '', /requestFlow\(/)
  assert.match(homeSources['RequestStepper.tsx'] ?? '', /data-alert/, 'observada is an alert state')
})

test('the page composes the editorial sections from the existing hooks', () => {
  for (const name of ['StatsStrip', 'TodaySheet', 'CareerSheet', 'DataGrid', 'MigrationChecklist', 'HomeSkeleton', 'LinkButton']) {
    assert.ok(homeSources[`${name}.tsx`], `${name}.tsx exists`)
    assert.match(page, new RegExp(`<${name}\\b`), `the page renders ${name}`)
  }
  for (const hook of ['useStudentSchedule', 'useStudentHistory', 'useStudentMigrationDocuments', 'useStudentReenrollment', 'useStudentMe']) {
    assert.ok(homeTsx.includes(`${hook}()`), `${hook} still feeds Inicio`)
  }
  assert.match(homeSources['TodaySheet.tsx'], /nextClassToday\(/)
  assert.match(homeSources['CareerSheet.tsx'], /summarizeHistory\(|careerSemesters\(/)
  assert.match(homeSources['TodaySheet.tsx'], /<Sheet\b/)
  assert.match(homeSources['CareerSheet.tsx'], /<Sheet\b/)
})

test('no native <dl> or plain list remains: Mis datos is an icon grid, lists carry editorial classes', () => {
  for (const [name, source] of Object.entries(tsx)) {
    assert.doesNotMatch(source, /<(?:dl|dt|dd)\b/, `${name}: native description list`)
    assert.doesNotMatch(source, /list-disc|list-decimal|divide-y/, `${name}: default list styling`)
    for (const [, attrs] of source.matchAll(/<(?:ul|ol)\b([^>]*)>/g)) assert.match(attrs, /className=/, `${name}: a <ul>/<ol> without editorial classes`)
  }
  const grid = homeSources['DataGrid.tsx']
  assert.match(grid, /<Sheet\b/)
  for (const label of ['Documento', 'Plan de estudio', 'Celular', 'Correo académico', 'Correo personal', 'Nacionalidad']) assert.ok(grid.includes(label), label)
  assert.match(grid, /Sin dato/)
  assert.doesNotMatch(grid, /\|\| '—'|\?\? '—'/, 'the raw dash is replaced by the styled "Sin dato"')
})

test('plain text links became link-buttons with an icon', () => {
  assert.doesNotMatch(homeTsx, /quietLink|underline-offset|hover:underline/)
  const link = homeSources['LinkButton.tsx']
  assert.match(link, /<Link\b/)
  assert.match(link, /icon/)
  assert.match(link, /min-h-11|sph-link/)
  for (const target of ['/estudiante/rematricula', '/estudiante/horario', '/estudiante/historial']) assert.ok(homeTsx.includes(target), `${target} is still linked`)
  assert.doesNotMatch(page, /<Link\b/, 'the page links through LinkButton')
})

test('copy and behaviour guarantees stay: loading, errors, empty states and the observada alert', () => {
  for (const text of [
    'Hola', 'Montos informativos; el pago se realiza en caja.', 'No tenés clases hoy', 'Ya terminaron tus clases de hoy.',
    'Ver mi horario', 'Ver historial', 'No se pudo cargar tu horario.', 'No se pudo cargar tu avance.',
    'No se pudo cargar tu rematrícula.', 'Todavía no tenés materias en tu historial académico.',
    'Cargando tu rematrícula', 'Documentos migratorios', 'Mis datos', 'Si algo está mal, avisá en Registro.',
    'Presentalos en Registro para poder completar tu rematrícula.',
  ]) assert.ok(homeTsx.includes(text), `keeps "${text}"`)
  assert.match(page, /request\?\.status === 'observada'/)
  assert.match(page, /<Alert variant="error" role="alert">/)
  assert.match(page, /import \{ Skeleton \} from '@\/components\/ui\/skeleton'/)
  assert.match(page, /<Skeleton\b/)
  assert.match(homeSources['HomeSkeleton.tsx'], /role="status"/)
  assert.match(homeSources['HomeSkeleton.tsx'], /<Skeleton\b/)
  assert.match(homeSources['HomeSkeleton.tsx'], /aria-label="Cargando tu resumen"/)
  assert.match(page, /rematriculaCta\(/)
})

test('the migration documents are a styled checklist', () => {
  const list = homeSources['MigrationChecklist.tsx']
  assert.match(list, /pendingLabels\(/)
  assert.match(list, /<Sheet\b/)
  assert.match(list, /sph-check/)
  assert.match(list, /regularizado/)
})

test('the "Hoy" sheet counts down with a figure, keeps the later classes and the empty copy', () => {
  const today = homeSources['TodaySheet.tsx']
  assert.match(today, /countdownParts\(/)
  assert.match(today, /countdownLabel\(/)
  assert.match(today, /<Meter\b/)
  assert.match(today, /<InfoTip\b/)
  assert.match(today, /useNow/)
  assert.match(today, /teacherLabel\(/)
})

test('the career track is an ordered list with a tip per semester and aria-current on the current one', () => {
  const career = homeSources['CareerSheet.tsx']
  assert.match(career, /<ol\b[^>]*aria-label="Avance por semestre"/)
  assert.match(career, /aria-current=\{[^}]*'step'/)
  assert.match(career, /<InfoTip\b/)
  assert.match(career, /item\.tip/)
})

// --- tokens, shell and CSS --------------------------------------------------------------------------------------

test('TSX keeps colors in tokens: no hex, gradients, rgb or palette classes', () => {
  for (const [name, source] of Object.entries(tsx)) {
    assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b/, `${name}: hex`)
    assert.doesNotMatch(source, /gradient|rgba?\(/, `${name}: gradient or rgb`)
    assert.doesNotMatch(source, /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline|decoration|shadow|accent)-(?:gray|grey|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/, `${name}: palette class`)
    assert.doesNotMatch(source, /\b(?:bg|text|border)-(?:white|black)\b/, `${name}: white/black`)
    for (const [, style] of source.matchAll(/style=\{\{([\s\S]*?)\}\}/g)) assert.doesNotMatch(style, /color|background|gradient|shadow|border|fill|stroke/i, `${name}: color through style`)
  }
})

test('the page and the layout import their own CSS and the files only use tokens', () => {
  assert.match(page, /import '@\/styles\/student\/home\.css'/)
  assert.match(layout, /import '@\/styles\/student\/shell\.css'/)
  for (const [name, css] of [['home.css', homeCss], ['shell.css', shellCss]]) {
    assert.ok(css.length > 500, `${name} exists and is not empty`)
    assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, `${name}: hex colors come from tokens`)
    assert.match(css, /@media \(prefers-reduced-motion: reduce\)/, `${name}: reduced motion`)
    assert.match(css, /:focus-visible/, `${name}: visible focus`)
  }
  assert.match(homeCss, /@media \(max-width: 40rem\)|@media \(max-width: 640px\)/, 'phone layout')
  assert.match(homeCss, /min-height: 2\.75rem/, '44px targets')
  assert.match(homeCss, /overflow-wrap: anywhere|overflow-wrap: break-word|min-width: 0/, 'long values wrap instead of overflowing at 320px')
})

test('the shell has icon nav with heavier type, a tipped theme toggle and a glass account menu', () => {
  assert.match(layout, /<InfoTip\b[^>]*>[\s\S]*?<ThemeToggle\b[^>]*variant="brand"/)
  assert.match(layout, /content="Cambiar tema"/)
  assert.match(layout, /font-(?:extra)?bold|font-black/, 'heavier nav type')
  assert.match(layout, /sp-glass-sheet/, 'glass account menu')
  assert.match(layout, /document_number/)
  assert.match(layout, /curriculum_plan/)
  assert.match(layout, /initials\(me\.data\.full_name\)/, 'avatar initials')
  assert.match(layout, /aria-current=\{isActive|NavLink/)
  assert.ok(layout.includes('Cambiar contraseña') && layout.includes('Salir'))
  assert.match(layout, /className="student-scope[^"]*\bfont-student\b/)
  assert.match(layout, /<NotchTabBar\b/)
})
