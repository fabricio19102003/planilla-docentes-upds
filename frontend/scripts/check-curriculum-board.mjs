import assert from 'node:assert/strict'
import test from 'node:test'

import { hoursSplit, summarizePlan, summarizeSubjects } from '../src/lib/curriculumSummary.ts'

const slot = (id, theory, practice, credits, extra = {}) => ({
  id, subject_id: id, code: `MED ${1000 + id}`, name: `Materia ${id}`, theory_hours: theory, practice_hours: practice, credits, is_elective: false, ...extra,
})

const plan = {
  id: 1, code: 'MED-510-01', name: 'Medicina', program_code: 'MED', total_semesters: 3,
  semesters: [
    { semester: 1, subjects: [slot(1, 51, 51, 5), slot(2, 34, 17, 3)] },
    { semester: 2, subjects: [slot(3, 20, 0, 2, { is_elective: true, code: null })] },
    { semester: 3, subjects: [] },
  ],
}

test('a semester adds up its subjects, hours, credits and electives', () => {
  assert.deepEqual(summarizeSubjects(plan.semesters[0].subjects), {
    subjects: 2, theoryHours: 85, practiceHours: 68, hours: 153, credits: 8, electives: 0,
  })
  assert.deepEqual(summarizeSubjects(plan.semesters[1].subjects), {
    subjects: 1, theoryHours: 20, practiceHours: 0, hours: 20, credits: 2, electives: 1,
  })
})

test('the career totals add every semester', () => {
  const summary = summarizePlan(plan)
  assert.equal(summary.subjects, 3)
  assert.equal(summary.theoryHours, 105)
  assert.equal(summary.practiceHours, 68)
  assert.equal(summary.hours, 173)
  assert.equal(summary.credits, 10)
  assert.equal(summary.electives, 1)
})

test('the plan summary keeps one entry per semester in order', () => {
  const summary = summarizePlan(plan)
  assert.deepEqual(summary.semesters.map((item) => [item.semester, item.subjects, item.hours, item.credits]), [[1, 2, 153, 8], [2, 1, 20, 2], [3, 0, 0, 0]])
})

test('an empty plan or semester totals zero everywhere', () => {
  const zero = { subjects: 0, theoryHours: 0, practiceHours: 0, hours: 0, credits: 0, electives: 0 }
  assert.deepEqual(summarizeSubjects([]), zero)
  assert.deepEqual(summarizePlan({ ...plan, semesters: [] }), { ...zero, semesters: [] })
})

test('the theory/practice split is a percentage that always adds up to 100', () => {
  assert.deepEqual(hoursSplit(51, 51), { theory: 50, practice: 50 })
  assert.deepEqual(hoursSplit(34, 17), { theory: 67, practice: 33 })
  assert.deepEqual(hoursSplit(20, 0), { theory: 100, practice: 0 })
  assert.deepEqual(hoursSplit(0, 17), { theory: 0, practice: 100 })
})

test('a subject without hours has an empty split', () => {
  assert.deepEqual(hoursSplit(0, 0), { theory: 0, practice: 0 })
})
