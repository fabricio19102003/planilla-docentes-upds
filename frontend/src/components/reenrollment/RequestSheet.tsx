import { useState } from 'react'

import { useHandleRequest, useRequestDetail } from '@/api/hooks/useReenrollment'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Sheet, SheetDescription, SheetFooter, SheetHeader, SheetPanel, SheetPopup, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { completeBlockReason, documentBadge, formatExpiry, regularizadoBadge } from '@/lib/migrationDocumentsState'
import { OBSERVATION_REASONS, formatBs, requestStatus, type ObservationReason } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** The detail endpoint also returns the migration status of the student. */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </section>
  )
}

/** Request detail with the staff actions: mark done, observe with a reason, reopen. */
export function RequestSheet({ requestId, onClose }: { requestId: number | null; onClose: () => void }) {
  const detail = useRequestDetail(requestId)
  const handle = useHandleRequest()
  const [observing, setObserving] = useState(false)
  const [reason, setReason] = useState<ObservationReason>('documentos_migracion')
  const [message, setMessage] = useState('')
  const data = detail.data
  const blockReason = completeBlockReason(data?.migration)
  const regularizado = data ? regularizadoBadge(data.migration) : null

  const act = (action: 'complete' | 'observe' | 'reopen') => {
    if (requestId === null) return
    handle.mutate(
      { id: requestId, action, reason, message: message.trim() },
      { onSuccess: () => { setObserving(false); setMessage('') } },
    )
  }

  return (
    <Sheet open={requestId !== null} onOpenChange={(open) => { if (!open) { setObserving(false); onClose() } }}>
      <SheetPopup className="sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{data ? data.student.full_name : 'Solicitud de rematrícula'}</SheetTitle>
          <SheetDescription>
            {data && (
              <span className="flex flex-wrap items-center gap-2">
                {data.student.document_number} · {data.term_code} · semestre {data.target_semester}
                <Badge variant={requestStatus(data.status).variant}>{requestStatus(data.status).label}</Badge>
                {data.student.is_foreign && <Badge variant="warning">Extranjero</Badge>}
                {regularizado && <Badge variant={regularizado.variant}>{regularizado.label}</Badge>}
              </span>
            )}
          </SheetDescription>
        </SheetHeader>
        <SheetPanel className="space-y-5">
          {detail.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(detail.error, 'No se pudo cargar la solicitud.')}</AlertTitle></Alert>}
          {!data && !detail.isError && <p role="status" className="text-sm text-muted-foreground">Cargando solicitud…</p>}
          {data && (
            <>
              {data.migration.applies && (
                <Section title="Documentos migratorios">
                  {data.migration.documents.length === 0
                    ? <p className="text-sm text-muted-foreground">No hay documentos requeridos activos.</p>
                    : (
                      <ul className="divide-y rounded-lg border text-sm">
                        {data.migration.documents.map((row) => (
                          <li key={row.type_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                            <span>{row.name}</span>
                            <span className="flex items-center gap-2">
                              {row.requires_expiry && row.expires_on && <span className="text-xs text-muted-foreground">Vence {formatExpiry(row.expires_on)}</span>}
                              <Badge variant={documentBadge(row.state).variant} size="sm">{documentBadge(row.state).label}</Badge>
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  {blockReason && (
                    <Alert variant="warning">
                      <AlertDescription>{blockReason}. Registralos desde el detalle del estudiante antes de marcarla como realizada.</AlertDescription>
                    </Alert>
                  )}
                </Section>
              )}
              {data.status === 'observada' && (
                <Alert variant="error">
                  <AlertTitle>Observada: {data.observation_label}</AlertTitle>
                  <AlertDescription>{data.observation_message}</AlertDescription>
                </Alert>
              )}
              <Section title="Grupos elegidos">
                <ul className="divide-y rounded-lg border text-sm">
                  <li className="flex justify-between gap-3 px-3 py-2">
                    <span>Semestre {data.target_semester} (materias del semestre)</span>
                    <span className="font-medium">{data.main_group.code} · {data.main_group.shift}</span>
                  </li>
                  {data.items.map((item) => (
                    <li key={item.subject_code} className="flex justify-between gap-3 px-3 py-2">
                      <span>
                        {item.subject_name} <span className="text-xs text-muted-foreground">{item.subject_code} · sem. {item.semester}</span>
                        <Badge variant={item.kind === 'recursado' ? 'error' : 'info'} size="sm" className="ml-2">
                          {item.kind === 'recursado' ? 'Recursado' : 'Pendiente'}
                        </Badge>
                      </span>
                      <span className="shrink-0 font-medium">{item.group.code} · {item.group.shift}</span>
                    </li>
                  ))}
                </ul>
                {data.items.some((item) => item.kind === 'recursado') && (
                  <p className="text-xs text-muted-foreground">Verificá en caja el pago de las materias de recursado antes de marcarla como realizada.</p>
                )}
              </Section>
              <Section title="Beca y montos (informativo)">
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <dt className="text-muted-foreground">Categoría</dt><dd>{data.snapshot.scholarship.label}</dd>
                  <dt className="text-muted-foreground">Promedio último período</dt><dd>{data.snapshot.scholarship.average ?? '—'}</dd>
                  <dt className="text-muted-foreground">Cuota</dt><dd>{formatBs(data.snapshot.scholarship.cuota)} × {data.snapshot.scholarship.cuotas}</dd>
                  <dt className="text-muted-foreground">Recursado</dt>
                  <dd>{data.snapshot.recursado_fee.subjects} materia(s) · {formatBs(data.snapshot.recursado_fee.total)}</dd>
                </dl>
              </Section>
              <Section title="Contacto">
                <p className="text-sm">{data.student.phone ?? 'Sin celular'} · {data.student.personal_email ?? data.student.academic_email ?? 'Sin correo'}</p>
              </Section>
              {observing && (
                <Section title="Observar solicitud">
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor="observation-reason">Motivo</Label>
                      <select id="observation-reason" className={selectClass} value={reason} onChange={(event) => setReason(event.target.value as ObservationReason)}>
                        {OBSERVATION_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <Label htmlFor="observation-message">Mensaje para el estudiante</Label>
                      <Textarea id="observation-message" value={message} onChange={(event) => setMessage(event.target.value)}
                        placeholder="Ej: Presentá en Registro tu carnet de extranjero vigente." />
                    </div>
                  </div>
                </Section>
              )}
              {handle.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(handle.error, 'No se pudo actualizar la solicitud.')}</AlertTitle></Alert>}
            </>
          )}
        </SheetPanel>
        {data && (
          <SheetFooter>
            {observing ? (
              <>
                <Button variant="outline" onClick={() => setObserving(false)}>Cancelar</Button>
                <Button disabled={handle.isPending || message.trim().length < 5} onClick={() => act('observe')}>Enviar observación</Button>
              </>
            ) : data.status === 'pendiente' ? (
              <>
                <Button variant="outline" onClick={() => setObserving(true)}>Observar</Button>
                <Button disabled={handle.isPending || blockReason !== null} title={blockReason ?? undefined} onClick={() => act('complete')}>Marcar como realizada</Button>
              </>
            ) : (
              <Button variant="outline" disabled={handle.isPending} onClick={() => act('reopen')}>Reabrir como pendiente</Button>
            )}
          </SheetFooter>
        )}
      </SheetPopup>
    </Sheet>
  )
}
