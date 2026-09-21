import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { DragDropProvider, DragOverlay, useDraggable, useDroppable } from '@dnd-kit/react'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/react'
import { Archive, CalendarDays, GripVertical, Pencil, Plus, Trash2 } from 'lucide-react'

import { useAcademicCollection } from '@/api/hooks/useAcademicManagement'
import {
  useArchiveScheduleDraft,
  useCloneSchedulePublication,
  useCompatibleScheduleTeachers,
  useDeleteScheduleBlock,
  usePreviewSchedulePublication,
  usePublishScheduleDraft,
  useSaveScheduleBlock,
  useSaveScheduleAssignment,
  useSaveScheduleDraft,
  useScheduleAssignmentHistories,
  useScheduleBlocks,
  useScheduleDrafts,
  useSchedulePublications,
  useScheduleWorkload,
} from '@/api/hooks/useSchedulePlanner'
import type {
  AcademicScheduleAssignment,
  AcademicScheduleBlock,
  ScheduleActivityType,
  ScheduleWeekday,
  SubjectOffering,
} from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  addMinutes,
  assignmentForReferenceDate,
  assignmentPayload,
  EMPTY_SCHEDULE_BLOCK,
  parseScheduleCellId,
  publicationDiffItems,
  replacementWarning,
  scheduleBlockPayload,
  scheduleCellId,
  SCHEDULE_END_TIMES,
  SCHEDULE_TIMES,
  SCHEDULE_WEEKDAYS,
} from '@/lib/schedulePlannerState'
import type { ScheduleBlockForm } from '@/lib/schedulePlannerState'

const errorMessage = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: string | Array<{ msg: string }> } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  if (error instanceof Error) return error.message
  return 'No se pudo completar la operación. Revise los datos e intente nuevamente.'
}

type OfferingDragData = { offeringId: number; activityType: ScheduleActivityType; label: string }

function OfferingCard({
  offering,
  activityType,
  disabled,
  onAdd,
}: {
  offering: SubjectOffering
  activityType: ScheduleActivityType
  disabled: boolean
  onAdd: () => void
}) {
  const label = `${offering.subject.code} · ${activityType === 'theory' ? 'Teoría' : 'Práctica'}`
  const { ref, isDragging } = useDraggable<OfferingDragData>({
    id: `offering-${offering.id}-${activityType}`,
    data: { offeringId: offering.id, activityType, label },
    disabled,
  })
  return (
    <article className={`rounded-lg border bg-white p-3 ${isDragging ? 'opacity-40' : ''}`}>
      <div className="flex items-start gap-2">
        <button
          ref={ref}
          type="button"
          disabled={disabled}
          className="mt-0.5 rounded p-1 text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label={`Arrastrar ${label} al horario`}
        >
          <GripVertical aria-hidden="true" size={18} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">{offering.subject.name}</p>
          <p className="text-xs text-slate-500">{label} · Semestre {offering.semester}</p>
        </div>
      </div>
      <Button type="button" variant="outline" size="sm" className="mt-3 w-full" disabled={disabled} onClick={onAdd}>
        Agregar al horario
      </Button>
    </article>
  )
}

function ScheduleCell({
  weekday,
  time,
  blocks,
  disabled,
  currentAssignments,
  onEdit,
  onDelete,
  onAssign,
  onHistory,
}: {
  weekday: ScheduleWeekday
  time: string
  blocks: AcademicScheduleBlock[]
  disabled: boolean
  currentAssignments: Record<number, AcademicScheduleAssignment | null>
  onEdit: (block: AcademicScheduleBlock) => void
  onDelete: (block: AcademicScheduleBlock) => void
  onAssign: (block: AcademicScheduleBlock) => void
  onHistory: (block: AcademicScheduleBlock) => void
}) {
  const { ref, isDropTarget } = useDroppable({ id: scheduleCellId(weekday, time), disabled })
  return (
    <td
      ref={ref}
      className={`h-16 min-w-40 border-l border-t p-1 align-top transition-colors ${isDropTarget ? 'bg-sky-100 ring-2 ring-inset ring-sky-600' : 'bg-white'}`}
      aria-label={`${SCHEDULE_WEEKDAYS.find((day) => day.value === weekday)?.label}, ${time}`}
    >
      {blocks.map((block) => (
        <div key={block.id} className="rounded-md border border-sky-200 bg-sky-50 p-2 text-xs text-slate-800">
          <p className="font-semibold">{block.offering.subject.code} · {block.group.code}</p>
          <p>{block.start_time.slice(0, 5)}–{block.end_time.slice(0, 5)} · {block.classroom.code}</p>
          <p className="mt-1 font-medium text-sky-900">
            {currentAssignments[block.id]?.teacher_name ?? 'Sin docente asignado'}
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            <button type="button" onClick={() => onAssign(block)} disabled={disabled} className="rounded border border-sky-300 px-1.5 py-1 font-medium hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
              {currentAssignments[block.id] ? 'Reemplazar' : 'Asignar'}
            </button>
            <button type="button" onClick={() => onHistory(block)} className="rounded border border-slate-300 px-1.5 py-1 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
              Historial
            </button>
            <button type="button" onClick={() => onEdit(block)} disabled={disabled} className="rounded p-1 hover:bg-sky-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600" aria-label={`Editar bloque ${block.offering.subject.code}`}>
              <Pencil aria-hidden="true" size={14} />
            </button>
            <button type="button" onClick={() => onDelete(block)} disabled={disabled} className="rounded p-1 text-red-700 hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600" aria-label={`Eliminar bloque ${block.offering.subject.code}`}>
              <Trash2 aria-hidden="true" size={14} />
            </button>
          </div>
        </div>
      ))}
    </td>
  )
}

export function SchedulePlannerPage() {
  const programs = useAcademicCollection('programs')
  const offerings = useAcademicCollection('offerings')
  const groups = useAcademicCollection('groups')
  const classrooms = useAcademicCollection('classrooms')
  const drafts = useScheduleDrafts()
  const saveDraft = useSaveScheduleDraft()
  const archiveDraft = useArchiveScheduleDraft()
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null)
  const effectiveDraftId = selectedDraftId ?? drafts.data?.[0]?.id ?? null
  const selectedDraft = drafts.data?.find((draft) => draft.id === effectiveDraftId) ?? null
  const blocks = useScheduleBlocks(effectiveDraftId)
  const blockIds = blocks.data?.map((block) => block.id) ?? []
  const assignmentHistories = useScheduleAssignmentHistories(effectiveDraftId, blockIds)
  const saveBlock = useSaveScheduleBlock(effectiveDraftId)
  const deleteBlock = useDeleteScheduleBlock(effectiveDraftId)
  const [referenceDate, setReferenceDate] = useState(() => new Date().toISOString().slice(0, 10))
  const workload = useScheduleWorkload(effectiveDraftId, referenceDate)
  const publications = useSchedulePublications()
  const previewPublication = usePreviewSchedulePublication(effectiveDraftId)
  const publishDraft = usePublishScheduleDraft(effectiveDraftId)
  const clonePublication = useCloneSchedulePublication()
  const [draftOpen, setDraftOpen] = useState(false)
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null)
  const [draftForm, setDraftForm] = useState({ program_id: '', academic_period: '', name: '' })
  const [blockOpen, setBlockOpen] = useState(false)
  const [editingBlock, setEditingBlock] = useState<AcademicScheduleBlock | null>(null)
  const [blockForm, setBlockForm] = useState<ScheduleBlockForm>(EMPTY_SCHEDULE_BLOCK)
  const [assignmentBlock, setAssignmentBlock] = useState<AcademicScheduleBlock | null>(null)
  const [assignmentOpen, setAssignmentOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [publicationOpen, setPublicationOpen] = useState(false)
  const [publicationHistoryOpen, setPublicationHistoryOpen] = useState(false)
  const [publicationEffectiveFrom, setPublicationEffectiveFrom] = useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [selectedPublicationId, setSelectedPublicationId] = useState<number | null>(null)
  const [cloneName, setCloneName] = useState('')
  const publishConfirmRef = useRef<HTMLButtonElement>(null)
  const [teacherSearch, setTeacherSearch] = useState('')
  const [teacherPage, setTeacherPage] = useState(1)
  const [assignmentForm, setAssignmentForm] = useState({
    teacher_ci: '', effective_from: referenceDate, effective_to: '',
  })
  const compatibleTeachers = useCompatibleScheduleTeachers(
    effectiveDraftId,
    assignmentOpen ? assignmentBlock?.id ?? null : null,
    assignmentForm.effective_from,
    assignmentForm.effective_to,
    teacherSearch,
    teacherPage,
  )
  const saveAssignment = useSaveScheduleAssignment(effectiveDraftId, assignmentBlock?.id ?? null)
  const [error, setError] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [dragLabel, setDragLabel] = useState<string | null>(null)

  const editable = selectedDraft?.status === 'draft'
  const scopedOfferings = useMemo(() => offerings.data?.filter((item) =>
    item.active && item.program_id === selectedDraft?.program_id && item.academic_period === selectedDraft?.academic_period
  ) ?? [], [offerings.data, selectedDraft])
  const scopedGroups = groups.data?.filter((item) =>
    item.active && item.program_id === selectedDraft?.program_id && item.academic_period === selectedDraft?.academic_period
  ) ?? []
  const activeClassrooms = classrooms.data?.filter((item) => item.active) ?? []
  const currentAssignments = Object.fromEntries(blockIds.map((blockId) => [
    blockId,
    assignmentForReferenceDate(assignmentHistories.data[blockId] ?? [], referenceDate),
  ])) as Record<number, AcademicScheduleAssignment | null>

  const openAssignment = (block: AcademicScheduleBlock) => {
    setAssignmentBlock(block)
    setAssignmentForm({ teacher_ci: '', effective_from: referenceDate, effective_to: '' })
    setTeacherSearch('')
    setTeacherPage(1)
    setError(null)
    setAssignmentOpen(true)
  }

  const openHistory = (block: AcademicScheduleBlock) => {
    setAssignmentBlock(block)
    setHistoryOpen(true)
  }

  const openBlockForm = (
    offeringId: number,
    activityType: ScheduleActivityType,
    target?: { weekday: ScheduleWeekday; start_time: string },
  ) => {
    const offering = scopedOfferings.find((item) => item.id === offeringId)
    const firstGroup = scopedGroups.find((item) => item.semester === offering?.semester)
    setEditingBlock(null)
    setBlockForm({
      ...EMPTY_SCHEDULE_BLOCK,
      offering_id: String(offeringId),
      activity_type: activityType,
      group_id: firstGroup ? String(firstGroup.id) : '',
      classroom_id: activeClassrooms[0] ? String(activeClassrooms[0].id) : '',
      weekday: target?.weekday ?? 'monday',
      start_time: target?.start_time ?? '07:00',
      end_time: addMinutes(target?.start_time ?? '07:00', 60),
    })
    setError(null)
    setBlockOpen(true)
  }

  const editBlock = (block: AcademicScheduleBlock) => {
    setEditingBlock(block)
    setBlockForm({
      offering_id: String(block.offering_id), group_id: String(block.group_id),
      classroom_id: String(block.classroom_id), activity_type: block.activity_type,
      weekday: block.weekday, start_time: block.start_time.slice(0, 5), end_time: block.end_time.slice(0, 5),
    })
    setError(null)
    setBlockOpen(true)
  }

  const handleDragStart = (event: DragStartEvent) => {
    const data = event.operation.source?.data as OfferingDragData | undefined
    setDragLabel(data?.label ?? null)
    setAnnouncement(data ? `Moviendo ${data.label}. Use las flechas para elegir una celda y presione Enter para soltar.` : '')
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const data = event.operation.source?.data as OfferingDragData | undefined
    const target = event.operation.target ? parseScheduleCellId(String(event.operation.target.id)) : null
    setDragLabel(null)
    if (!event.canceled && data && target) {
      openBlockForm(data.offeringId, data.activityType, target)
      setAnnouncement(`${data.label} seleccionado para ${target.weekday} a las ${target.start_time}. Complete los datos del bloque.`)
    } else {
      setAnnouncement('Movimiento cancelado.')
    }
  }

  const submitDraft = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const created = await saveDraft.mutateAsync({ id: editingDraftId ?? undefined, payload: {
        program_id: Number(draftForm.program_id), academic_period: draftForm.academic_period, name: draftForm.name,
      } })
      setSelectedDraftId(created.id)
      setDraftOpen(false)
    } catch (caught) { setError(errorMessage(caught)) }
  }

  const submitBlock = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await saveBlock.mutateAsync({ id: editingBlock?.id, payload: scheduleBlockPayload(blockForm) })
      setBlockOpen(false)
    } catch (caught) { setError(errorMessage(caught)) }
  }

  const submitAssignment = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!assignmentBlock) return
    const replacesExisting = Boolean(assignmentForReferenceDate(
      assignmentHistories.data[assignmentBlock.id] ?? [], assignmentForm.effective_from,
    ))
    try {
      await saveAssignment.mutateAsync({
        replace: replacesExisting,
        payload: assignmentPayload(
          assignmentForm.teacher_ci,
          assignmentForm.effective_from,
          assignmentForm.effective_to,
        ),
      })
      setAssignmentOpen(false)
    } catch (caught) { setError(errorMessage(caught)) }
  }

  const removeBlock = async (block: AcademicScheduleBlock) => {
    setError(null)
    try { await deleteBlock.mutateAsync(block.id) } catch (caught) { setError(errorMessage(caught)) }
  }

  const queryError = drafts.isError || offerings.isError || groups.isError || classrooms.isError || blocks.isError || assignmentHistories.isError
  const loading = drafts.isLoading || offerings.isLoading || groups.isLoading || classrooms.isLoading
  const selectedHistory = assignmentBlock ? assignmentHistories.data[assignmentBlock.id] ?? [] : []
  const assignmentAtEffectiveDate = assignmentForReferenceDate(
    selectedHistory, assignmentForm.effective_from,
  )
  const compatiblePageCount = Math.max(1, Math.ceil((compatibleTeachers.data?.total ?? 0) / 20))
  const selectedPublication = publications.data?.find(
    (publication) => publication.id === selectedPublicationId,
  ) ?? publications.data?.[0] ?? null

  useEffect(() => {
    if (previewPublication.data?.can_publish) publishConfirmRef.current?.focus()
  }, [previewPublication.data])

  const openPublicationReview = () => {
    previewPublication.reset()
    setError(null)
    setPublicationOpen(true)
  }

  const publishReviewedDraft = async () => {
    if (!previewPublication.data) return
    setError(null)
    try {
      const publication = await publishDraft.mutateAsync({
        effectiveFrom: publicationEffectiveFrom,
        digest: previewPublication.data.digest,
      })
      setSelectedPublicationId(publication.id)
      setPublicationOpen(false)
    } catch (caught) { setError(errorMessage(caught)) }
  }

  const cloneSelectedPublication = async () => {
    if (!selectedPublication) return
    setError(null)
    try {
      const draft = await clonePublication.mutateAsync({
        publicationId: selectedPublication.id, name: cloneName,
      })
      setSelectedDraftId(draft.id)
      setCloneName('')
      setPublicationHistoryOpen(false)
    } catch (caught) { setError(errorMessage(caught)) }
  }

  return (
    <DragDropProvider onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <main className="flex flex-col gap-6 p-4 sm:p-6" aria-labelledby="schedule-planner-title">
        <span className="sr-only" aria-live="assertive">{announcement}</span>
        <header className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-sky-700"><CalendarDays size={17} />Gestión académica</div>
            <h1 id="schedule-planner-title" className="text-2xl font-bold text-slate-950">Planificador de horarios</h1>
            <p className="mt-1 text-sm text-slate-600">Organice borradores semanales de lunes a sábado, entre 07:00 y 22:00.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => { setError(null); setPublicationHistoryOpen(true) }}>
              Historial de publicaciones
            </Button>
            {editable && <Button variant="outline" onClick={openPublicationReview}>Revisar publicación</Button>}
            <Button onClick={() => { setEditingDraftId(null); setDraftForm({ program_id: '', academic_period: '', name: '' }); setError(null); setDraftOpen(true) }}>
              <Plus aria-hidden="true" />Nuevo borrador
            </Button>
          </div>
        </header>

        <div role="note" className="rounded-md border-2 border-amber-400 bg-amber-50 p-4 text-sm font-medium text-amber-950">
          No despliegue esta publicación sola en producción. La integración de asistencia regular permanece en modo de lectura; práctica, planillas, contratos y facturación todavía usan el origen heredado.
        </div>

        {error && !blockOpen && !draftOpen && !assignmentOpen && !publicationOpen && !publicationHistoryOpen && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {loading && <p role="status" className="rounded-md border bg-slate-50 p-3 text-sm text-slate-600">Cargando planificador…</p>}
        {queryError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">No se pudo cargar la información del planificador.</p>}

        {!loading && !queryError && (
          <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="flex flex-col gap-4">
              <div className="rounded-xl border bg-white p-4">
                <Label htmlFor="schedule-draft">Borrador activo</Label>
                <select id="schedule-draft" value={effectiveDraftId ?? ''} onChange={(event) => setSelectedDraftId(event.target.value ? Number(event.target.value) : null)} className="mt-2 h-10 w-full rounded-md border px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
                  <option value="">Seleccione un borrador</option>
                  {drafts.data?.map((draft) => <option key={draft.id} value={draft.id}>{draft.name} · {draft.academic_period}</option>)}
                </select>
                {selectedDraft && (
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <Badge variant={editable ? 'default' : 'secondary'}>
                      {selectedDraft.status === 'draft' ? 'Borrador' : selectedDraft.status === 'published' ? 'Publicado e inmutable' : 'Archivado'}
                    </Badge>
                    {editable && <div className="flex gap-1"><Button size="sm" variant="outline" onClick={() => { setEditingDraftId(selectedDraft.id); setDraftForm({ program_id: String(selectedDraft.program_id), academic_period: selectedDraft.academic_period, name: selectedDraft.name }); setError(null); setDraftOpen(true) }}><Pencil aria-hidden="true" />Editar</Button><Button size="sm" variant="outline" onClick={() => void archiveDraft.mutateAsync(selectedDraft.id).catch((caught) => setError(errorMessage(caught)))}><Archive aria-hidden="true" />Archivar</Button></div>}
                  </div>
                )}
              </div>
              <div className="rounded-xl border bg-white p-4">
                <Label htmlFor="schedule-reference-date">Fecha de referencia</Label>
                <Input
                  id="schedule-reference-date"
                  type="date"
                  value={referenceDate}
                  onChange={(event) => setReferenceDate(event.target.value)}
                  className="mt-2"
                />
                <p className="mt-2 text-xs text-slate-500">Define qué docente y carga semanal se muestran.</p>
                {assignmentHistories.isLoading && <p role="status" className="mt-2 text-xs text-slate-500">Cargando asignaciones…</p>}
              </div>
              <div className="rounded-xl border bg-slate-50 p-4">
                <h2 className="font-semibold text-slate-900">Actividades disponibles</h2>
                <p className="mb-3 mt-1 text-xs text-slate-500">Arrastre una actividad o use “Agregar al horario”.</p>
                <div className="flex flex-col gap-2">
                  {scopedOfferings.flatMap((offering) => (['theory', 'practice'] as const)
                    .filter((type) => (type === 'theory' ? offering.theory_hours : offering.practice_hours) > 0)
                    .map((type) => <OfferingCard key={`${offering.id}-${type}`} offering={offering} activityType={type} disabled={!editable} onAdd={() => openBlockForm(offering.id, type)} />))}
                  {selectedDraft && !scopedOfferings.length && <p className="text-sm text-slate-500">No hay ofertas activas para este programa y período.</p>}
                  {!selectedDraft && <p className="text-sm text-slate-500">Seleccione o cree un borrador para comenzar.</p>}
                </div>
              </div>
              <div className="rounded-xl border bg-white p-4" aria-labelledby="workload-title">
                <h2 id="workload-title" className="font-semibold text-slate-900">Carga docente semanal</h2>
                {workload.isLoading && <p role="status" className="mt-2 text-sm text-slate-500">Cargando carga docente…</p>}
                {workload.isError && <p role="alert" className="mt-2 text-sm text-red-700">No se pudo cargar la vista previa.</p>}
                {!workload.isLoading && !workload.isError && !workload.data?.items.length && <p className="mt-2 text-sm text-slate-500">No hay asignaciones vigentes en esta fecha.</p>}
                <ul className="mt-3 flex flex-col gap-2">
                  {workload.data?.items.map((item) => <li key={item.teacher_ci} className="rounded-md bg-slate-50 p-2 text-xs">
                    <p className="font-semibold text-slate-800">{item.teacher_name}</p>
                    <p className="text-slate-600">Teoría {item.theory_minutes_week / 60} h · Práctica {item.practice_minutes_week / 60} h · Total {item.total_minutes_week / 60} h</p>
                  </li>)}
                </ul>
              </div>
            </aside>

            <section aria-labelledby="weekly-grid-title" className="min-w-0">
              <h2 id="weekly-grid-title" className="sr-only">Horario semanal</h2>
              {blocks.isLoading && <p role="status" className="rounded-md border bg-slate-50 p-3 text-sm text-slate-600">Cargando bloques…</p>}
              {selectedDraft && !blocks.isLoading ? (
                <div className="max-h-[70vh] overflow-auto rounded-xl border bg-white">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="sticky top-0 z-10 bg-slate-100 text-slate-700">
                      <tr><th scope="col" className="min-w-20 p-3">Hora</th>{SCHEDULE_WEEKDAYS.map((day) => <th key={day.value} scope="col" className="min-w-40 border-l p-3">{day.label}</th>)}</tr>
                    </thead>
                    <tbody>
                      {SCHEDULE_TIMES.map((time) => <tr key={time}>
                        <th scope="row" className="border-t bg-slate-50 p-2 align-top font-medium text-slate-600">{time}</th>
                        {SCHEDULE_WEEKDAYS.map((day) => <ScheduleCell key={day.value} weekday={day.value} time={time} disabled={!editable} blocks={blocks.data?.filter((block) => block.weekday === day.value && block.start_time.slice(0, 5) === time) ?? []} currentAssignments={currentAssignments} onAssign={openAssignment} onHistory={openHistory} onEdit={editBlock} onDelete={(block) => void removeBlock(block)} />)}
                      </tr>)}
                    </tbody>
                  </table>
                </div>
              ) : !blocks.isLoading && <div className="rounded-xl border border-dashed bg-white p-12 text-center text-sm text-slate-500">Seleccione un borrador para ver la semana.</div>}
            </section>
          </section>
        )}

        <Dialog open={draftOpen} onOpenChange={setDraftOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>{editingDraftId ? 'Editar borrador' : 'Nuevo borrador'}</DialogTitle><DialogDescription>Defina el programa, período y un nombre descriptivo.</DialogDescription></DialogHeader>
            <form onSubmit={submitDraft} className="flex flex-col gap-4">
              <div><Label htmlFor="draft-program">Programa</Label><select id="draft-program" required value={draftForm.program_id} onChange={(event) => setDraftForm((value) => ({ ...value, program_id: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3"><option value="">Seleccione</option>{programs.data?.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></div>
              <div><Label htmlFor="draft-period">Período académico</Label><Input id="draft-period" required maxLength={30} value={draftForm.academic_period} onChange={(event) => setDraftForm((value) => ({ ...value, academic_period: event.target.value }))} /></div>
              <div><Label htmlFor="draft-name">Nombre</Label><Input id="draft-name" required maxLength={120} value={draftForm.name} onChange={(event) => setDraftForm((value) => ({ ...value, name: event.target.value }))} /></div>
              {error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
              <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setDraftOpen(false)}>Cancelar</Button><Button type="submit" disabled={saveDraft.isPending}>{saveDraft.isPending ? 'Guardando…' : editingDraftId ? 'Guardar cambios' : 'Crear borrador'}</Button></div>
            </form>
          </DialogContent>
        </Dialog>

        <Dialog open={blockOpen} onOpenChange={setBlockOpen}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
            <DialogHeader><DialogTitle>{editingBlock ? 'Editar bloque' : 'Agregar bloque'}</DialogTitle><DialogDescription>Los horarios usan intervalos de 30 minutos.</DialogDescription></DialogHeader>
            <form onSubmit={submitBlock} className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2"><Label htmlFor="block-offering">Oferta académica</Label><select id="block-offering" required value={blockForm.offering_id} onChange={(event) => setBlockForm((value) => ({ ...value, offering_id: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3"><option value="">Seleccione</option>{scopedOfferings.map((item) => <option key={item.id} value={item.id}>{item.subject.code} · {item.subject.name}</option>)}</select></div>
              <div><Label htmlFor="block-group">Grupo</Label><select id="block-group" required value={blockForm.group_id} onChange={(event) => setBlockForm((value) => ({ ...value, group_id: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3"><option value="">Seleccione</option>{scopedGroups.map((item) => <option key={item.id} value={item.id}>{item.code} · Semestre {item.semester}</option>)}</select></div>
              <div><Label htmlFor="block-classroom">Aula</Label><select id="block-classroom" required value={blockForm.classroom_id} onChange={(event) => setBlockForm((value) => ({ ...value, classroom_id: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3"><option value="">Seleccione</option>{activeClassrooms.map((item) => <option key={item.id} value={item.id}>{item.code} · Cap. {item.capacity}</option>)}</select></div>
              <div><Label htmlFor="block-activity">Actividad</Label><select id="block-activity" value={blockForm.activity_type} onChange={(event) => setBlockForm((value) => ({ ...value, activity_type: event.target.value as ScheduleActivityType }))} className="mt-1 h-10 w-full rounded-md border px-3"><option value="theory">Teoría</option><option value="practice">Práctica</option></select></div>
              <div><Label htmlFor="block-day">Día</Label><select id="block-day" value={blockForm.weekday} onChange={(event) => setBlockForm((value) => ({ ...value, weekday: event.target.value as ScheduleWeekday }))} className="mt-1 h-10 w-full rounded-md border px-3">{SCHEDULE_WEEKDAYS.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}</select></div>
              <div><Label htmlFor="block-start">Inicio</Label><select id="block-start" value={blockForm.start_time} onChange={(event) => setBlockForm((value) => ({ ...value, start_time: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3">{SCHEDULE_TIMES.map((time) => <option key={time}>{time}</option>)}</select></div>
              <div><Label htmlFor="block-end">Fin</Label><select id="block-end" value={blockForm.end_time} onChange={(event) => setBlockForm((value) => ({ ...value, end_time: event.target.value }))} className="mt-1 h-10 w-full rounded-md border px-3">{SCHEDULE_END_TIMES.map((time) => <option key={time}>{time}</option>)}</select></div>
              {error && <p role="alert" className="sm:col-span-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
              <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={() => setBlockOpen(false)}>Cancelar</Button><Button type="submit" disabled={saveBlock.isPending}>{saveBlock.isPending ? 'Guardando…' : 'Guardar bloque'}</Button></div>
            </form>
          </DialogContent>
        </Dialog>

        <Dialog open={assignmentOpen} onOpenChange={setAssignmentOpen}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>{assignmentAtEffectiveDate ? 'Reemplazar docente' : 'Asignar docente'}</DialogTitle>
              <DialogDescription>
                {assignmentBlock ? `${assignmentBlock.offering.subject.name} · ${assignmentBlock.group.code}` : 'Seleccione un bloque.'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={submitAssignment} className="flex flex-col gap-4" aria-busy={saveAssignment.isPending}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="assignment-from">Vigente desde</Label>
                  <Input
                    id="assignment-from"
                    type="date"
                    required
                    value={assignmentForm.effective_from}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'assignment-error' : undefined}
                    onChange={(event) => { setAssignmentForm((value) => ({ ...value, effective_from: event.target.value })); setTeacherPage(1) }}
                  />
                </div>
                <div>
                  <Label htmlFor="assignment-to">Vigente hasta (opcional)</Label>
                  <Input
                    id="assignment-to"
                    type="date"
                    min={assignmentForm.effective_from}
                    value={assignmentForm.effective_to}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'assignment-error' : undefined}
                    onChange={(event) => { setAssignmentForm((value) => ({ ...value, effective_to: event.target.value })); setTeacherPage(1) }}
                  />
                </div>
              </div>
              {assignmentAtEffectiveDate && (
                <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  Reemplazará a {assignmentAtEffectiveDate.teacher_name}. {replacementWarning(assignmentForm.effective_from)}
                </p>
              )}
              <div>
                <Label htmlFor="compatible-teacher-search">Buscar docente compatible</Label>
                <Input
                  id="compatible-teacher-search"
                  maxLength={120}
                  value={teacherSearch}
                  placeholder="Nombre o CI"
                  onChange={(event) => { setTeacherSearch(event.target.value); setTeacherPage(1) }}
                />
              </div>
              {compatibleTeachers.isLoading && <p role="status" className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">Buscando docentes con disponibilidad…</p>}
              {compatibleTeachers.isError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">No se pudieron consultar los docentes compatibles.</p>}
              {!compatibleTeachers.isLoading && !compatibleTeachers.isError && compatibleTeachers.data?.items.length === 0 && (
                <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  No existe un docente con disponibilidad completa y sin cruces para este bloque e intervalo.
                </p>
              )}
              {compatibleTeachers.data && compatibleTeachers.data.items.length > 0 && (
                <div>
                  <Label htmlFor="assignment-teacher">Docente</Label>
                  <select
                    id="assignment-teacher"
                    required
                    value={assignmentForm.teacher_ci}
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'assignment-error' : undefined}
                    onChange={(event) => setAssignmentForm((value) => ({ ...value, teacher_ci: event.target.value }))}
                    className="mt-1 h-10 w-full rounded-md border px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600"
                  >
                    <option value="">Seleccione un docente</option>
                    {compatibleTeachers.data.items.map((teacher) => <option key={teacher.ci} value={teacher.ci}>{teacher.full_name} · {teacher.ci}</option>)}
                  </select>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                    <Button type="button" size="sm" variant="outline" disabled={teacherPage <= 1} onClick={() => setTeacherPage((page) => page - 1)}>Anterior</Button>
                    <span>Página {teacherPage} de {compatiblePageCount}</span>
                    <Button type="button" size="sm" variant="outline" disabled={teacherPage >= compatiblePageCount} onClick={() => setTeacherPage((page) => page + 1)}>Siguiente</Button>
                  </div>
                </div>
              )}
              {error && <p id="assignment-error" role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setAssignmentOpen(false)}>Cancelar</Button>
                <Button type="submit" disabled={saveAssignment.isPending || !assignmentForm.teacher_ci || compatibleTeachers.isLoading}>
                  {saveAssignment.isPending ? 'Guardando…' : assignmentAtEffectiveDate ? 'Confirmar reemplazo' : 'Asignar docente'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>

        <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Historial de asignaciones</DialogTitle>
              <DialogDescription>
                {assignmentBlock ? `${assignmentBlock.offering.subject.name} · ${assignmentBlock.group.code}` : 'Bloque seleccionado'}
              </DialogDescription>
            </DialogHeader>
            {assignmentHistories.isLoading ? (
              <p role="status" className="rounded-md bg-slate-50 p-4 text-sm text-slate-600">Cargando historial…</p>
            ) : !selectedHistory.length ? (
              <p className="rounded-md bg-slate-50 p-4 text-sm text-slate-600">Este bloque todavía no tiene asignaciones.</p>
            ) : (
              <ol className="flex flex-col gap-2">
                {selectedHistory.map((assignment) => <li key={assignment.id} className="rounded-md border p-3 text-sm">
                  <p className="font-semibold text-slate-900">{assignment.teacher_name}</p>
                  <p className="text-slate-600">{assignment.effective_from} — {assignment.effective_to ?? 'Sin fecha final'}</p>
                </li>)}
              </ol>
            )}
          </DialogContent>
        </Dialog>

        <Dialog open={publicationOpen} onOpenChange={setPublicationOpen}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Revisar publicación completa</DialogTitle>
              <DialogDescription>
                La vista previa valida y sella todo el borrador. No se publican bloques individuales.
              </DialogDescription>
            </DialogHeader>
            <form
              className="flex flex-col gap-4"
              aria-busy={previewPublication.isPending || publishDraft.isPending}
              onSubmit={(event) => {
                event.preventDefault()
                setError(null)
                previewPublication.mutate(publicationEffectiveFrom, {
                  onError: (caught) => setError(errorMessage(caught)),
                })
              }}
            >
              <div>
                <Label htmlFor="publication-effective-from">Fecha efectiva</Label>
                <Input
                  id="publication-effective-from"
                  type="date"
                  required
                  autoFocus
                  value={publicationEffectiveFrom}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'publication-error' : 'publication-effective-help'}
                  onChange={(event) => {
                    setPublicationEffectiveFrom(event.target.value)
                    previewPublication.reset()
                  }}
                />
                <p id="publication-effective-help" className="mt-1 text-xs text-slate-500">
                  Las fechas retroactivas se bloquean cuando ya existen datos operativos afectados.
                </p>
              </div>
              <Button type="submit" variant="outline" disabled={previewPublication.isPending || !publicationEffectiveFrom}>
                {previewPublication.isPending ? 'Validando…' : 'Generar vista previa vinculante'}
              </Button>
              {previewPublication.isError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">No se pudo generar la vista previa.</p>}
              {previewPublication.data && (
                <section aria-labelledby="publication-preview-title" className="flex flex-col gap-4 rounded-lg border p-4">
                  <div>
                    <h3 id="publication-preview-title" className="font-semibold text-slate-950">Resumen sellado</h3>
                    <p className="text-sm text-slate-600">
                      Secuencia {previewPublication.data.sequence} · {previewPublication.data.block_count} bloques · {previewPublication.data.assignment_count} intervalos docentes
                    </p>
                    <p className="mt-1 break-all font-mono text-xs text-slate-500">Digest: {previewPublication.data.digest}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                    {publicationDiffItems(previewPublication.data.diff).map((item) => (
                      <p key={item.key} className={`rounded p-2 ${item.className}`}>
                        {item.label}: <strong>{item.value}</strong>
                      </p>
                    ))}
                  </div>
                  {previewPublication.data.diff.workload_changes.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold">Cambios de carga semanal</h4>
                      <ul className="mt-2 flex flex-col gap-1 text-sm">
                        {previewPublication.data.diff.workload_changes.map((item) => <li key={item.teacher_ci}>
                          {item.teacher_name}: {item.total_minutes_week > 0 ? '+' : ''}{item.total_minutes_week} min
                        </li>)}
                      </ul>
                    </div>
                  )}
                  {previewPublication.data.blockers.length > 0 && (
                    <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                      <h4 className="font-semibold">Publicación bloqueada</h4>
                      <ul className="mt-2 list-disc pl-5">
                        {previewPublication.data.blockers.map((blocker) => <li key={`${blocker.category}-${blocker.message}`}>
                          {blocker.message} ({blocker.count})
                        </li>)}
                      </ul>
                    </div>
                  )}
                  <div role="note" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
                    <h4 className="font-semibold">Límite operativo</h4>
                    <ul className="mt-2 list-disc pl-5">
                      {previewPublication.data.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                    </ul>
                  </div>
                </section>
              )}
              {error && <p id="publication-error" role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setPublicationOpen(false)}>Cancelar</Button>
                {previewPublication.data?.can_publish && (
                  <Button
                    ref={publishConfirmRef}
                    type="button"
                    disabled={publishDraft.isPending}
                    onClick={() => void publishReviewedDraft()}
                  >
                    {publishDraft.isPending ? 'Publicando…' : 'Publicar borrador completo'}
                  </Button>
                )}
              </div>
            </form>
          </DialogContent>
        </Dialog>

        <Dialog open={publicationHistoryOpen} onOpenChange={setPublicationHistoryOpen}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle>Historial de publicaciones</DialogTitle>
              <DialogDescription>Las revisiones publicadas son inmutables.</DialogDescription>
            </DialogHeader>
            {publications.isLoading && <p role="status" className="rounded-md bg-slate-50 p-3 text-sm">Cargando publicaciones…</p>}
            {publications.isError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">No se pudo cargar el historial.</p>}
            {!publications.isLoading && !publications.isError && !publications.data?.length && (
              <p className="rounded-md bg-slate-50 p-4 text-sm text-slate-600">Todavía no existen publicaciones.</p>
            )}
            {publications.data && publications.data.length > 0 && (
              <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
                <nav aria-label="Revisiones publicadas">
                  <ul className="flex flex-col gap-2">
                    {publications.data.map((publication) => <li key={publication.id}>
                      <button
                        type="button"
                        aria-pressed={selectedPublication?.id === publication.id}
                        onClick={() => setSelectedPublicationId(publication.id)}
                        className="w-full rounded-md border p-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 aria-pressed:border-sky-500 aria-pressed:bg-sky-50"
                      >
                        <span className="block font-semibold">{publication.academic_period}</span>
                        <span className="text-slate-600">{publication.effective_from} · Rev. {publication.sequence}</span>
                      </button>
                    </li>)}
                  </ul>
                </nav>
                {selectedPublication && (
                  <section aria-labelledby="publication-detail-title" className="rounded-lg border p-4">
                    <h3 id="publication-detail-title" className="font-semibold">Detalle inmutable</h3>
                    <p className="mt-1 text-sm text-slate-600">{selectedPublication.blocks.length} bloques · Fuente #{selectedPublication.source_draft_id}</p>
                    <p className="mt-1 break-all font-mono text-xs text-slate-500">{selectedPublication.content_digest}</p>
                    <ul className="mt-4 flex max-h-56 flex-col gap-2 overflow-y-auto">
                      {selectedPublication.blocks.map((block) => <li key={block.id} className="rounded-md bg-slate-50 p-3 text-sm">
                        <p className="font-semibold">{block.subject_code} · {block.group_code}</p>
                        <p>{block.weekday} {block.start_time.slice(0, 5)}–{block.end_time.slice(0, 5)} · {block.classroom_code}</p>
                        <p className="text-slate-600">{block.assignments.map((item) => item.teacher_name).join(' → ')}</p>
                      </li>)}
                    </ul>
                    <div className="mt-4">
                      <Label htmlFor="clone-publication-name">Nombre del nuevo borrador</Label>
                      <Input
                        id="clone-publication-name"
                        required
                        maxLength={120}
                        value={cloneName}
                        aria-invalid={Boolean(error)}
                        aria-describedby={error ? 'clone-error' : undefined}
                        onChange={(event) => setCloneName(event.target.value)}
                      />
                      {error && <p id="clone-error" role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
                      <Button className="mt-3" type="button" disabled={!cloneName.trim() || clonePublication.isPending} onClick={() => void cloneSelectedPublication()}>
                        {clonePublication.isPending ? 'Clonando…' : 'Clonar como borrador editable'}
                      </Button>
                    </div>
                  </section>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
      <DragOverlay>{dragLabel ? <div className="rounded-lg border border-sky-300 bg-white px-4 py-3 text-sm font-semibold shadow-lg">{dragLabel}</div> : null}</DragOverlay>
    </DragDropProvider>
  )
}
