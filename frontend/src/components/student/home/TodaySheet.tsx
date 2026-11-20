import { CalendarCheck, CalendarClock, Clock, MapPin, UserRound } from 'lucide-react'

import { useStudentSchedule } from '@/api/hooks/useStudentPortal'
import { Eyebrow, InfoTip, Meter, Sheet } from '@/components/student'
import { Skeleton } from '@/components/ui/skeleton'
import { countdownLabel, nextClassToday } from '@/lib/studentHomeState'
import { teacherLabel } from '@/lib/studentScheduleState'
import { useNow } from '../use-now'
import { classProgress, countdownParts } from './home-state'
import { LinkButton } from './LinkButton'

/** "Hoy" ink sheet: the next class as a countdown figure, its room and teacher, and the rest of the day. */
export function TodaySheet() {
  const schedule = useStudentSchedule()
  const now = useNow()
  const view = schedule.data
  const today = view ? nextClassToday(view.entries, now) : null
  const next = today?.next
  const parts = next ? countdownParts(next) : null

  return (
    <section aria-labelledby="sph-hoy">
      <Sheet depth={3} padding="md" className="sph-today">
        <Eyebrow>
          <span id="sph-hoy">Hoy · siguiente clase</span>
        </Eyebrow>
        {schedule.isError && (
          <div className="sph-state">
            <span aria-hidden="true" className="sph-state-icon"><CalendarClock /></span>
            <p>No se pudo cargar tu horario.</p>
          </div>
        )}
        {!schedule.isError && !view && (
          <div role="status" aria-label="Cargando tu horario de hoy" className="sph-today-skel">
            <Skeleton className="sph-skel-big" />
            <Skeleton className="sph-skel-line" />
            <Skeleton className="sph-skel-line sph-skel-line--short" />
          </div>
        )}
        {next && parts && (
          <>
            <p className="sph-countdown" aria-label={countdownLabel(next)}>
              <span aria-hidden="true" className="sp-figure sph-countdown-figure" data-size="xl">{parts.value}</span>
              <span aria-hidden="true" className="sph-countdown-unit">{parts.unit}</span>
              <span className="sph-countdown-caption">{countdownLabel(next)} · {parts.caption}</span>
            </p>
            <h3 className="sph-today-title">{next.entry.subject_name}</h3>
            <div className="sph-meta">
              <span className="sph-meta-item"><Clock aria-hidden="true" /><time>{next.entry.start_time}</time> – <time>{next.entry.end_time}</time></span>
              <InfoTip content={`Aula ${next.entry.classroom.name} (${next.entry.classroom.code}).`}>
                <span className="sph-meta-item" tabIndex={0}><MapPin aria-hidden="true" />{next.entry.classroom.name}</span>
              </InfoTip>
              <InfoTip content={`Docente a cargo: ${teacherLabel(next.entry.teacher_name)}.`}>
                <span className="sph-meta-item" tabIndex={0}><UserRound aria-hidden="true" />{teacherLabel(next.entry.teacher_name)}</span>
              </InfoTip>
            </div>
            {next.state === 'in_progress' && (
              <div className="sph-prog">
                <Meter value={classProgress(next)} label="Avance de la clase" valueText={`${classProgress(next)} % de la clase`} />
                <small><span>Empezó {next.entry.start_time}</span><span>Termina {next.entry.end_time}</span></small>
              </div>
            )}
            {today.later.length > 0 && (
              <ol className="sph-later" aria-label="Más clases de hoy">
                {today.later.map((entry) => (
                  <li key={`${entry.subject_code}-${entry.group_code}-${entry.start_time}`}>
                    <time>{entry.start_time}</time>
                    <span>{entry.subject_name} · {entry.classroom.name}</span>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
        {view && !next && (
          <div className="sph-state">
            <span aria-hidden="true" className="sph-state-icon"><CalendarCheck /></span>
            <p>
              {today?.total ? 'Ya terminaron tus clases de hoy.' : view.entries.length === 0 && view.status.message ? view.status.message : 'No tenés clases hoy.'}
            </p>
          </div>
        )}
        <LinkButton to="/estudiante/horario" variant="light">Ver mi horario</LinkButton>
      </Sheet>
    </section>
  )
}
