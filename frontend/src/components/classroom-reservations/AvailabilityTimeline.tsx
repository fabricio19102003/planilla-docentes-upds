import { daySegments, timelinePosition, toMinutes, type DaySegment } from '@/lib/classroomReservations'
import { cn } from '@/lib/utils'

/** 1.2 px per minute keeps a 45-minute period tall enough to read its label. */
const PX_PER_MINUTE = 1.2
const MIN_LABEL_MINUTES = 30

export interface TimelineSelection {
  start: string
  end: string
  conflict: boolean
}

interface AvailabilityTimelineProps {
  busy: Parameters<typeof daySegments>[0]
  dayStart: string
  dayEnd: string
  selection: TimelineSelection | null
}

function hourMarks(dayStart: string, dayEnd: string): number[] {
  const first = Math.ceil((toMinutes(dayStart) ?? 0) / 60)
  const last = Math.floor((toMinutes(dayEnd) ?? 0) / 60)
  return Array.from({ length: Math.max(last - first + 1, 0) }, (_, index) => first + index)
}

function segmentLabel(segment: DaySegment): { title: string; detail: string | null } {
  if (segment.type === 'free') return { title: 'Disponible', detail: null }
  const { busy } = segment
  const title = busy.kind === 'reservation' && busy.mine ? 'Tu reserva' : busy.label
  return { title, detail: busy.kind === 'class' ? busy.detail : null }
}

function segmentTone(segment: DaySegment): string {
  if (segment.type === 'free') return 'border-success/30 bg-success/8 text-success-foreground'
  if (segment.busy.kind === 'class') return 'border-destructive/30 bg-destructive/10 text-destructive-foreground'
  return segment.busy.mine
    ? 'border-info/40 bg-info/12 text-info-foreground'
    : 'border-warning/40 bg-warning/12 text-warning-foreground'
}

export function AvailabilityTimeline({ busy, dayStart, dayEnd, selection }: AvailabilityTimelineProps) {
  const totalMinutes = (toMinutes(dayEnd) ?? 0) - (toMinutes(dayStart) ?? 0)
  const segments = daySegments(busy, dayStart, dayEnd)

  return (
    <div className="flex gap-3" data-testid="availability-timeline">
      <div className="relative w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground" style={{ height: totalMinutes * PX_PER_MINUTE }} aria-hidden="true">
        {hourMarks(dayStart, dayEnd).map((hour) => (
          <span
            key={hour}
            className="absolute right-0 -translate-y-1/2"
            style={{ top: `${timelinePosition(`${String(hour).padStart(2, '0')}:00`, dayEnd, dayStart, dayEnd).top}%` }}
          >
            {String(hour).padStart(2, '0')}:00
          </span>
        ))}
      </div>

      <ol className="relative min-w-0 flex-1 rounded-lg border bg-muted/20" style={{ height: totalMinutes * PX_PER_MINUTE }} aria-label="Disponibilidad del día">
        {segments.map((segment) => {
          const { top, height } = timelinePosition(segment.start, segment.end, dayStart, dayEnd)
          const { title, detail } = segmentLabel(segment)
          const minutes = (toMinutes(segment.end) ?? 0) - (toMinutes(segment.start) ?? 0)
          return (
            <li
              key={`${segment.type}-${segment.start}-${segment.end}`}
              className={cn('absolute inset-x-0 overflow-hidden border-y px-3 text-sm', segmentTone(segment))}
              style={{ top: `${top}%`, height: `${height}%` }}
            >
              <div className={cn('flex flex-wrap items-baseline gap-x-2', minutes >= MIN_LABEL_MINUTES ? 'pt-1' : 'hidden')}>
                <span className="font-medium">{title}</span>
                {detail && <span className="truncate text-xs opacity-80">{detail}</span>}
                <span className="text-xs tabular-nums opacity-80">{segment.start} – {segment.end}</span>
              </div>
            </li>
          )
        })}

        {selection && (
          <div
            aria-hidden="true"
            className={cn(
              'pointer-events-none absolute inset-x-1 rounded-md border-2 border-dashed',
              selection.conflict ? 'border-destructive bg-destructive/10' : 'border-primary bg-primary/10',
            )}
            style={(() => {
              const { top, height } = timelinePosition(selection.start, selection.end, dayStart, dayEnd)
              return { top: `${top}%`, height: `${height}%` }
            })()}
          />
        )}
      </ol>
    </div>
  )
}
