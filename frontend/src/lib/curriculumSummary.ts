import type { CurriculumPlan, CurriculumSlot } from './academicRecordsState'

export interface CurriculumTotals {
  subjects: number
  theoryHours: number
  practiceHours: number
  /** Theory plus practice. */
  hours: number
  credits: number
  electives: number
}

export interface SemesterTotals extends CurriculumTotals {
  semester: number
}

export interface PlanSummary extends CurriculumTotals {
  semesters: SemesterTotals[]
}

type SlotHours = Pick<CurriculumSlot, 'theory_hours' | 'practice_hours' | 'credits' | 'is_elective'>

export function summarizeSubjects(subjects: readonly SlotHours[]): CurriculumTotals {
  const theoryHours = subjects.reduce((sum, subject) => sum + subject.theory_hours, 0)
  const practiceHours = subjects.reduce((sum, subject) => sum + subject.practice_hours, 0)
  return {
    subjects: subjects.length,
    theoryHours,
    practiceHours,
    hours: theoryHours + practiceHours,
    credits: subjects.reduce((sum, subject) => sum + subject.credits, 0),
    electives: subjects.filter((subject) => subject.is_elective).length,
  }
}

/** Career totals and the totals of each semester, in plan order. */
export function summarizePlan(plan: Pick<CurriculumPlan, 'semesters'>): PlanSummary {
  const semesters = plan.semesters.map((item) => ({ semester: item.semester, ...summarizeSubjects(item.subjects) }))
  const all = summarizeSubjects(plan.semesters.flatMap((item) => item.subjects))
  return { ...all, semesters }
}

/** Theory and practice shares as whole percentages that add up to 100 (both 0 without hours). */
export function hoursSplit(theoryHours: number, practiceHours: number): { theory: number; practice: number } {
  const total = theoryHours + practiceHours
  if (total <= 0) return { theory: 0, practice: 0 }
  const theory = Math.round((theoryHours / total) * 100)
  return { theory, practice: 100 - theory }
}
