import assert from 'node:assert/strict'
import test from 'node:test'

import { classifyRecord, summarizeHistory } from '../src/lib/studentHistorySummary.ts'

const term = (code, is_intensive = false) => ({ code, name: code, year: 2025, kind: 'I', is_intensive })
const record = (id, subject_code, status, grade) => ({
  legacy_registration_id: id, subject_code, subject_name: subject_code, group_code: null, shift: null,
  teacher_name: null, status, grade, in_curriculum: true,
})

const history = [
  { term: term('2025-II'), records: [record(1, 'A', 'aprobado', 80), record(2, 'B', 'reprobado', 40), record(3, 'C', 'retirado', null), record(4, 'D', 'pendiente', null)] },
  { term: term('2025-I'), records: [record(5, 'B', 'aprobado', 60), record(6, 'E', 'aprobado', 70), record(7, 'F', 'retirado', 90)] },
]

test('each record status maps to one outcome', () => {
  assert.equal(classifyRecord('aprobado'), 'approved')
  assert.equal(classifyRecord('reprobado'), 'failed')
  assert.equal(classifyRecord('retirado'), 'withdrawn')
  assert.equal(classifyRecord('pendiente'), 'pending')
})

test('the average counts final grades of approved and failed records only', () => {
  // (80 + 40 + 60 + 70) / 4 = 62.5; the withdrawn record graded 90 and the pending one are excluded.
  assert.equal(summarizeHistory(history).average, 62.5)
})

test('the average rounds to two decimals like the term average', () => {
  const rows = [{ term: term('T'), records: [record(1, 'A', 'aprobado', 51), record(2, 'B', 'aprobado', 52), record(3, 'C', 'aprobado', 52)] }]
  assert.equal(summarizeHistory(rows).average, 51.67)
})

test('a subject failed and later approved counts once, as approved', () => {
  // A, B (failed then approved), E are approved; C, D, F are not.
  assert.equal(summarizeHistory(history).approved, 3)
})

test('the total is the number of distinct subjects in the history', () => {
  assert.equal(summarizeHistory(history).total, 6)
})

test('progress is approved over total as a rounded percentage', () => {
  assert.equal(summarizeHistory(history).progress, 50)
  const third = [{ term: term('T'), records: [record(1, 'A', 'aprobado', 70), record(2, 'B', 'reprobado', 30), record(3, 'C', 'pendiente', null)] }]
  assert.equal(summarizeHistory(third).progress, 33)
})

test('an empty history has no average and zero progress', () => {
  assert.deepEqual(summarizeHistory([]), { average: null, approved: 0, total: 0, progress: 0 })
  assert.deepEqual(summarizeHistory([{ term: term('T'), records: [] }]), { average: null, approved: 0, total: 0, progress: 0 })
})

test('a history without graded records has no average', () => {
  const rows = [{ term: term('T'), records: [record(1, 'A', 'retirado', null), record(2, 'B', 'pendiente', null)] }]
  assert.equal(summarizeHistory(rows).average, null)
})
