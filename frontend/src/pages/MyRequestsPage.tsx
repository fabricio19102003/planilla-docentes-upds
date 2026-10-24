import { useState } from 'react'
import { useMyRequests, useCreateRequest } from '@/api/hooks/useAuth'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import {
  Select,
  SelectItem,
  SelectPopup,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TableCard } from '@/components/shared/TableCard'
import type { Tone } from '@/components/shared/tones'
import { cn } from '@/lib/utils'
import { AlertCircle, PlusCircle, MessageSquare, Eye } from 'lucide-react'
import type { DetailRequestInfo } from '@/api/types'
import { ResolutionSnapshotPanel } from '@/components/requests/ResolutionSnapshotPanel'

function getRequestErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

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

const REQUEST_STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: 'En espera', tone: 'warning' },
  approved: { label: 'Aprobada', tone: 'success' },
  rejected: { label: 'Rechazada', tone: 'destructive' },
}

function RequestStatusBadge({ status }: { status: string }) {
  const { label, tone } = REQUEST_STATUS[status] ?? { label: status, tone: 'neutral' as Tone }
  return <StatusBadge tone={tone}>{label}</StatusBadge>
}

function NewRequestDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createReq = useCreateRequest()
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [form, setForm] = useState({
    month: currentMonth,
    year: currentYear,
    request_type: '',
    message: '',
  })
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.request_type) {
      setError('Seleccioná un tipo de solicitud.')
      return
    }
    setError(null)
    try {
      await createReq.mutateAsync({
        month: form.month,
        year: form.year,
        request_type: form.request_type,
        message: form.message || undefined,
      })
      setForm({ month: currentMonth, year: currentYear, request_type: '', message: '' })
      onClose()
    } catch (err: unknown) {
      setError(getRequestErrorMessage(err, 'No se pudo enviar la solicitud. Intentá de nuevo.'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => {
      if (!nextOpen && !createReq.isPending) onClose()
    }}>
      <DialogPopup className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nueva Solicitud</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogPanel className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="request-month">Mes *</FieldLabel>
                <Select
                  value={String(form.month)}
                  items={MONTH_NAMES}
                  onValueChange={(v) => setForm((f) => ({ ...f, month: v ? Number(v) : f.month }))}
                >
                  <SelectTrigger
                    id="request-month"
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'request-form-error' : undefined}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectPopup className="max-h-48">
                    {Object.entries(MONTH_NAMES).map(([num, name]) => (
                      <SelectItem key={num} value={num}>
                        {name}
                      </SelectItem>
                    ))}
                  </SelectPopup>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="request-year">Año *</FieldLabel>
                <Input
                  id="request-year"
                  type="number"
                  value={form.year}
                  onChange={(e) => setForm((f) => ({ ...f, year: Number(e.target.value) }))}
                  min={2020}
                  max={currentYear + 1}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'request-form-error' : undefined}
                />
              </Field>
            </div>

            <Field>
              <FieldLabel htmlFor="request-type">Tipo de Solicitud *</FieldLabel>
              <Select
                value={form.request_type || null}
                items={REQUEST_TYPE_LABELS}
                onValueChange={(v) => setForm((f) => ({ ...f, request_type: v ?? '' }))}
              >
                <SelectTrigger
                  id="request-type"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? 'request-form-error' : undefined}
                >
                  <SelectValue placeholder="Seleccioná un tipo..." />
                </SelectTrigger>
                <SelectPopup>
                  {Object.entries(REQUEST_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectPopup>
              </Select>
            </Field>

            <Field>
              <FieldLabel htmlFor="request-message">Mensaje (opcional)</FieldLabel>
              <Textarea
                id="request-message"
                value={form.message}
                onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
                placeholder="Describí tu solicitud o dejá un mensaje para el administrador..."
                rows={3}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'request-form-error' : undefined}
              />
            </Field>

            {error && (
              <Alert id="request-form-error" variant="error">
                <AlertCircle aria-hidden="true" />
                <AlertDescription className="text-destructive-foreground">{error}</AlertDescription>
              </Alert>
            )}

          </DialogPanel>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={createReq.isPending}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createReq.isPending}
            >
              {createReq.isPending ? 'Enviando...' : 'Enviar Solicitud'}
            </Button>
          </DialogFooter>
        </form>
      </DialogPopup>
    </Dialog>
  )
}

function ViewRequestDialog({ request, onClose }: { request: DetailRequestInfo | null; onClose: () => void }) {
  if (!request) return null

  return (
    <Dialog open={Boolean(request)} onOpenChange={onClose}>
      <DialogPopup className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Detalle de Solicitud</DialogTitle>
          <DialogDescription className="sr-only">
            Consulta la solicitud, la información histórica resuelta y las observaciones del administrador.
          </DialogDescription>
        </DialogHeader>
        <DialogPanel className="space-y-4">
          {/* Request info */}
          <div className="space-y-1.5 rounded-lg bg-muted/50 p-3 text-sm">
            <p>
              <span className="text-muted-foreground">Tipo:</span>{' '}
              <span className="font-medium">{REQUEST_TYPE_LABELS[request.request_type] ?? request.request_type}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Período:</span>{' '}
              <span className="font-medium">{MONTH_NAMES[request.month]} {request.year}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Fecha de envío:</span>{' '}
              <span className="font-medium tabular-nums">{new Date(request.created_at).toLocaleDateString('es-BO')}</span>
            </p>
            <p>
              <span className="text-muted-foreground">Estado:</span>{' '}
              <RequestStatusBadge status={request.status} />
            </p>
          </div>

          {/* My message */}
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tu mensaje</p>
            <div className="rounded-lg border bg-card p-3 text-sm text-foreground">
              {request.message || <span className="italic text-muted-foreground">Sin mensaje</span>}
            </div>
          </div>

          {request.resolution_snapshot && <ResolutionSnapshotPanel snapshot={request.resolution_snapshot} />}

          {/* Admin response */}
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Observaciones del administrador</p>
            {request.admin_response ? (
              <div
                className={cn(
                  'rounded-lg border p-3 text-sm',
                  request.status === 'approved' && 'border-success/32 bg-success/4 text-success-foreground',
                  request.status === 'rejected' && 'border-destructive/32 bg-destructive/4 text-destructive-foreground',
                  request.status !== 'approved' && request.status !== 'rejected' && 'bg-muted/50 text-foreground',
                )}
              >
                {request.admin_response}
              </div>
            ) : request.status === 'pending' ? (
              <div className="rounded-lg border border-warning/32 bg-warning/4 p-3 text-sm italic text-warning-foreground">
                Esperando respuesta del administrador...
              </div>
            ) : (
              <div className="rounded-lg border bg-muted/50 p-3 text-sm italic text-muted-foreground">
                El administrador no dejó una respuesta escrita
              </div>
            )}
            {request.responded_at && (
              <p className="mt-1 text-xs text-muted-foreground">
                Respondido el {new Date(request.responded_at).toLocaleDateString('es-BO')}
              </p>
            )}
          </div>
        </DialogPanel>
      </DialogPopup>
    </Dialog>
  )
}

export function MyRequestsPage() {
  const { data: requests, isLoading, error, refetch, isFetching } = useMyRequests()
  const [createOpen, setCreateOpen] = useState(false)
  const [viewTarget, setViewTarget] = useState<DetailRequestInfo | null>(null)

  if (isLoading) {
    return (
      <div className="max-w-3xl">
        <PageHeader title="Mis Solicitudes" description="Pedí detalles biométricos, resúmenes de horas o de horario." />
        <div role="status" aria-busy="true" className="space-y-3">
          <span className="sr-only">Cargando solicitudes</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-3xl">
        <PageHeader title="Mis Solicitudes" description="Pedí detalles biométricos, resúmenes de horas o de horario." />
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No se pudieron cargar tus solicitudes</AlertTitle>
          <AlertDescription>
            {getRequestErrorMessage(error, 'Ocurrió un problema al consultar el servidor.')}
          </AlertDescription>
          <AlertAction>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void refetch()}
              disabled={isFetching}
            >
              {isFetching ? 'Reintentando...' : 'Reintentar'}
            </Button>
          </AlertAction>
        </Alert>
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Mis Solicitudes"
        description={`${requests?.length ?? 0} solicitud${requests?.length !== 1 ? 'es' : ''} enviada${requests?.length !== 1 ? 's' : ''}`}
        actions={
          <Button onClick={() => setCreateOpen(true)} className="w-full gap-2 sm:w-auto">
            <PlusCircle size={16} aria-hidden="true" />
            Nueva Solicitud
          </Button>
        }
      />

      {/* Empty state */}
      {!requests?.length ? (
        <Card>
          <EmptyState
            icon={MessageSquare}
            title="No tenés solicitudes todavía"
            description="Podés pedir detalles biométricos, resúmenes de horas o detalle de horario."
            action={
              <Button onClick={() => setCreateOpen(true)} className="gap-2">
                <PlusCircle size={16} aria-hidden="true" />
                Crear tu primera solicitud
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          {/* Cards below sm so the status never scrolls out of view; the table from sm up */}
          <div data-testid="requests-mobile-list" className="space-y-3 sm:hidden">
            {requests.map((req) => (
              <Card key={req.id} render={<article />} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 font-medium text-foreground">
                    {MONTH_NAMES[req.month]} {req.year}
                  </p>
                  <RequestStatusBadge status={req.status} />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {REQUEST_TYPE_LABELS[req.request_type] ?? req.request_type}
                </p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {new Date(req.created_at).toLocaleDateString('es-BO')}
                  </span>
                  <Button variant="outline" size="xs" onClick={() => setViewTarget(req)}>
                    <Eye aria-hidden="true" />
                    Ver detalle
                  </Button>
                </div>
              </Card>
            ))}
          </div>
          <TableCard title="Historial de Solicitudes" className="hidden sm:flex" tableClassName="min-w-[560px]">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                {['Período', 'Tipo', 'Estado', 'Fecha', 'Acciones'].map((h) => (
                  <TableHead key={h} className="h-10 px-4 text-xs font-medium uppercase tracking-wider">
                    {h}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {requests.map((req) => (
                <TableRow key={req.id}>
                  <TableCell className="px-4 py-3 font-medium text-foreground">
                    {MONTH_NAMES[req.month]} {req.year}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-foreground">
                    {REQUEST_TYPE_LABELS[req.request_type] ?? req.request_type}
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <RequestStatusBadge status={req.status} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
                    {new Date(req.created_at).toLocaleDateString('es-BO')}
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <Button variant="outline" size="xs" onClick={() => setViewTarget(req)}>
                      <Eye aria-hidden="true" />
                      Ver detalle
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </TableCard>
        </>
      )}

      <NewRequestDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <ViewRequestDialog request={viewTarget} onClose={() => setViewTarget(null)} />
    </div>
  )
}
