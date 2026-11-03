import { BookOpen, CalendarPlus, Clock, GraduationCap, Pencil, Plus, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useCurricula, useCurriculum, useEditCurriculum, useLoadDefaultCurriculum, type CurriculumChange } from '@/api/hooks/useAcademicRecords'
import { OfferingsDialog } from '@/components/curriculum/OfferingsDialog'
import { SemesterColumn } from '@/components/curriculum/SemesterColumn'
import { SlotDialog } from '@/components/curriculum/SlotDialog'
import { SubjectCard } from '@/components/curriculum/SubjectCard'
import { CountUp } from '@/components/shared/CountUp'
import { ConfirmAlertDialog, type ConfirmAlertSummary } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { CurriculumSlot } from '@/lib/academicRecordsState'
import { semesterTone } from '@/lib/academicTones'
import { emptySlotForm, moveSlot, type SlotForm } from '@/lib/curriculumEditing'
import { summarizePlan } from '@/lib/curriculumSummary'
import { apiErrorMessage } from '@/lib/userCredentials'

function slotForm(slot: CurriculumSlot, semester: number): SlotForm {
  return {
    semester: String(semester), name: slot.name, code: slot.code ?? '', theory_hours: String(slot.theory_hours),
    practice_hours: String(slot.practice_hours), credits: String(slot.credits), is_elective: slot.is_elective,
  }
}

export function CurriculumPage() {
  const plans = useCurricula()
  const planId = plans.data?.[0]?.id
  const plan = useCurriculum(planId)
  const load = useLoadDefaultCurriculum()
  const edit = useEditCurriculum(planId)
  const [editing, setEditing] = useState(false)
  const [offeringsOpen, setOfferingsOpen] = useState(false)
  const [dialog, setDialog] = useState<{ form: SlotForm; slotId?: number } | null>(null)
  const [confirm, setConfirm] = useState<{ summary: ConfirmAlertSummary; change: CurriculumChange } | null>(null)
  const lastSemester = plan.data?.semesters.at(-1)
  const summary = plan.data ? summarizePlan(plan.data) : null

  const apply = (change: CurriculumChange) => edit.mutate(change, { onSuccess: () => { setDialog(null); setConfirm(null) } })

  const loadButton = (
    <Button onClick={() => load.mutate()} disabled={load.isPending}>
      {load.isPending ? 'Cargando…' : 'Cargar malla Medicina 510-01'}
    </Button>
  )

  return (
    <div className="space-y-5">
      <PageHeader
        title="Malla curricular"
        description={plan.data ? `${plan.data.name} · ${plan.data.total_semesters} semestres` : 'Materias de cada semestre con su carga horaria y créditos.'}
        actions={plan.data && (
          <>
            {editing && (
              <Button variant="outline" onClick={() => setOfferingsOpen(true)}>
                <CalendarPlus aria-hidden="true" />Generar ofertas
              </Button>
            )}
            <Button variant={editing ? 'default' : 'outline'} onClick={() => setEditing((on) => !on)}>
              <Pencil aria-hidden="true" />{editing ? 'Terminar edición' : 'Editar malla'}
            </Button>
          </>
        )}
      />

      {(plans.isError || plan.isError) && (
        <Alert variant="error" role="alert">
          <AlertTitle>No se pudo cargar la malla curricular.</AlertTitle>
          <AlertDescription><Button size="sm" variant="outline" onClick={() => void plans.refetch()}>Reintentar</Button></AlertDescription>
        </Alert>
      )}
      {load.isError && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(load.error, 'No se pudo cargar la malla.')}</AlertTitle></Alert>
      )}
      {edit.isError && !dialog && (
        <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(edit.error, 'No se pudo modificar la malla.')}</AlertTitle></Alert>
      )}

      {(plans.isLoading || (planId !== undefined && plan.isLoading)) && (
        <div role="status" className="space-y-5">
          <span className="sr-only">Cargando malla curricular…</span>
          <div aria-hidden="true" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
          </div>
          <div aria-hidden="true" className="flex gap-4 overflow-hidden">
            {Array.from({ length: 4 }, (_, column) => (
              <div key={column} className="w-[85vw] shrink-0 space-y-3 rounded-2xl border bg-muted/40 p-3 sm:w-72">
                <div className="flex items-center gap-3">
                  <Skeleton className="size-9 rounded-xl" />
                  <div className="flex-1 space-y-1.5"><Skeleton className="h-4 w-24" /><Skeleton className="h-3 w-36" /></div>
                </div>
                {Array.from({ length: 3 }, (_, card) => <Skeleton key={card} className="h-24 rounded-lg" />)}
              </div>
            ))}
          </div>
        </div>
      )}

      {plans.data && plans.data.length === 0 && (
        <EmptyState illustration="empty-document"
          icon={BookOpen}
          title="Todavía no hay una malla cargada"
          description="Cargá la malla de Medicina 510-01. También se carga sola la primera vez que importás el historial académico."
          action={loadButton}
        />
      )}

      {plan.data && editing && (
        <div className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>Los cambios aplican a la malla vigente para todos los estudiantes (semestre a cursar, recursados y materias fuera de malla). Quitar una materia no borra el historial de nadie.</AlertDescription>
          </Alert>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={edit.isPending} onClick={() => apply({ kind: 'add-semester' })}><Plus aria-hidden="true" />Agregar semestre</Button>
            {lastSemester && lastSemester.subjects.length === 0 && (
              <Button variant="outline" disabled={edit.isPending} onClick={() => apply({ kind: 'remove-semester', semester: lastSemester.semester })}>
                <Trash2 aria-hidden="true" />Quitar semestre {lastSemester.semester} (vacío)
              </Button>
            )}
          </div>
        </div>
      )}

      {plan.data && summary && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatCard icon={BookOpen} tone="primary" title="Materias" value={<CountUp value={summary.subjects} />}
              hint={`En ${plan.data.semesters.length} semestres`} />
            <StatCard icon={Clock} tone="cyan" title="Horas" value={<CountUp value={summary.hours} />}
              hint={`${summary.theoryHours.toLocaleString('es-BO')} teoría · ${summary.practiceHours.toLocaleString('es-BO')} práctica`} />
            <StatCard icon={GraduationCap} tone="success" title="Créditos" value={<CountUp value={summary.credits} />}
              hint="Total de la carrera" />
            <StatCard icon={Sparkles} tone="violet" title="Electivas" value={<CountUp value={summary.electives} />}
              hint={summary.electives === 1 ? 'Materia electiva' : 'Materias electivas'} />
          </div>

          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Leyenda del tablero">
            <li className="flex items-center gap-1.5"><span aria-hidden="true" className="h-1.5 w-4 rounded-full bg-primary" />Horas teóricas</li>
            <li className="flex items-center gap-1.5"><span aria-hidden="true" className="h-1.5 w-4 rounded-full bg-success" />Horas prácticas</li>
            <li className="flex items-center gap-1.5"><StatusBadge tone="violet">Electiva</StatusBadge></li>
            <li>cr = créditos</li>
          </ul>

          <div role="region" aria-label="Tablero de semestres" tabIndex={0}
            className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-3 outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {plan.data.semesters.map((semester, position) => {
              const ids = semester.subjects.map((subject) => subject.id)
              const tone = semesterTone(semester.semester)
              return (
                <SemesterColumn key={semester.semester} totals={summary.semesters[position]}
                  onAdd={editing ? () => { edit.reset(); setDialog({ form: emptySlotForm(semester.semester) }) } : undefined}>
                  {semester.subjects.map((subject, index) => (
                    <SubjectCard key={subject.id} subject={subject} tone={tone} actions={editing ? {
                      canMoveUp: index > 0,
                      canMoveDown: index < ids.length - 1,
                      pending: edit.isPending,
                      onMove: (direction) => apply({ kind: 'reorder', semester: semester.semester, slotIds: moveSlot(ids, subject.id, direction) }),
                      onEdit: () => { edit.reset(); setDialog({ form: slotForm(subject, semester.semester), slotId: subject.id }) },
                      onRemove: () => setConfirm({
                        summary: {
                          title: 'Quitar materia de la malla', confirmLabel: 'Quitar', tone: 'destructive',
                          rows: [{ label: 'Materia', value: `${subject.name}${subject.code ? ` (${subject.code})` : ''}` }, { label: 'Semestre', value: String(semester.semester) }],
                          consequence: 'Deja de ofrecerse y de contarse para la rematrícula. El historial de los estudiantes no se borra.',
                        },
                        change: { kind: 'remove', slotId: subject.id },
                      }),
                    } : undefined} />
                  ))}
                </SemesterColumn>
              )
            })}
          </div>
        </>
      )}

      {plan.data && <OfferingsDialog planId={plan.data.id} open={offeringsOpen} onOpenChange={setOfferingsOpen} />}

      <SlotDialog
        initial={dialog?.form ?? null}
        title={dialog?.slotId ? 'Editar materia' : 'Agregar materia'}
        totalSemesters={plan.data?.total_semesters ?? 1}
        pending={edit.isPending}
        error={edit.isError ? apiErrorMessage(edit.error, 'No se pudo guardar la materia.') : null}
        onSave={(payload) => apply(dialog?.slotId ? { kind: 'update', slotId: dialog.slotId, payload } : { kind: 'add', payload })}
        onClose={() => setDialog(null)}
      />
      <ConfirmAlertDialog summary={confirm?.summary ?? null} pending={edit.isPending}
        onConfirm={() => confirm && apply(confirm.change)} onCancel={() => setConfirm(null)} />
    </div>
  )
}
