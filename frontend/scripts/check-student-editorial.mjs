import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  clampPercent,
  formatFigure,
  meterPercent,
  meterSegments,
  ringCircumference,
  ringDashOffset,
  stepperStates,
} from '../src/components/student/student-editorial.ts'

// S2, S3: the editorial foundation of the student portal upgrade (artboard 03): Geist scoped to the student portal,
// the type scale, sheet depth tiers, glass sheets and the accessible primitives built on them.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const css = read('src/index.css')
const cssNoComments = css.replace(/\/\*[\s\S]*?\*\//g, '')
const main = read('src/main.tsx')
const layout = read('src/pages/student/StudentPortalLayout.tsx')
const index = read('src/components/student/index.ts')
const pkg = JSON.parse(read('package.json'))

const PRIMITIVES = [
  'InfoTip',
  'Eyebrow',
  'SectionHeader',
  'Sheet',
  'DisplayFigure',
  'ProgressRing',
  'Meter',
  'Stepper',
  'Timeline',
]
const sources = Object.fromEntries(PRIMITIVES.map((name) => [name, read(`src/components/student/${name}.tsx`)]))

/** Body of every rule whose selector list contains `selector` (exact entry before `{`). */
function rules(selector) {
  const bodies = []
  const pattern = /([^{}]+)\{([^{}]*)\}/g
  for (const match of cssNoComments.matchAll(pattern)) {
    const selectors = match[1].split(',').map((entry) => entry.trim())
    if (selectors.includes(selector)) bodies.push(match[2])
  }
  return bodies.join('\n')
}

/** Body of every `@media (prefers-reduced-motion: reduce)` block (balanced braces). */
function reducedMotionCss() {
  let out = ''
  let from = 0
  for (;;) {
    const start = css.indexOf('@media (prefers-reduced-motion: reduce)', from)
    if (start === -1) return out
    const open = css.indexOf('{', start)
    let depth = 0
    let i = open
    for (; i < css.length; i++) {
      if (css[i] === '{') depth++
      if (css[i] === '}' && --depth === 0) break
    }
    out += css.slice(open + 1, i)
    from = i
  }
}

test('S2: figures use es-BO grouping (1.200) and decimal comma, with fixed decimals when asked', () => {
  assert.equal(formatFigure(1200), '1.200')
  assert.equal(formatFigure(12345.6, 1), '12.345,6')
  assert.equal(formatFigure(1200.5, 2), '1.200,50')
  assert.equal(formatFigure(0), '0')
  assert.equal(formatFigure(Number.NaN), '0')
  assert.equal(formatFigure(-5), '-5')
})

test('S2: ring maths draws value% of the circumference and clamps outside 0-100', () => {
  assert.equal(clampPercent(140), 100)
  assert.equal(clampPercent(-3), 0)
  assert.equal(clampPercent(Number.NaN), 0)
  const length = ringCircumference(120, 9)
  assert.equal(length, Number((2 * Math.PI * 55.5).toFixed(3)))
  assert.equal(ringDashOffset(100, length), 0)
  assert.equal(ringDashOffset(0, length), length)
  assert.equal(ringDashOffset(25, length), Number((length * 0.75).toFixed(3)))
  assert.equal(ringDashOffset(250, length), 0)
})

test('S2: meters expose a clamped percentage and the filled segments of a seats bar', () => {
  assert.equal(meterPercent(30, 40), 75)
  assert.equal(meterPercent(50, 40), 100)
  assert.equal(meterPercent(5, 0), 0)
  assert.equal(meterPercent(-2, 40), 0)
  assert.deepEqual(meterSegments(30, 40), { filled: 30, total: 40 })
  assert.deepEqual(meterSegments(10, 40, 20), { filled: 5, total: 20 })
  assert.deepEqual(meterSegments(1, 40, 10), { filled: 1, total: 10 }, 'a non-empty meter shows at least one segment')
  assert.deepEqual(meterSegments(0, 40, 10), { filled: 0, total: 10 })
  assert.deepEqual(meterSegments(99, 40, 10), { filled: 10, total: 10 })
  assert.deepEqual(meterSegments(3, 0), { filled: 0, total: 0 })
})

test('S2: stepper states: before the current step is done, after it is pending, past the end is all done', () => {
  assert.deepEqual(stepperStates(4, 1), ['done', 'current', 'pending', 'pending'])
  assert.deepEqual(stepperStates(3, 0), ['current', 'pending', 'pending'])
  assert.deepEqual(stepperStates(3, 3), ['done', 'done', 'done'])
  assert.deepEqual(stepperStates(3, -1), ['pending', 'pending', 'pending'])
  assert.deepEqual(stepperStates(0, 0), [])
})

test('S2: Geist is bundled once, only for the student scope, and exposed as font-student', () => {
  const imports = main.match(/@fontsource-variable\/geist/g) ?? []
  assert.equal(imports.length, 1, 'main.tsx imports the variable Geist font exactly once')
  assert.match(main, /import ['"]@fontsource-variable\/geist\/index\.css['"]/)
  assert.ok(!/@fontsource/.test(css), 'index.css does not import the font a second time')
  assert.match(css, /--font-student:\s*[^;]*Geist Variable/, 'the student font stack starts with Geist Variable')
  assert.match(rules('.student-scope'), /font-family:\s*var\(--font-student\)/, '.student-scope uses the student font')
  assert.match(layout, /className="student-scope[^"]*\bfont-student\b/, 'the student layout root applies font-student')
  assert.doesNotMatch(rules('body'), /Geist/, 'the global body font is untouched')
  assert.doesNotMatch(css.slice(0, css.indexOf('--font-student')), /--font-sans:[^;]*Geist/)
})

test('S2: editorial type scale: display 900 clamp 40-56px, titles 700-800, eyebrow caps, tabular figures', () => {
  const display = rules('.sp-display')
  assert.match(display, /font-weight:\s*900/)
  assert.match(display, /clamp\(2\.5rem,[^)]*,\s*3\.5rem\)/, 'display runs from 40px to 56px')
  assert.match(display, /letter-spacing:\s*-0\.0[3-6]\d*em/, 'display tracking is tight')
  assert.match(rules('.sp-title'), /font-weight:\s*800/)
  assert.match(rules('.sp-title-2'), /font-weight:\s*700/)
  const eyebrow = rules('.sp-eyebrow')
  assert.match(eyebrow, /text-transform:\s*uppercase/)
  assert.match(eyebrow, /letter-spacing:\s*0\.1\d*em/)
  assert.match(eyebrow, /font-weight:\s*[78]00/)
  assert.match(rules('.sp-figure'), /font-variant-numeric:\s*tabular-nums/)
  assert.match(rules('.sp-figure'), /font-weight:\s*900/)
  assert.match(rules('.sp-rule'), /background:\s*var\(--sp-violet\)/, 'the violet rule uses the accent')
})

test('S2: sheets have three depth tiers backed by shadow tokens in both themes', () => {
  for (const tier of [1, 2, 3]) {
    assert.match(rules(`.sp-sheet-${tier}`), new RegExp(`box-shadow:\\s*var\\(--sp-sh${tier}\\)`), `sheet-${tier} uses --sp-sh${tier}`)
  }
  const light = rules(':root')
  const dark = rules('.dark')
  for (const token of ['--sp-sh1', '--sp-sh2', '--sp-sh3', '--sp-glass', '--sp-glass-solid', '--sp-tip-bg', '--sp-track']) {
    assert.ok(light.includes(`${token}:`), `${token} defined for light`)
    assert.ok(dark.includes(`${token}:`), `${token} defined for dark`)
  }
})

test('S2: glass sheets are dense enough for AA text, blur only where supported, solid when asked for less transparency', () => {
  const glass = rules('.sp-glass-sheet')
  assert.match(glass, /backdrop-filter:\s*blur\(/)
  assert.match(glass, /background:\s*var\(--sp-glass\)/)
  assert.match(css, /@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)/)
  assert.match(css, /@media \(prefers-reduced-transparency: reduce\)/)
  const alpha = /--sp-glass:\s*rgba\([^)]*,\s*(0?\.\d+)\)/g
  const alphas = [...css.matchAll(alpha)].map((match) => Number(match[1]))
  assert.ok(alphas.length >= 2 && alphas.every((value) => value >= 0.7), 'glass scrims are at least 70% opaque')
  const tip = rules('.sp-tip')
  assert.match(tip, /background:\s*var\(--sp-tip-bg\)/)
  assert.match(tip, /color:\s*var\(--sp-tip-fg\)/)
})

test('S3: reduced motion keeps the final state of the editorial animations', () => {
  const reduced = reducedMotionCss()
  assert.match(reduced, /\.sp-meter-fill/)
  assert.match(reduced, /\.sp-seg/)
  assert.match(reduced, /\.sp-tl-body/)
  assert.match(reduced, /animation:\s*none/)
  assert.match(reduced, /transition(-duration)?:\s*(none|0)/)
})

test('S2: primitives are exported from the student index and are typed function components', () => {
  for (const name of [
    'InfoTip',
    'Eyebrow',
    'SectionHeader',
    'Sheet',
    'DisplayFigure',
    'ProgressRing',
    'Meter',
    'Stepper',
    'Timeline',
    'TimelineItem',
  ]) {
    assert.match(index, new RegExp(`\\b${name}\\b`), `${name} is exported from components/student/index.ts`)
  }
  for (const [name, source] of Object.entries(sources)) {
    assert.match(source, new RegExp(`export function ${name}\\b`), `${name} is a named function component`)
    assert.ok(!/\bany\b/.test(source.replace(/\/\*[\s\S]*?\*\//g, '')), `${name} avoids any`)
  }
})

test('S2: InfoTip wraps ui/tooltip with a 44px trigger, opens on hover/focus/tap, closes with Escape and is described', () => {
  const tip = sources.InfoTip
  assert.match(tip, /from '@\/components\/ui\/tooltip'/)
  assert.match(tip, /\bTooltipTrigger\b/)
  assert.match(tip, /\bTooltipPopup\b/)
  assert.match(tip, /onOpenChange/, 'hover, focus and Escape reach the controlled open state')
  assert.match(tip, /pointerType(?:\.current)?\s*===\s*'touch'/, 'a tap on touch screens toggles the tip')
  assert.match(tip, /onClick/)
  assert.match(tip, /aria-describedby/)
  assert.match(tip, /role="tooltip"/)
  assert.match(tip, /sp-infotip-trigger/)
  assert.match(tip, /sp-tip/)
  assert.match(rules('.sp-infotip-trigger'), /min-(?:width|height):\s*2\.75rem/, 'the trigger is at least 44px')
})

test('S2: Stepper marks the current step, Meter and Ring expose their value, Timeline collapses with aria-expanded', () => {
  assert.match(sources.Stepper, /aria-current=\{[^}]*'step'/)
  assert.match(sources.Meter, /role="meter"/)
  assert.match(sources.Meter, /aria-valuenow/)
  assert.match(sources.ProgressRing, /role="img"|role="meter"|role="progressbar"/)
  assert.match(sources.ProgressRing, /useReducedMotion/)
  assert.match(sources.DisplayFigure, /useReducedMotion/)
  assert.match(sources.DisplayFigure, /es-BO|formatFigure/)
  assert.match(sources.Timeline, /aria-expanded/)
  assert.match(sources.Timeline, /aria-controls/)
  assert.match(sources.Timeline, /<button\b/)
})

test('S3: the new student TSX carries no hex colors, gradients or palette classes', () => {
  for (const [name, source] of Object.entries(sources)) {
    assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b/, `${name} has no hex colors`)
    assert.doesNotMatch(source, /linear-gradient|radial-gradient|conic-gradient|gradient-/, `${name} has no gradients`)
    assert.doesNotMatch(source, /\brgba?\(/, `${name} has no rgb()`)
    assert.doesNotMatch(
      source,
      /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline|decoration|shadow|accent)-(?:gray|slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/,
      `${name} has no palette classes`,
    )
    assert.doesNotMatch(source, /\b(?:bg|text|border)-(?:white|black)\b/, `${name} has no white/black classes`)
  }
})

test('S2: the package exposes test:student-editorial and the editorial styles stay scoped to sp- classes', () => {
  assert.match(pkg.scripts['test:student-editorial'] ?? '', /check-student-editorial\.mjs/)
  assert.ok(existsSync(resolve(root, 'src/components/student/student-editorial.ts')))
  const selectors = [...css.matchAll(/(^|\n)\s*(\.sp-[a-z0-9-]+)/g)].map((match) => match[2])
  assert.ok(selectors.includes('.sp-display') && selectors.includes('.sp-sheet-3'))
})
