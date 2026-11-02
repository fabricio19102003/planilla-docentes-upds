import { CalendarPlus, Inbox as InboxIcon } from 'lucide-react'
import { useState } from 'react'

import { useInbox, useReenrollmentWindows, useSaveWindow } from '@/api/hooks/useReenrollment'
import { RequestSheet } from '@/components/reenrollment/RequestSheet'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateInBolivia, formatShortDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import {
  INBOX_PAGE_SIZE,
  requestStatus,
  windowState,
  type InboxFilters,
  type ReenrollmentWindow,
  type RequestStatusValue,
} from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
const EMPTY_FORM = { id: undefined as number | undefined, term_code: '', starts_on: '', ends_on: '' }

function WindowForm({ initial, onDone }: { initial: typeof EMPTY_FORM; onDone: () => void }) {
  const [form, setForm] = useState(initial)
  const save = useSaveWindow()
  return (
    <form
      className="grid gap-3 rounded-lg border p-4 sm:grid-cols-4"
      onSubmit={(event) => { event.preventDefault(); save.mutate(form, { onSuccess: onDone }) }}
    >
      <div>
        <Label htmlFor="window-term">Período a rematricular</Label>
        <Input id="window-term" value={form.term_code} disabled={form.id !== undefined} placeholder="I/2027"
          onChange={(event) => setForm((f) => ({ ...f, term_code: event.target.value.toUpperCase() }))} />
      </div>
      <div>
        <Label htmlFor="window-start">Desde</Label>
        <Input id="window-start" type="date" value={form.starts_on} onChange={(event) => setForm((f) => ({ ...f, starts_on: event.target.value }))} />
      </div>
      <div>
        <Label htmlFor="window-end">Hasta</Label>
        <Input id="window-end" type="date" value={form.ends_on} onChange={(event) => setForm((f) => ({ ...f, ends_on: event.target.value }))} />
      </div>
      <div className="flex items-end gap-2">
        <Button type="submit" disabled={save.isPending || !form.term_code || !form.starts_on || !form.ends_on}>Guardar</Button>
        <Button type="button" variant="outline" onClick={onDone}>Cancelar</Button>
      </div>
      {save.isError && (
        <Alert variant="error" role="alert" className="sm:col-span-4"><AlertTitle>{apiErrorMessage(save.error, 'No se pudo guardar la ventana.')}</AlertTitle></Alert>
      )}
    </form>
  )
}

function WindowsCard({ windows, selectedId, onSelect }: {
  windows: ReenrollmentWindow[]; selectedId: number | undefined; onSelect: (id: number) => void
}) {
  const [editing, setEditing] = useState<typeof EMPTY_FORM | null>(null)
  const today = getTodayInBolivia()
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Ventanas de rematrícula</CardTitle>
          <CardDescription>Fuera de estas fechas el portal solo muestra el historial y el estado de la solicitud. Los grupos y cupos del período se cargan en Gestión académica.</CardDescription>
        </div>
        {!editing && <Button onClick={() => setEditing(EMPTY_FORM)}><CalendarPlus aria-hidden="true" />Nueva ventana</Button>}
      </CardHeader>
      <CardContent className="space-y-3">
        {editing && <WindowForm key={editing.id ?? 'new'} initial={editing} onDone={() => setEditing(null)} />}
        {windows.length === 0 && !editing && <p className="text-sm text-muted-foreground">Todavía no abriste ninguna rematrícula.</p>}
        <ul className="divide-y rounded-lg border">
          {windows.map((window) => {
            const state = windowState(window, today)
            return (
              <li key={window.id} className={`flex flex-wrap items-center justify-between gap-3 px-4 py-3 ${window.id === selectedId ? 'bg-accent/40' : ''}`}>
                <button type="button" className="text-left" onClick={() => onSelect(window.id)}>
                  <p className="flex items-center gap-2 font-medium text-foreground">{window.term_code} <Badge variant={state.variant} size="sm">{state.label}</Badge></p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateInBolivia(window.starts_on)} al {formatDateInBolivia(window.ends_on)}
                    {window.requests && ` · ${window.requests.pendiente} pendiente(s) · ${window.requests.observada} observada(s) · ${window.requests.realizada} realizada(s)`}
                  </p>
                </button>
                <Button size="sm" variant="outline" onClick={() => setEditing({ id: window.id, term_code: window.term_code, starts_on: window.starts_on, ends_on: window.ends_on })}>
                  Cambiar fechas
                </Button>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

export function ReenrollmentPage() {
  const windows = useReenrollmentWindows()
  const [windowId, setWindowId] = useState<number | undefined>()
  const [filters, setFilters] = useState<InboxFilters>({ status: 'pendiente', semester: '', search: '', foreign: 'all', page: 1 })
  const [openRequest, setOpenRequest] = useState<number | null>(null)
  const list = windows.data ?? []
  const activeId = windowId ?? (list.find((w) => w.is_open) ?? list[0])?.id
  const inbox = useInbox(activeId, filters)
  const update = (patch: Partial<InboxFilters>) => setFilters((current) => ({ ...current, page: 1, ...patch }))
  const total = inbox.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / INBOX_PAGE_SIZE))

  return (
    <div className="space-y-5">
      <PageHeader title="Rematrícula" description="Solicitudes enviadas desde el portal del estudiante. Registralas en el sistema académico y marcalas como realizadas, u observalas con un mensaje para el estudiante." />
      {windows.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudieron cargar las ventanas de rematrícula.</AlertTitle></Alert>}
      {windows.data && <WindowsCard windows={list} selectedId={activeId} onSelect={setWindowId} />}

      {activeId !== undefined && (
        <>
          <div className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-4" role="search">
            <div>
              <Label htmlFor="inbox-status">Estado</Label>
              <select id="inbox-status" className={selectClass} value={filters.status} onChange={(event) => update({ status: event.target.value as RequestStatusValue | '' })}>
                <option value="">Todos</option>
                <option value="pendiente">Pendientes</option>
                <option value="observada">Observadas</option>
                <option value="realizada">Realizadas</option>
              </select>
            </div>
            <div>
              <Label htmlFor="inbox-semester">Semestre</Label>
              <select id="inbox-semester" className={selectClass} value={filters.semester} onChange={(event) => update({ semester: event.target.value })}>
                <option value="">Todos</option>
                {Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={String(i + 1)}>Semestre {i + 1}</option>)}
              </select>
            </div>
            <div>
              <Label htmlFor="inbox-foreign">Nacionalidad</Label>
              <select id="inbox-foreign" className={selectClass} value={filters.foreign} onChange={(event) => update({ foreign: event.target.value as InboxFilters['foreign'] })}>
                <option value="all">Todas</option>
                <option value="national">Bolivianos</option>
                <option value="foreign">Extranjeros</option>
              </select>
            </div>
            <div>
              <Label htmlFor="inbox-search">Buscar</Label>
              <Input id="inbox-search" type="search" value={filters.search} placeholder="Nombre o documento" onChange={(event) => update({ search: event.target.value })} />
            </div>
          </div>

          {inbox.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(inbox.error, 'No se pudieron cargar las solicitudes.')}</AlertTitle></Alert>}
          {inbox.data && total === 0 ? (
            <EmptyState icon={InboxIcon} title="No hay solicitudes con estos filtros" description="Las solicitudes aparecen acá apenas el estudiante las envía desde su portal." />
          ) : (
            <TableCard
              tableClassName="min-w-[860px]"
              footer={(
                <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
                  <span>{total} solicitud(es) · página {filters.page} de {pages}</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>Anterior</Button>
                    <Button size="sm" variant="outline" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>Siguiente</Button>
                  </div>
                </div>
              )}
            >
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="px-4">Estudiante</TableHead>
                  <TableHead className="px-4">Semestre</TableHead>
                  <TableHead className="px-4">Grupo</TableHead>
                  <TableHead className="px-4">Recursado</TableHead>
                  <TableHead className="px-4">Beca</TableHead>
                  <TableHead className="px-4">Estado</TableHead>
                  <TableHead className="px-4">Enviada</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!inbox.data && <TableRow><TableCell colSpan={7} role="status" className="px-4 py-10 text-center text-muted-foreground">Cargando solicitudes…</TableCell></TableRow>}
                {inbox.data?.items.map((row) => {
                  const status = requestStatus(row.status)
                  return (
                    <TableRow key={row.id} className="cursor-pointer" onClick={() => setOpenRequest(row.id)}>
                      <TableCell className="px-4 py-3">
                        <button type="button" className="text-left font-medium text-foreground underline-offset-4 hover:underline" onClick={() => setOpenRequest(row.id)}>{row.full_name}</button>
                        <p className="flex items-center gap-2 text-xs text-muted-foreground">{row.document_number}{row.is_foreign && <Badge variant="warning" size="sm">Extranjero</Badge>}</p>
                      </TableCell>
                      <TableCell className="px-4 py-3">{row.target_semester}</TableCell>
                      <TableCell className="px-4 py-3">{row.main_group_code} · {row.main_group_shift}</TableCell>
                      <TableCell className="px-4 py-3">{row.recursado_count > 0 ? <Badge variant="error" size="sm">{row.recursado_count} materia(s)</Badge> : '—'}</TableCell>
                      <TableCell className="px-4 py-3">{row.scholarship_label ?? '—'}</TableCell>
                      <TableCell className="px-4 py-3"><Badge variant={status.variant}>{status.label}</Badge></TableCell>
                      <TableCell className="px-4 py-3">{formatShortDateInBolivia(row.submitted_at)}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </TableCard>
          )}
        </>
      )}
      <RequestSheet requestId={openRequest} onClose={() => setOpenRequest(null)} />
    </div>
  )
}
