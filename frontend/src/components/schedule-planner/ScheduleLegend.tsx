import { TONE_CHIP, TONE_DOT, type Tone } from '@/components/shared/tones'
import { cn } from '@/lib/utils'

/**
 * Legend for the weekly grid: one chip per semester present in the draft (same tones as the
 * blocks) and the theory (solid border) versus practice (dashed border) distinction.
 */
export function ScheduleLegend({ semesters }: { semesters: { semester: number; tone: Tone }[] }) {
  return (
    <ul aria-label="Leyenda del horario" className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
      {semesters.map(({ semester, tone }) => (
        <li key={semester} className={cn('flex items-center gap-1.5 rounded-md px-2 py-1 font-medium', TONE_CHIP[tone])}>
          <span aria-hidden="true" className={cn('size-2 rounded-full', TONE_DOT[tone])} />
          Semestre {semester}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="h-3.5 w-6 rounded-sm border border-solid border-foreground/40 bg-muted" />
        Teoría
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="h-3.5 w-6 rounded-sm border border-dashed border-foreground/40 bg-muted" />
        Práctica
      </li>
    </ul>
  )
}
