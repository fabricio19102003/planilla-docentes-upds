import type { AcademicScheduleAssignment, AcademicScheduleBlock, ScheduleWorkloadItem } from '../api/types'
import type { Tone } from '../components/shared/tones'
import { semesterTone } from './academicTones.ts'

/**
 * Presentation helpers for the schedule planner: KPIs, block colors and workload bars.
 * Everything here is display-only; none of it changes what the backend pays or validates.
 */

/**
 * UI-only reference for the teacher workload bar: a full bar is 40 h/week and anything above it
 * is highlighted as overloaded. It is not a business rule; the backend decides the real limits.
 */
export const TEACHER_WEEKLY_LOAD_MAX_HOURS = 40

export interface PlannerKpis {
  blocks: number
  unassigned: number
  paidHours: number
  teachers: number
}

/** Totals for the active draft; a block with no current assignment counts as "sin docente". */
export function plannerKpis(
  blocks: readonly Pick<AcademicScheduleBlock, 'id' | 'paid_hours'>[],
  assignments: Readonly<Record<number, Pick<AcademicScheduleAssignment, 'teacher_ci'> | null | undefined>>,
): PlannerKpis {
  const teachers = new Set<string>()
  let unassigned = 0
  let paidHours = 0
  for (const block of blocks) {
    paidHours += block.paid_hours
    const assignment = assignments[block.id]
    if (assignment) teachers.add(assignment.teacher_ci)
    else unassigned += 1
  }
  return { blocks: blocks.length, unassigned, paidHours, teachers: teachers.size }
}

/** Semester decides the color; practice blocks get a dashed border to tell them from theory. */
export function blockTone(
  block: Pick<AcademicScheduleBlock, 'activity_type'> & { offering: Pick<AcademicScheduleBlock['offering'], 'semester'> },
): { tone: Tone; dashed: boolean } {
  return { tone: semesterTone(block.offering.semester), dashed: block.activity_type === 'practice' }
}

export interface WorkloadSegments {
  theoryPct: number
  practicePct: number
  overloaded: boolean
}

/** Theory/practice minutes as percentages of `TEACHER_WEEKLY_LOAD_MAX_HOURS`, scaled down to fit when over it. */
export function workloadSegments(
  item: Pick<ScheduleWorkloadItem, 'theory_minutes_week' | 'practice_minutes_week'>,
): WorkloadSegments {
  const maxMinutes = TEACHER_WEEKLY_LOAD_MAX_HOURS * 60
  const total = item.theory_minutes_week + item.practice_minutes_week
  const scale = total > maxMinutes ? total : maxMinutes
  return {
    theoryPct: (item.theory_minutes_week / scale) * 100,
    practicePct: (item.practice_minutes_week / scale) * 100,
    overloaded: total > maxMinutes,
  }
}

export function draftStatusTone(status: 'draft' | 'published' | 'archived'): Tone {
  if (status === 'draft') return 'info'
  return status === 'published' ? 'success' : 'neutral'
}
