import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

// T10.4: the docente portal pages follow the S11 page rules (theme tokens only, shared PageHeader,
// StatusBadge, Skeleton, EmptyState and Alert states, tabular-nums money).

const root = resolve(import.meta.dirname, '..')

const PAGES = [
  'BillingPage',
  'BillingHistoryPage',
  'SchedulePage',
  'RetentionLetterPage',
  'MyRequestsPage',
  'NotificationsPage',
  'MyProfilePage',
]

const sources = Object.fromEntries(
  PAGES.map((name) => [name, readFileSync(resolve(root, `src/pages/${name}.tsx`), 'utf8')]),
)

// Hex colors that the image export genuinely needs. Each entry must be a named top-level constant
// with a comment line right above it explaining why a literal is required.
const ALLOWED_HEX = [{ page: 'SchedulePage', constant: 'EXPORT_BACKGROUND', value: '#ffffff' }]

const HEX = /#[0-9a-fA-F]{3,8}\b/g
const PALETTE_CLASS =
  /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline|decoration|shadow|accent)-(?:gray|grey|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g
const WHITE_BLACK_CLASS = /\b(?:bg|text|border)-(?:white|black)\b/g

function withoutAllowedHex(name) {
  const lines = sources[name].split('\n')
  return lines
    .map((line, index) => {
      const allowed = ALLOWED_HEX.find(
        (entry) => entry.page === name && new RegExp(`^const ${entry.constant} = '${entry.value}'`).test(line),
      )
      if (!allowed) return line
      const above = (lines[index - 1] ?? '').trim()
      assert.match(above, /^(\/\/|\/\*|\*)/, `${name}: ${allowed.constant} needs a comment line explaining why it is a literal`)
      return line.replace(allowed.value, '')
    })
    .join('\n')
}

for (const name of PAGES) {
  test(`${name} uses theme tokens only: no hex, gradients, card-3d or color styles`, () => {
    const code = withoutAllowedHex(name)
    assert.deepEqual(code.match(HEX) ?? [], [], `${name} must not contain hex colors`)
    assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${name} must not use gradient-* classes`)
    assert.deepEqual(code.match(/(?:linear|radial)-gradient/g) ?? [], [], `${name} must not use CSS gradients`)
    assert.deepEqual(code.match(/\brgba?\(/g) ?? [], [], `${name} must not use rgb()/rgba() colors`)
    assert.doesNotMatch(code, /\bcard-3d/, `${name} must not use card-3d`)
    for (const [, style] of code.matchAll(/style=\{\{([\s\S]*?)\}\}/g)) {
      assert.doesNotMatch(style, /color|background|gradient|shadow|border|fill|stroke/i, `${name} must not set colors through style`)
    }
  })

  test(`${name} uses no raw Tailwind palette classes`, () => {
    const code = withoutAllowedHex(name)
    assert.deepEqual(code.match(PALETTE_CLASS) ?? [], [], `${name} must use token colors, not palette classes`)
    assert.deepEqual(code.match(WHITE_BLACK_CLASS) ?? [], [], `${name} must use token colors, not white/black`)
  })

  test(`${name} renders the shared PageHeader`, () => {
    const code = sources[name]
    assert.match(code, /import \{ PageHeader \} from '@\/components\/shared\/PageHeader'/)
    assert.match(code, /<PageHeader\b/)
  })

  test(`${name} shows a Skeleton, not a hand-made spinner, while loading`, () => {
    const code = sources[name]
    assert.match(code, /import \{ Skeleton \} from '@\/components\/ui\/skeleton'/)
    assert.match(code, /<Skeleton\b/)
    assert.doesNotMatch(code, /rounded-full animate-spin/, `${name} must not draw its own spinner`)
  })
}

test('only the allowlisted export constants carry hex colors', () => {
  const found = []
  for (const name of PAGES) {
    for (const line of sources[name].split('\n')) {
      if (HEX.test(line)) found.push(`${name}: ${line.trim()}`)
      HEX.lastIndex = 0
    }
  }
  assert.deepEqual(
    found,
    ALLOWED_HEX.map((entry) => `${entry.page}: const ${entry.constant} = '${entry.value}'`),
  )
})

test('SchedulePage image export uses the named background constant, not a literal', () => {
  const code = sources.SchedulePage
  assert.match(code, /backgroundColor: EXPORT_BACKGROUND/)
  assert.match(code, /toPng\(/)
})

test('money is tabular-nums on the billing pages', () => {
  assert.match(sources.BillingPage, /tabular-nums/)
  assert.match(sources.BillingHistoryPage, /tabular-nums/)
  for (const name of ['BillingPage', 'BillingHistoryPage']) {
    // Every amount element (dd/strong/td/p) that renders formatBs carries tabular-nums on itself or on its row.
    const cells = [...sources[name].matchAll(/<(?:dd|strong|td|p|span)\b[^>]*>[^<]*\{[^}]*formatBs\(/g)].map((m) => m[0])
    assert.ok(cells.length > 0, `${name} must render amounts`)
    for (const cell of cells) assert.match(cell, /tabular-nums/, `${name}: amount without tabular-nums -> ${cell.slice(0, 100)}`)
  }
})

test('billing pages keep the hero amount and the mobile cards visible on narrow screens', () => {
  assert.match(sources.BillingPage, /data-testid="designation-mobile-list"[^>]*sm:hidden/)
  assert.match(sources.BillingPage, /data-testid="billing-mobile-totals"/)
  assert.match(sources.BillingHistoryPage, /data-testid="history-mobile-list"[^>]*sm:hidden/)
  assert.match(sources.BillingHistoryPage, /break-words/, 'hero amount must wrap instead of overflowing')
})

test('request and notification states use the shared StatusBadge', () => {
  for (const name of ['MyRequestsPage', 'NotificationsPage']) {
    assert.match(sources[name], /import \{ StatusBadge \} from '@\/components\/shared\/StatusBadge'/, `${name} imports StatusBadge`)
    assert.match(sources[name], /<StatusBadge\b/, `${name} renders StatusBadge`)
  }
  assert.doesNotMatch(sources.MyRequestsPage, /function StatusBadge\(/, 'MyRequestsPage must not keep its own StatusBadge')
})

test('error states use Alert, with a retry where a refetch exists', () => {
  for (const name of ['BillingPage', 'BillingHistoryPage', 'SchedulePage', 'MyRequestsPage', 'NotificationsPage']) {
    assert.match(sources[name], /import \{[^}]*\bAlert\b[^}]*\} from '@\/components\/ui\/alert'/, `${name} imports Alert`)
    assert.match(sources[name], /<Alert\b/, `${name} renders Alert`)
  }
  assert.match(sources.MyRequestsPage, /Reintentar/)
  assert.match(sources.NotificationsPage, /Reintentar/)
})

test('empty results use the shared EmptyState', () => {
  for (const name of ['BillingHistoryPage', 'SchedulePage', 'MyRequestsPage', 'NotificationsPage']) {
    assert.match(sources[name], /import \{ EmptyState \} from '@\/components\/shared\/EmptyState'/, `${name} imports EmptyState`)
    assert.match(sources[name], /<EmptyState\b/, `${name} renders EmptyState`)
  }
})

test('profile and retention forms keep their accessible field names', () => {
  for (const label of ['Contraseña actual *', 'Nueva contraseña *', 'Confirmar nueva contraseña *', 'Email', 'Teléfono', 'Banco', 'Número de Cuenta']) {
    assert.ok(sources.MyProfilePage.includes(label), `MyProfilePage keeps label "${label}"`)
  }
  for (const label of ['Título profesional *', 'Matrícula profesional *', 'Mes de cobro *', 'Año de cobro *', 'Período académico *']) {
    assert.ok(sources.RetentionLetterPage.includes(label), `RetentionLetterPage keeps label "${label}"`)
  }
})

test('schedule keeps its three views, the turn filter and both export buttons', () => {
  const code = sources.SchedulePage
  for (const text of ['Por Día', 'Por Materia', 'Grilla Semanal', 'Exportar Imagen', 'Exportar PDF', 'Filtrar horario por turno', 'Mi Horario Semanal']) {
    assert.ok(code.includes(text), `SchedulePage keeps "${text}"`)
  }
  assert.match(code, /Horario semanal agrupado por día y hora de inicio/)
  assert.match(code, /id="schedule-content"/)
})

test('retention letter keeps the printable letter layout', () => {
  const code = sources.RetentionLetterPage
  assert.match(code, /font-serif/)
  assert.match(code, /max-w-\[680px\]/)
  assert.match(code, /Vista previa de la carta/)
  assert.match(code, /Generar y Descargar PDF/)
})
