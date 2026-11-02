import { ArrowDown, ArrowUp, BookOpen, CalendarPlus, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useCurricula, useCurriculum, useEditCurriculum, useGenerateOfferings, useLoadDefaultCurriculum, type CurriculumChange } from '@/api/hooks/useAcademicRecords'
import { SlotDialog } from '@/components/curriculum/SlotDialog'
import { ConfirmAlertDialog, type ConfirmAlertSummary } from '@/components/shared/ConfirmAlertDialog'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CurriculumSlot } from '@/lib/academicRecordsState'
import { emptySlotForm, moveSlot, offeringSummary, type SlotForm } from '@/lib/curriculumEditing'
import { apiErrorMessage } from '@/lib/userCredentials'

function slotForm(slot: CurriculumSlot, semester: number): SlotForm {
  return {
    semester: String(semester), name: slot.name, code: slot.code ?? '', theory_hours: String(slot.theory_hours),
    practice_hours: String(slot.practice_hours), credits: String(slot.credits), is_elective: slot.is_elective,
  }
}

function OfferingsCard({ planId }: { planId: number }) {
  const [period, setPeriod] = useState('')
  const generate = useGenerateOfferings(planId)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Generar ofertas de un período</CardTitle>
        <CardDescription>Crea las ofertas con las materias, semestres y horas de esta malla. Las que ya existen no se tocan; después se ajustan en Gestión académica.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); generate.mutate(period.trim().toUpperCase()) }}>
          <div>
            <Label htmlFor="offerings-period">Período</Label>
            <Input id="offerings-period" value={period} placeholder="I/2027" onChange={(event) => setPeriod(event.target.value)} />
          </div>
          <Button type="submit" loading={generate.isPending} disabled={!period.trim()}><CalendarPlus aria-hidden="true" />Generar ofertas</Button>
        </form>
        {generate.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(generate.error, 'No se pudieron generar las ofertas. Usá el formato I/2027, II/2027, INV/2027 o VER/2027.')}</AlertTitle></Alert>}
        {generate.data && (
          <Alert variant="success" role="status">
            <AlertTitle>{offeringSummary(generate.data)}</AlertTitle>
            {generate.data.skipped.length > 0 && (
              <AlertDescription>
                No generadas: {generate.data.skipped.map((item) => `${item.name} (sem. ${item.semester}: ${item.reason})`).join(' · ')}
              </AlertDescription>
            )}
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

export function CurriculumPage() {
  const plans = useCurricula()
  const planId = plans.data?.[0]?.id
  const plan = useCurriculum(planId)
  const load = useLoadDefaultCurriculum()
  const edit = useEditCurriculum(planId)
  const [editing, setEditing] = useState(false)
  const [dialog, setDialog] = useState<{ form: SlotForm; slotId?: number } | null>(null)
  const [confirm, setConfirm] = useState<{ summary: ConfirmAlertSummary; change: CurriculumChange } | null>(null)
  const lastSemester = plan.data?.semesters.at(-1)

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
          <Button variant={editing ? 'default' : 'outline'} onClick={() => setEditing((on) => !on)}>
            <Pencil aria-hidden="true" />{editing ? 'Terminar edición' : 'Editar malla'}
          </Button>
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

      {plans.isLoading && <p role="status" className="text-sm text-muted-foreground">Cargando malla curricular…</p>}

      {plans.data && plans.data.length === 0 && (
        <EmptyState
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
          <OfferingsCard planId={plan.data.id} />
        </div>
      )}

      {plan.data && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {plan.data.semesters.map((semester) => {
            const credits = semester.subjects.reduce((sum, subject) => sum + subject.credits, 0)
            const hours = semester.subjects.reduce((sum, subject) => sum + subject.theory_hours + subject.practice_hours, 0)
            const ids = semester.subjects.map((subject) => subject.id)
            return (
              <Card key={semester.semester}>
                <CardHeader>
                  <CardTitle className="text-base">Semestre {semester.semester}</CardTitle>
                  <CardDescription>{semester.subjects.length} materias · {hours} horas · {credits} créditos</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y text-sm">
                    {semester.subjects.map((subject, index) => (
                      <li key={subject.id} className="flex items-start justify-between gap-3 py-2">
                        <div className="min-w-0">
                          <p className="font-medium text-foreground">{subject.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {subject.is_elective ? <Badge variant="info" size="sm">Electiva</Badge> : subject.code}
                            {subject.is_elective && subject.code && <span className="ml-1">{subject.code}</span>}
                          </p>
                        </div>
                        {editing ? (
                          <div className="flex shrink-0 gap-1">
                            <Button size="icon-sm" variant="ghost" aria-label={`Subir ${subject.name}`} disabled={index === 0 || edit.isPending}
                              onClick={() => apply({ kind: 'reorder', semester: semester.semester, slotIds: moveSlot(ids, subject.id, 'up') })}><ArrowUp aria-hidden="true" /></Button>
                            <Button size="icon-sm" variant="ghost" aria-label={`Bajar ${subject.name}`} disabled={index === ids.length - 1 || edit.isPending}
                              onClick={() => apply({ kind: 'reorder', semester: semester.semester, slotIds: moveSlot(ids, subject.id, 'down') })}><ArrowDown aria-hidden="true" /></Button>
                            <Button size="icon-sm" variant="ghost" aria-label={`Editar ${subject.name}`}
                              onClick={() => { edit.reset(); setDialog({ form: slotForm(subject, semester.semester), slotId: subject.id }) }}><Pencil aria-hidden="true" /></Button>
                            <Button size="icon-sm" variant="ghost" aria-label={`Quitar ${subject.name}`}
                              onClick={() => setConfirm({
                                summary: {
                                  title: 'Quitar materia de la malla', confirmLabel: 'Quitar', tone: 'destructive',
                                  rows: [{ label: 'Materia', value: `${subject.name}${subject.code ? ` (${subject.code})` : ''}` }, { label: 'Semestre', value: String(semester.semester) }],
                                  consequence: 'Deja de ofrecerse y de contarse para la rematrícula. El historial de los estudiantes no se borra.',
                                },
                                change: { kind: 'remove', slotId: subject.id },
                              })}><Trash2 aria-hidden="true" /></Button>
                          </div>
                        ) : (
                          <p className="shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                            HT {subject.theory_hours} · HP {subject.practice_hours}<br />{subject.credits} créditos
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                  {editing && (
                    <Button size="sm" variant="outline" className="mt-3" onClick={() => { edit.reset(); setDialog({ form: emptySlotForm(semester.semester) }) }}>
                      <Plus aria-hidden="true" />Agregar materia
                    </Button>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

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
