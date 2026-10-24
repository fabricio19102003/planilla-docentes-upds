import { useState } from 'react'
import { useAllRequests, useRespondRequest } from '@/api/hooks/useAuth'
import { usePlanillaDetail, usePlanillaStatus, useTeacherDesignations } from '@/api/hooks/usePlanilla'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import type { Tone } from '@/components/shared/tones'
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Field, FieldLabel } from '@/components/ui/field'
import { AlertCircle, Check, X, Filter, Eye, Inbox } from 'lucide-react'
import type { DetailRequestInfo } from '@/api/types'
import { ResolutionSnapshotPanel } from '@/components/requests/ResolutionSnapshotPanel'
import { selectAdminRequestEvidence } from '@/lib/adminRequestResolution'

type StatusFilter = 'all' | 'pending' | 'approved' | 'rejected'

const REQUEST_TYPE_LABELS: Record<string, string> = {
  biometric_detail: 'Detalle Biométrico',
  hours_summary: 'Resumen de Horas',
  schedule_detail: 'Detalle de Horario',
}

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

const STATUS_TONE: Record<string, Tone> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'destructive',
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  approved: 'Aprobada',
  rejected: 'Rechazada',
}

function RequestStatusBadge({ status }: { status: string }) {
  return <StatusBadge tone={STATUS_TONE[status] ?? 'neutral'}>{STATUS_LABEL[status] ?? status}</StatusBadge>
}

function RequestDetailDialog({
  request,
  onClose,
}: {
  request: DetailRequestInfo | null
  onClose: () => void
}) {
  const shouldLoadLiveContext = request?.status === 'pending'
  // Live data is decision support only while the request is pending.
  const { data: reqPlanillaStatus } = usePlanillaStatus(
    request?.month ?? 0,
    request?.year ?? 0,
    Boolean(request) && shouldLoadLiveContext,
  )
  const reqDiscountMode = (reqPlanillaStatus?.discount_mode === 'attendance' || reqPlanillaStatus?.discount_mode === 'full')
    ? reqPlanillaStatus.discount_mode
    : 'attendance'

  // Load planilla detail for this teacher's billing info
  const { data: planillaDetail } = usePlanillaDetail(
    request?.month ?? 0,
    request?.year ?? 0,
    Boolean(request) && shouldLoadLiveContext,
    undefined,
    undefined,
    reqDiscountMode,
  )

  // Load teacher designations with schedule info
  const { data: teacherSchedule } = useTeacherDesignations(
    request?.teacher_ci ?? '',
    Boolean(request) && shouldLoadLiveContext,
  )

  const teacherBilling = planillaDetail?.teacher_totals?.find(
    t => t.teacher_ci === request?.teacher_ci,
  )
  const teacherDesignations = planillaDetail?.detail?.filter(
    d => d.teacher_ci === request?.teacher_ci,
  )

  if (!request) return null
  const evidence = selectAdminRequestEvidence(request, {
    billing: teacherBilling,
    designations: teacherDesignations,
    schedule: teacherSchedule,
  })

  return (
    <Dialog open={Boolean(request)} onOpenChange={onClose}>
      <DialogPopup className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Detalle de Solicitud</DialogTitle>
        </DialogHeader>
        <DialogPanel className="space-y-4">
          {/* Request info */}
          <div className="bg-muted/40 rounded-lg p-3 space-y-1.5 text-sm">
            <p>
              <span className="text-muted-foreground">Docente:</span>{' '}
              <span className="font-medium">{request.teacher_name ?? request.teacher_ci}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Solicitud:</span>{' '}
              <span className="font-medium">
                {REQUEST_TYPE_LABELS[request.request_type] ?? request.request_type}
              </span>
            </p>
            <p>
              <span className="text-muted-foreground">Período:</span>{' '}
              <span className="font-medium">{MONTH_NAMES[request.month]} {request.year}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Fecha:</span>{' '}
              <span className="font-medium">{new Date(request.created_at).toLocaleDateString('es-BO')}</span>
            </p>
          </div>

          {/* Docente's message */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Mensaje del docente</p>
            <div className="bg-white border border-border rounded-lg p-3 text-sm text-foreground">
              {request.message || <span className="text-muted-foreground italic">Sin mensaje</span>}
            </div>
          </div>

          {/* Admin response */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Respuesta del administrador</p>
            {request.admin_response ? (
              <div className={`border rounded-lg p-3 text-sm ${
                request.status === 'approved'
                  ? 'bg-success/4 border-success/32 text-success-foreground'
                  : request.status === 'rejected'
                  ? 'bg-destructive/4 border-destructive/32 text-destructive-foreground'
                  : 'bg-muted/40 border-border text-foreground'
              }`}>
                {request.admin_response}
              </div>
            ) : (
              <div className="bg-muted/40 border border-border rounded-lg p-3 text-sm text-muted-foreground italic">
                Sin respuesta
              </div>
            )}
            {request.responded_at && (
              <p className="text-xs text-muted-foreground mt-1">
                Respondido el {new Date(request.responded_at).toLocaleDateString('es-BO')}
              </p>
            )}
          </div>

          {evidence.kind === 'historical' && (
            <div className="rounded-lg border border-primary/32 bg-primary/40 p-3">
              <p className="mb-3 text-sm font-semibold text-foreground">
                Evidencia histórica autoritativa
              </p>
              <ResolutionSnapshotPanel
                snapshot={evidence.snapshot}
                heading="Resolución histórica guardada"
              />
            </div>
          )}

          {evidence.kind === 'legacy-fallback' && (
            <div
              role="status"
              aria-label="Solicitud histórica sin resolución guardada"
              className="rounded-lg border border-warning/32 bg-warning/4 p-3 text-sm text-warning-foreground"
            >
              <p className="font-semibold">Solicitud histórica sin evidencia guardada</p>
              <p className="mt-1 text-xs">
                Esta solicitud fue resuelta antes de incorporar instantáneas inmutables. El contexto actual no se usa como reemplazo.
              </p>
            </div>
          )}

          {/* Teacher billing info */}
          {evidence.kind === 'live-pending' && teacherBilling && (
            <div className="bg-primary/50 rounded-lg p-3 space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Contexto actual de facturación · solo apoyo</p>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Total a facturar</span>
                <span className="text-lg font-bold tabular-nums text-foreground">
                  Bs {teacherBilling.total_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{teacherBilling.total_base_hours}h asignadas</span>
                <span>{teacherBilling.total_absent_hours > 0 ? `-${teacherBilling.total_absent_hours}h ausencias` : 'Sin ausencias'}</span>
                <span>{teacherBilling.total_payable_hours}h a pagar</span>
              </div>
              {teacherDesignations && teacherDesignations.length > 0 && (
                <div className="mt-2 space-y-1">
                  {teacherDesignations.map(d => (
                    <div key={`${d.subject}-${d.group_code}`} className="flex justify-between text-xs">
                      <span className="text-muted-foreground">{d.subject} ({d.group_code})</span>
                      <span className="font-medium text-foreground">Bs {d.calculated_payment.toLocaleString('es-BO', { minimumFractionDigits: 2 })}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Teacher Schedule */}
          {evidence.kind === 'live-pending' && teacherSchedule && teacherSchedule.designations.length > 0 && (
            <div className="bg-success/50 rounded-lg p-3 space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Contexto actual de horarios · solo apoyo ({teacherSchedule.designation_count} materia{teacherSchedule.designation_count !== 1 ? 's' : ''} · {teacherSchedule.total_weekly_hours}h/sem)
              </p>
              <div className="space-y-2">
                {teacherSchedule.designations.map(d => (
                  <div key={d.source_key} className="text-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-foreground">{d.subject}</span>
                      <Badge variant="outline" size="sm">{d.group_code}</Badge>
                      <Badge variant="info" size="sm">
                        {d.activity_kind === 'practice' ? 'Práctica' : 'Teoría'}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{d.semester}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 ml-2">
                      {d.schedule.map((slot, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-border text-xs text-muted-foreground">
                          <span className="font-medium capitalize">{slot.dia}</span>
                          <span>{slot.hora_inicio}-{slot.hora_fin}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </DialogPanel>
      </DialogPopup>
    </Dialog>
  )
}

function RespondDialog({
  request,
  action,
  onClose,
}: {
  request: DetailRequestInfo | null
  action: 'approved' | 'rejected' | null
  onClose: () => void
}) {
  const respond = useRespondRequest()
  const [adminResponse, setAdminResponse] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmingReject, setConfirmingReject] = useState(false)

  // Load teacher designations with schedule info
  const { data: teacherSchedule } = useTeacherDesignations(
    request?.teacher_ci ?? '',
    Boolean(request),
  )

  const submitResponse = async () => {
    if (!request || !action) return
    setError(null)
    try {
      await respond.mutateAsync({
        id: request.id,
        data: {
          status: action,
          admin_response: adminResponse || undefined,
        },
      })
      setAdminResponse('')
      setConfirmingReject(false)
      onClose()
    } catch {
      setError('No se pudo procesar la solicitud.')
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Rejecting is final for the docente, so it goes through a summary confirmation first.
    if (action === 'rejected') {
      setConfirmingReject(true)
      return
    }
    void submitResponse()
  }

  if (!request || !action) return null

  return (
    <Dialog open={Boolean(request)} onOpenChange={onClose}>
      <DialogPopup className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            {action === 'approved' ? 'Aprobar Solicitud' : 'Rechazar Solicitud'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogPanel className="space-y-4">
            {/* Request info */}
            <div className="bg-muted/40 rounded-lg p-3 space-y-1.5 text-sm">
              <p>
                <span className="text-muted-foreground">Docente:</span>{' '}
                <span className="font-medium">{request.teacher_name ?? request.teacher_ci}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Solicitud:</span>{' '}
                <span className="font-medium">
                  {REQUEST_TYPE_LABELS[request.request_type] ?? request.request_type}
                </span>
              </p>
              <p>
                <span className="text-muted-foreground">Período:</span>{' '}
                <span className="font-medium">{MONTH_NAMES[request.month]} {request.year}</span>
              </p>
              {request.message && (
                <div className="mt-2 pt-2 border-t border-border">
                  <span className="text-muted-foreground">Mensaje del docente:</span>
                  <p className="text-foreground mt-1 bg-white rounded p-2 border border-border text-sm">
                    {request.message}
                  </p>
                </div>
              )}
            </div>

            {/* Teacher Schedule */}
            {teacherSchedule && teacherSchedule.designations.length > 0 && (
              <div className="bg-success/50 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Horarios asignados ({teacherSchedule.designation_count} materia{teacherSchedule.designation_count !== 1 ? 's' : ''} · {teacherSchedule.total_weekly_hours}h/sem)
                </p>
                <div className="space-y-2">
                  {teacherSchedule.designations.map(d => (
                    <div key={d.source_key} className="text-sm">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-foreground">{d.subject}</span>
                        <Badge variant="outline" size="sm">{d.group_code}</Badge>
                        <Badge variant="info" size="sm">
                          {d.activity_kind === 'practice' ? 'Práctica' : 'Teoría'}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{d.semester}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 ml-2">
                        {d.schedule.map((slot, i) => (
                          <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-border text-xs text-muted-foreground">
                            <span className="font-medium capitalize">{slot.dia}</span>
                            <span>{slot.hora_inicio}-{slot.hora_fin}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Field>
              <FieldLabel htmlFor="admin-request-observation">Observaciones para el docente (opcional)</FieldLabel>
              <Textarea
                id="admin-request-observation"
                value={adminResponse}
                onChange={(e) => setAdminResponse(e.target.value)}
                placeholder="Agregá una observación sobre la resolución..."
                rows={3}
              />
            </Field>

            {error && (
              <Alert variant="error">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

          </DialogPanel>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              loading={respond.isPending && action === 'approved'}
              variant={action === 'approved' ? 'default' : 'destructive'}
            >
              {respond.isPending && action === 'approved'
                ? 'Procesando...'
                : action === 'approved'
                ? 'Aprobar'
                : 'Rechazar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogPopup>

      <ConfirmAlertDialog
        summary={
          confirmingReject
            ? {
                title: 'Rechazar solicitud',
                confirmLabel: 'Confirmar rechazo',
                tone: 'destructive',
                rows: [
                  { label: 'Docente', value: request.teacher_name ?? request.teacher_ci },
                  { label: 'Solicitud', value: REQUEST_TYPE_LABELS[request.request_type] ?? request.request_type },
                  { label: 'Período', value: `${MONTH_NAMES[request.month]} ${request.year}` },
                  { label: 'Observaciones', value: adminResponse.trim() || 'Sin observaciones' },
                ],
                consequence: 'El docente verá la solicitud como rechazada.',
              }
            : null
        }
        pending={respond.isPending}
        description={error ?? undefined}
        onConfirm={() => void submitResponse()}
        onCancel={() => setConfirmingReject(false)}
      />
    </Dialog>
  )
}

export function AdminRequestsPage() {
  const { data: requests, isLoading, error, refetch } = useAllRequests()
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [respondTarget, setRespondTarget] = useState<DetailRequestInfo | null>(null)
  const [respondAction, setRespondAction] = useState<'approved' | 'rejected' | null>(null)
  const [viewTarget, setViewTarget] = useState<DetailRequestInfo | null>(null)

  const handleRespond = (req: DetailRequestInfo, action: 'approved' | 'rejected') => {
    setRespondTarget(req)
    setRespondAction(action)
  }

  const handleClose = () => {
    setRespondTarget(null)
    setRespondAction(null)
  }

  const filtered = requests?.filter((r) => {
    if (filter === 'all') return true
    return r.status === filter
  })

  const pendingCount = requests?.filter((r) => r.status === 'pending').length ?? 0

  const filterButtons: { key: StatusFilter; label: string }[] = [
    { key: 'all', label: 'Todas' },
    { key: 'pending', label: 'Pendientes' },
    { key: 'approved', label: 'Aprobadas' },
    { key: 'rejected', label: 'Rechazadas' },
  ]

  if (isLoading) {
    return (
      <div role="status" aria-live="polite" aria-label="Cargando solicitudes" className="space-y-6">
        <Skeleton className="h-14 w-full max-w-md" />
        <Skeleton className="h-8 w-full max-w-sm" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertCircle aria-hidden="true" />
        <AlertTitle>No se pudieron cargar las solicitudes</AlertTitle>
        <AlertDescription>Revisá tu conexión e intentá nuevamente.</AlertDescription>
        <AlertAction>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Solicitudes de Docentes"
        description={
          pendingCount > 0
            ? `${pendingCount} solicitud${pendingCount !== 1 ? 'es' : ''} pendiente${pendingCount !== 1 ? 's' : ''}`
            : 'Sin solicitudes pendientes'
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Filter size={15} className="text-muted-foreground" aria-hidden="true" />
        {filterButtons.map((btn) => (
          <Button
            key={btn.key}
            type="button"
            size="sm"
            variant={filter === btn.key ? 'default' : 'outline'}
            aria-pressed={filter === btn.key}
            onClick={() => setFilter(btn.key)}
          >
            {btn.label}
            {btn.key === 'pending' && pendingCount > 0 && (
              <Badge variant="warning" size="sm" className="tabular-nums">
                {pendingCount}
              </Badge>
            )}
          </Button>
        ))}
      </div>

      {/* Table */}
      <TableCard title={`${filtered?.length ?? 0} solicitud${filtered?.length !== 1 ? 'es' : ''}`}>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            {['Docente', 'Período', 'Tipo de Solicitud', 'Mensaje', 'Estado', 'Fecha', 'Acciones'].map((h) => (
              <TableHead key={h} className="h-10 px-4 text-xs font-medium uppercase tracking-wider">
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {!filtered?.length ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={7} className="p-0 whitespace-normal">
                <EmptyState icon={Inbox} title="No hay solicitudes para mostrar" />
              </TableCell>
            </TableRow>
          ) : (
            filtered.map((req) => (
              <TableRow key={req.id}>
                <TableCell className="px-4 py-3 font-medium text-foreground">{req.teacher_name ?? req.teacher_ci}</TableCell>
                <TableCell className="px-4 py-3 text-muted-foreground">
                  {MONTH_NAMES[req.month]} {req.year}
                </TableCell>
                <TableCell className="px-4 py-3 text-foreground">
                  {REQUEST_TYPE_LABELS[req.request_type] ?? req.request_type}
                </TableCell>
                <TableCell className="max-w-[200px] truncate px-4 py-3 text-muted-foreground">{req.message || '—'}</TableCell>
                <TableCell className="px-4 py-3">
                  <RequestStatusBadge status={req.status} />
                </TableCell>
                <TableCell className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
                  {new Date(req.created_at).toLocaleDateString('es-BO')}
                </TableCell>
                <TableCell className="px-4 py-3">
                  {req.status === 'pending' ? (
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="xs" onClick={() => handleRespond(req, 'approved')}>
                        <Check aria-hidden="true" />
                        Aprobar
                      </Button>
                      <Button variant="destructive-outline" size="xs" onClick={() => handleRespond(req, 'rejected')}>
                        <X aria-hidden="true" />
                        Rechazar
                      </Button>
                    </div>
                  ) : (
                    <Button variant="ghost" size="xs" className="text-primary" onClick={() => setViewTarget(req)}>
                      <Eye aria-hidden="true" />
                      Ver detalle
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </TableCard>

      <RespondDialog request={respondTarget} action={respondAction} onClose={handleClose} />
      <RequestDetailDialog request={viewTarget} onClose={() => setViewTarget(null)} />
    </div>
  )
}
