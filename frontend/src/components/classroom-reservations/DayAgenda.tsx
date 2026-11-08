import { timeAtPosition } from '@/lib/classroomReservationDay'
import { timelinePosition, toMinutes, type BusyRange } from '@/lib/classroomReservations'
import { cn } from '@/lib/utils'

/** 0.75 px per minute keeps a 45-minute period 34 px tall, enough for one line of label. */
const PX_PER_MINUTE = 0.75
const GUTTER = '3rem'

export interface AgendaSelection {
  start: string
  end: string
  conflict: boolean
}

interface DayAgendaProps {
  busy: BusyRange[]
  dayStart: string
  dayEnd: string
  selection: AgendaSelection | null
  hint: string | null
  onPick: (time: string) => void
}

function hourMarks(dayStart: string, dayEnd: string): string[] {
  const first = Math.ceil((toMinutes(dayStart) ?? 0) / 60)
  const last = Math.floor((toMinutes(dayEnd) ?? 0) / 60)
  return Array.from({ length: Math.max(last - first + 1, 0) }, (_, index) => `${String(first + index).padStart(2, '0')}:00`)
}

function blockLabel(range: BusyRange): string {
  if (range.kind === 'reservation') return range.mine ? 'Tu reserva' : range.label
  return range.detail ? `${range.label} · ${range.detail}` : range.label
}

function blockTone(range: BusyRange): string {
  if (range.kind === 'class') return 'bg-destructive/10 text-destructive-foreground'
  return range.mine ? 'bg-info/12 text-info-foreground' : 'bg-warning/15 text-warning-foreground'
}

export function DayAgenda({ busy, dayStart, dayEnd, selection, hint, onPick }: DayAgendaProps) {
  const total = (toMinutes(dayEnd) ?? 0) - (toMinutes(dayStart) ?? 0)
  const place = (start: string, end: string) => {
    const { top, height } = timelinePosition(start, end, dayStart, dayEnd)
    return { top: `${top}%`, height: `${height}%` }
  }

  return (
    <div className="space-y-2">
      <div className="max-h-[36rem] overflow-y-auto xl:max-h-none">
        <div className="relative" style={{ height: total * PX_PER_MINUTE, paddingLeft: GUTTER }}>
          <div className="absolute inset-y-0 left-0 text-[11px] tabular-nums text-muted-foreground" style={{ width: GUTTER }} aria-hidden="true">
            {hourMarks(dayStart, dayEnd).map((hour) => (
              <span key={hour} className="absolute -translate-y-1/2" style={{ top: place(hour, dayEnd).top }}>{hour}</span>
            ))}
          </div>
          <div
            role="group"
            aria-label="Agenda del día. Tocá una hora libre para empezar ahí."
            className="relative h-full cursor-pointer rounded-lg border bg-muted/20"
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect()
              onPick(timeAtPosition((event.clientY - rect.top) / rect.height, dayStart, dayEnd))
            }}
          >
            {hourMarks(dayStart, dayEnd).map((hour) => (
              <div key={hour} aria-hidden="true" className="pointer-events-none absolute inset-x-0 border-t" style={{ top: place(hour, dayEnd).top }} />
            ))}
            <ol className="contents" aria-label="Tramos ocupados">
              {busy.map((range) => (
                <li
                  key={`${range.start_time}-${range.end_time}-${range.kind}`}
                  className={cn('pointer-events-none absolute inset-x-1 overflow-hidden rounded-md px-2 py-1 text-xs font-semibold', blockTone(range))}
                  style={place(range.start_time, range.end_time)}
                >
                  {blockLabel(range)}
                  <span className="sr-only">, de {range.start_time} a {range.end_time}</span>
                </li>
              ))}
            </ol>
            {selection && (
              <div
                className={cn(
                  'pointer-events-none absolute inset-x-1 overflow-hidden rounded-md border-2 border-dashed px-2 py-1 text-xs font-semibold',
                  selection.conflict ? 'border-destructive bg-destructive/10 text-destructive-foreground' : 'border-brand bg-primary/10 text-brand',
                )}
                style={place(selection.start, selection.end)}
              >
                Tu selección · {selection.start} – {selection.end}{selection.conflict && ' · No disponible'}
              </div>
            )}
          </div>
        </div>
      </div>
      <p className="min-h-5 text-sm text-warning-foreground" role="status" aria-live="polite">{hint}</p>
    </div>
  )
}
