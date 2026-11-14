import { CalendarDays, CalendarX, Clock, Flag, MapPin, Sun, User } from 'lucide-react'
import { useState } from 'react'

import { useStudentSchedule } from '@/api/hooks/useStudentPortal'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { GlassStage, GlassSwitch, type GlassSwitchOption } from '@/components/student'
import { useNow } from '@/components/student/use-now'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { termLabel } from '@/lib/intensiveCoursesState'
import { countdownLabel, nextClassToday, type TodayClass } from '@/lib/studentHomeState'
import {
  activityLabel,
  emptyMessage,
  sourceBadge,
  teacherLabel,
  timeRange,
  upcomingNote,
  type ScheduleEntry,
  type StudentScheduleView,
} from '@/lib/studentScheduleState'
import { defaultScheduleMode, scheduleViewDays, scheduleViewEmpty, type ScheduleViewMode } from '@/lib/studentScheduleView'

const iconChip = 'grid size-6 shrink-0 place-items-center rounded-lg bg-student-accent-soft text-student-accent-text'

function EntryRow({ entry, state }: { entry: ScheduleEntry; state: TodayClass | null }) {
  const badge = sourceBadge(entry.source)
  return (
    <li className="sp-sched-row grid gap-2 p-4 text-sm sm:grid-cols-[9rem_1fr] sm:gap-4">
      <p className="flex items-center gap-2 font-medium tabular-nums">
        <span aria-hidden="true" className={iconChip}><Clock className="size-3.5" /></span>
        {timeRange(entry)}
      </p>
      <div className="min-w-0 space-y-1.5">
        <p className="flex flex-wrap items-center gap-2 font-medium text-foreground">
          {entry.subject_name}
          <span className="text-xs font-normal text-muted-foreground">{entry.subject_code}</span>
          {badge && <Badge variant={badge.variant} size="sm">{badge.label}</Badge>}
          {state && <Badge variant={state.state === 'in_progress' ? 'success' : 'info'} size="sm">{countdownLabel(state)}</Badge>}
        </p>
        <p className="text-muted-foreground">
          Grupo {entry.group_code} · {activityLabel(entry.activity_type)}
          {entry.source === 'intensivo' && ` · ${termLabel(entry.term_code)}`}
        </p>
        <p className="flex flex-wrap gap-x-4 gap-y-1.5 text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <span aria-hidden="true" className={iconChip}><MapPin className="size-3.5" /></span>{entry.classroom.name}
          </span>
          <span className="inline-flex items-center gap-2">
            <span aria-hidden="true" className={iconChip}><User className="size-3.5" /></span>{teacherLabel(entry.teacher_name)}
          </span>
        </p>
      </div>
    </li>
  )
}

export function StudentSchedulePage() {
  const view = useStudentSchedule()

  return (
    <>
      <PageHeader as="h1"
        title="Mi horario"
        description="Horario publicado de tu grupo, de las materias que recursás o tenés pendientes y de tus cursos de verano e invierno."
      />
      {view.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar tu horario.</AlertTitle></Alert>}
      {!view.isError && !view.data && (
        <div role="status" aria-label="Cargando horario" className="space-y-4">
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      )}
      {view.data && <ScheduleContent view={view.data} />}
    </>
  )
}

const PANEL_ID = 'schedule-panel'
const MODE_OPTIONS: GlassSwitchOption<ScheduleViewMode>[] = [
  { value: 'today', label: 'Hoy', icon: Sun, controls: PANEL_ID },
  { value: 'week', label: 'Semana', icon: CalendarDays, controls: PANEL_ID },
  { value: 'upcoming', label: 'Próximo', icon: Flag, controls: PANEL_ID },
]

function ScheduleContent({ view }: { view: StudentScheduleView }) {
  const { entries, unscheduled } = view
  const now = useNow()
  const [mode, setMode] = useState<ScheduleViewMode>(() => defaultScheduleMode(entries, new Date()))
  const days = scheduleViewDays(entries, mode, now)
  const message = days.length === 0 ? (mode === 'week' ? emptyMessage(view) : scheduleViewEmpty(mode)) : null
  const upcoming = upcomingNote(entries)
  // In Hoy the class in progress (or the next one) says how long is left.
  const current = mode === 'today' ? nextClassToday(entries, now).next : null

  return (
    <>
      <GlassStage wallpaper="aurora" className="sp-home-stage">
        <GlassSwitch id="schedule" label="Vista del horario" options={MODE_OPTIONS} value={mode} onChange={setMode} />
      </GlassStage>
      {upcoming && (
        <Alert variant="info" role="status">
          <AlertTitle>{upcoming}</AlertTitle>
          <AlertDescription>Este horario todavía no empezó a regir; puede cambiar hasta esa fecha.</AlertDescription>
        </Alert>
      )}
      <div id={PANEL_ID} role="tabpanel" aria-labelledby={`schedule-${mode}`} className="space-y-6">
        {message && <EmptyState illustration="empty-calendar" icon={CalendarX} title="Sin clases para mostrar" description={message} />}
        {days.map((day) => (
          <Card key={day.weekday}>
            <CardHeader><CardTitle className="text-base">{day.label}</CardTitle></CardHeader>
            <CardContent className="p-0">
              <ul className="divide-y">
                {day.entries.map((entry) => (
                  <EntryRow key={`${entry.source}-${entry.subject_code}-${entry.group_code}-${entry.weekday}-${entry.start_time}-${entry.activity_type}`}
                    entry={entry} state={current?.entry === entry ? current : null} />
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
        {mode === 'week' && unscheduled.length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-base">Cursos intensivos sin horario publicado</CardTitle></CardHeader>
            <CardContent className="p-0">
              <ul className="divide-y">
                {unscheduled.map((course) => (
                  <li key={`${course.term_code}-${course.subject_code}`} className="p-4 text-sm">
                    <p className="flex flex-wrap items-center gap-2 font-medium text-foreground">
                      {course.subject_name}
                      <span className="text-xs font-normal text-muted-foreground">{course.subject_code}</span>
                      <Badge variant="success" size="sm">Intensivo</Badge>
                    </p>
                    <p className="text-muted-foreground">{termLabel(course.term_code)} · El horario todavía no fue publicado.</p>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
