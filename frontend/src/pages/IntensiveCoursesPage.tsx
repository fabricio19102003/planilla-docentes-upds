import { CalendarPlus, Sun } from 'lucide-react'
import { useState } from 'react'

import { useIntensiveCourses, useIntensiveSettings } from '@/api/hooks/useIntensiveCourses'
import { CourseDialog, type CourseDialogTarget } from '@/components/intensive/CourseDialog'
import { CourseSheet } from '@/components/intensive/CourseSheet'
import { SettingsCard } from '@/components/intensive/SettingsCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatShortDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import {
  courseStatus,
  priceLabel,
  seatsLabel,
  type CourseFilters,
  type CourseStatusValue,
} from '@/lib/intensiveCoursesState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function IntensiveCoursesPage() {
  const settings = useIntensiveSettings()
  const [filters, setFilters] = useState<CourseFilters>({ term_code: '', status: '' })
  const courses = useIntensiveCourses(filters)
  const [dialog, setDialog] = useState<CourseDialogTarget | null>(null)
  const [openCourse, setOpenCourse] = useState<number | null>(null)
  const today = getTodayInBolivia()
  const configured = settings.data?.is_configured === true
  const list = courses.data ?? []

  return (
    <div className="space-y-5">
      <PageHeader
        title="Cursos intensivos"
        description="Cursos de verano e invierno para recursar o completar materias pendientes. Abrí el curso, los estudiantes se inscriben desde su portal y al cerrar la inscripción el precio queda fijo."
        actions={(
          <Button disabled={!configured} onClick={() => setDialog({ mode: 'create' })}>
            <CalendarPlus aria-hidden="true" />Abrir curso
          </Button>
        )}
      />
      {settings.data && !configured && (
        <Alert variant="warning"><AlertTitle>Configurá los montos de cursos intensivos para poder abrir un curso.</AlertTitle></Alert>
      )}
      <SettingsCard />

      <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2" role="search">
        <div>
          <Label htmlFor="course-filter-term">Período</Label>
          <Input id="course-filter-term" value={filters.term_code} placeholder="VER/2027"
            onChange={(event) => setFilters((current) => ({ ...current, term_code: event.target.value.toUpperCase() }))} />
        </div>
        <div>
          <Label htmlFor="course-filter-status">Estado</Label>
          <select id="course-filter-status" className={selectClass} value={filters.status}
            onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value as CourseStatusValue | '' }))}>
            <option value="">Todos</option>
            <option value="open">Abiertos</option>
            <option value="closed">Cerrados</option>
          </select>
        </div>
      </div>

      {courses.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(courses.error, 'No se pudieron cargar los cursos.')}</AlertTitle></Alert>}
      {courses.data && list.length === 0 ? (
        <EmptyState illustration="empty-search" icon={Sun} title="No hay cursos intensivos con estos filtros" description="Abrí un curso de verano o invierno para que los estudiantes puedan inscribirse desde su portal." />
      ) : (
        <TableCard tableClassName="min-w-[960px]">
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-4">Materia</TableHead>
              <TableHead className="px-4">Docente</TableHead>
              <TableHead className="px-4">Período</TableHead>
              <TableHead className="px-4">Inscritos</TableHead>
              <TableHead className="px-4">Precio</TableHead>
              <TableHead className="px-4">Inscripción</TableHead>
              <TableHead className="px-4">Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!courses.data && !courses.isError && <TableRow><TableCell colSpan={7} role="status" className="px-4 py-10 text-center text-muted-foreground">Cargando cursos…</TableCell></TableRow>}
            {list.map((course) => {
              const status = courseStatus(course, today)
              return (
                <TableRow key={course.id} className="cursor-pointer" onClick={() => setOpenCourse(course.id)}>
                  <TableCell className="px-4 py-3">
                    <button type="button" className="text-left font-medium text-foreground underline-offset-4 hover:underline" onClick={() => setOpenCourse(course.id)}>{course.subject.name}</button>
                    <p className="text-xs text-muted-foreground">{course.subject.code}</p>
                  </TableCell>
                  <TableCell className="px-4 py-3">{course.teacher.full_name}</TableCell>
                  <TableCell className="px-4 py-3">{course.term_code}</TableCell>
                  <TableCell className="px-4 py-3 tabular-nums">{seatsLabel(course)}{course.is_full && <Badge variant="warning" size="sm" className="ml-2">Lleno</Badge>}</TableCell>
                  <TableCell className="px-4 py-3">{priceLabel(course.price)}</TableCell>
                  <TableCell className="px-4 py-3">{formatShortDateInBolivia(course.enrollment_starts_on)} al {formatShortDateInBolivia(course.enrollment_ends_on)}</TableCell>
                  <TableCell className="px-4 py-3"><Badge variant={status.variant}>{status.label}</Badge></TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </TableCard>
      )}

      <CourseSheet courseId={openCourse} onClose={() => setOpenCourse(null)} onEdit={(course) => setDialog({ mode: 'edit', course })} />
      <CourseDialog target={dialog} onClose={() => setDialog(null)} />
    </div>
  )
}
