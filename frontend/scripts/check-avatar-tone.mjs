import assert from 'node:assert/strict'
import test from 'node:test'

import { avatarTone, initials } from '../src/lib/avatarTone.ts'

const PALETTE = ['primary', 'violet', 'cyan', 'success', 'warning', 'info']
const SAMPLE = Array.from({ length: 60 }, (_, i) => String(1000000 + i * 7919))

test('the same key always maps to the same tone', () => {
  for (const key of SAMPLE) assert.equal(avatarTone(key), avatarTone(key))
  assert.equal(avatarTone('4567890'), avatarTone('4567890'))
})

test('an empty key is neutral', () => {
  assert.equal(avatarTone(''), 'neutral')
})

test('tones stay inside the colorful palette and never reach destructive or neutral', () => {
  for (const key of SAMPLE) {
    const tone = avatarTone(key)
    assert.ok(PALETTE.includes(tone), `${key} -> ${tone}`)
    assert.notEqual(tone, 'destructive')
    assert.notEqual(tone, 'neutral')
  }
})

test('a sample of CIs covers at least four tones', () => {
  const seen = new Set(SAMPLE.map(avatarTone))
  assert.ok(seen.size >= 4, `only ${seen.size} tones: ${[...seen].join(', ')}`)
})

test('initials take the first letters of the first two words, uppercase', () => {
  assert.equal(initials('maria lopez'), 'ML')
  assert.equal(initials('Juan Carlos Perez Soliz'), 'JC')
  assert.equal(initials('  ana   gomez '), 'AG')
  assert.equal(initials('Pedro'), 'P')
})

test('initials fall back to U when there is no name', () => {
  assert.equal(initials(''), 'U')
  assert.equal(initials('   '), 'U')
  assert.equal(initials(null), 'U')
  assert.equal(initials(undefined), 'U')
})
