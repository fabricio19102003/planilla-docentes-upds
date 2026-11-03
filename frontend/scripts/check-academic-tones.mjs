import assert from 'node:assert/strict'
import test from 'node:test'

import { semesterNumber, semesterTone, shiftFromGroupCode, shiftLabel, shiftTone } from '../src/lib/academicTones.ts'

test('semesterNumber reads numbers and Spanish ordinal names', () => {
  assert.equal(semesterNumber(3), 3)
  assert.equal(semesterNumber('7'), 7)
  assert.equal(semesterNumber('PRIMERO'), 1)
  assert.equal(semesterNumber('Séptimo'), 7)
  assert.equal(semesterNumber('DECIMO'), 10)
  assert.equal(semesterNumber('otro'), null)
})

test('semesterTone gives neighbouring semesters different colorful tones and is stable', () => {
  const tones = Array.from({ length: 10 }, (_, i) => semesterTone(i + 1))
  for (let i = 1; i < tones.length; i++) assert.notEqual(tones[i], tones[i - 1])
  assert.ok(!tones.includes('neutral') && !tones.includes('destructive'))
  assert.equal(semesterTone('PRIMERO'), semesterTone(1))
  assert.equal(semesterTone('x'), 'neutral')
})

test('shift comes from the group code prefix and maps to a tone and label', () => {
  assert.equal(shiftFromGroupCode('M-1'), 'M')
  assert.equal(shiftFromGroupCode('t-2'), 'T')
  assert.equal(shiftFromGroupCode('N1'), 'N')
  assert.equal(shiftFromGroupCode('X-1'), null)
  assert.deepEqual(['M', 'T', 'N'].map(shiftLabel), ['Mañana', 'Tarde', 'Noche'])
  assert.equal(new Set(['M', 'T', 'N'].map(shiftTone)).size, 3)
  assert.equal(shiftTone(null), 'neutral')
})
