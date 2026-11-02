import assert from 'node:assert/strict'
import test from 'node:test'

import { emptySlotForm, moveSlot, offeringSummary, slotFormProblem, slotPayload } from '../src/lib/curriculumEditing.ts'

test('a new subject form starts in the chosen semester', () => {
  assert.deepEqual(emptySlotForm(3), {
    semester: '3', name: '', code: '', theory_hours: '0', practice_hours: '0', credits: '0', is_elective: false,
  })
})

test('the form explains what is wrong before saving', () => {
  const form = { ...emptySlotForm(3), name: 'Bioética', code: 'BIO 0300', theory_hours: '2', credits: '2' }
  assert.equal(slotFormProblem(form), null)
  assert.equal(slotFormProblem({ ...form, name: '  ' }), 'Escribí el nombre de la materia.')
  assert.equal(slotFormProblem({ ...form, code: 'bio-300' }), 'La sigla va con 3 letras, un espacio y 4 números (ej: BIO 0300).')
  assert.equal(slotFormProblem({ ...form, code: '' }), 'Una materia que no es electiva necesita sigla.')
  assert.equal(slotFormProblem({ ...form, code: '', is_elective: true }), null)
  assert.equal(slotFormProblem({ ...form, theory_hours: '0', practice_hours: '0' }), 'La materia necesita al menos una hora teórica o práctica.')
  assert.equal(slotFormProblem({ ...form, credits: '-1' }), 'Las horas y los créditos son números enteros desde 0.')
})

test('the payload trims, uppercases the code and sends numbers', () => {
  const form = { ...emptySlotForm(3), name: ' Bioética ', code: ' bio 0300 ', theory_hours: '2', practice_hours: '1', credits: '3' }
  assert.deepEqual(slotPayload(form), {
    semester: 3, name: 'Bioética', code: 'BIO 0300', theory_hours: 2, practice_hours: 1, credits: 3, is_elective: false,
  })
  assert.equal(slotPayload({ ...form, code: '', is_elective: true }).code, null)
})

test('moving a subject swaps it with its neighbour and stays inside the list', () => {
  assert.deepEqual(moveSlot([1, 2, 3], 2, 'up'), [2, 1, 3])
  assert.deepEqual(moveSlot([1, 2, 3], 2, 'down'), [1, 3, 2])
  assert.deepEqual(moveSlot([1, 2, 3], 1, 'up'), [1, 2, 3])
  assert.deepEqual(moveSlot([1, 2, 3], 3, 'down'), [1, 2, 3])
})

test('the offering result reads as one sentence', () => {
  assert.equal(offeringSummary({ academic_period: 'I/2027', created: ['A', 'B'], existing: ['C'], skipped: [{ name: 'Electiva I', semester: 8, reason: 'x' }] }),
    'I/2027: 2 ofertas creadas, 1 ya existía, 1 no generada.')
  assert.equal(offeringSummary({ academic_period: 'I/2027', created: [], existing: ['A', 'B'], skipped: [] }),
    'I/2027: 0 ofertas creadas, 2 ya existían, 0 no generadas.')
})
