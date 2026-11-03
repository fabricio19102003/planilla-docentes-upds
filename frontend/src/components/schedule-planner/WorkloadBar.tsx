import { workloadSegments } from '@/lib/schedulePlannerView'
import type { ScheduleWorkloadItem } from '@/api/types'
import { cn } from '@/lib/utils'

/**
 * Stacked theory/practice bar for one teacher's weekly load. The scale is a UI reference
 * (see `TEACHER_WEEKLY_LOAD_MAX_HOURS`); above it the track gets a destructive ring.
 */
export function WorkloadBar({ item }: { item: Pick<ScheduleWorkloadItem, 'theory_minutes_week' | 'practice_minutes_week'> }) {
  const { theoryPct, practicePct, overloaded } = workloadSegments(item)
  return (
    <div
      aria-hidden="true"
      className={cn('flex h-1.5 w-full overflow-hidden rounded-full bg-input', overloaded && 'ring-2 ring-destructive/60')}
    >
      <div className="h-full bg-primary" style={{ width: `${theoryPct}%` }} />
      <div className="h-full bg-tone-cyan" style={{ width: `${practicePct}%` }} />
    </div>
  )
}
