import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  GLASS_SPRING,
  WALLPAPERS,
  glassVars,
  isActivePath,
  nextRovingIndex,
  notchPosition,
  pickActiveIndex,
  tiltAngles,
} from '../src/components/student/student-helpers.ts'

// S2-S7: the student portal redesign components (R1-R6) keep the reference look, expose the chosen
// settings as props with those defaults, work on phones, in both themes, with keyboard and reduced motion.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const css = read('src/index.css')
const COMPONENTS = ['NotchTabBar', 'PrintReceipt', 'ThermalLoader', 'ClinicNotFound', 'GlassStage', 'GlassCard', 'GlassSwitch']
const sources = Object.fromEntries(COMPONENTS.map((name) => [name, read(`src/components/student/${name}.tsx`)]))

/** Rule bodies for a selector (exact selector text before `{`). */
function rules(selector) {
  const bodies = []
  const pattern = new RegExp(`(?:^|[}\\s])${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`, 'g')
  for (const match of css.matchAll(pattern)) bodies.push(match[1])
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

test('notchPosition centres the bubble on tab 1..N instead of hardcoded 10/30/50/70/90', () => {
  assert.deepEqual([1, 2, 3, 4, 5].map((p) => notchPosition(p, 5)), [10, 30, 50, 70, 90])
  assert.equal(notchPosition(2, 3), 50)
  assert.equal(notchPosition(1, 4), 12.5)
  assert.equal(notchPosition(9, 5), 90, 'position beyond N is clamped to the last tab')
  assert.equal(notchPosition(0, 5), 10, 'position below 1 is clamped to the first tab')
})

test('nextRovingIndex wraps with the arrows and jumps with Home/End; other keys do nothing', () => {
  assert.equal(nextRovingIndex(0, 'ArrowRight', 5), 1)
  assert.equal(nextRovingIndex(4, 'ArrowRight', 5), 0)
  assert.equal(nextRovingIndex(0, 'ArrowLeft', 5), 4)
  assert.equal(nextRovingIndex(3, 'ArrowLeft', 5), 2)
  assert.equal(nextRovingIndex(2, 'Home', 5), 0)
  assert.equal(nextRovingIndex(2, 'End', 5), 4)
  assert.equal(nextRovingIndex(2, 'Enter', 5), null)
  assert.equal(nextRovingIndex(2, 'a', 5), null)
  assert.equal(nextRovingIndex(0, 'ArrowRight', 0), null, 'no items, no move')
})

test('isActivePath matches the exact path, or sub-paths when the item is not `end`', () => {
  assert.equal(isActivePath('/estudiante', '/estudiante', true), true)
  assert.equal(isActivePath('/estudiante', '/estudiante/', true), true)
  assert.equal(isActivePath('/estudiante', '/estudiante/horario', true), false)
  assert.equal(isActivePath('/estudiante/horario', '/estudiante/horario/semana', false), true)
  assert.equal(isActivePath('/estudiante/horario', '/estudiante/horarios', false), false)
})

test('pickActiveIndex returns the most specific matching item, or -1 when none matches', () => {
  const items = [
    { to: '/estudiante', end: true },
    { to: '/estudiante/horario' },
    { to: '/estudiante/rematricula' },
    { to: '/estudiante/historial' },
    { to: '/estudiante/intensivos' },
  ]
  assert.equal(pickActiveIndex(items, '/estudiante'), 0)
  assert.equal(pickActiveIndex(items, '/estudiante/horario'), 1)
  assert.equal(pickActiveIndex(items, '/estudiante/rematricula/'), 2)
  assert.equal(pickActiveIndex(items, '/estudiante/intensivos/3'), 4)
  assert.equal(pickActiveIndex(items, '/estudiante/cambiar-clave'), -1)
  assert.equal(pickActiveIndex([{ to: '/estudiante' }, { to: '/estudiante/horario' }], '/estudiante/horario'), 1)
})

test('glassVars maps blur / opacity / shine to the --lg-* custom properties (Aurora defaults 20 / 12 / 25)', () => {
  assert.deepEqual(glassVars('aurora', 20, 12, 25), { '--lg-blur': '20px', '--lg-a': 0.12, '--lg-shine': 0.25 })
  assert.deepEqual(glassVars('ocean', 4, 40, 60), { '--lg-blur': '4px', '--lg-a': 0.4, '--lg-shine': 0.6 })
})

test('glassVars lifts the glass opacity on the light wallpaper (capped at 0.6) and clamps to the reference ranges', () => {
  assert.equal(glassVars('light', 20, 12, 25)['--lg-a'], 0.35)
  assert.equal(glassVars('light', 20, 40, 25)['--lg-a'], 0.6)
  assert.deepEqual(glassVars('sunset', 100, 99, 99), { '--lg-blur': '40px', '--lg-a': 0.4, '--lg-shine': 0.6 })
  assert.deepEqual(glassVars('sunset', 0, 0, -5), { '--lg-blur': '4px', '--lg-a': 0.04, '--lg-shine': 0 })
})

test('tiltAngles is +-8deg and flat at the centre', () => {
  assert.deepEqual(tiltAngles(0.5, 0.5), { rotateX: 0, rotateY: 0 })
  assert.deepEqual(tiltAngles(0, 0), { rotateX: 8, rotateY: -8 })
  assert.deepEqual(tiltAngles(1, 1), { rotateX: -8, rotateY: 8 })
  assert.deepEqual(tiltAngles(-3, 9), { rotateX: -8, rotateY: -8 }, 'pointer outside the card is clamped')
})

test('the wallpapers are Aurora (default), Sunset, Ocean and Light, each styled in index.css', () => {
  assert.deepEqual(WALLPAPERS, ['aurora', 'sunset', 'ocean', 'light'])
  for (const wall of WALLPAPERS) assert.match(css, new RegExp(`data-wallpaper='?"?${wall}`), `${wall} wallpaper has CSS`)
  assert.match(sources.GlassStage, /wallpaper = 'aurora'/)
  assert.match(sources.GlassStage, /blur = 20/)
  assert.match(sources.GlassStage, /opacity = 12/)
  assert.match(sources.GlassStage, /shine = 25/)
})

for (const name of COMPONENTS) {
  test(`${name} keeps colors in index.css: no hex, gradients, rgb() or color styles in the TSX`, () => {
    const code = sources[name].replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
    assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${name} must not contain hex colors`)
    assert.deepEqual(code.match(/(?:linear|radial|conic)-gradient/g) ?? [], [], `${name} must not use CSS gradients`)
    assert.deepEqual(code.match(/\brgba?\(/g) ?? [], [], `${name} must not use rgb()/rgba() colors`)
    assert.doesNotMatch(code, /\b(?:bg|text|border|ring|fill|stroke)-(?:white|black|(?:gray|slate|zinc|neutral|red|green|violet|purple|blue)-\d{2,3})\b/)
    assert.doesNotMatch(code, /framer-motion/, `${name} animates with motion/react`)
    for (const [, style] of code.matchAll(/style=\{\{([\s\S]*?)\}\}/g)) {
      assert.doesNotMatch(style, /color|background|gradient|shadow|border|fill|stroke/i, `${name} must not set colors through style`)
    }
  })
}

test('the student accent tokens exist for light and dark and are exposed as Tailwind colors', () => {
  for (const token of ['--student-accent', '--student-accent-foreground', '--student-accent-soft', '--student-accent-text']) {
    assert.ok(rules(':root').includes(`${token}:`), `:root defines ${token}`)
  }
  assert.match(rules(':root'), /--student-accent:\s*#7c3aed/i)
  assert.match(rules('.dark'), /--student-accent-text:\s*#a78bfa/i, 'dark mode lifts the accent text for contrast')
  assert.match(rules('.dark'), /--student-notch-surface:\s*var\(--card\)/, 'dark notch bar uses the card token, not white')
  assert.match(css, /--color-student-accent:\s*var\(--student-accent\)/)
})

test('R1 notch bar: reference geometry, easing and mask, driven by --sp-notch-x', () => {
  assert.match(css, /@property --sp-notch-x/)
  const bar = rules('.sp-notch-bar')
  assert.match(bar, /border-radius:\s*1\.4em/)
  assert.match(bar, /radial-gradient\(circle 2\.15em at var\(--sp-notch-x\) -\.25em,\s*transparent 98%,\s*#000\)/)
  assert.match(bar, /cubic-bezier\(\.22,\s*1,\s*\.36,\s*1\)/)
  const bubble = rules('.sp-notch-bubble')
  assert.match(bubble, /top:\s*-1\.6em/)
  assert.match(bubble, /width:\s*3em/)
  assert.match(bubble, /left:\s*var\(--sp-notch-x\)/)
  const nav = rules('.sp-notch')
  assert.match(nav, /height:\s*4\.2em/)
  assert.match(nav, /width:\s*min\(20em,\s*100%\)/)
  assert.match(nav, /grid-template-columns:\s*repeat\(var\(--sp-notch-count\),\s*1fr\)/)
  assert.match(css, /\.sp-notch-link\[aria-current='page'\] \.sp-notch-icon[\s\S]*?translateY\(-1\.95em\)/)
  assert.match(css, /@container \(max-width: 360px\)/, 'bar fills the width at 360px or less')
  assert.match(rules('.sp-notch-link'), /min-height:\s*44px/)
  assert.match(rules('.sp-notch-dock'), /env\(safe-area-inset-bottom/)
})

test('R1 NotchTabBar: links with aria-current, default label, roving tabindex and keys', () => {
  const code = sources.NotchTabBar
  assert.match(code, /label = 'Navegación'/)
  assert.match(code, /aria-label=\{label\}/)
  assert.match(code, /aria-current=\{active \? 'page' : undefined\}/)
  assert.match(code, /tabIndex=\{index === tabbable \? 0 : -1\}/)
  assert.match(code, /nextRovingIndex\(/)
  assert.match(code, /notchPosition\(/)
  assert.match(code, /from 'react-router-dom'/)
  assert.match(code, /size = 16/)
  assert.match(code, /speed = 1/)
  assert.doesNotMatch(code, /10%|30%|70%|90%/, 'bubble position comes from the active index')
})

test('R2 receipt: printer, ticket zigzag, 18-step feed and LED blink like the reference', () => {
  assert.match(rules('.sp-receipt-ticket'), /transform:\s*translateY\(-101%\)/)
  assert.match(css, /\.sp-receipt\.on \.sp-receipt-ticket[\s\S]*?transition:\s*transform calc\(2\.4s \/ var\(--k\)\) steps\(18,\s*end\)/)
  assert.match(css, /conic-gradient\(from -45deg at bottom,\s*#0000,\s*#000 1deg 89deg,\s*#0000 90deg\) 50%\/\.9em 100%/)
  assert.match(css, /@keyframes sp-receipt-led/)
  assert.match(rules('.sp-receipt-button'), /min-height:\s*44px/)
  assert.match(rules('.sp-receipt-printer'), /width:\s*16em/)
  assert.match(rules('.sp-receipt-paper'), /width:\s*13\.4em/)
})

test('R2 PrintReceipt: Spanish defaults, replay by reflow and polite announcement', () => {
  const code = sources.PrintReceipt
  assert.match(code, /title = 'UPDS COBIJA'/)
  assert.match(code, /buttonLabel = 'Imprimir comprobante'/)
  assert.match(code, /Comprobante impreso/)
  assert.match(code, /role="status"/)
  assert.match(code, /aria-live="polite"/)
  assert.match(code, /classList\.remove\('on', 'pg'\)/)
  assert.match(code, /offsetWidth/, 'reflow restarts the transition')
  assert.match(code, /classList\.add\('on', 'pg'\)/)
  assert.match(code, /useReducedMotion/)
})

test('R3 thermal loader: reference timings and feed keyframes', () => {
  assert.match(rules('.sp-printer-paper'), /animation:\s*sp-printer-feed calc\(3\.4s \/ var\(--k\)\) infinite/)
  assert.match(css, /@keyframes sp-printer-feed[\s\S]*?steps\(14,\s*end\)[\s\S]*?translateY\(2\.6em\) rotate\(7deg\)/)
  assert.match(rules('.sp-printer-window'), /width:\s*6\.6em/)
  assert.match(rules('.sp-printer-window'), /height:\s*7\.4em/)
})

test('R3 ThermalLoader: role=status with a visually hidden label', () => {
  const code = sources.ThermalLoader
  assert.match(code, /label = 'Enviando tu solicitud'/)
  assert.match(code, /role="status"/)
  assert.match(code, /sp-printer-sr/)
  assert.match(code, /aria-hidden="true"/)
})

test('R4 clinic 404: ECG path verbatim, default Spanish copy, link to reception', () => {
  const code = sources.ClinicNotFound
  assert.ok(
    code.includes('M0 150 H40 q10 -16 20 0 H86 l6 10 l9 -126 l10 150 l7 -34 H150 q18 -30 36 0 H232 q10 -16 20 0 H278 l6 10 l9 -126 l10 150 l7 -34 H342 q16 -26 32 0 H414 L484 40 V260 V150 H556 V100 C556 26 652 26 652 100 V200 C652 274 556 274 556 200 V150 V200 C556 274 652 274 652 200 V150 H716 L786 40 V260 V150 H1200'),
    'ECG path is the reference path',
  )
  assert.match(code, /pathLength="1000"/)
  assert.match(code, /title = 'Esta página no tiene pulso\.'/)
  assert.match(code, /Hicimos todos los estudios y no hay nada más que hacer\. Vos, en cambio, estás de diez\./)
  assert.match(code, /tag = 'URGENCIAS · DIAGNÓSTICO 404'/)
  assert.match(code, /ctaLabel = 'Volver a recepción'/)
  assert.match(code, /ctaTo = '\/estudiante'/)
  assert.match(code, /contained/)
  assert.match(code, /sp-404--contained/)
  assert.match(code, /<Link\b/)
})

test('R4 CSS: fixed by default, absolute when contained, 5s ECG loop, no animated trail on reduced motion', () => {
  assert.match(rules('.sp-404'), /position:\s*fixed/)
  assert.match(rules('.sp-404--contained'), /position:\s*absolute/)
  assert.match(rules('.sp-404'), /--accent:\s*var\(--student-clinic-accent\)/)
  assert.match(css, /--student-clinic-accent:\s*#2dd4bf/i)
  assert.match(css, /animation:\s*sp-404-trail calc\(5s \/ var\(--k\)\) linear infinite/)
  assert.match(css, /animation:\s*sp-404-beam calc\(5s \/ var\(--k\)\) linear infinite/)
  assert.match(rules('.sp-404-cta'), /min-height:\s*44px/)
  assert.match(reducedMotionCss(), /\.sp-404-trail,\s*\.sp-404-beam\s*\{\s*display:\s*none/)
})

test('R5/R6 Liquid Glass CSS: blur, border of light, pointer reflection and static highlight on touch', () => {
  const glass = rules('.lg-glass')
  assert.match(glass, /backdrop-filter:\s*blur\(var\(--lg-blur,\s*20px\)\) saturate\(180%\)/)
  assert.match(glass, /rgba\(255,\s*255,\s*255,\s*var\(--lg-a,\s*0\.12\)\)/)
  assert.match(css, /\.lg-glass::after[\s\S]*?circle 140px at var\(--x,\s*50%\) var\(--y,\s*0%\)/)
  assert.match(css, /@media \(hover: none\)[\s\S]*?\.lg-glass[\s\S]*?--lg-hover:\s*1/)
  assert.match(css, /@keyframes lg-drift/)
  assert.match(rules('.sp-glass-stage'), /border-radius:\s*22px/)
  assert.match(rules('.sp-glass-card'), /border-radius:\s*32px/)
})

test('the glass spring is stiffness 400, damping 30', () => {
  assert.deepEqual(GLASS_SPRING, { type: 'spring', stiffness: 400, damping: 30 })
})

test('R5 GlassCard: spring tilt with motion/react only on fine pointers, flat otherwise', () => {
  const code = sources.GlassCard
  assert.match(code, /from 'motion\/react'/)
  assert.match(code, /GLASS_SPRING/)
  assert.match(code, /useReducedMotion/)
  assert.match(code, /useFinePointer/)
  assert.match(code, /perspective: 1000/)
  assert.match(code, /tiltAngles\(/)
})

test('R6 GlassSwitch: tablist semantics, stretching pill and keyboard', () => {
  const code = sources.GlassSwitch
  assert.match(code, /role="tablist"/)
  assert.match(code, /role="tab"/)
  assert.match(code, /aria-selected=\{selected\}/)
  assert.match(code, /tabIndex=\{selected \? 0 : -1\}/)
  assert.match(code, /layoutId=/)
  assert.match(code, /scaleX: \[1, 1\.15, 1\]/)
  assert.match(code, /duration: 0\.45/)
  assert.match(code, /ease: \[0\.25, 0\.1, 0\.25, 1\]/)
  assert.match(code, /GLASS_SPRING/)
  assert.match(code, /nextRovingIndex\(/)
  assert.match(code, /useReducedMotion/)
  assert.match(rules('.sp-glass-switch-tab'), /height:\s*54px/)
})

test('every component has a prefers-reduced-motion rule that keeps the final state', () => {
  const reduced = reducedMotionCss()
  assert.match(reduced, /\.sp-notch-bar,[\s\S]*?\.sp-notch-bubble/)
  assert.match(reduced, /\.sp-receipt,\s*\.sp-receipt \*/)
  assert.match(reduced, /\.sp-printer,\s*\.sp-printer \*/)
  assert.match(reduced, /\.sp-printer-paper\s*\{[^}]*animation:\s*none!important[^}]*transform:\s*none/)
  assert.match(reduced, /\.sp-404 \*/)
  assert.match(reduced, /\.sp-glass-stage \.sp-glass-blob\s*\{[^}]*animation:\s*none/)
})
