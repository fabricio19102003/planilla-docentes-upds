import { toMinutes } from '@/lib/classroomReservations'
import type { StartOption } from '@/lib/classroomReservationDay'
import { cn } from '@/lib/utils'

interface StartTimeGridProps {
  options: StartOption[]
  start: string
  end: string | null
  onSelect: (time: string) => void
}

/** Keyboard-friendly alternative to clicking the agenda: every quarter-hour start as a button. */
export function StartTimeGrid({ options, start, end, onSelect }: StartTimeGridProps) {
  const startMinutes = toMinutes(start)
  const endMinutes = end ? toMinutes(end) : null
  return (
    <div role="group" aria-label="Hora de inicio" className="grid max-h-52 grid-cols-4 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-6 xl:grid-cols-4">
      {options.map((option) => {
        const minutes = toMinutes(option.time) ?? 0
        const selected = option.time === start
        const inRange = !selected && startMinutes !== null && endMinutes !== null && minutes > startMinutes && minutes < endMinutes
        return (
          <button
            key={option.time}
            type="button"
            disabled={!option.available}
            aria-pressed={selected}
            onClick={() => onSelect(option.time)}
            className={cn(
              'rounded-md border bg-card py-1.5 text-sm tabular-nums outline-none transition-colors hover:border-primary focus-visible:ring-2 focus-visible:ring-ring',
              inRange && 'border-primary/40 bg-primary/10',
              selected && 'border-primary bg-primary font-semibold text-primary-foreground hover:border-primary',
              !option.available && 'cursor-not-allowed border-transparent bg-muted text-muted-foreground/70 line-through hover:border-transparent',
            )}
          >
            {option.time}
          </button>
        )
      })}
    </div>
  )
}
