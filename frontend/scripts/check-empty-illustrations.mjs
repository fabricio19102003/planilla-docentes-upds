import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

const root = resolve(import.meta.dirname, '..')
const src = join(root, 'src')

const illustrations = {
  EmptyBoxIllustration: 'empty-box',
  EmptyInboxIllustration: 'empty-inbox',
  EmptyCalendarIllustration: 'empty-calendar',
  EmptyDocumentIllustration: 'empty-document',
  EmptySearchIllustration: 'empty-search',
}

function read(relative) {
  const path = join(src, relative)
  assert.ok(existsSync(path), `src/${relative} is missing`)
  return readFileSync(path, 'utf8')
}

for (const name of Object.keys(illustrations)) {
  test(`${name} is a token-only decorative SVG`, () => {
    const file = `components/illustrations/${name}.tsx`
    const code = read(file)
    assert.match(code, new RegExp(`export function ${name}\\b`), `${file} must export ${name}`)
    assert.match(code, /<svg\b/, `${file} must render an svg`)
    assert.match(code, /aria-hidden="true"/, `${file} must be aria-hidden`)
    assert.match(code, /viewBox="0 0 160 120"/, `${file} must use the 160x120 viewBox`)
    assert.match(code, /className/, `${file} must accept className`)
    assert.doesNotMatch(code, /<text\b/, `${file} must not contain text`)
    assert.deepEqual(code.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [], [], `${file} must not contain hex colors`)
    assert.deepEqual(code.match(/\b(?:rgb|rgba|hsl|hsla|oklch)\(/g) ?? [], [], `${file} must not use color functions`)
    assert.deepEqual(code.match(/\bgradient-[\w-]+/g) ?? [], [], `${file} must not use gradient-* classes`)
    assert.deepEqual(code.match(/(?:linear|radial)-gradient|<(?:linear|radial)Gradient/g) ?? [], [], `${file} must not use gradients`)
    assert.doesNotMatch(code, /style=/, `${file} must not use inline styles`)
    for (const match of code.matchAll(/\b(?:fill|stroke)="([^"]*)"/g)) {
      assert.match(match[1], /^(?:none|currentColor|var\(--color-[\w-]+\))$/, `${file} has a non-token paint: ${match[1]}`)
    }
  })
}

test('illustrations index exports every illustration, IllustrationName and the map', () => {
  const code = read('components/illustrations/index.ts')
  for (const [name, key] of Object.entries(illustrations)) {
    assert.match(code, new RegExp(`\\b${name}\\b`), `index.ts must export ${name}`)
    assert.match(code, new RegExp(`['"]?${key}['"]?\\s*:\\s*${name}`), `index.ts must map ${key} to ${name}`)
  }
  assert.match(code, /export type IllustrationName\b/)
  assert.match(code, /export const illustrations\b/)
})

test('EmptyState accepts an illustration and keeps the icon props', () => {
  const code = read('components/shared/EmptyState.tsx')
  assert.match(code, /illustration\?: IllustrationName/)
  assert.match(code, /@\/components\/illustrations/)
  assert.match(code, /w-36/)
  for (const prop of ['icon', 'title', 'description', 'action', 'className']) {
    assert.match(code, new RegExp(`\\b${prop}\\b`), `EmptyState must keep the ${prop} prop`)
  }
  assert.match(code, /<EmptyState illustration=/, 'JSDoc must show an illustration example')
  assert.match(code, /<EmptyState icon=/, 'JSDoc must keep the icon example')
})
