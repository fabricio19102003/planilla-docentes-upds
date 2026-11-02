import { useStudentSchedule } from '@/api/hooks/useStudentPortal'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { termLabel } from '@/lib/intensiveCoursesState'
import {
  activityLabel,
  emptyMessage,
  groupByWeekday,
  sourceBadge,
  teacherLabel,
  timeRange,
  upcomingNote,
  type ScheduleEntry,
} from '@/lib/studentScheduleState'

function EntryRow({ entry }: { entry: ScheduleEntry }) {
  const badge = sourceBadge(entry.source)
  return (
    <li className="grid gap-1 p-4 text-sm sm:grid-cols-[9rem_1fr] sm:gap-4">
      <p className="font-medium tabular-nums">{timeRange(entry)}</p>
      <div className="space-y-1">
        <p className="flex flex-wrap items-center gap-2 font-medium text-foreground">
          {entry.subject_name}
          <span className="text-xs font-normal text-muted-foreground">{entry.subject_code}</span>
          {badge && <Badge variant={badge.variant} size="sm">{badge.label}</Badge>}
        </p>
        <p className="text-muted-foreground">
          Grupo {entry.group_code} · {activityLabel(entry.activity_type)} · {entry.classroom.name}
          {entry.source === 'intensivo' && ` · ${termLabel(entry.term_code)}`}
        </p>
        <p className="text-muted-foreground">{teacherLabel(entry.teacher_name)}</p>
      </div>
    </li>
  )
}

export function StudentSchedulePage() {
  const view = useStudentSchedule()

  if (view.isError) return <Alert variant="error" role="alert"><AlertTitle>No se pudo cargar tu horario.</AlertTitle></Alert>
  if (!view.data) return <p role="status" className="text-sm text-muted-foreground">Cargando horario…</p>

  const { entries, unscheduled } = view.data
  const days = groupByWeekday(entries)
  const message = emptyMessage(view.data)
  const upcoming = upcomingNote(entries)

  return (
    <>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Mi horario</h1>
        <p className="text-sm text-muted-foreground">Horario publicado de tu grupo, de las materias que recursás o tenés pendientes y de tus cursos de verano e invierno.</p>
      </div>
      {upcoming && (
        <Alert variant="info" role="status">
          <AlertTitle>{upcoming}</AlertTitle>
          <AlertDescription>Este horario todavía no empezó a regir; puede cambiar hasta esa fecha.</AlertDescription>
        </Alert>
      )}
      {message && <Alert variant="info" role="status"><AlertTitle>{message}</AlertTitle></Alert>}
      {days.map((day) => (
        <Card key={day.weekday}>
          <CardHeader><CardTitle className="text-base">{day.label}</CardTitle></CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y">
              {day.entries.map((entry) => <EntryRow key={`${entry.source}-${entry.subject_code}-${entry.group_code}-${entry.weekday}-${entry.start_time}-${entry.activity_type}`} entry={entry} />)}
            </ul>
          </CardContent>
        </Card>
      ))}
      {unscheduled.length > 0 && (
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
    </>
  )
}
