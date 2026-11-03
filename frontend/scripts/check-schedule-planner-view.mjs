import assert from 'node:assert/strict'
import test from 'node:test'

import {
  TEACHER_WEEKLY_LOAD_MAX_HOURS,
  blockTone,
  draftStatusTone,
  plannerKpis,
  workloadSegments,
} from '../src/lib/schedulePlannerView.ts'

const block = (overrides) => ({
  id: 1,
  activity_type: 'theory',
  paid_hours: 2,
  offering: { semester: 1 },
  ...overrides,
})

test('plannerKpis counts blocks, blocks without teacher, paid hours and distinct teachers', () => {
  const blocks = [block({ id: 1, paid_hours: 2 }), block({ id: 2, paid_hours: 1.5 }), block({ id: 3, paid_hours: 3 })]
  const assignments = { 1: { teacher_ci: '100' }, 2: { teacher_ci: '100' }, 3: null }
  assert.deepEqual(plannerKpis(blocks, assignments), {
    blocks: 3,
    unassigned: 1,
    paidHours: 6.5,
    teachers: 1,
  })
})

test('plannerKpis treats a block missing from the assignment map as unassigned and handles an empty draft', () => {
  assert.deepEqual(plannerKpis([block({ id: 9 })], {}), { blocks: 1, unassigned: 1, paidHours: 2, teachers: 0 })
  assert.deepEqual(plannerKpis([], {}), { blocks: 0, unassigned: 0, paidHours: 0, teachers: 0 })
})

test('blockTone colors by offering semester and dashes practice blocks only', () => {
  assert.deepEqual(blockTone(block({ offering: { semester: 1 } })), { tone: 'primary', dashed: false })
  assert.deepEqual(blockTone(block({ offering: { semester: 2 }, activity_type: 'practice' })), { tone: 'violet', dashed: true })
  assert.equal(blockTone(block({ offering: { semester: 7 } })).tone, 'primary')
})

test('workloadSegments turns minutes into percentages of the UI weekly maximum', () => {
  assert.equal(TEACHER_WEEKLY_LOAD_MAX_HOURS, 40)
  const result = workloadSegments({ theory_minutes_week: 600, practice_minutes_week: 300 })
  assert.equal(result.theoryPct, 25)
  assert.equal(result.practicePct, 12.5)
  assert.equal(result.overloaded, false)
})

test('workloadSegments flags overload above the maximum and keeps segments within 100%', () => {
  const over = workloadSegments({ theory_minutes_week: 2400, practice_minutes_week: 600 })
  assert.equal(over.overloaded, true)
  assert.ok(over.theoryPct + over.practicePct <= 100 + 1e-9)
  assert.ok(over.theoryPct > over.practicePct)
  const exact = workloadSegments({ theory_minutes_week: 2400, practice_minutes_week: 0 })
  assert.equal(exact.overloaded, false)
  assert.equal(exact.theoryPct, 100)
})

test('draftStatusTone maps draft, published and archived to info, success and neutral', () => {
  assert.equal(draftStatusTone('draft'), 'info')
  assert.equal(draftStatusTone('published'), 'success')
  assert.equal(draftStatusTone('archived'), 'neutral')
})
