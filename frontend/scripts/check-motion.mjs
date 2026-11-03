import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import {
  COUNT_UP_DURATION_MS,
  countUpFrame,
  countUpTarget,
  easeOutCubic,
  interpolate,
} from '../src/lib/countUp.ts'

// S5: micro-interactions (card hover elevation, page transition, count-up) that respect prefers-reduced-motion.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const css = read('src/index.css')

/** Body of the `@media (prefers-reduced-motion: reduce)` block (balanced braces). */
function reducedMotionBlock() {
  const start = css.indexOf('@media (prefers-reduced-motion: reduce)')
  assert.notEqual(start, -1, 'index.css has no prefers-reduced-motion block')
  const open = css.indexOf('{', start)
  let depth = 0
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++
    if (css[i] === '}' && --depth === 0) return css.slice(open + 1, i)
  }
  throw new Error('unbalanced prefers-reduced-motion block')
}

test('easeOutCubic starts at 0 and ends at 1', () => {
  assert.equal(easeOutCubic(0), 0)
  assert.equal(easeOutCubic(1), 1)
})

test('easeOutCubic is monotonic and clamps outside 0..1', () => {
  let previous = -Infinity
  for (let i = 0; i <= 100; i++) {
    const value = easeOutCubic(i / 100)
    assert.ok(value >= previous, `not monotonic at ${i / 100}`)
    previous = value
  }
  assert.equal(easeOutCubic(-0.5), 0)
  assert.equal(easeOutCubic(2), 1)
})

test('interpolate hits the exact target at progress 1 and the start at 0', () => {
  assert.equal(interpolate(0, 412500.37, 1), 412500.37)
  assert.equal(interpolate(0, 93.4, 1), 93.4)
  assert.equal(interpolate(0, 93.4, 0), 0)
  assert.equal(interpolate(0, 100, 0.5), 50)
})

test('countUpFrame runs from 0 to the exact target over the duration', () => {
  assert.ok(COUNT_UP_DURATION_MS >= 600 && COUNT_UP_DURATION_MS <= 800)
  assert.equal(countUpFrame(42, 0), 0)
  assert.equal(countUpFrame(42, COUNT_UP_DURATION_MS), 42)
  assert.equal(countUpFrame(42, COUNT_UP_DURATION_MS * 3), 42)
  const middle = countUpFrame(100, COUNT_UP_DURATION_MS / 2)
  assert.ok(middle > 50 && middle < 100, 'ease-out is past the halfway value at half the time')
})

test('non-numeric values pass through: only finite numbers animate', () => {
  assert.equal(countUpTarget(7), 7)
  assert.equal(countUpTarget(0), 0)
  assert.equal(countUpTarget('Sin datos'), null)
  assert.equal(countUpTarget('93.4%'), null)
  assert.equal(countUpTarget(null), null)
  assert.equal(countUpTarget(undefined), null)
  assert.equal(countUpTarget(Number.NaN), null)
  assert.equal(countUpTarget(Number.POSITIVE_INFINITY), null)
})

test('index.css defines the new motion utilities', () => {
  assert.match(css, /@utility card-hover/)
  assert.match(css, /@utility page-enter/)
})

test('index.css disables the new and legacy motion under prefers-reduced-motion', () => {
  const block = reducedMotionBlock()
  for (const name of ['card-hover', 'page-enter', 'animate-fade-in-up', 'animate-fade-in', 'animate-slide-in-left', 'animate-count-up', 'card-3d']) {
    assert.ok(block.includes(`.${name}`), `reduced-motion block does not cover .${name}`)
  }
})

test('Card exposes an opt-in interactive prop and StatCard uses it', () => {
  assert.match(read('src/components/ui/card.tsx'), /interactive/)
  assert.match(read('src/components/ui/card.tsx'), /card-hover/)
  assert.match(read('src/components/shared/StatCard.tsx'), /<Card[^>]*\binteractive\b/)
})

test('Layout and StudentPortalLayout key the outlet wrapper by pathname', () => {
  for (const path of ['src/components/layout/Layout.tsx', 'src/pages/student/StudentPortalLayout.tsx']) {
    const source = read(path)
    assert.match(source, /useLocation/, `${path} does not read the location`)
    assert.match(source, /<(main|div)\b[^>]*\bkey=\{[^}]*pathname[^}]*\}[^>]*page-enter[^>]*>\s*(<Outlet \/>|[\s\S]*?<Outlet \/>)/, `${path} does not key the outlet wrapper by pathname`)
  }
})

test('CountUp uses the reduced-motion hook and exposes the final value to screen readers', () => {
  const countUp = read('src/components/shared/CountUp.tsx')
  assert.match(countUp, /useReducedMotion/)
  assert.match(countUp, /sr-only/)
  assert.match(countUp, /aria-hidden/)
  assert.match(countUp, /requestAnimationFrame/)
  assert.match(read('src/hooks/use-reduced-motion.ts'), /prefers-reduced-motion: reduce/)
})

test('DashboardPage animates its numeric stat values', () => {
  const dashboard = read('src/pages/DashboardPage.tsx')
  assert.match(dashboard, /<CountUp/)
  assert.ok((dashboard.match(/<CountUp/g) ?? []).length >= 5, 'expected CountUp on the five numeric stats')
})
