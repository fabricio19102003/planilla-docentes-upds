import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const PAGES = {
  PlanillaPage: read('src/pages/PlanillaPage.tsx'),
  PracticaPlanillaContent: read('src/pages/PracticaPlanillaContent.tsx'),
  ReportsPage: read('src/pages/ReportsPage.tsx'),
}
const PLANILLA_PAGES = ['PlanillaPage', 'PracticaPlanillaContent']

const PALETTE = 'gray|slate|zinc|neutral|stone|red|green|blue|yellow|amber|orange|purple|emerald|sky|indigo|violet|teal|cyan|lime|rose|pink|fuchsia'

/** Body of `const name = (...) => { ... }` found by brace matching from its first `{`. */
function functionBody(source, name) {
  const start = source.indexOf(`const ${name} = `)
  assert.notEqual(start, -1, `${name} must exist`)
  const open = source.indexOf('{', source.indexOf('=>', start))
  let depth = 0
  for (let i = open; i < source.length; i++) {
    if (source[i] === '{') depth++
    else if (source[i] === '}' && --depth === 0) return source.slice(open, i + 1)
  }
  throw new Error(`unbalanced braces in ${name}`)
}

for (const [name, source] of Object.entries(PAGES)) {
  test(`${name} holds no hex colors`, () => {
    assert.deepEqual(source.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [])
  })

  test(`${name} holds no color style props or style mutations`, () => {
    assert.deepEqual(
      source.match(/style=\{\{[^}]*\b(?:color|background|backgroundColor|backgroundImage|borderColor|borderLeftColor)\b[^}]*\}\}/g) ?? [],
      [],
    )
    assert.deepEqual(source.match(/\.style\.[a-zA-Z]+\s*=/g) ?? [], [])
  })

  test(`${name} holds no gradient or card-3d chrome`, () => {
    assert.deepEqual(source.match(/gradient-[\w-]+|card-3d[\w-]*|linear-gradient/g) ?? [], [])
  })

  test(`${name} uses theme tokens instead of palette utilities`, () => {
    const palette = new RegExp(`\\b(?:bg|text|border|ring|from|to|via|divide|fill|stroke|accent|placeholder)-(?:${PALETTE})-\\d{2,3}(?:/\\d+)?\\b`, 'g')
    assert.deepEqual(source.match(palette) ?? [], [])
  })
}

for (const [name, source] of Object.entries(PAGES)) {
  test(`${name} opens with the shared PageHeader`, () => {
    if (name === 'PracticaPlanillaContent') {
      // Embedded in PlanillaPage's tab: the header belongs to the host page.
      assert.doesNotMatch(source, /<PageHeader/)
      return
    }
    assert.match(source, /@\/components\/shared\/PageHeader/)
    assert.match(source, /<PageHeader/)
  })
}

for (const name of PLANILLA_PAGES) {
  const source = PAGES[name]

  test(`${name} keeps every payroll action behind requestConfirm and ConfirmActionDialog`, () => {
    assert.match(source, /<ConfirmActionDialog/)
    assert.match(source, /onConfirm=\{runConfirmedAction\}/)
    assert.match(source, /onCancel=\{\(\) => setPendingConfirm\(null\)\}/)
    for (const action of ['generate', 'approve', 'reject', 'publish', 'unpublish']) {
      assert.match(source, new RegExp(`onClick=\\{\\(\\) => requestConfirm\\('${action}'\\)\\}`), `${action} button must request a confirmation`)
    }
  })

  test(`${name} runs approve, reject, publish and unpublish only from the confirmed action`, () => {
    const confirmed = functionBody(source, 'runConfirmedAction')
    for (const handler of ['approvePlanilla', 'rejectPlanilla', 'publishBilling', 'unpublishBilling']) {
      const calls = source.match(new RegExp(`(?<![A-Za-z])${handler}\\.mutate\\(`, 'g')) ?? []
      assert.equal(calls.length, 1, `${handler}.mutate must be called exactly once`)
      assert.ok(confirmed.includes(`${handler}.mutate(`), `${handler}.mutate must live in runConfirmedAction`)
    }
    assert.equal((source.match(/runGenerate\(\)/g) ?? []).length, 1)
    assert.ok(confirmed.includes('runGenerate()'))
    assert.equal((source.match(/generatePlanilla\.mutate\(/g) ?? []).length, 1)
    assert.doesNotMatch(source, /(?:onClick|onChange|onSubmit)=\{[^}]*(?<![A-Za-z])(?:approvePlanilla|rejectPlanilla|publishBilling|unpublishBilling|generatePlanilla)\.mutate/)
  })

  test(`${name} overwrites an approved planilla only through a destructive generate confirmation`, () => {
    assert.match(source, /pendingConfirm === 'generate' && planillaStatus\?\.status === 'approved'/)
    assert.match(source, /tone: 'destructive'/)
  })

  test(`${name} renders status as StatusBadge and tables inside TableCard`, () => {
    assert.match(source, /@\/components\/shared\/StatusBadge/)
    assert.match(source, /<StatusBadge/)
    assert.match(source, /@\/components\/shared\/TableCard/)
    assert.match(source, /<TableCard/)
    assert.doesNotMatch(source, /<table\b/)
  })

  test(`${name} shows summary figures as StatCard with tabular money`, () => {
    assert.match(source, /<StatCard/)
    assert.match(source, /tabular-nums/)
  })

  test(`${name} shows loading, empty and error states with the shared primitives`, () => {
    assert.match(source, /<Skeleton/)
    assert.match(source, /<EmptyState/)
    assert.match(source, /<Alert variant="error"/)
    assert.match(source, /Reintentar/)
    assert.match(source, /detailQuery\.refetch\(\)/)
    assert.doesNotMatch(source, /<LoadingPage/)
  })

  test(`${name} keeps the cut-off guard, mode radiogroup and labels`, () => {
    assert.match(source, /getGenerationGuard\(/)
    assert.match(source, /role="radiogroup"/)
    assert.match(source, /DISCOUNT_MODE_LABELS\[option\]/)
    assert.match(source, /formatGenerationSummary\(/)
    assert.doesNotMatch(source, /startDate \|\| undefined/)
  })
}

test('PlanillaPage keeps the Teóricas/Prácticas tab switch on the tab query param', () => {
  const source = PAGES.PlanillaPage
  assert.match(source, /searchParams\.get\('tab'\) === 'practicas'/)
  assert.match(source, /params\.set\('tab', next\)/)
  assert.match(source, />\s*Teóricas\s*</)
  assert.match(source, />\s*Prácticas\s*</)
})

test('PlanillaPage keeps the publication, approval and billing delivery controls', () => {
  const source = PAGES.PlanillaPage
  for (const label of ['Aprobar', 'Rechazar', 'Despublicar', 'Publicar para Docentes', 'Enviar correo', 'Generar vista previa WhatsApp', 'Confirmar envío']) {
    assert.ok(source.includes(label), `${label} must stay`)
  }
  assert.match(source, /confirmBillingNotifications\.mutate\(/)
  assert.match(source, /previewBillingNotifications\.mutate\(/)
})

test('ReportsPage restyles with shared components and keeps the preview contract', () => {
  const source = PAGES.ReportsPage
  assert.match(source, /<StatCard/)
  assert.match(source, /<StatusBadge/)
  assert.match(source, /<TableCard/)
  assert.match(source, /<Skeleton/)
  assert.match(source, /<EmptyState/)
  assert.match(source, /<Alert variant="error"/)
  assert.match(source, /tabular-nums/)
  assert.doesNotMatch(source, /<table\b/)
  assert.doesNotMatch(source, /<Loader2 size=\{2[48]\} className="animate-spin text-/)
})

test('ReportsPage retries a failed preview and keeps its generate and download actions', () => {
  const source = PAGES.ReportsPage
  assert.match(source, /Reintentar/)
  assert.match(source, /refetchPreview\(\)/)
  for (const label of ['Vista Previa', 'Generar PDF', 'Descargar PDF']) {
    assert.ok(source.includes(label), `${label} must stay`)
  }
  assert.match(source, /generateReport\.mutate\(filters/)
})
