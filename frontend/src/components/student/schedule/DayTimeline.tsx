import { Check, Clock, MapPin, User } from 'lucide-react'
import type { CSSProperties } from 'react'

import { InfoTip, Sheet } from '@/components/student'
import { Badge } from '@/components/ui/badge'
import { buildDayTimeline, clockLabel, type DayBlock } from '@/lib/studentDayTimeline'
import { boliviaClock, countdownLabel, type TodayClass } from '@/lib/studentHomeState'
import { activityLabel, sourceBadge, teacherLabel, timeRange, type ScheduleEntry } from '@/lib/studentScheduleState'
import '@/styles/student/schedule.css'

const NOW_STATE_NOTE = {
  before: 'Todavía no empezaron tus clases de hoy.',
  after: 'Ya terminaron tus clases de hoy.',
} as const

function BlockBadge({ block, current }: { block: DayBlock<ScheduleEntry>; current: TodayClass | null }) {
  if (current?.entry === block.entry) {
    return <Badge variant={current.state === 'in_progress' ? 'success' : 'info'} className="sp-day-badge">{countdownLabel(current)}</Badge>
  }
  if (block.status === 'done') return <Badge variant="outline" className="sp-day-badge"><Check aria-hidden="true" />Finalizada</Badge>
  return null
}

function ClassBlock({ block, current }: { block: DayBlock<ScheduleEntry>; current: TodayClass | null }) {
  const { entry } = block
  const source = sourceBadge(entry.source)
  const style = { '--sp-top': `${block.top}px`, '--sp-h': `${block.height}px`, '--sp-lane': block.lane, '--sp-lanes': block.lanes } as CSSProperties
  return (
    <li
      className="sp-day-block"
      data-tone={block.tone}
      data-status={block.status}
      aria-current={block.status === 'now' ? 'time' : undefined}
      style={style}
    >
      <p className="sp-day-block-top">
        <span className="sp-day-time"><Clock aria-hidden="true" />{timeRange(entry)}</span>
        <BlockBadge block={block} current={current} />
      </p>
      <h3 className="sp-day-title">{entry.subject_name}</h3>
      <p className="sp-day-sub">
        {entry.subject_code} · Grupo {entry.group_code} · {activityLabel(entry.activity_type)}
        {source && <Badge variant={source.variant} className="sp-day-badge">{source.label}</Badge>}
      </p>
      <p className="sp-day-meta">
        <InfoTip content={`${entry.classroom.name} (código ${entry.classroom.code}).`} label={`Aula: ${entry.classroom.name}`}>
          <button type="button" className="sp-day-chip"><MapPin aria-hidden="true" />{entry.classroom.name}</button>
        </InfoTip>
        <InfoTip content={`Docente: ${teacherLabel(entry.teacher_name)}.`} label={`Docente: ${teacherLabel(entry.teacher_name)}`}>
          <button type="button" className="sp-day-chip"><User aria-hidden="true" />{teacherLabel(entry.teacher_name)}</button>
        </InfoTip>
      </p>
    </li>
  )
}

interface DayTimelineProps {
  /** Heading of the day, e.g. "Hoy · Lunes". */
  label: string
  /** The classes of the day, already filtered and sorted. */
  entries: ScheduleEntry[]
  now: Date
  /** The class in progress or the next one, to say how long is left. */
  current: TodayClass | null
}

/** The Horario "Hoy" sheet: an hourly axis, one block per class placed by time and colored by subject, and a "now" line. */
export function DayTimeline({ label, entries, now, current }: DayTimelineProps) {
  const timeline = buildDayTimeline(entries, boliviaClock(now).minutes)
  if (!timeline) return null
  const { blocks, ticks, now: position } = timeline
  const note = position && position.state !== 'within' ? NOW_STATE_NOTE[position.state] : null
  return (
    <Sheet as="section" depth={2} padding="none" className="sp-day-sheet">
      <header className="sp-day-head">
        <h2 className="sp-title-2">{label}</h2>
        <p className="sp-day-summary">
          {blocks.length} {blocks.length === 1 ? 'clase' : 'clases'} · de {clockLabel(timeline.startMinutes)} a {clockLabel(timeline.endMinutes)}
          {note && <span className="sp-day-note">{note}</span>}
        </p>
      </header>
      <div className="sp-day" style={{ height: timeline.height }}>
        {ticks.map((tick) => (
          <div key={tick.minutes} aria-hidden="true" className="sp-day-tick" style={{ '--sp-top': `${tick.top}px` } as CSSProperties}>
            <span>{tick.label}</span>
          </div>
        ))}
        <ol className="sp-day-blocks">
          {blocks.map((block) => (
            <ClassBlock key={`${block.entry.source}-${block.entry.subject_code}-${block.entry.group_code}-${block.entry.start_time}-${block.entry.activity_type}`} block={block} current={current} />
          ))}
        </ol>
        {position?.top != null && (
          <div aria-hidden="true" className="sp-day-now" style={{ '--sp-top': `${position.top}px` } as CSSProperties}>
            <span>Ahora {position.label}</span>
          </div>
        )}
      </div>
    </Sheet>
  )
}
