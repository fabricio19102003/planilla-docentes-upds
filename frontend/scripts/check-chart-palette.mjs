import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import test from 'node:test'

import { CHART_SERIES_PALETTE, seriesColor } from '../src/lib/chartPalette.ts'

const src = join(resolve(import.meta.dirname, '..'), 'src')

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return sourceFiles(full)
    return /\.(ts|tsx)$/.test(name) ? [full] : []
  })
}

test('series palette follows the theme order and holds only CSS variables', () => {
  assert.deepEqual(CHART_SERIES_PALETTE, [
    'var(--color-chart-1)',
    'var(--color-tone-violet)',
    'var(--color-tone-cyan)',
    'var(--color-success)',
    'var(--color-warning)',
    'var(--color-chart-2)',
    'var(--color-chart-3)',
  ])
  for (const color of CHART_SERIES_PALETTE) assert.doesNotMatch(color, /#[0-9a-fA-F]{3,8}\b/)
})

test('seriesColor cycles through the palette', () => {
  const size = CHART_SERIES_PALETTE.length
  assert.equal(seriesColor(0), CHART_SERIES_PALETTE[0])
  assert.equal(seriesColor(size - 1), CHART_SERIES_PALETTE[size - 1])
  assert.equal(seriesColor(size), CHART_SERIES_PALETTE[0])
  assert.equal(seriesColor(size + 2), CHART_SERIES_PALETTE[2])
  assert.equal(seriesColor(-1), CHART_SERIES_PALETTE[size - 1])
})

test('every file importing recharts takes colors from the palette or theme variables only', () => {
  const chartFiles = sourceFiles(src).filter((file) => /from\s+['"]recharts['"]/.test(readFileSync(file, 'utf8')))
  assert.ok(chartFiles.length > 0, 'expected at least one recharts chart')
  for (const file of chartFiles) {
    const code = readFileSync(file, 'utf8')
    const name = relative(src, file)
    assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${name} must not contain hex colors`)
    assert.deepEqual(code.match(/\b(?:fill|stroke)=["'](?!var\(--)[^"'{]+["']/g) ?? [], [], `${name} must use var(--…) fills and strokes`)
    assert.match(code, /chartPalette|var\(--color-/, `${name} must use chartPalette or var(--color-…) strings`)
  }
})

test('the dashboard bar charts color each bar from the palette', () => {
  const code = readFileSync(join(src, 'pages/DashboardPage.tsx'), 'utf8')
  assert.match(code, /from '@\/lib\/chartPalette'/)
  assert.match(code, /seriesColor\(/)
  assert.match(code, /<Cell\b[^>]*seriesColor\(/)
})
