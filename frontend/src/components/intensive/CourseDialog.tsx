import { useState } from 'react'

import { useCurricula, useCurriculum } from '@/api/hooks/useAcademicRecords'
import { useSaveIntensiveCourse } from '@/api/hooks/useIntensiveCourses'
import { useTeachers } from '@/api/hooks/useTeachers'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogPanel, DialogPopup, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  courseFormFrom,
  courseFormProblem,
  coursePayload,
  courseUpdatePayload,
  emptyCourseForm,
  termLabel,
  type AdminIntensiveCourse,
  type CourseForm,
} from '@/lib/intensiveCoursesState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60'

export type CourseDialogTarget = { mode: 'create' } | { mode: 'edit'; course: AdminIntensiveCourse }

function CourseFormBody({ target, onClose }: { target: CourseDialogTarget; onClose: () => void }) {
  const editing = target.mode === 'edit'
  const [form, setForm] = useState<CourseForm>(() => (target.mode === 'edit' ? courseFormFrom(target.course) : emptyCourseForm()))
  const save = useSaveIntensiveCourse()
  const teachers = useTeachers({ perPage: 500 })
  const plans = useCurricula()
  const plan = useCurriculum(plans.data?.[0]?.id)
  const set = (patch: Partial<CourseForm>) => { save.reset(); setForm((current) => ({ ...current, ...patch })) }
  const slots = (plan.data?.semesters ?? []).flatMap((semester) => semester.subjects.filter((slot) => slot.code))
  const slot = slots.find((candidate) => candidate.code === form.subject_code)
  const problem = courseFormProblem(form, editing ? 'edit' : 'create')

  const submit = () => {
    if (problem) return
    const done = { onSuccess: onClose }
    if (target.mode === 'edit') save.mutate({ id: target.course.id, payload: courseUpdatePayload(form) }, done)
    else save.mutate({ payload: coursePayload(form) }, done)
  }
  const hours = (id: string, label: string, field: 'theory_hours' | 'practice_hours', fromCurriculum: number | undefined) => (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} inputMode="numeric" value={form[field]} placeholder={fromCurriculum === undefined ? '' : `Malla: ${fromCurriculum}`}
        onChange={(event) => set({ [field]: event.target.value })} />
    </div>
  )

  return (
    <form className="flex min-h-0 flex-1 flex-col" onSubmit={(event) => { event.preventDefault(); submit() }}>
      <DialogHeader>
        <DialogTitle>{editing ? 'Editar curso intensivo' : 'Abrir curso intensivo'}</DialogTitle>
        <DialogDescription>
          {editing
            ? `${termLabel(form.term_code)} · ${form.subject_code}. El período y la materia no se pueden cambiar.`
            : 'Los estudiantes con la materia reprobada o pendiente podrán inscribirse desde su portal mientras la inscripción esté abierta.'}
        </DialogDescription>
      </DialogHeader>
      <DialogPanel className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="course-term">Período</Label>
            <Input id="course-term" value={form.term_code} disabled={editing} placeholder="VER/2027"
              onChange={(event) => set({ term_code: event.target.value.toUpperCase() })} />
            <p className="mt-1 text-xs text-muted-foreground">VER = verano, INV = invierno, seguido del año.</p>
          </div>
          <div>
            <Label htmlFor="course-subject">Materia</Label>
            <select id="course-subject" className={selectClass} value={form.subject_code} disabled={editing}
              onChange={(event) => set({ subject_code: event.target.value })}>
              <option value="">{plan.isLoading ? 'Cargando materias…' : 'Elegí la materia'}</option>
              {editing && <option value={form.subject_code}>{form.subject_code}</option>}
              {slots.map((candidate) => <option key={candidate.id} value={candidate.code ?? ''}>{candidate.code} · {candidate.name}</option>)}
            </select>
          </div>
        </div>
        <div>
          <Label htmlFor="course-teacher">Docente</Label>
          <select id="course-teacher" className={selectClass} value={form.teacher_ci} onChange={(event) => set({ teacher_ci: event.target.value })}>
            <option value="">{teachers.isLoading ? 'Cargando docentes…' : 'Elegí el docente'}</option>
            {(teachers.data?.items ?? []).map((teacher) => <option key={teacher.ci} value={teacher.ci}>{teacher.full_name} ({teacher.ci})</option>)}
          </select>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="course-capacity">Cupos</Label>
            <Input id="course-capacity" inputMode="numeric" value={form.capacity} onChange={(event) => set({ capacity: event.target.value })} />
          </div>
          <div>
            <Label htmlFor="course-start">Inscripción desde</Label>
            <Input id="course-start" type="date" value={form.enrollment_starts_on} onChange={(event) => set({ enrollment_starts_on: event.target.value })} />
          </div>
          <div>
            <Label htmlFor="course-end">Inscripción hasta</Label>
            <Input id="course-end" type="date" value={form.enrollment_ends_on} onChange={(event) => set({ enrollment_ends_on: event.target.value })} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {hours('course-theory', 'Horas de teoría', 'theory_hours', slot?.theory_hours)}
          {hours('course-practice', 'Horas de práctica', 'practice_hours', slot?.practice_hours)}
        </div>
        {!editing && <p className="text-xs text-muted-foreground">Dejá las horas vacías para usar las de la malla curricular (HT y HP de la materia). Con ellas se calcula el pago docente y el precio.</p>}
        {problem && <p className="text-sm text-muted-foreground">{problem}</p>}
        {save.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(save.error, 'No se pudo guardar el curso.')}</AlertTitle></Alert>}
      </DialogPanel>
      <DialogFooter>
        <Button type="button" variant="outline" disabled={save.isPending} onClick={onClose}>Cancelar</Button>
        <Button type="submit" loading={save.isPending} disabled={problem !== null}>{editing ? 'Guardar cambios' : 'Abrir curso'}</Button>
      </DialogFooter>
    </form>
  )
}

/** Open a new intensive course or edit an open one; a null `target` closes the dialog. */
export function CourseDialog({ target, onClose }: { target: CourseDialogTarget | null; onClose: () => void }) {
  return (
    <Dialog open={target !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogPopup className="max-w-xl">
        {target && <CourseFormBody key={target.mode === 'edit' ? target.course.id : 'new'} target={target} onClose={onClose} />}
      </DialogPopup>
    </Dialog>
  )
}
