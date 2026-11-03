import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

import { THEME_STORAGE_KEY, readStoredPreference, resolveTheme } from '../src/lib/theme.ts'

// S9: dark mode toggle Claro / Oscuro / Sistema. Default follows the OS, remembered per browser.

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')
const storageWith = (value) => ({ getItem: (key) => (key === THEME_STORAGE_KEY ? value : null) })

test('the preference is remembered under the sipad-theme key', () => {
  assert.equal(THEME_STORAGE_KEY, 'sipad-theme')
})

test('nothing stored defaults to system', () => {
  assert.equal(readStoredPreference(storageWith(null)), 'system')
})

test('a stored light, dark or system value is kept', () => {
  assert.equal(readStoredPreference(storageWith('light')), 'light')
  assert.equal(readStoredPreference(storageWith('dark')), 'dark')
  assert.equal(readStoredPreference(storageWith('system')), 'system')
})

test('an invalid stored value falls back to system', () => {
  assert.equal(readStoredPreference(storageWith('blue')), 'system')
  assert.equal(readStoredPreference(storageWith('')), 'system')
})

test('unavailable storage falls back to system', () => {
  assert.equal(readStoredPreference(null), 'system')
  assert.equal(readStoredPreference({ getItem: () => { throw new Error('denied') } }), 'system')
})

test('light and dark ignore the OS preference', () => {
  assert.equal(resolveTheme('light', true), 'light')
  assert.equal(resolveTheme('light', false), 'light')
  assert.equal(resolveTheme('dark', true), 'dark')
  assert.equal(resolveTheme('dark', false), 'dark')
})

test('system follows the OS preference', () => {
  assert.equal(resolveTheme('system', true), 'dark')
  assert.equal(resolveTheme('system', false), 'light')
})

test('index.html applies the theme before React loads, without a flash', () => {
  const html = read('index.html')
  const script = html.match(/<script>([\s\S]*?)<\/script>/)
  assert.ok(script, 'an inline (non-module) script exists')
  assert.ok(html.indexOf('<script>') < html.indexOf('src="/src/main.tsx"'), 'inline script runs before the app bundle')
  assert.match(script[1], /sipad-theme/)
  assert.match(script[1], /prefers-color-scheme: dark/)
  assert.match(script[1], /classList\.toggle\(\s*'dark'/)
  assert.match(script[1], /colorScheme/)
  assert.match(script[1], /try\s*{[\s\S]*catch/)
})

test('the provider wraps the app and follows OS changes live', () => {
  assert.match(read('src/main.tsx'), /<ThemeProvider>[\s\S]*<App \/>[\s\S]*<\/ThemeProvider>/)
  const context = read('src/context/ThemeContext.tsx')
  assert.match(context, /prefers-color-scheme: dark/)
  assert.match(context, /addEventListener\('change'/)
  assert.match(context, /removeEventListener\('change'/)
  assert.match(context, /THEME_STORAGE_KEY/)
})

test('the staff header and the student band render the toggle', () => {
  assert.match(read('src/components/layout/Header.tsx'), /<ThemeToggle\b/)
  const student = read('src/pages/student/StudentPortalLayout.tsx')
  assert.match(student, /<ThemeToggle\b[^>]*variant="brand"/)
})

test('the toggle offers Claro, Oscuro and Sistema with accessible labels and stays token-only', () => {
  const toggle = read('src/components/layout/ThemeToggle.tsx')
  for (const label of ['Claro', 'Oscuro', 'Sistema']) assert.match(toggle, new RegExp(label))
  assert.match(toggle, /Tema: /)
  assert.match(toggle, /aria-label/)
  assert.doesNotMatch(toggle, /#[0-9a-fA-F]{3,8}\b/)
  assert.doesNotMatch(toggle, /gradient/)
})

test('the dark theme defines its own brand, sidebar and canvas tokens', () => {
  const css = read('src/index.css')
  const dark = css.match(/\n\.dark \{([\s\S]*?)\n\}/)?.[1] ?? ''
  for (const token of ['--brand', '--brand-strong', '--brand-foreground', '--canvas', '--sidebar', '--border']) {
    assert.match(dark, new RegExp(`${token}:`), `${token} in .dark`)
  }
  assert.doesNotMatch(dark, /--canvas: var\(--background\)/, 'canvas is distinct from the card surface')
})
