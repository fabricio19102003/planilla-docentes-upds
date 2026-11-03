import { Layers } from 'lucide-react'
import { useState } from 'react'

import { useGroupOpening, useSaveGroupSize } from '@/api/hooks/useGroupOpening'
import { useReenrollmentWindows } from '@/api/hooks/useReenrollment'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { TableCard } from '@/components/shared/TableCard'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateInBolivia, getTodayInBolivia } from '@/lib/boliviaDates'
import { activeWindowId, capacityLabel, differenceBadge, groupSizeProblem, shiftLabel } from '@/lib/groupOpeningState'
import { windowState } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

const selectClass = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

function GroupSizeForm({ current }: { current: number }) {
  const [value, setValue] = useState(String(current))
  const save = useSaveGroupSize()
  const problem = groupSizeProblem(value)
  return (
    <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); if (!problem) save.mutate(value) }}>
      <div>
        <Label htmlFor="group-size">Estudiantes por grupo</Label>
        <Input id="group-size" inputMode="numeric" className="w-32" value={value} aria-invalid={problem !== null}
          onChange={(event) => { save.reset(); setValue(event.target.value) }} />
      </div>
      <Button type="submit" disabled={save.isPending || problem !== null || value.trim() === String(current)}>Guardar</Button>
      {problem && value.trim() !== '' && <p className="basis-full text-sm text-destructive" role="alert">{problem}</p>}
      {save.isError && <Alert variant="error" role="alert" className="basis-full"><AlertTitle>{apiErrorMessage(save.error, 'No se pudo guardar el tamaño de grupo.')}</AlertTitle></Alert>}
      {save.isSuccess && <p className="basis-full text-sm text-muted-foreground" role="status">Tamaño de grupo guardado.</p>}
    </form>
  )
}

export function GroupOpeningPage() {
  const windows = useReenrollmentWindows()
  const [selected, setSelected] = useState<number | undefined>()
  const list = windows.data ?? []
  const windowId = activeWindowId(list, selected)
  const opening = useGroupOpening(windows.isSuccess ? windowId : undefined)
  const today = getTodayInBolivia()
  const data = opening.data
  const state = data?.window ? windowState(data.window, today) : null

  return (
    <div className="space-y-5">
      <PageHeader title="Apertura de grupos" description="Cuántos grupos conviene abrir por semestre y turno, según las solicitudes de rematrícula pendientes y realizadas, comparado con los grupos ya creados." />
      {windows.isError && <Alert variant="error" role="alert"><AlertTitle>No se pudieron cargar las ventanas de rematrícula.</AlertTitle></Alert>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Parámetros</CardTitle>
          <CardDescription>La sugerencia es el total de solicitudes dividido por el tamaño de grupo, redondeado hacia arriba. Los grupos se crean en Gestión académica.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="opening-window">Ventana de rematrícula</Label>
            <select id="opening-window" className={selectClass} value={windowId ?? ''} disabled={list.length === 0}
              onChange={(event) => setSelected(Number(event.target.value))}>
              {list.length === 0 && <option value="">Sin ventanas</option>}
              {list.map((w) => <option key={w.id} value={w.id}>{w.term_code}</option>)}
            </select>
            {data?.window && state && (
              <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant={state.variant} size="sm">{state.label}</Badge>
                {formatDateInBolivia(data.window.starts_on)} al {formatDateInBolivia(data.window.ends_on)}
              </p>
            )}
          </div>
          {data && <GroupSizeForm key={data.group_size} current={data.group_size} />}
        </CardContent>
      </Card>

      {opening.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(opening.error, 'No se pudieron cargar las sugerencias.')}</AlertTitle></Alert>}
      {windows.isSuccess && list.length === 0 && (
        <EmptyState illustration="empty-calendar" icon={Layers} title="Todavía no hay una rematrícula abierta" description="Abrí una ventana en Rematrícula; con las solicitudes de los estudiantes acá vas a ver cuántos grupos abrir." />
      )}
      {data?.window && data.rows.length === 0 && (
        <EmptyState illustration="empty-inbox" icon={Layers} title="Sin solicitudes ni grupos" description={`Todavía no hay solicitudes pendientes o realizadas ni grupos activos de ${data.window.term_code}.`} />
      )}
      {data?.window && data.rows.length > 0 && (
        <TableCard
          tableClassName="min-w-[900px]"
          footer={<p className="text-sm text-muted-foreground">Los recursantes eligen grupo por materia y solo se muestran para informar: no suman a los grupos sugeridos.</p>}
        >
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-4">Semestre</TableHead>
              <TableHead className="px-4">Turno</TableHead>
              <TableHead className="px-4 text-right">Solicitudes</TableHead>
              <TableHead className="px-4 text-right">Recursantes</TableHead>
              <TableHead className="px-4 text-right">Grupos sugeridos</TableHead>
              <TableHead className="px-4 text-right">Grupos creados</TableHead>
              <TableHead className="px-4 text-right">Capacidad</TableHead>
              <TableHead className="px-4">Diferencia</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((row) => {
              const badge = differenceBadge(row)
              return (
                <TableRow key={`${row.semester}-${row.shift}`}>
                  <TableCell className="px-4 py-3 font-medium">Semestre {row.semester}</TableCell>
                  <TableCell className="px-4 py-3">{shiftLabel(row.shift)}</TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{row.requests}</TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{row.retakers}</TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{row.suggested_groups}</TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{row.existing_groups}</TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">{capacityLabel(row)}</TableCell>
                  <TableCell className="px-4 py-3"><Badge variant={badge.variant}>{badge.label}</Badge></TableCell>
                </TableRow>
              )
            })}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={2} className="px-4 py-3 font-medium">Total</TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">{data.totals.requests}</TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">{data.totals.retakers}</TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">{data.totals.suggested_groups}</TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">{data.totals.existing_groups}</TableCell>
              <TableCell className="px-4 py-3 text-right tabular-nums">{data.totals.existing_capacity}</TableCell>
              <TableCell className="px-4 py-3 text-sm text-muted-foreground">
                {data.totals.missing_groups} por abrir · {data.totals.leftover_groups} de más
              </TableCell>
            </TableRow>
          </TableFooter>
        </TableCard>
      )}
    </div>
  )
}
