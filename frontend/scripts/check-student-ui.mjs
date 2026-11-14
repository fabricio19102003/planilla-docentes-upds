import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

// S1: the student portal pages follow the same page rules as the docente pages (theme tokens only,
// shared PageHeader, Skeleton while loading, Alert errors and EmptyState results).

const root = resolve(import.meta.dirname, '..')

const PAGES = ['StudentHomePage', 'StudentHistoryPage', 'StudentReenrollmentPage', 'StudentSchedulePage', 'StudentIntensivePage']
// Inicio keeps its welcome card (the R5 glass hero, with the page h1) as its header.
const HEADER_PAGES = PAGES.filter((name) => name !== 'StudentHomePage')

const sources = Object.fromEntries(
  PAGES.map((name) => [name, readFileSync(resolve(root, `src/pages/student/${name}.tsx`), 'utf8')]),
)

const HEX = /#[0-9a-fA-F]{3,8}\b/g
const PALETTE_CLASS =
  /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline|decoration|shadow|accent)-(?:gray|grey|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g
const WHITE_BLACK_CLASS = /\b(?:bg|text|border)-(?:white|black)\b/g

for (const name of PAGES) {
  test(`${name} uses theme tokens only: no hex, gradients or color styles`, () => {
    const code = sources[name]
    assert.deepEqual(code.match(HEX) ?? [], [], `${name} must not contain hex colors`)
    assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${name} must not use gradient-* classes`)
    assert.deepEqual(code.match(/(?:linear|radial)-gradient/g) ?? [], [], `${name} must not use CSS gradients`)
    assert.deepEqual(code.match(/\brgba?\(/g) ?? [], [], `${name} must not use rgb()/rgba() colors`)
    for (const [, style] of code.matchAll(/style=\{\{([\s\S]*?)\}\}/g)) {
      assert.doesNotMatch(style, /color|background|gradient|shadow|border|fill|stroke/i, `${name} must not set colors through style`)
    }
  })

  test(`${name} uses no raw Tailwind palette classes`, () => {
    const code = sources[name]
    assert.deepEqual(code.match(PALETTE_CLASS) ?? [], [], `${name} must use token colors, not palette classes`)
    assert.deepEqual(code.match(WHITE_BLACK_CLASS) ?? [], [], `${name} must use token colors, not white/black`)
  })

  test(`${name} shows a Skeleton, not loading text or a hand-made spinner, while loading`, () => {
    const code = sources[name]
    assert.match(code, /import \{ Skeleton \} from '@\/components\/ui\/skeleton'/)
    assert.match(code, /<Skeleton\b/)
    assert.doesNotMatch(code, /rounded-full animate-spin/, `${name} must not draw its own spinner`)
    assert.doesNotMatch(code, /Cargando [\wáéíóúñ ]+…/, `${name} must not show loading text`)
  })
}

for (const name of HEADER_PAGES) {
  test(`${name} renders the shared PageHeader and keeps exactly one h1`, () => {
    const code = sources[name]
    assert.match(code, /import \{ PageHeader \} from '@\/components\/shared\/PageHeader'/)
    assert.match(code, /<PageHeader\b/)
    // The student layout has no app header, so each page's PageHeader renders the single h1.
    assert.equal((code.match(/<PageHeader as="h1"/g) ?? []).length, 1, `${name} must render exactly one PageHeader as h1`)
    assert.equal((code.match(/<h1\b/g) ?? []).length, 0, `${name} must not add another h1`)
  })
}

test('Inicio keeps its welcome card as the page header with the single h1', () => {
  const code = sources.StudentHomePage
  assert.equal((code.match(/<h1\b/g) ?? []).length, 1)
  // The welcome is the R5 glass card on an Aurora strip (it replaced the bg-brand-soft wash).
  assert.match(code, /<GlassStage\b/)
  assert.match(code, /<GlassCard\b/)
  assert.match(code, /Hola/)
})

test('error states use Alert', () => {
  for (const name of HEADER_PAGES) {
    assert.match(sources[name], /import \{[^}]*\bAlert\b[^}]*\} from '@\/components\/ui\/alert'/, `${name} imports Alert`)
    assert.match(sources[name], /<Alert\b/, `${name} renders Alert`)
  }
})

test('empty results use the shared EmptyState with an icon', () => {
  for (const name of ['StudentHistoryPage', 'StudentSchedulePage', 'StudentIntensivePage']) {
    assert.match(sources[name], /import \{ EmptyState \} from '@\/components\/shared\/EmptyState'/, `${name} imports EmptyState`)
    assert.match(sources[name], /<EmptyState\b[^>]*icon=\{/, `${name} renders EmptyState with an icon`)
  }
})

test('the pages keep their titles and key texts', () => {
  for (const [name, texts] of Object.entries({
    StudentHistoryPage: ['Historial académico'],
    StudentReenrollmentPage: ['Rematrícula', 'No se pudo cargar la rematrícula.'],
    StudentSchedulePage: ['Mi horario', 'No se pudo cargar tu horario.'],
    StudentIntensivePage: ['Cursos de verano e invierno', 'Mis inscripciones', 'Cursos disponibles para vos'],
  })) {
    for (const text of texts) assert.ok(sources[name].includes(text), `${name} keeps "${text}"`)
  }
})
